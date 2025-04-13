################################################################################
# ESTRUCTURA DEL PROYECTO
################################################################################

# === ARCHIVOS IMPLEMENTADOS ===
# - core/__init__.py  # [INICIADOR] (vacío)
# - core/config.py
# - core/connection.py
# - core/data_collector.py
# - executors/__init__.py  # [INICIADOR] (vacío)
# - executors/trade_manager.py
# - main.py
# - pocket_options_examples/async/check_win.py
# - pocket_options_examples/async/create_raw_iterator.py
# - pocket_options_examples/async/create_raw_order.py
# - pocket_options_examples/async/get_balance.py
# - pocket_options_examples/async/get_candles.py
# - pocket_options_examples/async/get_open_and_close_trades.py
# - pocket_options_examples/async/history.py
# - pocket_options_examples/async/log_iterator.py
# - pocket_options_examples/async/logs.py
# - pocket_options_examples/async/payout.py
# - pocket_options_examples/async/raw_send.py
# - pocket_options_examples/async/subscribe_symbol.py
# - pocket_options_examples/async/subscribe_symbol_chuncked.py
# - pocket_options_examples/async/subscribe_symbol_timed.py
# - pocket_options_examples/async/trade.py
# - pocket_options_examples/async/validator.py
# - pocket_options_examples/asyncronous.py
# - pocket_options_examples/get_assets_pocketoption.py
# - pocket_options_examples/test_connection.py
# - pocket_options_examples/tests/test.py
# - pocket_options_examples/tests/test_sync.py
# - strategy/__init__.py  # [INICIADOR] (vacío)
# - strategy/strategies.py
# - utils/logger.py

# === ARCHIVOS PENDIENTES DE IMPLEMENTACIÓN ===




# ============================== main.py ==============================
# 📁 Ruta: main.py
################################################################################

import asyncio
import time
import traceback
from core.connection import ConnectionManager
from core.config import Config
from core.data_collector import DataCollector
from executors.trade_manager import TradeManager
from strategy.strategies import MovingAverageCrossover, RSI, MACD, BollingerBands
from utils.logger import Logger
import signal as signal_module
import sys

# Variable para controlar la ejecución
running = True
WARMUP_PERIOD = 300  # 5 minutos de warmup antes de realizar operaciones

def signal_handler(sig, frame):
    """Manejador de señales para terminar limpiamente."""
    global running
    logger = Logger()  # Usar nivel por defecto
    logger.debug("Señal de terminación recibida. Cerrando bot...")
    running = False

async def main():
    # Registrar manejador de señales para CTRL+C
    signal_module.signal(signal_module.SIGINT, signal_handler)
    signal_module.signal(signal_module.SIGTERM, signal_handler)
    
    # Variables para manejo de recursos
    connection_manager = None
    
    try:
        # Configuración
        config = Config()
        logger = Logger(level=config.log_level)
        logger.debug("Iniciando bot de trading")
        logger.debug("Cargando configuración...")
        logger.debug("Configuración cargada correctamente")
        
        asset = "EURUSD_otc"
        timeframe = 60  # Intervalo de velas en segundos
        period = 3600  # Período histórico en segundos (1 hora)
        amount = 1  # Monto de la operación
        
        # Inicializar y establecer conexión
        logger.debug("Inicializando conexión...")
        try:
            connection_manager = ConnectionManager(config)
            await connection_manager.initialize()
            logger.debug("Conexión inicializada correctamente")
        except Exception as e:
            logger.error(f"Error al inicializar la conexión: {str(e)}")
            logger.error(traceback.format_exc())
            return
        
        # Verificar activo
        try:
            if not await connection_manager.verify_asset(asset):
                logger.error(f"El activo {asset} no está disponible")
                return
            logger.debug(f"Activo {asset} verificado correctamente")
        except Exception as e:
            logger.error(f"Error al verificar el activo: {str(e)}")
            logger.error(traceback.format_exc())
            return
        
        # Inicializar componentes con la misma conexión y logger
        try:
            logger.debug("Inicializando componentes...")
            data_collector = DataCollector(connection_manager.client, logger)
            trade_manager = TradeManager(connection_manager.client, logger)
            logger.debug("Componentes inicializados correctamente")
        except Exception as e:
            logger.error(f"Error al inicializar componentes: {str(e)}")
            logger.error(traceback.format_exc())
            return
        
        # Inicializar múltiples estrategias
        try:
            logger.debug("Inicializando estrategias...")
            strategies = {
                "MA_Cross": MovingAverageCrossover(short_period=8, long_period=21),
                "RSI": RSI(period=14, overbought=70, oversold=30),
                "MACD": MACD(fast_period=12, slow_period=26, signal_period=9),
                "Bollinger": BollingerBands(period=20, std_dev=2.0)
            }
            logger.debug("Estrategias inicializadas correctamente")
        except Exception as e:
            logger.error(f"Error al inicializar estrategias: {str(e)}")
            logger.error(traceback.format_exc())
            return
        
        # Obtener datos históricos
        logger.debug("Obteniendo datos históricos...")
        try:
            candles = await data_collector.get_historical_data(asset, timeframe, period)
            
            if not candles:
                logger.error("No se pudieron obtener datos históricos")
                return
                
            logger.debug(f"Datos históricos obtenidos: {len(candles)} velas")
        except Exception as e:
            logger.error(f"Error al obtener datos históricos: {str(e)}")
            logger.error(traceback.format_exc())
            return
            
        # Inicializar todas las estrategias con datos históricos
        try:
            logger.debug("Inicializando estrategias con datos históricos...")
            for name, strategy in strategies.items():
                strategy.initialize(candles)
            logger.debug("Estrategias inicializadas con datos históricos correctamente")
        except Exception as e:
            logger.error(f"Error al inicializar estrategias con datos históricos: {str(e)}")
            logger.error(traceback.format_exc())
            return
        
        # Iniciar período de calentamiento
        start_time = time.time()
        logger.debug(f"Iniciando período de calentamiento de {WARMUP_PERIOD} segundos...")
        
        # Suscribir a datos en tiempo real
        logger.debug("Iniciando suscripción a datos en tiempo real...")
        
        try:
            # Esperar 5 segundos para estabilización
            logger.debug("Esperando 5 segundos para estabilización...")
            await asyncio.sleep(5)
            
            # Usar un timeout para la suscripción en tiempo real
            logger.debug("Obteniendo suscripción en tiempo real...")
            realtime_subscription = data_collector.subscribe_realtime(asset, timeframe)
            logger.debug("Suscripción en tiempo real obtenida correctamente")
            
            logger.debug("Iniciando bucle principal...")
            async with asyncio.timeout(30):
                async for candle in realtime_subscription:
                    logger.debug("Entrando al bucle de velas en tiempo real")
                    if not running:
                        logger.debug("Deteniendo bot por señal externa...")
                        break
                    logger.debug(f"Nueva vela recibida: {candle}")                                      
                
                # Calcular tiempo transcurrido
                elapsed_time = time.time() - start_time
                in_warmup = elapsed_time < WARMUP_PERIOD
                
                if in_warmup:
                    remaining = WARMUP_PERIOD - elapsed_time
                    if remaining % 60 < 1:  # Mostrar cada minuto aproximadamente
                        logger.debug(f"Período de calentamiento: {remaining:.0f} segundos restantes")
                    if signals:
                        logger.debug(f"Señales detectadas durante warmup: {signals} - No se ejecutará ninguna operación")
                else:
                    # Señales de las estrategias
                    signals = {}
                    for name, strategy in strategies.items():
                        signal = strategy.update(candle)
                        if signal:
                            signals[name] = signal
                            
                    # Determinar la señal final basada en las estrategias
                    if len(signals) >= 2:  # Requiere al menos 2 estrategias con la misma señal
                        call_count = sum(1 for s in signals.values() if s == 'call')
                        put_count = sum(1 for s in signals.values() if s == 'put')
                        
                        if call_count >= 2 and call_count > put_count:
                            final_signal = 'call'
                            should_trade = True
                        elif put_count >= 2 and put_count > call_count:
                            final_signal = 'put'
                            should_trade = True
                        else:
                            logger.debug(f"Señales contradictorias: {signals} - No se ejecutará ninguna operación")
                            should_trade = False
                            
                        if should_trade:
                            logger.debug(f"Señal de trading confirmada por múltiples estrategias: {final_signal}")
                            
                            # Ejecutar operación
                            try:
                                trade_id = await trade_manager.execute_trade(
                                    asset=asset,
                                    amount=amount,
                                    direction=final_signal,
                                    duration=timeframe
                                )
                                
                                if trade_id:
                                    logger.debug(f"Operación ejecutada exitosamente. ID: {trade_id}")
                                    
                                    # Verificar resultado
                                    result = await trade_manager.check_trade_result(trade_id)
                                    if result:
                                        logger.debug(f"Resultado de la operación: {result}")
                                        
                                        # Mostrar estadísticas
                                        stats = trade_manager.get_performance_stats()
                                        logger.debug(f"Estadísticas: {stats['win_rate']:.1f}% win rate, {stats['total_trades']} trades, profit: {stats['profit']}")
                                    else:
                                        logger.warning("No se pudo verificar el resultado de la operación")
                                        
                            except Exception as e:
                                logger.error(f"Error al ejecutar operación: {str(e)}")
                                logger.error(traceback.format_exc())
                    else:
                        logger.debug(f"Señal detectada por {list(signals.keys())[0]}, pero se requiere confirmación de otras estrategias")
                
                # Pequeña pausa para evitar saturar la CPU
                await asyncio.sleep(0.1)
                
        except asyncio.CancelledError:
            logger.debug("Suscripción en tiempo real cancelada")
        except Exception as e:
            logger.error(f"Error en la suscripción en tiempo real: {str(e)}")
            logger.error(traceback.format_exc())
                    
    except KeyboardInterrupt:
        logger.debug("Bot detenido manualmente")
    except Exception as e:
        logger.error(f"Error en el programa principal: {str(e)}")
        logger.error(traceback.format_exc())
    finally:
        # Cerrar conexión al finalizar
        if connection_manager:
            try:
                await connection_manager.close()
                logger.debug("Conexión cerrada correctamente")
            except Exception as e:
                logger.error(f"Error al cerrar la conexión: {str(e)}")
                logger.error(traceback.format_exc())
        logger.debug("Bot de trading finalizado")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot terminado por el usuario")
    except Exception as e:
        print(f"Error fatal: {str(e)}")
        print(traceback.format_exc())
        sys.exit(1)

