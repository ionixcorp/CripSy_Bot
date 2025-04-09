# Ruta del módulo: core\connection.py

import time
import asyncio
import logging
from aiohttp import ClientSession, ClientWebSocketResponse, WSMsgType
from BinaryOptionsToolsV2.pocketoption import PocketOptionAsync
from BinaryOptionsToolsV2.validator import Validator
from datetime import timedelta
import json
from dotenv import load_dotenv

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PocketOptionAPI")

class PocketOptionAPI:
    """
    Clase que actúa como un wrapper alrededor de PocketOptionAsync para conectar el bot
    con la API de Pocket Option en tiempo real.
    """
    
    def __init__(self, ssid: str, api_url=None, ws_url=None):
        """
        Inicializa la conexión con Pocket Option.

        Args:
            ssid (str): Session ID para autenticación.
            api_url (str, optional): URL base para peticiones HTTP (no usado actualmente).
            ws_url (str, optional): URL para WebSocket (no usado, manejado por PocketOptionAsync).
        """
        load_dotenv()
        self.ssid = ssid
        self.api_url = api_url or "https://api.pocketoption.com"
        self.ws_url = ws_url or "wss://ws.pocketoption.com/v2"
        self.client = None  # Instancia de PocketOptionAsync
        self.session = None
        self.is_connected = False
        self.authenticated = False
        self.callbacks = {}  # Callbacks para ticks y resultados de operaciones
        self.ping_task = None
        self.subscription_task = None

    async def initialize(self):
        """Inicializa la sesión y el cliente de Pocket Option."""
        if self.client is None:
            self.session = ClientSession()
            self.client = PocketOptionAsync(self.ssid)
            logger.info("Cliente PocketOptionAsync inicializado")

    async def verify_connection(self) -> bool:
        """
        Verifica si la conexión y autenticación son exitosas.

        Returns:
            bool: True si la conexión es válida, False en caso contrario.
        """
        await self.initialize()
        try:
            # Verificar si es una cuenta demo o real (esto también prueba la conexión)
            is_demo = await self.client.is_demo()
            self.is_connected = True
            self.authenticated = True
            logger.info(f"Conexión verificada. Cuenta: {'demo' if is_demo else 'real'}")
            # Iniciar ping para mantener la conexión viva
            self.ping_task = asyncio.create_task(self._ping_loop())
            return True
        except Exception as e:
            logger.error(f"Error al verificar conexión: {str(e)}")
            self.is_connected = False
            self.authenticated = False
            return False

    async def reconnect(self):
        """Intenta reconectar al servidor en caso de desconexión."""
        logger.info("Intentando reconectar...")
        self.is_connected = False
        if self.ping_task:
            self.ping_task.cancel()
        if self.subscription_task:
            self.subscription_task.cancel()
        await self.verify_connection()

    async def ping(self) -> bool:
        """Envía un ping al servidor y verifica la respuesta."""
        try:
            await self.client.send_raw_message('42["ping"]')
            return True
        except Exception as e:
            logger.error(f"Error en ping: {str(e)}")
            return False

    async def _ping_loop(self):
        """Mantiene la conexión viva enviando pings periódicos."""
        while self.is_connected:
            try:
                await asyncio.sleep(30)  # Ping cada 30 segundos
                if not await self.ping():
                    logger.warning("Ping fallido, intentando reconectar...")
                    await self.reconnect()
            except Exception as e:
                logger.error(f"Error en bucle de ping: {str(e)}")
                await asyncio.sleep(5)

    async def subscribe_to_ticks(self, asset: str) -> bool:
        """
        Suscribe al bot a actualizaciones de ticks en tiempo real para un activo.

        Args:
            asset (str): Par de divisas (ej. "EURUSD").

        Returns:
            bool: True si la suscripción es exitosa, False en caso contrario.
        """
        if not self.is_connected or not self.authenticated:
            logger.error("No se puede suscribir: no conectado o no autenticado")
            return False

        try:
            # Usar subscribe_symbol para obtener datos en tiempo real
            self.subscription_task = asyncio.create_task(self._tick_listener(asset))
            logger.info(f"Suscrito a ticks en tiempo real para {asset}")
            return True
        except Exception as e:
            logger.error(f"Error al suscribir a {asset}: {str(e)}")
            return False

    async def _tick_listener(self, asset: str):
        """Escucha ticks en tiempo real y los pasa al callback."""
        while self.is_connected:
            try:
                stream = await self.client.subscribe_symbol(asset)
                self.logger.info(f"Escuchando ticks para {asset}")
                async for message in stream:
                    self.logger.debug(f"Tick recibido para {asset}: {message}")
                    if 'tick_callback' in self.callbacks:
                        tick_data = {
                            "pair": asset,
                            "timestamp": message.get("time", int(time.time())),
                            "price": message.get("close", message.get("price")),
                            "volume": message.get("volume", 1)
                        }
                        await self.callbacks['tick_callback'](tick_data)
            except asyncio.TimeoutError:
                self.logger.warning("Timeout en el stream de ticks, reintentando...")
                await asyncio.sleep(2)
                continue
            except Exception as e:
                self.logger.error(f"Error en el listener de ticks: {str(e)}")
                self.is_connected = False
                await self.reconnect()
                await asyncio.sleep(5)

    async def execute_trade(self, pair: str, direction: str, amount: float, expiration: int) -> str:
        """Ejecuta una operación en la plataforma."""
        if not self.is_connected or not self.authenticated:
            self.logger.error("No se puede ejecutar operación: no conectado o no autenticado")
            return None

        try:
            direction = direction.lower()
            if direction not in ["call", "put"]:
                self.logger.error(f"Dirección inválida: {direction}")
                return None

            # Verificar conexión antes de enviar
            if not await self.ping():
                self.logger.warning("Conexión perdida antes de enviar orden, intentando reconectar...")
                await self.reconnect()
                if not self.is_connected:
                    self.logger.error("No se pudo restablecer conexión para enviar orden")
                    return None

            method = self.client.buy if direction == "call" else self.client.sell
            self.logger.debug(f"Enviando orden {direction.upper()} para {pair}, monto: {amount}, expiración: {expiration}s")
            
            # Usar timeout explícito para la llamada
            trade_id, trade_details = await asyncio.wait_for(
                method(asset=pair, amount=amount, time=expiration, check_win=False),
                timeout=10.0  # Timeout de 10 segundos
            )

            if not trade_id:
                self.logger.error("No se recibió trade_id del servidor")
                return None

            if isinstance(trade_details, str):
                trade_details = json.loads(trade_details)

            self.logger.info(f"Orden {direction.upper()} enviada exitosamente - ID: {trade_id}, Detalles: {trade_details}")
            return trade_id

        except asyncio.TimeoutError:
            self.logger.error(f"Timeout al enviar orden {direction.upper()} para {pair}")
            return None
        except Exception as e:
            self.logger.error(f"Error al enviar orden {direction.upper()} para {pair}: {str(e)}")
            return None

    async def set_tick_callback(self, callback):
        """
        Registra un callback para procesar ticks en tiempo real.

        Args:
            callback: Función a llamar con cada tick recibido.
        """
        self.callbacks['tick_callback'] = callback
        logger.debug("Callback de ticks registrado")

    async def set_order_update_callback(self, callback):
        """
        Registra un callback para procesar resultados de operaciones.

        Args:
            callback: Función a llamar con cada resultado de operación.
        """
        self.callbacks['order_update_callback'] = callback
        # Iniciar escucha de resultados de operaciones
        asyncio.create_task(self._order_result_listener())
        logger.debug("Callback de resultados de operaciones registrado")

    async def _order_result_listener(self):
        """Escucha resultados de operaciones y los pasa al callback."""
        validator = Validator.contains('"type":"trade"')
        try:
            async for message in await self.client.create_raw_iterator(
                '42["trade/subscribe"]',
                validator.raw_validator,  # Usar raw_validator
                timeout=timedelta(minutes=10)
            ):
                data = json.loads(message)
                if 'order_update_callback' in self.callbacks and "data" in data:
                    trade_data = data["data"]
                    operation_id = trade_data.get("id")
                    profit = float(trade_data.get("profit", 0))
                    result = "win" if profit > 0 else "loss" if profit < 0 else "tie"
                    await self.callbacks['order_update_callback'](operation_id, result, profit)
        except Exception as e:
            logger.error(f"Error en listener de resultados: {str(e)}")
            await self.reconnect()

    async def unsubscribe_all(self):
        """Cancela todas las suscripciones y cierra la conexión."""
        if self.subscription_task:
            self.subscription_task.cancel()
        if self.ping_task:
            self.ping_task.cancel()
        if self.client:
            # No hay un método explícito para cerrar en PocketOptionAsync,
            # pero cerramos la sesión manualmente si es necesario
            if self.session and not self.session.closed:
                await self.session.close()
        self.is_connected = False
        self.authenticated = False
        logger.info("Todas las suscripciones canceladas y conexión cerrada")

    async def get_order_status(self, order_id: str) -> dict:
        """
        Obtiene el estado de una operación específica.

        Args:
            order_id (str): ID de la operación.

        Returns:
            dict: Estado de la operación.
        """
        try:
            result = await self.client.check_win(order_id)
            return {
                "status": "completed" if result["result"] in ["win", "loss", "draw"] else "pending",
                "profit": result.get("profit", 0)
            }
        except Exception as e:
            logger.error(f"Error al obtener estado de operación {order_id}: {str(e)}")
            return None

    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancela una operación activa (si es posible).

        Args:
            order_id (str): ID de la operación.

        Returns:
            bool: True si se cancela con éxito, False en caso contrario.
        """
        # PocketOptionAsync no proporciona un método directo para cancelar órdenes,
        # esto dependería de la implementación específica de la plataforma.
        logger.warning(f"Cancelación de orden {order_id} no implementada en la API")
        return False

    async def binary_order(self, asset: str, amount: float, direction: str, expiration_time: int) -> str:
        """
        Compatibilidad con OperationExecutor: ejecuta una orden binaria.

        Args:
            asset (str): Activo a operar.
            amount (float): Monto de la operación.
            direction (str): "buy" o "sell".
            expiration_time (int): Tiempo de expiración en segundos.

        Returns:
            str: ID de la operación.
        """
        direction_map = {"buy": "call", "sell": "put"}
        return await self.execute_trade(asset, direction_map.get(direction, direction), amount, expiration_time)