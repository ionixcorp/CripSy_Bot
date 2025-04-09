# Ruta del módulo: strategy\strategy_base.py

import os
import logging
import asyncio
from datetime import datetime, timedelta
import pytz
import pandas as pd
import numpy as np
from enum import Enum

# Importar configuraciones
from core.settings import (
    POC_STRATEGY_CONFIG,
    TRADING_CONFIG,
    TIMEZONE,
    LOGGING_CONFIG
)

# Configurar logging
logging.basicConfig(
    level=getattr(logging, LOGGING_CONFIG["level"]), 
    format=LOGGING_CONFIG["format"]
)
logger = logging.getLogger("POCStrategy")

class SignalType(Enum):
    """Enumeración para tipos de señales"""
    CALL = "CALL"  # Señal de compra
    PUT = "PUT"    # Señal de venta
    NONE = "NONE"  # Sin señal

class POCReboundStrategy:
    def __init__(self, candle_constructor, tick_collector):
        self.logger = logging.getLogger("POCStrategy")
        self.candle_constructor = candle_constructor
        self.tick_collector = tick_collector
        self.timezone = pytz.timezone(TIMEZONE)
        self.price_tolerance = POC_STRATEGY_CONFIG["price_tolerance"]
        self.min_distance_percentage = POC_STRATEGY_CONFIG["min_distance_percentage"] / 100
        self.max_distance_percentage = POC_STRATEGY_CONFIG["max_distance_percentage"] / 100
        self.wait_for_confirmation = POC_STRATEGY_CONFIG["wait_for_confirmation"]
        self.confirmation_candles = POC_STRATEGY_CONFIG["confirmation_candles"]
        self.current_signal = SignalType.NONE
        self.last_signal_time = None
        self.last_trade_time = None
        self.last_analyzed_candle = None
        self.poc_touched = False
        self.waiting_for_execution = False
        self.signal_price = None
        self.signals_history = []
        self.trades_history = []
        self.win_count = 0
        self.loss_count = 0
        self.lock = asyncio.Lock()
        self.logger.info("Estrategia de rebote al POC inicializada")

    async def monitor_price(self):
        """Monitorea el precio en tiempo real para detectar el toque del POC"""
        while True:
            try:
                current_price_data = self.tick_collector.get_current_price()
                if not current_price_data:
                    await asyncio.sleep(0.1)
                    continue

                current_price = current_price_data["mid"]
                last_poc = self.candle_constructor.get_latest_poc()
                last_candle = self.candle_constructor.get_latest_candle()

                if not last_poc or not last_candle:
                    await asyncio.sleep(0.1)
                    continue

                candle_key = last_candle["timestamp"].strftime("%Y-%m-%d %H:%M")
                if self.last_trade_time and (datetime.now(self.timezone) - self.last_trade_time).total_seconds() < 60:
                    await asyncio.sleep(0.1)
                    continue

                poc_touched = self._is_price_touching_poc(current_price, last_poc)
                if poc_touched and not self.waiting_for_execution:
                    signal = self._generate_signal(current_price, last_poc, last_candle["color"])
                    if signal != SignalType.NONE and self._check_filters(current_price, last_poc):
                        self._add_signal(signal, current_price, last_poc)
                        return signal  # Retornamos inmediatamente para ejecutar

                await asyncio.sleep(0.05)  # Pequeña pausa para no saturar CPU
            except Exception as e:
                self.logger.error(f"Error en monitoreo de precio: {str(e)}")
                await asyncio.sleep(1)

    def _generate_signal(self, current_price, last_poc, last_candle_color):
        """Genera una señal basada en el toque del POC"""
        if last_candle_color == "green" and current_price <= last_poc:
            self.logger.info(f"Señal CALL generada: Precio={current_price} rebota al POC={last_poc} tras vela verde")
            return SignalType.CALL
        elif last_candle_color == "red" and current_price >= last_poc:
            self.logger.info(f"Señal PUT generada: Precio={current_price} rebota al POC={last_poc} tras vela roja")
            return SignalType.PUT
        return SignalType.NONE
    
    async def analyze_market(self):
        async with self.lock:
            last_candle = self.candle_constructor.get_latest_candle()
            if not last_candle:
                self.logger.debug("No hay velas disponibles aún para análisis")
                return SignalType.NONE

            candle_key = last_candle["timestamp"].strftime("%Y-%m-%d %H:%M")
            if self.last_analyzed_candle == candle_key and self.waiting_for_execution:
                self.logger.debug(f"Esperando ejecución de señal previa para la vela {candle_key}, omitiendo...")
                return SignalType.NONE

            if self.last_analyzed_candle == candle_key:
                self.logger.debug(f"Ya se analizó la vela {candle_key} sin señal pendiente, omitiendo...")
                return SignalType.NONE

            current_price_data = self.tick_collector.get_current_price()
            if not current_price_data:
                self.logger.warning("No hay precio actual disponible")
                return SignalType.NONE

            current_price = current_price_data["mid"]
            last_poc = self.candle_constructor.get_latest_poc()
            last_candle_color = self.candle_constructor.get_latest_candle_color()

            self.logger.debug(f"Analizando: Precio actual={current_price}, POC={last_poc}, Color vela={last_candle_color}")

            if not last_poc or not last_candle_color:
                self.logger.warning("Falta POC o color de vela")
                return SignalType.NONE

            poc_touched = self._is_price_touching_poc(current_price, last_poc)
            self.logger.debug(f"POC tocado: {poc_touched}, Diferencia: {abs(current_price - last_poc)}")

            if not poc_touched:
                return SignalType.NONE

            signal = SignalType.NONE
            if last_candle_color == "green" and current_price <= last_poc:
                signal = SignalType.CALL
                self.logger.info(f"Señal CALL generada: Precio={current_price} rebota al POC={last_poc} tras vela verde")
            elif last_candle_color == "red" and current_price >= last_poc:
                signal = SignalType.PUT
                self.logger.info(f"Señal PUT generada: Precio={current_price} rebota al POC={last_poc} tras vela roja")

            if signal != SignalType.NONE and self._check_filters(current_price, last_poc):
                self._add_signal(signal, current_price, last_poc)
                self.last_analyzed_candle = candle_key  # Actualizamos inmediatamente
                return signal

            self.last_analyzed_candle = candle_key  # Actualizamos incluso si no hay señal
            return SignalType.NONE
    
    def _is_price_touching_poc(self, price, poc):
        """Verifica si el precio está dentro de la tolerancia del POC."""
        return abs(price - poc) <= self.price_tolerance

    def _check_filters(self, current_price, last_poc):
        """Aplica filtros de distancia mínima y máxima."""
        distance = abs(current_price - last_poc) / last_poc
        return self.min_distance_percentage <= distance <= self.max_distance_percentage

    def _add_signal(self, signal, current_price, last_poc):
        """Registra una nueva señal."""
        self.current_signal = signal
        self.signal_price = current_price
        self.last_signal_time = datetime.now(self.timezone)
        self.waiting_for_execution = True
        self._record_signal(signal, current_price, last_poc, self.candle_constructor.get_latest_candle_color())
        self.logger.debug(f"Señal añadida: {signal.value}, Precio={current_price}, POC={last_poc}")

    def _should_cancel_signal(self, current_price):
        """
        Verifica si una señal pendiente debe ser cancelada.
        
        Args:
            current_price (float): Precio actual
            
        Returns:
            bool: True si la señal debe ser cancelada, False en caso contrario
        """
        if not self.signal_price:
            return False
            
        price_movement = abs(current_price - self.signal_price) / self.signal_price
        time_passed = datetime.now(self.timezone) - self.last_signal_time if self.last_signal_time else timedelta(0)
        
        return price_movement > 0.001 or time_passed.total_seconds() > 60
    
    def get_trading_signal(self):
        """
        Retorna la señal de trading actual.
        
        Returns:
            dict: Información de la señal de trading
        """
        if self.current_signal == SignalType.NONE or not self.waiting_for_execution:
            return None
            
        signal_info = {
            "type": self.current_signal.value,
            "price": self.signal_price,
            "poc": self.candle_constructor.get_latest_poc(),
            "timestamp": self.last_signal_time,
            "expiration": TRADING_CONFIG["expiration_time"],
            "amount": TRADING_CONFIG["amount"]
        }
        
        return signal_info
    
    def ready_for_execution(self):
        """Verifica si hay una señal lista para ser ejecutada."""
        return self.waiting_for_execution and self.current_signal != SignalType.NONE
    
    def _record_signal(self, signal, price, poc, candle_color):
        """Registra una señal en el historial."""
        signal_data = {
            "timestamp": datetime.now(self.timezone),
            "type": signal.value,
            "price": price,
            "poc": poc,
            "candle_color": candle_color,
            "distance": abs(price - poc),
            "distance_pips": abs(price - poc) * 10000,
            "distance_percentage": abs(price - poc) / poc * 100
        }
        
        self.signals_history.append(signal_data)
        if len(self.signals_history) > 100:
            self.signals_history = self.signals_history[-100:]
    
    def record_trade_execution(self, signal, entry_price, expiration, amount, trade_id=None):
        """Registra la ejecución de una operación."""
        trade_data = {
            "timestamp": datetime.now(self.timezone),
            "type": signal,
            "entry_price": entry_price,
            "expiration": expiration,
            "amount": amount,
            "trade_id": trade_id,
            "expected_close_time": datetime.now(self.timezone) + timedelta(seconds=expiration),
            "result": "PENDING"
        }
        
        self.trades_history.append(trade_data)
        self.last_trade_time = datetime.now(self.timezone)
        self.waiting_for_execution = False
        self.current_signal = SignalType.NONE
        
        logger.info(f"Operación ejecutada: {signal} a {entry_price}, exp: {expiration}s, monto: {amount}")
        if len(self.trades_history) > 100:
            self.trades_history = self.trades_history[-100:]
    
    def record_trade_result(self, trade_id, result, profit=None):
        """Registra el resultado de una operación."""
        for trade in self.trades_history:
            if trade.get("trade_id") == trade_id:
                trade["result"] = result
                trade["profit"] = profit
                if result == "WIN":
                    self.win_count += 1
                elif result == "LOSS":
                    self.loss_count += 1
                logger.info(f"Resultado de operación {trade_id}: {result}, profit: {profit}")
                break
    
    def get_signal_history(self):
        """Obtiene el historial de señales."""
        return self.signals_history
    
    def get_trade_history(self):
        """Obtiene el historial de operaciones."""
        return self.trades_history
    
    def get_performance_stats(self):
        """Obtiene estadísticas de rendimiento de la estrategia."""
        total_trades = self.win_count + self.loss_count
        win_rate = self.win_count / total_trades * 100 if total_trades > 0 else 0
        total_profit = sum(trade.get("profit", 0) for trade in self.trades_history 
                          if trade.get("result") != "PENDING" and trade.get("profit") is not None)
        
        return {
            "total_trades": total_trades,
            "wins": self.win_count,
            "losses": self.loss_count,
            "win_rate": win_rate,
            "total_profit": total_profit,
            "avg_profit_per_trade": total_profit / total_trades if total_trades > 0 else 0
        }
    
    def reset(self):
        """Restablece el estado de la estrategia."""
        self.current_signal = SignalType.NONE
        self.waiting_for_execution = False
        self.signal_price = None
        self.last_analyzed_candle = None
        logger.info("Estado de la estrategia restablecido")
    
    async def backtest(self, historical_candles, historical_ticks=None):
        """Ejecuta un backtest de la estrategia con datos históricos."""
        logger.info("Función de backtest en desarrollo")
        return {"status": "not_implemented", "message": "Backtest en desarrollo"}