# ========================= FIN DE main.py =========================


# ============================== config.py ==============================
# 📁 Ruta: core/config.py
################################################################################

from typing import Optional
import logging
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Config(BaseModel):
    # Connection settings
    ssid: Optional[str] = Field(default=None, description="Session ID for PocketOption")
    url: Optional[str] = Field(default=None, description="Custom PocketOption URL")
    
    # Trading settings
    asset: str = Field(default="EURUSD_otc", description="Asset to trade")
    amount: float = Field(default=1.0, description="Trade amount")
    expiry: int = Field(default=60, description="Trade expiry time in seconds")
    
    # Data settings
    candle_period: int = Field(default=60, description="Candle period in seconds")
    historical_candles: int = Field(default=1000, description="Number of historical candles to fetch")
    
    # Strategy settings
    override_payout: bool = Field(default=False, description="Whether to override the API payout")
    payout: float = Field(default=73.0, description="Override payout percentage")
    
    # Risk management
    max_trades: int = Field(default=10, description="Maximum number of concurrent trades")
    stop_loss: float = Field(default=0.0, description="Stop loss percentage (0 to disable)")
    take_profit: float = Field(default=0.0, description="Take profit percentage (0 to disable)")
    
    # Logging settings
    log_level: str = Field(default="INFO", description="Console log level (DEBUG, INFO, WARNING, ERROR)")

    def __init__(self, **data):
        super().__init__(**data)
        load_dotenv()
        
        # Load SSID from environment if not provided
        if not self.ssid:
            self.ssid = os.getenv("POCKETOPTION_SSID")
            if not self.ssid:
                logger.error("POCKETOPTION_SSID not found in environment variables")
                raise ValueError("POCKETOPTION_SSID not found in environment variables")
                
        logger.info(f"Configuration loaded - Asset: {self.asset}, Amount: {self.amount}, Expiry: {self.expiry}s")

# ========================= FIN DE config.py =========================


# ============================== connection.py ==============================
# 📁 Ruta: core/connection.py
################################################################################

from typing import Optional
import logging
import asyncio
from BinaryOptionsToolsV2.pocketoption import PocketOptionAsync
from core.config import Config
from dotenv import load_dotenv
import os
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self, config: Config):
        self.config = config
        self.client: Optional[PocketOptionAsync] = None
        self.connected = False
        self.max_retries = 3
        self.retry_delay = 5
        self.stabilization_delay = 5  # Tiempo de espera para estabilización
        
        # Cargar SSID desde .env
        load_dotenv()
        self.ssid = os.getenv("POCKETOPTION_SSID")
        if not self.ssid:
            logger.error("POCKETOPTION_SSID not found in .env file")
            raise ValueError("POCKETOPTION_SSID not found in .env file")

    async def initialize(self) -> None:
        """Initialize the connection to PocketOption."""
        logger.info("Initializing connection to PocketOption...")
        
        for attempt in range(self.max_retries):
            try:
                # Crear cliente
                self.client = PocketOptionAsync(ssid=self.ssid)
                logger.info(f"Connection attempt {attempt + 1}/{self.max_retries}")
                
                # Esperar estabilización
                logger.info(f"Waiting {self.stabilization_delay} seconds for connection stabilization...")
                await asyncio.sleep(self.stabilization_delay)
                
                # Verificar conexión
                if await self.verify_connection():
                    self.connected = True
                    logger.info("Connection successfully established and verified")
                    return
                    
            except Exception as e:
                logger.error(f"Connection attempt {attempt + 1} failed: {str(e)}")
                if attempt < self.max_retries - 1:
                    logger.info(f"Retrying in {self.retry_delay} seconds...")
                    await asyncio.sleep(self.retry_delay)
                else:
                    raise ConnectionError(f"Failed to establish connection after {self.max_retries} attempts")

    async def verify_connection(self) -> bool:
        """Verify the connection is working."""
        try:
            # Verificar balance
            logger.info("Verifying connection with balance check...")
            raw_balance = await self.client.balance()
            
            if raw_balance is None or raw_balance < 0:
                logger.error("Invalid balance received. Connection may not be established properly.")
                return False
                
            # Verificar tipo de cuenta
            is_demo = await self.client.is_demo()
            account_type = "Demo" if is_demo else "Real"
            
            logger.info(f"Connection verified - Balance: {raw_balance}, Account: {account_type}")
            return True
                
        except Exception as e:
            logger.error(f"Connection verification failed: {str(e)}")
            return False

    async def verify_asset(self, asset: str) -> bool:
        """Verify if the asset is available and get its payout."""
        try:
            logger.info(f"Verifying asset {asset}...")
            payout = await self.client.payout(asset)
            
            if payout is None or payout <= 0:
                logger.error(f"Invalid payout received for {asset}")
                return False
                
            # Override payout if configured
            if self.config.override_payout:
                logger.warning(f"API reported payout {payout}% for {asset}, overriding to {self.config.payout}%")
                payout = self.config.payout
                
            logger.info(f"Asset {asset} verified - Payout: {payout}%")
            return True
            
        except Exception as e:
            logger.error(f"Asset verification failed: {str(e)}")
            return False

    async def close(self) -> None:
        """Close the connection."""
        if self.connected:
            self.connected = False
            logger.info("Connection closed")

# ========================= FIN DE connection.py =========================


# ============================== data_collector.py ==============================
# 📁 Ruta: core/data_collector.py
################################################################################

import asyncio
import time
import datetime
from utils.logger import Logger

class DataCollector:
    def __init__(self, api_client, logger=None):
        self.api_client = api_client
        self.logger = logger or Logger()
        self.candles = []
        self.last_candle_time = 0
        self.duplicate_count = 0
        
    def _parse_time(self, time_str):
        """Convierte una cadena ISO a timestamp entero."""
        try:
            # Si ya es un entero, devolverlo
            if isinstance(time_str, (int, float)):
                return int(time_str)
                
            # Si es un string ISO, convertirlo
            if isinstance(time_str, str):
                if time_str.endswith('Z'):
                    # Formato ISO 8601 (2025-04-13T12:10:41.050Z)
                    dt = datetime.datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                    return int(dt.timestamp())
                    
            # Si no se puede parsear, usar el tiempo actual
            return int(time.time())
        except Exception as e:
            self.logger.error(f"Error al parsear tiempo '{time_str}': {str(e)}")
            return int(time.time())
        
    async def get_historical_data(self, asset, timeframe, period, max_candles=1000):
        """
        Obtiene datos históricos de velas para un activo.
        
        Args:
            asset (str): Par de trading (ej: "EURUSD_otc")
            timeframe (int): Intervalo de tiempo en segundos (ej: 60 para velas de 1 minuto)
            period (int): Período histórico en segundos
            max_candles (int): Número máximo de velas a obtener
            
        Returns:
            list: Lista de velas con formato [time, open, high, low, close]
        """
        try:
            self.logger.info(f"Iniciando obtención de datos históricos para {asset}")
            
            # Usar history en lugar de get_candles
            candles = await self.api_client.history(asset, period)
            
            if not candles:
                self.logger.warning("No se obtuvieron datos históricos")
                return []
                
            # Convertir a formato correcto sin volumen
            formatted_candles = []
            for candle in candles:
                try:
                    # Parsear el tiempo correctamente
                    candle_time = self._parse_time(candle.get('time', int(time.time())))
                    
                    formatted_candles.append([
                        candle_time,
                        float(candle['open']),
                        float(candle['high']),
                        float(candle['low']),
                        float(candle['close'])
                    ])
                except (KeyError, ValueError) as e:
                    self.logger.error(f"Error al formatear vela: {str(e)}")
                    continue
            
            # Ordenar cronológicamente y verificar
            formatted_candles.sort(key=lambda x: x[0])
            
            # Detectar y eliminar velas duplicadas o con datos inconsistentes
            clean_candles = []
            last_time = 0
            
            for candle in formatted_candles:
                # Verificar que el tiempo es mayor que el último
                if candle[0] <= last_time:
                    continue
                    
                # Verificar que los datos son consistentes
                if candle[2] < candle[1] or candle[2] < candle[4] or candle[3] > candle[1] or candle[3] > candle[4]:
                    continue
                    
                clean_candles.append(candle)
                last_time = candle[0]
            
            # Limitar al número máximo de velas
            if len(clean_candles) > max_candles:
                clean_candles = clean_candles[-max_candles:]
                
            # Registrar la última vela
            if clean_candles:
                self.last_candle_time = clean_candles[-1][0]
                self.logger.debug(f"Última vela histórica: {clean_candles[-1]}, timestamp: {self.last_candle_time}")
                    
                self.logger.info(f"Obtención de datos históricos completada: {len(clean_candles)} velas válidas de {len(formatted_candles)} recibidas")
            self.candles = clean_candles
            
            return clean_candles
            
        except Exception as e:
            self.logger.error(f"Error crítico al obtener datos históricos: {str(e)}")
            return []
            
    async def subscribe_realtime(self, asset, timeframe):
        try:
            self.logger.info(f"Iniciando suscripción a datos en tiempo real para {asset}")
            self.last_candle_time = 0  # Resetear para aceptar todas las velas nuevas
            await asyncio.sleep(5)
            stream = await self.api_client.subscribe_symbol(asset)
            self.logger.info("Conexión WebSocket establecida correctamente")
        # ... resto del código ...

            self.logger.debug(f"Último tiempo registrado: {self.last_candle_time}")
            async for tick in stream:
                self.logger.debug(f"Tick recibido: {tick}")
                if not tick:
                    continue
                    
                if 'open' in tick and 'high' in tick and 'low' in tick and 'close' in tick:
                    formatted_candle = [
                        self._parse_time(tick.get('time', int(time.time()))),
                        float(tick['open']),
                        float(tick['high']),
                        float(tick['low']),
                        float(tick['close'])
                    ]
                    self.candles.append(formatted_candle)
                    self.last_candle_time = formatted_candle[0]
                    self.logger.debug(f"Vela producida: {formatted_candle}")
                    yield formatted_candle
                else:
                    self.logger.debug("Vela descartada: timestamp no es mayor")
                    
        except Exception as e:
            self.logger.error(f"Error crítico en suscripción: {str(e)}")
            raise

