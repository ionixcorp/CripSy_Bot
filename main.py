# main.py

import os
import sys
import time
import signal
import logging
import asyncio
from datetime import datetime
from dotenv import load_dotenv

from core.connection import PocketOptionAPI
from core.settings import SETTINGS
from modules.collector import TickCollector
from modules.constructor import CandleConstructor
from modules.executor import OperationExecutor
from strategy.strategy_base import POCReboundStrategy, SignalType

def setup_logging():
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_level = getattr(logging, SETTINGS.get('logging', {}).get('level', 'INFO'))
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[
            logging.FileHandler(f"{log_dir}/bot_{datetime.now().strftime('%Y%m%d')}.log"),
            logging.StreamHandler(sys.stdout)
        ]
    )
    module_loggers = ['connection', 'collector', 'constructor', 'executor', 'strategy']
    for module in module_loggers:
        logger = logging.getLogger(module)
        logger.setLevel(log_level)
    return logging.getLogger('main')

class PocketOptionBot:
    def __init__(self):
        load_dotenv()
        self.logger = setup_logging()
        self.logger.info("Iniciando PocketOptionBot...")
        self.ssid = os.getenv('POCKET_OPTION_SSID')
        if not self.ssid:
            self.logger.error("SSID no encontrado en variables de entorno. Por favor configure el archivo .env")
            sys.exit(1)
        self.running = False
        self.api = None
        self.collector = None
        self.constructor = None
        self.executor = None
        self.strategy = None
        self.last_operation_candle = None
        self.processing_signal = False  # Nueva bandera para evitar reentradas
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)
    
    async def initialize_components(self):
        # ... (sin cambios aquí) ...
        try:
            self.logger.info("Inicializando API de Pocket Option...")
            self.api = PocketOptionAPI(self.ssid)
            await asyncio.sleep(5)
            if not await self.api.verify_connection():
                self.logger.error("No se pudo verificar la conexión con Pocket Option. SSID inválido o expirado.")
                return False
            self.logger.info("Inicializando componentes del bot...")
            self.constructor = CandleConstructor(pair=SETTINGS['trading']['asset'])
            self.collector = TickCollector(pair=SETTINGS['trading']['asset'], candle_constructor=self.constructor)
            self.executor = OperationExecutor(self.api)
            self.strategy = POCReboundStrategy(candle_constructor=self.constructor, tick_collector=self.collector)
            self.logger.info(f"Suscribiendo a {SETTINGS['trading']['asset']}...")
            asset_subscription = await self.api.subscribe_to_ticks(SETTINGS['trading']['asset'])
            if not asset_subscription:
                self.logger.error(f"No se pudo suscribir a {SETTINGS['trading']['asset']}")
                return False
            await self.api.set_tick_callback(self.collector.process_tick)
            await self.api.set_order_update_callback(self.executor.handle_operation_result)
            if SETTINGS.get('load_historical_data', False):
                self.logger.info("Cargando datos históricos...")
                await self.constructor.load_historical_candles()
            self.logger.info("Todos los componentes inicializados correctamente")
            return True
        except Exception as e:
            self.logger.error(f"Error al inicializar componentes: {str(e)}")
            return False
    
    async def check_trading_signals(self):
            try:
                if self.processing_signal:
                    self.logger.debug("Procesando señal anterior, omitiendo...")
                    return

                latest_candle = self.constructor.get_latest_candle()
                if not latest_candle:
                    self.logger.debug("No hay velas disponibles para verificar señales")
                    return

                candle_key = latest_candle["timestamp"].strftime("%Y-%m-%d %H:%M")
                if self.last_operation_candle == candle_key:
                    self.logger.debug(f"Ya se realizó una operación en el ciclo {candle_key}, omitiendo...")
                    return

                signal = await self.strategy.analyze_market()
                if signal != SignalType.NONE:
                    self.processing_signal = True
                    self.last_operation_candle = candle_key  # Bloqueamos el ciclo inmediatamente
                    self.logger.info(f"Señal detectada: {signal.value}, ejecutando operación...")
                    operation_id = await self.executor.execute_operation(
                        operation_type=signal.value,
                        reason="POC Rebound Strategy"
                    )
                    if operation_id:
                        self.strategy.record_trade_execution(
                            signal=signal.value,
                            entry_price=self.collector.get_current_price()["mid"],
                            expiration=SETTINGS["trading"]["expiration_time"],
                            amount=SETTINGS["trading"]["amount"],
                            trade_id=operation_id
                        )
                    else:
                        self.logger.warning("Fallo al ejecutar la operación, liberando ciclo")
                        self.last_operation_candle = None  # Liberamos si falla
                    self.processing_signal = False
                else:
                    self.logger.debug("No hay señal de trading válida en este momento")
            except Exception as e:
                self.processing_signal = False
                self.logger.error(f"Error al verificar o ejecutar señales de trading: {str(e)}")

    async def wait_for_next_candle_cycle(self):
        # ... (sin cambios aquí) ...
        current_time = datetime.now()
        minutes_to_next_cycle = 5 - (current_time.minute % 5)
        seconds_to_next_cycle = (minutes_to_next_cycle * 60) - current_time.second - (current_time.microsecond / 1_000_000)
        if seconds_to_next_cycle <= 0:
            seconds_to_next_cycle += 300
        self.logger.info(f"Esperando {seconds_to_next_cycle:.2f} segundos para el próximo ciclo de 5 minutos...")
        await asyncio.sleep(seconds_to_next_cycle)

    async def run(self):
            try:
                if not await self.initialize_components():
                    self.logger.error("No se pudo inicializar el bot")
                    return
                self.running = True
                self.logger.info("Bot iniciado correctamente")
                
                # Iniciar tarea de monitoreo en tiempo real
                price_monitor_task = asyncio.create_task(self.monitor_and_execute())
                
                # Bucle principal para mantener el bot vivo y manejar reconexiones
                while self.running:
                    try:
                        if not await self.api.ping():
                            self.logger.warning("Problemas de conexión detectados, intentando reconectar...")
                            await self.api.reconnect()
                            await asyncio.sleep(5)
                            continue
                        await self.executor.check_operation_status()
                        # Log para verificar que el bucle principal sigue vivo
                        if datetime.now().second % 30 == 0:  # Log cada 30 segundos
                            self.logger.debug("Bucle principal activo")
                        await asyncio.sleep(0.1)
                    except Exception as e:
                        self.logger.error(f"Error en el bucle principal: {str(e)}")
                        await asyncio.sleep(5)
                
                # Esperar a que la tarea de monitoreo termine
                await price_monitor_task
                self.logger.info("Bucle principal finalizado")
            except Exception as e:
                self.logger.error(f"Error crítico en run(): {str(e)}")
            finally:
                await self.shutdown()

    async def monitor_and_execute(self):
        """Monitorea el precio y ejecuta operaciones cuando se detecta una señal"""
        # Esperar el inicio del próximo ciclo de 5 minutos
        await self.wait_for_next_candle_cycle()
        self.logger.info("Ciclo inicial alcanzado, esperando primera vela...")
        
        # Esperar hasta que tengamos al menos una vela
        while self.running and not self.constructor.candles:
            self.logger.debug("Esperando datos iniciales de velas...")
            await asyncio.sleep(1)
        
        self.logger.info("Primera vela completa recibida, comenzando monitoreo en tiempo real...")
        
        while self.running:
            try:
                signal = await self.strategy.monitor_price()
                if signal != SignalType.NONE:
                    self.logger.info(f"Señal detectada en tiempo real: {signal.value}")
                    operation_id = await self.executor.execute_operation(
                        operation_type=signal.value,
                        reason="POC Rebound Strategy - Real Time"
                    )
                    if operation_id:
                        current_price = self.collector.get_current_price()["mid"]
                        self.strategy.record_trade_execution(
                            signal=signal.value,
                            entry_price=current_price,
                            expiration=SETTINGS["trading"]["expiration_time"],
                            amount=SETTINGS["trading"]["amount"],
                            trade_id=operation_id
                        )
                        self.logger.info(f"Operación ejecutada con ID: {operation_id}")
                    else:
                        self.logger.warning("Fallo al ejecutar la operación en tiempo real")
                # Log para verificar que el monitoreo sigue activo
                if datetime.now().second % 60 == 0:  # Log cada minuto
                    self.logger.debug("Monitoreo en tiempo real activo")
                await asyncio.sleep(0.05)
            except Exception as e:
                self.logger.error(f"Error en monitor_and_execute: {str(e)}")
                await asyncio.sleep(1)

    async def wait_for_next_candle_cycle(self):
        current_time = datetime.now()
        minutes_to_next_cycle = 5 - (current_time.minute % 5)
        seconds_to_next_cycle = (minutes_to_next_cycle * 60) - current_time.second - (current_time.microsecond / 1_000_000)
        if seconds_to_next_cycle <= 0:
            seconds_to_next_cycle += 300
        self.logger.info(f"Esperando {seconds_to_next_cycle:.2f} segundos para el próximo ciclo de 5 minutos...")
        await asyncio.sleep(seconds_to_next_cycle)
        self.logger.info("Espera completada, continuando con el ciclo")
    
    def handle_shutdown(self, signum, frame):
        self.logger.info(f"Recibida señal de cierre ({signum})")
        self.running = False
    
    async def shutdown(self):
        self.logger.info("Iniciando cierre ordenado...")
        try:
            if self.executor:
                await self.executor.cancel_all_operations()
            if self.api:
                await self.api.unsubscribe_all()
            if self.collector:
                await self.collector.save_ticks_to_file()
            if self.constructor:
                self.constructor.save_candles_to_file()
            self.logger.info("Cierre completado")
        except Exception as e:
            self.logger.error(f"Error durante el cierre: {str(e)}")

if __name__ == "__main__":
    print("Iniciando el programa...")
    bot = PocketOptionBot()
    asyncio.run(bot.run())