# ========================= FIN DE data_collector.py =========================


# ============================== __init__.py ==============================
# 📁 Ruta: core/__init__.py
################################################################################

# (Archivo vacío)


# ========================= FIN DE __init__.py =========================


# ============================== trade_manager.py ==============================
# 📁 Ruta: executors/trade_manager.py
################################################################################

import asyncio
import time
from utils.logger import Logger

class TradeManager:
    def __init__(self, api_client, logger=None):
        self.api_client = api_client
        self.logger = logger or Logger()
        self.active_trades = {}
        self.last_trade_time = 0
        self.min_trade_interval = 60  # Intervalo mínimo entre operaciones (segundos)
        self.cooldown = False
        self.trade_history = []
        
    async def execute_trade(self, asset, amount, direction, duration):
        """
        Ejecuta una operación de trading con protección contra operaciones consecutivas.
        
        Args:
            asset (str): Par de trading
            amount (float): Monto de la operación
            direction (str): Dirección de la operación ('call' o 'put')
            duration (int): Duración de la operación en segundos
            
        Returns:
            str: ID de la operación o None si falla
        """
        try:
            # Protección contra operaciones inmediatas
            current_time = time.time()
            
            # No ejecutar si estamos en cooldown
            if self.cooldown:
                self.logger.warning(f"Operación ignorada: sistema en enfriamiento")
                return None
                
            # Verificar tiempo mínimo entre operaciones
            time_since_last_trade = current_time - self.last_trade_time
            if time_since_last_trade < self.min_trade_interval:
                self.logger.warning(f"Operación ignorada: demasiado pronto desde la última operación ({time_since_last_trade:.1f}s < {self.min_trade_interval}s)")
                return None
            
            # Verificar si ya tenemos demasiadas operaciones activas
            if len(self.active_trades) >= 3:
                self.logger.warning(f"Operación ignorada: demasiadas operaciones activas ({len(self.active_trades)})")
                return None
            
            # Ejecutar trade sin check_win
            if direction.lower() == 'call':
                trade_id, trade_info = await self.api_client.buy(
                    asset=asset,
                    amount=amount,
                    time=duration,
                    check_win=False
                )
            else:
                trade_id, trade_info = await self.api_client.sell(
                    asset=asset,
                    amount=amount,
                    time=duration,
                    check_win=False
                )
            
            if not trade_id or not trade_info:
                self.logger.error(f"Error al ejecutar trade en {asset}")
                return None
                
            # Registrar trade activo
            self.active_trades[trade_id] = {
                'asset': asset,
                'amount': amount,
                'direction': direction,
                'duration': duration,
                'start_time': current_time,
                'expiry_time': current_time + duration
            }
            
            # Actualizar tiempo de última operación
            self.last_trade_time = current_time
            
            # Activar cooldown por 5 segundos para evitar operaciones inmediatas
            self.cooldown = True
            asyncio.create_task(self._reset_cooldown())
                
            self.logger.info(f"Operación {direction} en {asset} ejecutada con ID: {trade_id}")
            return trade_id
            
        except Exception as e:
            self.logger.error(f"Error al ejecutar trade: {str(e)}")
            return None
            
    async def _reset_cooldown(self):
        """Restablece el cooldown después de 5 segundos"""
        await asyncio.sleep(5)
        self.cooldown = False
            
    async def check_trade_result(self, trade_id):
        """
        Verifica el resultado de una operación.
        
        Args:
            trade_id (str): ID de la operación
            
        Returns:
            dict: Resultado de la operación o None si falla
        """
        try:
            if trade_id not in self.active_trades:
                self.logger.warning(f"No se encontró el trade {trade_id} en la lista de operaciones activas")
                return None
                
            trade_info = self.active_trades[trade_id]
            current_time = time.time()
            
            # Esperar hasta que expire la operación + 2 segundos para asegurar
            remaining_time = trade_info['expiry_time'] - current_time + 2
            if remaining_time > 0:
                self.logger.info(f"Esperando {remaining_time:.1f}s para verificar resultado de operación {trade_id}")
                await asyncio.sleep(remaining_time)
                
            # Verificar resultado
            max_attempts = 3
            for attempt in range(max_attempts):
                try:
                    result = await self.api_client.check_win(trade_id)
                    if result:
                        # Almacenar en historial
                        self.trade_history.append({
                            'id': trade_id,
                            'asset': trade_info['asset'],
                            'direction': trade_info['direction'],
                            'result': result,
                            'time': time.time()
                        })
                        
                        # Limpiar de activos
                        del self.active_trades[trade_id]
                        return result
                    
                    # Si no hay resultado pero no es el último intento
                    if attempt < max_attempts - 1:
                        self.logger.warning(f"Intento {attempt+1}/{max_attempts} falló, reintentando en 2 segundos...")
                        await asyncio.sleep(2)
                except Exception as e:
                    self.logger.error(f"Error en intento {attempt+1}/{max_attempts}: {str(e)}")
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(2)
            
            # Si llegamos aquí, no se pudo verificar el resultado
            self.logger.error(f"No se pudo verificar el resultado del trade {trade_id} después de {max_attempts} intentos")
            return None
            
        except Exception as e:
            self.logger.error(f"Error al verificar resultado de trade {trade_id}: {str(e)}")
            return None
            
    def get_performance_stats(self):
        """
        Obtiene estadísticas de rendimiento del trading.
        
        Returns:
            dict: Estadísticas de rendimiento
        """
        total_trades = len(self.trade_history)
        if total_trades == 0:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'profit': 0
            }
            
        wins = sum(1 for trade in self.trade_history if trade.get('result', {}).get('result') == 'win')
        win_rate = (wins / total_trades) * 100
        profit = sum(trade.get('result', {}).get('profit', 0) for trade in self.trade_history)
        
        return {
            'total_trades': total_trades,
            'wins': wins,
            'losses': total_trades - wins,
            'win_rate': win_rate,
            'profit': profit
        } 

# ========================= FIN DE trade_manager.py =========================


# ============================== __init__.py ==============================
# 📁 Ruta: executors/__init__.py
################################################################################

# (Archivo vacío)


# ========================= FIN DE __init__.py =========================


# ============================== asyncronous.py ==============================
# 📁 Ruta: pocket_options_examples/asyncronous.py
################################################################################

from BinaryOptionsToolsV2.validator import Validator
from BinaryOptionsToolsV2 import RawPocketOption, Logger
from datetime import timedelta


import asyncio
import json
import time 
import sys 


class AsyncSubscription:
    def __init__(self, subscription):
        """Asyncronous Iterator over json objects"""
        self.subscription = subscription
        
    def __aiter__(self):
        return self
        
    async def __anext__(self):
        return json.loads(await anext(self.subscription))
    
# This file contains all the async code for the PocketOption Module
class PocketOptionAsync:
    def __init__(self, ssid: str, **kwargs):
        if kwargs.get("url") is not None:
            self.client = RawPocketOption.new_with_url(ssid, kwargs.get("url"))
        else:
            self.client = RawPocketOption(ssid)
        self.logger = Logger()
    
    
    async def buy(self, asset: str, amount: float, time: int, check_win: bool = False) -> tuple[str, dict]:
        """
        Places a buy (call) order for the specified asset.

        Args:
            asset (str): Trading asset (e.g., "EURUSD_otc", "EURUSD")
            amount (float): Trade amount in account currency
            time (int): Expiry time in seconds (e.g., 60 for 1 minute)
            check_win (bool): If True, waits for trade result. Defaults to True.

        Returns:
            tuple[str, dict]: Tuple containing (trade_id, trade_details)
            trade_details includes:
                - asset: Trading asset
                - amount: Trade amount
                - direction: "buy"
                - expiry: Expiry timestamp
                - result: Trade result if check_win=True ("win"/"loss"/"draw")
                - profit: Profit amount if check_win=True

        Raises:
            ConnectionError: If connection to platform fails
            ValueError: If invalid parameters are provided
            TimeoutError: If trade confirmation times out
        """
        (trade_id, trade) = await self.client.buy(asset, amount, time)
        if check_win:
            return trade_id, await self.check_win(trade_id) 
        else:
            trade = json.loads(trade)
            return trade_id, trade 
       
    async def sell(self, asset: str, amount: float, time: int, check_win: bool = False) -> tuple[str, dict]:
        """
        Places a sell (put) order for the specified asset.

        Args:
            asset (str): Trading asset (e.g., "EURUSD_otc", "EURUSD")
            amount (float): Trade amount in account currency
            time (int): Expiry time in seconds (e.g., 60 for 1 minute)
            check_win (bool): If True, waits for trade result. Defaults to True.

        Returns:
            tuple[str, dict]: Tuple containing (trade_id, trade_details)
            trade_details includes:
                - asset: Trading asset
                - amount: Trade amount
                - direction: "sell"
                - expiry: Expiry timestamp
                - result: Trade result if check_win=True ("win"/"loss"/"draw")
                - profit: Profit amount if check_win=True

        Raises:
            ConnectionError: If connection to platform fails
            ValueError: If invalid parameters are provided
            TimeoutError: If trade confirmation times out
        """
        (trade_id, trade) = await self.client.sell(asset, amount, time)
        if check_win:
            return trade_id, await self.check_win(trade_id)   
        else:
            trade = json.loads(trade)
            return trade_id, trade 
 
    async def check_win(self, id: str) -> dict:
        """
        Checks the result of a specific trade.

        Args:
            trade_id (str): ID of the trade to check

        Returns:
            dict: Trade result containing:
                - result: "win", "loss", or "draw"
                - profit: Profit/loss amount
                - details: Additional trade details
                - timestamp: Result timestamp

        Raises:
            ValueError: If trade_id is invalid
            TimeoutError: If result check times out
        """
        end_time = await self.client.get_deal_end_time(id)
        
        if end_time is not None:
            duration = end_time - int(time.time())
            if duration <= 0:
                duration = 5 # If duration is less than 0 then the trade is closed and the function should take less than 5 seconds to run
        else:
            duration = 5
        duration += 6
        
        self.logger.debug(f"Timeout set to: {duration} (6 extra seconds)")
        async def check(id):
            trade = await self.client.check_win(id)
            trade = json.loads(trade)
            win = trade["profit"]
            if win > 0:
                trade["result"] = "win"
            elif win == 0:
                trade["result"] = "draw"
            else:
                trade["result"] = "loss"
            return trade
        return await _timeout(check(id), duration)
        
        
    async def get_candles(self, asset: str, period: int, offset: int) -> list[dict]:  
        """
        Retrieves historical candle data for an asset.

        Args:
            asset (str): Trading asset (e.g., "EURUSD_otc")
            timeframe (int): Candle timeframe in seconds (e.g., 60 for 1-minute candles)
            period (int): Historical period in seconds to fetch

        Returns:
            list[dict]: List of candles, each containing:
                - time: Candle timestamp
                - open: Opening price
                - high: Highest price
                - low: Lowest price
                - close: Closing price
                - volume: Trading volume

        Note:
            Available timeframes: 1, 5, 15, 30, 60, 300 seconds
            Maximum period depends on the timeframe
        """
        candles = await self.client.get_candles(asset, period, offset)
        return json.loads(candles)
    
    async def balance(self) -> float:
        """
        Retrieves current account balance.

        Returns:
            float: Account balance in account currency

        Note:
            Updates in real-time as trades are completed
        """
        return json.loads(await self.client.balance())["balance"]
    
    async def opened_deals(self) -> list[dict]:
        "Returns a list of all the opened deals as dictionaries"
        return json.loads(await self.client.opened_deals())
    
    async def closed_deals(self) -> list[dict]:
        "Returns a list of all the closed deals as dictionaries"
        return json.loads(await self.client.closed_deals())
    
    async def clear_closed_deals(self) -> None:
        "Removes all the closed deals from memory, this function doesn't return anything"
        await self.client.clear_closed_deals()

    async def payout(self, asset: None | str | list[str] = None) -> dict | list[int] | int:
        """
        Retrieves current payout percentages for all assets.

        Returns:
            dict: Asset payouts mapping:
                {
                    "EURUSD_otc": 85,  # 85% payout
                    "GBPUSD": 82,      # 82% payout
                    ...
                }
            list: If asset is a list, returns a list of payouts for each asset in the same order
            int: If asset is a string, returns the payout for that specific asset
            none: If asset didn't match and valid asset none will be returned
        """        
        payout = json.loads(await self.client.payout())
        if isinstance(asset, str):
            return payout.get(asset)
        elif isinstance(asset, list):
            return [payout.get(ast) for ast in asset]
        return payout
    
    async def history(self, asset: str, period: int) -> list[dict]:
        "Returns a list of dictionaries containing the latest data available for the specified asset starting from 'period', the data is in the same format as the returned data of the 'get_candles' function."
        return json.loads(await self.client.history(asset, period))
    
    async def _subscribe_symbol_inner(self, asset: str) :
        return await self.client.subscribe_symbol(asset)
    
    async def _subscribe_symbol_chuncked_inner(self, asset: str, chunck_size: int):
        return await self.client.subscribe_symbol_chuncked(asset, chunck_size)
    
    async def _subscribe_symbol_timed_inner(self, asset: str, time: timedelta):
        return await self.client.subscribe_symbol_timed(asset, time)
    
    async def subscribe_symbol(self, asset: str) -> AsyncSubscription:
        """
        Creates a real-time data subscription for an asset.

        Args:
            asset (str): Trading asset to subscribe to

        Returns:
            AsyncSubscription: Async iterator yielding real-time price updates

        Example:
            ```python
            async with api.subscribe_symbol("EURUSD_otc") as subscription:
                async for update in subscription:
                    print(f"Price update: {update}")
            ```
        """
        return AsyncSubscription(await self._subscribe_symbol_inner(asset))
    
    async def subscribe_symbol_chuncked(self, asset: str, chunck_size: int) -> AsyncSubscription:
        """Returns an async iterator over the associated asset, it will return real time candles formed with the specified amount of raw candles and will return new candles while the 'PocketOptionAsync' class is loaded if the class is droped then the iterator will fail"""
        return AsyncSubscription(await self._subscribe_symbol_chuncked_inner(asset, chunck_size))
    
    async def subscribe_symbol_timed(self, asset: str, time: timedelta) -> AsyncSubscription:
        """
        Creates a timed real-time data subscription for an asset.

        Args:
            asset (str): Trading asset to subscribe to
            interval (int): Update interval in seconds

        Returns:
            AsyncSubscription: Async iterator yielding price updates at specified intervals

        Example:
            ```python
            # Get updates every 5 seconds
            async with api.subscribe_symbol_timed("EURUSD_otc", 5) as subscription:
                async for update in subscription:
                    print(f"Timed update: {update}")
            ```
        """
        return AsyncSubscription(await self._subscribe_symbol_timed_inner(asset, time))
    
    async def send_raw_message(self, message: str) -> None:
        """
        Sends a raw WebSocket message without waiting for a response.
        
        Args:
            message: Raw WebSocket message to send (e.g., '42["ping"]')
        """
        await self.client.send_raw_message(message)
        
    async def create_raw_order(self, message: str, validator: Validator) -> str:
        """
        Sends a raw WebSocket message and waits for a validated response.
        
        Args:
            message: Raw WebSocket message to send
            validator: Validator instance to validate the response
            
        Returns:
            str: The first message that matches the validator's conditions
            
        Example:
            ```python
            validator = Validator.starts_with('451-["signals/load"')
            response = await client.create_raw_order(
                '42["signals/subscribe"]',
                validator
            )
            ```
        """
        return await self.client.create_raw_order(message, validator.raw_validator)
        
    async def create_raw_order_with_timout(self, message: str, validator: Validator, timeout: timedelta) -> str:
        """
        Similar to create_raw_order but with a timeout.
        
        Args:
            message: Raw WebSocket message to send
            validator: Validator instance to validate the response
            timeout: Maximum time to wait for a valid response
            
        Returns:
            str: The first message that matches the validator's conditions
            
        Raises:
            TimeoutError: If no valid response is received within the timeout period
        """

        return await self.client.create_raw_order_with_timeout(message, validator.raw_validator, timeout)
    
    async def create_raw_order_with_timeout_and_retry(self, message: str, validator: Validator, timeout: timedelta) -> str:
        """
        Similar to create_raw_order_with_timout but with automatic retry on failure.
        
        Args:
            message: Raw WebSocket message to send
            validator: Validator instance to validate the response
            timeout: Maximum time to wait for each attempt
            
        Returns:
            str: The first message that matches the validator's conditions
        """

        return await self.client.create_raw_order_with_timeout_and_retry(message, validator.raw_validator, timeout)
 
    async def create_raw_iterator(self, message: str, validator: Validator, timeout: timedelta | None = None):
        """
        Creates an async iterator that yields validated WebSocket messages.
        
        Args:
            message: Initial WebSocket message to send
            validator: Validator instance to filter incoming messages
            timeout: Optional timeout for the entire stream
            
        Returns:
            AsyncIterator yielding validated messages
            
        Example:
            ```python
            validator = Validator.starts_with('{"signals":')
            async for message in client.create_raw_iterator(
                '42["signals/subscribe"]',
                validator,
                timeout=timedelta(minutes=5)
            ):
                print(f"Received: {message}")
            ```
        """
        return await self.client.create_raw_iterator(message, validator, timeout)
    
    async def is_demo(self) -> bool:
        """
        Checks if the current account is a demo account.

        Returns:
            bool: True if using a demo account, False if using a real account

        Examples:
            ```python
            # Basic account type check
            async with PocketOptionAsync(ssid) as client:
                is_demo = await client.is_demo()
                print("Using", "demo" if is_demo else "real", "account")

            # Example with balance check
            async def check_account():
                is_demo = await client.is_demo()
                balance = await client.balance()
                print(f"{'Demo' if is_demo else 'Real'} account balance: {balance}")

            # Example with trade validation
            async def safe_trade(asset: str, amount: float, duration: int):
                is_demo = await client.is_demo()
                if not is_demo and amount > 100:
                    raise ValueError("Large trades should be tested in demo first")
                return await client.buy(asset, amount, duration)
            ```
        """
        return await self.client.is_demo()

async def _timeout(future, timeout: int):
    if sys.version_info[:3] >= (3,11): 
        async with asyncio.timeout(timeout):
            return await future
    else:
        return await asyncio.wait_for(future, timeout)


# ========================= FIN DE asyncronous.py =========================


# ============================== get_assets_pocketoption.py ==============================
# 📁 Ruta: pocket_options_examples/get_assets_pocketoption.py
################################################################################

# obtener_activos.py (basado en TU script y funcional)

import asyncio
import json
from BinaryOptionsToolsV2.pocketoption import PocketOptionAsync

# Main part of the code
async def main(ssid: str):
    api = PocketOptionAsync(ssid)
    
    print("⏳ Esperando 5 segundos antes de conectarse...")
    await asyncio.sleep(5)

    # Full payout como dict
    full_payout = await api.payout()
    
    if not full_payout:
        print("⚠️ No se obtuvo información. Verifica el SSID o el estado del servidor.")
        return

    # Ordenar
    ordered_payout = dict(sorted(full_payout.items()))

    # Mostrar en consola
    print("\n🔹 Activos ordenados:\n")
    for symbol, payout in ordered_payout.items():
        print(f"  {symbol:<15} → {payout:>3}%")

    # Guardar en JSON ordenado
    with open("utils/pocket_options/activos_pocketoption.json", "w", encoding="utf-8") as f:
        json.dump(ordered_payout, f, indent=4, ensure_ascii=False)

    print("\n✅ Guardado en: utils/pocket_options/activos_pocketoption.json")

if __name__ == '__main__':
    ssid = input("🔐 Ingresa tu SSID de PocketOption: ")
    asyncio.run(main(ssid))


# ========================= FIN DE get_assets_pocketoption.py =========================


# ============================== test_connection.py ==============================
# 📁 Ruta: pocket_options_examples/test_connection.py
################################################################################

import asyncio
import os
import time
from dotenv import load_dotenv
from BinaryOptionsToolsV2.pocketoption import PocketOptionAsync

load_dotenv()

SSID = os.getenv("POCKETOPTION_SSID")
SYMBOL = "EURUSD"

async def test_pocketoption_connection():
    if not SSID:
        print("ERROR: Falta POCKETOPTION_SSID en el archivo .env")
        return

    print("=== Iniciando prueba de conexión con Pocket Option ===")
    client = PocketOptionAsync(ssid=SSID)

    # Esperar para que se estabilice la conexión WebSocket
    await asyncio.sleep(5)

    try:
        raw_balance = await client.balance()
        print(f"> Balance recibido: {raw_balance}")

        if raw_balance is None or raw_balance < 0:
            print("⚠ Balance inválido. Verifica SSID o espera más.")
        else:
            print("✅ Balance válido confirmado.")

        stream = await client.subscribe_symbol(SYMBOL)
        print(f"> Suscrito a {SYMBOL}. Recibiendo ticks durante 30 segundos...")

        start_time = time.time()

        async for tick in stream:
            print(f"✅ Tick recibido: {tick}")
            if time.time() - start_time >= 30:
                print("⏹️ Tiempo de prueba completado (30 segundos).")
                break

    except Exception as e:
        print("ERROR en la prueba:", e)

asyncio.run(test_pocketoption_connection())

# ========================= FIN DE test_connection.py =========================


# ============================== check_win.py ==============================
# 📁 Ruta: pocket_options_examples/async/check_win.py
################################################################################

from BinaryOptionsToolsV2.pocketoption import PocketOptionAsync


import asyncio
# Main part of the code
async def main(ssid: str):
    # The api automatically detects if the 'ssid' is for real or demo account
    api = PocketOptionAsync(ssid)
    (buy_id, _) = await api.buy(asset="EURUSD_otc", amount=1.0, time=15, check_win=False)
    (sell_id, _) = await api.sell(asset="EURUSD_otc", amount=1.0, time=300, check_win=False)
    print(buy_id, sell_id)
    # This is the same as setting checkw_win to true on the api.buy and api.sell functions
    buy_data = await api.check_win(buy_id)
    print(f"Buy trade result: {buy_data['result']}\nBuy trade data: {buy_data}")
    sell_data = await api.check_win(sell_id)
    print(f"Sell trade result: {sell_data['result']}\nSell trade data: {sell_data}")


    
if __name__ == '__main__':
    ssid = input('Please enter your ssid: ')
    asyncio.run(main(ssid))
    

# ========================= FIN DE check_win.py =========================


# ============================== create_raw_iterator.py ==============================
# 📁 Ruta: pocket_options_examples/async/create_raw_iterator.py
################################################################################

from BinaryOptionsToolsV2.pocketoption import PocketOptionAsync
from BinaryOptionsToolsV2.validator import Validator
from datetime import timedelta

import asyncio

async def main(ssid: str):
    # Initialize the API client
    api = PocketOptionAsync(ssid)    
    await asyncio.sleep(5)  # Wait for connection to establish
    
    # Create a validator for price updates
    validator = Validator.regex(r'{"price":\d+\.\d+}')
    
    # Create an iterator with 5 minute timeout
    stream = await api.create_raw_iterator(
        '42["price/subscribe"]',  # WebSocket subscription message
        validator,
        timeout=timedelta(minutes=5)
    )
    
    try:
        # Process messages as they arrive
        async for message in stream:
            print(f"Received message: {message}")
    except TimeoutError:
        print("Stream timed out after 5 minutes")
    except Exception as e:
        print(f"Error processing stream: {e}")

if __name__ == '__main__':
    ssid = input('Please enter your ssid: ')
    asyncio.run(main(ssid))

# ========================= FIN DE create_raw_iterator.py =========================


# ============================== create_raw_order.py ==============================
# 📁 Ruta: pocket_options_examples/async/create_raw_order.py
################################################################################

from BinaryOptionsToolsV2.pocketoption import PocketOptionAsync
from BinaryOptionsToolsV2.validator import Validator
from datetime import timedelta

import asyncio

async def main(ssid: str):
    # Initialize the API client
    api = PocketOptionAsync(ssid)    
    await asyncio.sleep(5)  # Wait for connection to establish
    
    # Basic raw order example
    try:
        validator = Validator.contains('"status":"success"')
        response = await api.create_raw_order(
            '42["signals/subscribe"]',
            validator
        )
        print(f"Basic raw order response: {response}")
    except Exception as e:
        print(f"Basic raw order failed: {e}")

    # Raw order with timeout example
    try:
        validator = Validator.regex(r'{"type":"signal","data":.*}')
        response = await api.create_raw_order_with_timout(
            '42["signals/load"]',
            validator,
            timeout=timedelta(seconds=5)
        )
        print(f"Raw order with timeout response: {response}")
    except TimeoutError:
        print("Order timed out after 5 seconds")
    except Exception as e:
        print(f"Order with timeout failed: {e}")

    # Raw order with timeout and retry example
    try:
        # Create a validator that checks for both conditions
        validator = Validator.all([
            Validator.contains('"type":"trade"'),
            Validator.contains('"status":"completed"')
        ])
        
        response = await api.create_raw_order_with_timeout_and_retry(
            '42["trade/subscribe"]',
            validator,
            timeout=timedelta(seconds=10)
        )
        print(f"Raw order with retry response: {response}")
    except Exception as e:
        print(f"Order with retry failed: {e}")

if __name__ == '__main__':
    ssid = input('Please enter your ssid: ')
    asyncio.run(main(ssid))

# ========================= FIN DE create_raw_order.py =========================


# ============================== get_balance.py ==============================
# 📁 Ruta: pocket_options_examples/async/get_balance.py
################################################################################

from BinaryOptionsToolsV2 import PocketOptionAsync

import asyncio
# Main part of the code
async def main(ssid: str):
    # The api automatically detects if the 'ssid' is for real or demo account
    api = PocketOptionAsync(ssid)
    await asyncio.sleep(5)
    
    balance = await api.balance()
    print(f"Balance: {balance}")
    
if __name__ == '__main__':
    ssid = input('Please enter your ssid: ')
    asyncio.run(main(ssid))
    

# ========================= FIN DE get_balance.py =========================


# ============================== get_candles.py ==============================
# 📁 Ruta: pocket_options_examples/async/get_candles.py
################################################################################

from BinaryOptionsToolsV2.pocketoption import PocketOptionAsync

import pandas as pd
import asyncio
# Main part of the code
async def main(ssid: str):
    # The api automatically detects if the 'ssid' is for real or demo account
    api = PocketOptionAsync(ssid)    
    await asyncio.sleep(5)
    
    # Candñes are returned in the format of a list of dictionaries
    times = [ 3600 * i for i in range(1, 11)]
    time_frames = [ 1, 5, 15, 30, 60, 300]
    for time in times:
        for frame in time_frames:
            
            candles = await api.get_candles("EURUSD_otc", 60, time)
            # print(f"Raw Candles: {candles}")
            candles_pd = pd.DataFrame.from_dict(candles)
            print(f"Candles: {candles_pd}")
    
if __name__ == '__main__':
    ssid = input('Please enter your ssid: ')
    asyncio.run(main(ssid))
    

# ========================= FIN DE get_candles.py =========================


# ============================== get_open_and_close_trades.py ==============================
# 📁 Ruta: pocket_options_examples/async/get_open_and_close_trades.py
################################################################################

from BinaryOptionsToolsV2.pocketoption import PocketOptionAsync

import asyncio
# Main part of the code
async def main(ssid: str):
    # The api automatically detects if the 'ssid' is for real or demo account
    api = PocketOptionAsync(ssid)
    _ = await api.buy(asset="EURUSD_otc", amount=1.0, time=60, check_win=False)
    _ = await api.sell(asset="EURUSD_otc", amount=1.0, time=60, check_win=False)
    # This is the same as setting checkw_win to true on the api.buy and api.sell functions
    opened_deals = await api.opened_deals()
    print(f"Opened deals: {opened_deals}\nNumber of opened deals: {len(opened_deals)} (should be at least 2)")
    await asyncio.sleep(62) # Wait for the trades to complete
    closed_deals = await api.closed_deals()
    print(f"Closed deals: {closed_deals}\nNumber of closed deals: {len(closed_deals)} (should be at least 2)")

    
if __name__ == '__main__':
    ssid = input('Please enter your ssid: ')
    asyncio.run(main(ssid))
    

# ========================= FIN DE get_open_and_close_trades.py =========================


# ============================== history.py ==============================
# 📁 Ruta: pocket_options_examples/async/history.py
################################################################################

from BinaryOptionsToolsV2.pocketoption import PocketOptionAsync

import pandas as pd
import asyncio
# Main part of the code
async def main(ssid: str):
    # The api automatically detects if the 'ssid' is for real or demo account
    api = PocketOptionAsync(ssid)    
    await asyncio.sleep(5)
    
    # Candles are returned in the format of a list of dictionaries
    candles = await api.history("EURUSD_otc", 3600)
    print(f"Raw Candles: {candles}")
    candles_pd = pd.DataFrame.from_dict(candles)
    print(f"Candles: {candles_pd}")
    
if __name__ == '__main__':
    ssid = input('Please enter your ssid: ')
    asyncio.run(main(ssid))
    

# ========================= FIN DE history.py =========================


# ============================== logs.py ==============================
# 📁 Ruta: pocket_options_examples/async/logs.py
################################################################################

from BinaryOptionsToolsV2.tracing import start_logs
from BinaryOptionsToolsV2.pocketoption import PocketOptionAsync

import asyncio
# Main part of the code
async def main(ssid: str):
    # Start logs, it works perfectly on async code
    start_logs(path=".", level="DEBUG", terminal=True) # If false then the logs will only be written to the log files
    # The api automatically detects if the 'ssid' is for real or demo account
    api = PocketOptionAsync(ssid)
    (buy_id, _) = await api.buy(asset="EURUSD_otc", amount=1.0, time=300, check_win=False)
    (sell_id, _) = await api.sell(asset="EURUSD_otc", amount=1.0, time=300, check_win=False)
    print(buy_id, sell_id)
    # This is the same as setting checkw_win to true on the api.buy and api.sell functions
    buy_data = await api.check_win(buy_id)
    sell_data = await api.check_win(sell_id)
    print(f"Buy trade result: {buy_data['result']}\nBuy trade data: {buy_data}")
    print(f"Sell trade result: {sell_data['result']}\nSell trade data: {sell_data}")


    
if __name__ == '__main__':
    ssid = input('Please enter your ssid: ')
    asyncio.run(main(ssid))
    

# ========================= FIN DE logs.py =========================


# ============================== log_iterator.py ==============================
# 📁 Ruta: pocket_options_examples/async/log_iterator.py
################################################################################

# Import necessary modules
from BinaryOptionsToolsV2.tracing import Logger, LogBuilder
from datetime import timedelta
import asyncio

async def main():
    """
    Main asynchronous function demonstrating the usage of logging system.
    """
    
    # Create a Logger instance
    logger = Logger()
    
    # Create a LogBuilder instance
    log_builder = LogBuilder()
    
    # Create a new logs iterator with INFO level and 10-second timeout
    log_iterator = log_builder.create_logs_iterator(level="INFO", timeout=timedelta(seconds=10))

    # Configure logging to write to a file
    # This will create or append to 'logs.log' file with INFO level logs
    log_builder.log_file(path="app_logs.txt", level="INFO")

    # Configure terminal logging for DEBUG level
    log_builder.terminal(level="DEBUG")

    # Build and initialize the logging configuration
    log_builder.build()

    # Create a Logger instance with the built configuration
    logger = Logger()

    # Log some messages at different levels
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warn("This is a warning message")
    logger.error("This is an error message")

    # Example of logging with variables
    asset = "EURUSD"
    amount = 100
    logger.info(f"Bought {amount} units of {asset}")

    # Demonstrate async usage
    async def log_async():
        """
        Asynchronous logging function demonstrating async usage.
        """
        logger.debug("This is an asynchronous debug message")
        await asyncio.sleep(5)  # Simulate some work
        logger.info("Async operation completed")

    # Run the async function
    task1 = asyncio.create_task(log_async())

    # Example of using LogBuilder for creating iterators
    async def process_logs(log_iterator):
        """
        Function demonstrating the use of LogSubscription.
        """
        
        try:
            async for log in log_iterator:
                print(f"Received log: {log}")
                # Each log is a dict so we can access the message
                print(f"Log message: {log['message']}")
        except Exception as e:
            print(f"Error processing logs: {e}")

    # Run the logs processing function
    task2 = asyncio.create_task(process_logs(log_iterator))
    
    # Execute both tasks at the same time
    await asyncio.gather(task1, task2)

    

if __name__ == "__main__":
    asyncio.run(main())

# ========================= FIN DE log_iterator.py =========================


# ============================== payout.py ==============================
# 📁 Ruta: pocket_options_examples/async/payout.py
################################################################################

from BinaryOptionsToolsV2.pocketoption import PocketOptionAsync

import asyncio
# Main part of the code
async def main(ssid: str):
    # The api automatically detects if the 'ssid' is for real or demo account
    api = PocketOptionAsync(ssid)    
    await asyncio.sleep(5)
    
    # Candñes are returned in the format of a list of dictionaries
    full_payout = await api.payout() # Returns a dictionary asset: payout
    print(f"Full Payout: {full_payout}")
    partial_payout = await api.payout(["EURUSD_otc", "EURUSD", "AEX25"]) # Returns a list of the payout for each of the passed assets in order
    print(f"Partial Payout: {partial_payout}")
    single_payout = await api.payout("EURUSD_otc") # Returns the payout for the specified asset
    print(f"Single Payout: {single_payout}")
    
    
if __name__ == '__main__':
    ssid = input('Please enter your ssid: ')
    asyncio.run(main(ssid))
    

# ========================= FIN DE payout.py =========================


# ============================== raw_send.py ==============================
# 📁 Ruta: pocket_options_examples/async/raw_send.py
################################################################################

from BinaryOptionsToolsV2.pocketoption import PocketOptionAsync
import asyncio

async def main(ssid: str):
    # Initialize the API client
    api = PocketOptionAsync(ssid)    
    await asyncio.sleep(5)  # Wait for connection to establish
    
    # Example of sending a raw message
    try:
        # Subscribe to signals
        await api.send_raw_message('42["signals/subscribe"]')
        print("Sent signals subscription message")
        
        # Subscribe to price updates
        await api.send_raw_message('42["price/subscribe"]')
        print("Sent price subscription message")
        
        # Custom message example
        custom_message = '42["custom/event",{"param":"value"}]'
        await api.send_raw_message(custom_message)
        print(f"Sent custom message: {custom_message}")
        
        # Multiple messages in sequence
        messages = [
            '42["chart/subscribe",{"asset":"EURUSD"}]',
            '42["trades/subscribe"]',
            '42["notifications/subscribe"]'
        ]
        
        for msg in messages:
            await api.send_raw_message(msg)
            print(f"Sent message: {msg}")
            await asyncio.sleep(1)  # Small delay between messages
            
    except Exception as e:
        print(f"Error sending message: {e}")

if __name__ == '__main__':
    ssid = input('Please enter your ssid: ')



# ========================= FIN DE raw_send.py =========================


# ============================== subscribe_symbol.py ==============================
# 📁 Ruta: pocket_options_examples/async/subscribe_symbol.py
################################################################################

from BinaryOptionsToolsV2.pocketoption import PocketOptionAsync

import asyncio
# Main part of the code
async def main(ssid: str):
    # The api automatically detects if the 'ssid' is for real or demo account
    api = PocketOptionAsync(ssid)    
    stream = await api.subscribe_symbol("EURUSD_otc")
    
    # This should run forever so you will need to force close the program
    async for candle in stream:
        print(f"Candle: {candle}") # Each candle is in format of a dictionary 
    
if __name__ == '__main__':
    ssid = input('Please enter your ssid: ')
    asyncio.run(main(ssid))
    

# ========================= FIN DE subscribe_symbol.py =========================


# ============================== subscribe_symbol_chuncked.py ==============================
# 📁 Ruta: pocket_options_examples/async/subscribe_symbol_chuncked.py
################################################################################

from BinaryOptionsToolsV2.pocketoption import PocketOptionAsync

import asyncio
# Main part of the code
async def main(ssid: str):
    # The api automatically detects if the 'ssid' is for real or demo account
    api = PocketOptionAsync(ssid)    
    stream = await api.subscribe_symbol_chuncked("EURUSD_otc", 15) # Returns a candle obtained from combining 15 (chunk_size) candles
    
    # This should run forever so you will need to force close the program
    async for candle in stream:
        print(f"Candle: {candle}") # Each candle is in format of a dictionary 
    
if __name__ == '__main__':
    ssid = input('Please enter your ssid: ')
    asyncio.run(main(ssid))
    

# ========================= FIN DE subscribe_symbol_chuncked.py =========================


# ============================== subscribe_symbol_timed.py ==============================
# 📁 Ruta: pocket_options_examples/async/subscribe_symbol_timed.py
################################################################################

from BinaryOptionsToolsV2.pocketoption import PocketOptionAsync
from BinaryOptionsToolsV2.tracing import start_logs
from datetime import timedelta

import asyncio

# Main part of the code
async def main(ssid: str):
    # The api automatically detects if the 'ssid' is for real or demo account
    start_logs(".", "INFO")
    api = PocketOptionAsync(ssid)    
    stream = await api.subscribe_symbol_timed("EURUSD_otc", timedelta(seconds=5)) # Returns a candle obtained from combining candles that are inside a specific time range
    
    # This should run forever so you will need to force close the program
    async for candle in stream:
        print(f"Candle: {candle}") # Each candle is in format of a dictionary 
    
if __name__ == '__main__':
    ssid = input('Please enter your ssid: ')
    asyncio.run(main(ssid))
    

# ========================= FIN DE subscribe_symbol_timed.py =========================


# ============================== trade.py ==============================
# 📁 Ruta: pocket_options_examples/async/trade.py
################################################################################

from BinaryOptionsToolsV2.pocketoption import PocketOptionAsync

import asyncio
# Main part of the code
async def main(ssid: str):
    # The api automatically detects if the 'ssid' is for real or demo account
    api = PocketOptionAsync(ssid)
    
    (buy_id, buy) = await api.buy(asset="EURUSD_otc", amount=1.0, time=60, check_win=False)
    print(f"Buy trade id: {buy_id}\nBuy trade data: {buy}")
    (sell_id, sell) = await api.sell(asset="EURUSD_otc", amount=1.0, time=60, check_win=False)
    print(f"Sell trade id: {sell_id}\nSell trade data: {sell}")
    
if __name__ == '__main__':
    ssid = input('Please enter your ssid: ')
    asyncio.run(main(ssid))
    

# ========================= FIN DE trade.py =========================


# ============================== validator.py ==============================
# 📁 Ruta: pocket_options_examples/async/validator.py
################################################################################

from BinaryOptionsToolsV2.validator import Validator

if __name__ == "__main__":
    none = Validator()
    regex = Validator.regex("([A-Z])\w+")
    start = Validator.starts_with("Hello")
    end = Validator.ends_with("Bye")
    contains = Validator.contains("World")
    rnot = Validator.ne(contains)
    custom = Validator.custom(lambda x: x.startswith("Hello") and x.endswith("World"))

    # Modified for better testing - smaller groups with predictable outcomes
    rall = Validator.all([regex, start])  # Will need both capital letter and "Hello" at start
    rany = Validator.any([contains, end])  # Will need either "World" or end with "Bye"

    print(f"None validator: {none.check('hello')} (Expected: True)")
    print(f"Regex validator: {regex.check('Hello')} (Expected: True)")
    print(f"Regex validator: {regex.check('hello')} (Expected: False)")
    print(f"Starts_with validator: {start.check('Hello World')} (Expected: True)")
    print(f"Starts_with validator: {start.check('hi World')} (Expected: False)")
    print(f"Ends_with validator: {end.check('Hello Bye')} (Expected: True)")
    print(f"Ends_with validator: {end.check('Hello there')} (Expected: False)")
    print(f"Contains validator: {contains.check('Hello World')} (Expected: True)")
    print(f"Contains validator: {contains.check('Hello there')} (Expected: False)")
    print(f"Not validator: {rnot.check('Hello World')} (Expected: False)")
    print(f"Not validator: {rnot.check('Hello there')} (Expected: True)")
    try:
        print(f"Custom validator: {custom.check('Hello World')}, (Expected: True)")
        print(f"Custom validator: {custom.check('Hello there')}, (Expected: False)")
    except Exception as e:
        print(f"Error: {e}")        
    # Testing the all validator
    print(f"All validator: {rall.check('Hello World')} (Expected: True)")  # Starts with "Hello" and has capital
    print(f"All validator: {rall.check('hello World')} (Expected: False)")  # No capital at start
    print(f"All validator: {rall.check('Hey there')} (Expected: False)")  # Has capital but doesn't start with "Hello"

    # Testing the any validator
    print(f"Any validator: {rany.check('Hello World')} (Expected: True)")  # Contains "World"
    print(f"Any validator: {rany.check('Hello Bye')} (Expected: True)")  # Ends with "Bye"
    print(f"Any validator: {rany.check('Hello there')} (Expected: False)")  # Neither contains "World" nor ends with "Bye"

# ========================= FIN DE validator.py =========================


# ============================== test.py ==============================
# 📁 Ruta: pocket_options_examples/tests/test.py
################################################################################

import asyncio
# import pandas as pd # type: ignore
# import json

# import BinaryOptionsToolsV2
# from BinaryOptionsToolsV2 import connect

# print(BinaryOptionsToolsV2)
from BinaryOptionsToolsV2.BinaryOptionsToolsV2.pocketoption.asyncronous import PocketOptionAsync

# async def main(ssid):
#     api = await async_connect(ssid)
#     await asyncio.sleep(10)
#     payout = await api.payout()
#     candles = await api.history("EURUSD_otc", 7200)
#     trade = await api.buy("EURUSD_otc", 1, 5)
#     print(f"Payout: {payout}")
#     print(f"Candles: {candles}")
#     print(f"Trade: {trade}")
#     df = pd.DataFrame.from_dict(candles)
#     df.to_csv("candles_eurusd_otc.csv")    
async def main(ssid):
    # Testing the new iterator
    api = PocketOptionAsync(ssid)
    await asyncio.sleep(5)
    stream = await api.subscribe_symbol("EURUSD_otc")
    async for item in stream:
        print(item["time"], item["open"])

    
if __name__ == "__main__":
    ssid = input("Write your ssid: ")
    asyncio.run(main(ssid))



# ========================= FIN DE test.py =========================


# ============================== test_sync.py ==============================
# 📁 Ruta: pocket_options_examples/tests/test_sync.py
################################################################################

from BinaryOptionsToolsV2.BinaryOptionsToolsV2.pocketoption.syncronous import PocketOption
import time

def main(ssid):
    api = PocketOption(ssid)
    time.sleep(5)
    iterator = api.subscribe_symbol("EURUSD_otc")
    for item in iterator:
        print(item)


if __name__ == "__main__":
    ssid = input("Write your ssid: ")
    main(ssid)

# ========================= FIN DE test_sync.py =========================


# ============================== strategies.py ==============================
# 📁 Ruta: strategy/strategies.py
################################################################################

from typing import List, Dict, Optional
import logging
import talib
import numpy as np
import pandas as pd
from pandas_ta import rsi, macd, bbands, stoch, adx
from sklearn.preprocessing import MinMaxScaler
import warnings
warnings.filterwarnings('ignore')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Strategy:
    def evaluate(self, candles: List[Dict]) -> Optional[str]:
        pass

    def _prepare_data(self, candles: List[Dict]) -> pd.DataFrame:
        """Convertir velas a pandas DataFrame para análisis."""
        df = pd.DataFrame(candles)
        if 'time' not in df.columns:
            logger.error("Columna 'time' faltante en los datos de velas")
            return pd.DataFrame()
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)
        for col in ['open', 'high', 'low', 'close']:
            if col in df.columns:
                df[col] = df[col].astype(float)
            else:
                logger.warning(f"Columna {col} faltante, rellenando con NaN")
                df[col] = np.nan
        return df

class BaseStrategy:
    def __init__(self):
        self.name = self.__class__.__name__
        self.initialized = False
        self.candles = []
        self.last_signal = None
        self.last_signal_time = 0
        self.min_candles_required = 30  # Mínimo de velas necesarias
        self.signal_cooldown = 0  # Para implementar en subclases si es necesario
        
    def initialize(self, candles: List[List[float]]):
        """
        Inicializa la estrategia con datos históricos.
        
        Args:
            candles: Lista de velas con formato [time, open, high, low, close]
        """
        if len(candles) < self.min_candles_required:
            logger.warning(f"Se necesitan al menos {self.min_candles_required} velas para inicializar la estrategia {self.name}")
            self.candles = []
            self.initialized = False
            return
            
        self.candles = candles
        self.initialized = True
        logger.info(f"Estrategia {self.name} inicializada con {len(candles)} velas")
        
    def update(self, candle: List[float]) -> Optional[str]:
        """
        Actualiza la estrategia con una nueva vela y genera señal si corresponde.
        
        Args:
            candle: Nueva vela con formato [time, open, high, low, close]
            
        Returns:
            str: 'call' para compra, 'put' para venta, None si no hay señal
        """
        # Verificar si está inicializada
        if not self.initialized:
            return None
            
        # Verificar cooldown entre señales
        if self.last_signal_time > 0 and candle[0] - self.last_signal_time < self.signal_cooldown:
            return None
            
        # Agregar solo si es una vela nueva
        is_new = True
        if self.candles:
            last_candle_time = self.candles[-1][0]
            if candle[0] <= last_candle_time:
                is_new = False
                
        if is_new:
            self.candles.append(candle)
            # Limitar la cantidad de velas almacenadas para evitar uso excesivo de memoria
            if len(self.candles) > 1000:
                self.candles = self.candles[-1000:]
            
        # Generar señal
        signal = self.generate_signal(self.candles)
        
        # Registrar señal si existe
        if signal:
            self.last_signal = signal
            self.last_signal_time = candle[0]
            
        return signal
        
    def generate_signal(self, candles: List[List[float]]) -> Optional[str]:
        """
        Genera una señal de trading basada en los datos de velas.
        
        Args:
            candles: Lista de velas con formato [time, open, high, low, close]
            
        Returns:
            str: 'call' para compra, 'put' para venta, None si no hay señal
        """
        raise NotImplementedError
        
    def check_trend(self, candles: List[List[float]], period: int = 20) -> str:
        """
        Determina la tendencia actual del mercado.
        
        Args:
            candles: Lista de velas
            period: Período para la media móvil
        
        Returns:
            str: 'up', 'down' o 'sideways'
        """
        if len(candles) < period:
            return 'sideways'
            
        closes = np.array([candle[4] for candle in candles])
        sma = talib.SMA(closes, timeperiod=period)
        
        # Verificar tendencia basada en precio vs SMA
        price = closes[-1]
        prev_price = closes[-5] if len(closes) > 5 else closes[0]
        
        price_change = ((price - prev_price) / prev_price) * 100
        
        if price > sma[-1] and price_change > 0.1:
            return 'up'
        elif price < sma[-1] and price_change < -0.1:
            return 'down'
        else:
            return 'sideways'
            
    def check_volatility(self, candles: List[List[float]], period: int = 14) -> bool:
        """
        Determina si la volatilidad es adecuada para operar.
        
        Args:
            candles: Lista de velas
            period: Período para calcular ATR
        
        Returns:
            bool: True si la volatilidad es adecuada
        """
        if len(candles) < period:
            return False
            
        highs = np.array([candle[2] for candle in candles])
        lows = np.array([candle[3] for candle in candles])
        closes = np.array([candle[4] for candle in candles])
        
        atr = talib.ATR(highs, lows, closes, timeperiod=period)
        
        # ATR como porcentaje del precio
        atr_pct = (atr[-1] / closes[-1]) * 100
        
        # Volatilidad adecuada: entre 0.1% y 2%
        return 0.1 < atr_pct < 2.0

class MovingAverageCrossover(BaseStrategy):
    def __init__(self, short_period: int = 8, long_period: int = 21):
        super().__init__()
        self.short_period = short_period
        self.long_period = long_period
        self.min_candles_required = long_period + 5
        self.signal_cooldown = 300  # 5 minutos entre señales
        
    def generate_signal(self, candles: List[List[float]]) -> Optional[str]:
        if len(candles) < self.min_candles_required:
            return None
            
        # Verificar volatilidad
        if not self.check_volatility(candles):
            return None
            
        closes = np.array([candle[4] for candle in candles])
        
        # Calcular medias móviles
        short_ema = talib.EMA(closes, timeperiod=self.short_period)
        long_ema = talib.EMA(closes, timeperiod=self.long_period)
        
        # Verificar cruce
        crossover = short_ema[-2] <= long_ema[-2] and short_ema[-1] > long_ema[-1]
        crossunder = short_ema[-2] >= long_ema[-2] and short_ema[-1] < long_ema[-1]
        
        # Obtener tendencia
        trend = self.check_trend(candles)
        
        # Generar señal basada en tendencia + cruce
        if crossover and trend == 'up':
            return 'call'
        elif crossunder and trend == 'down':
            return 'put'
            
        return None

class RSI(BaseStrategy):
    def __init__(self, period: int = 14, overbought: float = 70, oversold: float = 30):
        super().__init__()
        self.period = period
        self.overbought = overbought
        self.oversold = oversold
        self.min_candles_required = period + 5
        self.signal_cooldown = 300  # 5 minutos entre señales
        
    def generate_signal(self, candles: List[List[float]]) -> Optional[str]:
        if len(candles) < self.min_candles_required:
            return None
            
        # Verificar volatilidad
        if not self.check_volatility(candles):
            return None
            
        closes = np.array([candle[4] for candle in candles])
        
        # Calcular RSI
        rsi_values = talib.RSI(closes, timeperiod=self.period)
        
        # RSI actual y previo
        current_rsi = rsi_values[-1]
        prev_rsi = rsi_values[-2]
        
        # Obtener tendencia
        trend = self.check_trend(candles)
        
        # Evaluar señales
        # Señal de compra: RSI sale de sobreventa en tendencia alcista
        if prev_rsi < self.oversold and current_rsi > self.oversold and trend != 'down':
            return 'call'
            
        # Señal de venta: RSI sale de sobrecompra en tendencia bajista
        elif prev_rsi > self.overbought and current_rsi < self.overbought and trend != 'up':
            return 'put'
            
        return None

class MACD(BaseStrategy):
    def __init__(self, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9):
        super().__init__()
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
        self.min_candles_required = slow_period + signal_period + 5
        self.signal_cooldown = 300  # 5 minutos entre señales
        
    def generate_signal(self, candles: List[List[float]]) -> Optional[str]:
        if len(candles) < self.min_candles_required:
            return None
            
        # Verificar volatilidad
        if not self.check_volatility(candles):
            return None
            
        closes = np.array([candle[4] for candle in candles])
        
        # Calcular MACD
        macd, signal, hist = talib.MACD(
            closes,
            fastperiod=self.fast_period,
            slowperiod=self.slow_period,
            signalperiod=self.signal_period
        )
        
        # Verificar cruce y dirección del histograma
        crossover = macd[-2] <= signal[-2] and macd[-1] > signal[-1]
        crossunder = macd[-2] >= signal[-2] and macd[-1] < signal[-1]
        
        # Histograma aumentando/disminuyendo
        hist_increasing = hist[-1] > hist[-2] > hist[-3]
        hist_decreasing = hist[-1] < hist[-2] < hist[-3]
        
        # Obtener tendencia
        trend = self.check_trend(candles)
        
        # Señal de compra: MACD cruza por encima de señal, histograma aumentando, tendencia alcista
        if crossover and hist_increasing and trend != 'down':
            return 'call'
            
        # Señal de venta: MACD cruza por debajo de señal, histograma disminuyendo, tendencia bajista
        elif crossunder and hist_decreasing and trend != 'up':
            return 'put'
            
        return None

class BollingerBands(BaseStrategy):
    def __init__(self, period: int = 20, std_dev: float = 2.0):
        super().__init__()
        self.period = period
        self.std_dev = std_dev
        self.min_candles_required = period + 5
        self.signal_cooldown = 300  # 5 minutos entre señales
        
    def generate_signal(self, candles: List[List[float]]) -> Optional[str]:
        if len(candles) < self.min_candles_required:
            return None
            
        # Verificar volatilidad
        if not self.check_volatility(candles):
            return None
            
        closes = np.array([candle[4] for candle in candles])
        
        # Calcular Bandas de Bollinger
        upper, middle, lower = talib.BBANDS(
            closes, 
            timeperiod=self.period,
            nbdevup=self.std_dev,
            nbdevdn=self.std_dev,
            matype=0  # SMA
        )
        
        # Obtener tendencia
        trend = self.check_trend(candles)
        
        # Precio actual y previo
        current_price = closes[-1]
        prev_price = closes[-2]
        
        # Señal de compra: Precio rebota desde banda inferior en tendencia alcista
        if prev_price <= lower[-2] and current_price > lower[-1] and trend != 'down':
            return 'call'
            
        # Señal de venta: Precio rebota desde banda superior en tendencia bajista
        elif prev_price >= upper[-2] and current_price < upper[-1] and trend != 'up':
            return 'put'
            
        return None

# ========================= FIN DE strategies.py =========================


# ============================== __init__.py ==============================
# 📁 Ruta: strategy/__init__.py
################################################################################

# (Archivo vacío)


# ========================= FIN DE __init__.py =========================


# ============================== logger.py ==============================
# 📁 Ruta: utils/logger.py
################################################################################

import logging
import os
from datetime import datetime

class Logger:
    _instance = None

    def __new__(cls, level="INFO"):
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, level="INFO"):
        if self._initialized:
            return

        self.logger = logging.getLogger('trading_bot')
        self.logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        self.logger.propagate = False

        if self.logger.handlers:
            self.logger.handlers.clear()

        if not os.path.exists('logs'):
            os.makedirs('logs')

        log_file = f'logs/trading_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)  # Archivo guarda todo

        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, level.upper(), logging.INFO))  # Consola usa nivel configurado

        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

        self._initialized = True

    def info(self, message): self.logger.info(message)
    def error(self, message): self.logger.error(message)
    def warning(self, message): self.logger.warning(message)
    def debug(self, message): self.logger.debug(message)

# ========================= FIN DE logger.py =========================
