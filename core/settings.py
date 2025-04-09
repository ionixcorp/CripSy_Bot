# Ruta del módulo: core\settings.py

"""
Módulo de configuraciones para el bot de Pocket Option.
Contiene todas las configuraciones necesarias para el funcionamiento del bot.
"""

class Settings:
    def __init__(self):
        self._settings = {
            # Configuración de conexión
            "connection": {
                "api_url": "https://api.pocketoption.com",
                "ws_url": "wss://ws.pocketoption.com/v2",
                "retry_attempts": 5,
                "retry_delay": 5,  # segundos
                "ping_interval": 30  # segundos
            },
            
            # Configuración de trading
            "trading": {
                "default_pair": "EURUSD",
                "default_timeframe": "5m",
                "amount": 10,
                "expiration_time": 60,
                "max_daily_operations": 10,
                "max_consecutive_losses": 3,
                "profit_target_percentage": 15,
                "stop_loss_percentage": 10,
                "asset": "EURUSD",
                "asset_precision": {
                    "EURUSD": 5,  # 5 decimales para EURUSD (ej. 1.08425)
                    "GBPUSD": 5,
                    "USDJPY": 3,  # 3 decimales para pares con JPY (ej. 150.123)
                    "default": 5  # Precisión por defecto
                }
            },
            
            # Configuración de la estrategia POC (Point of Control)
            "poc_strategy": {
                "candle_timeframe": "5m",  # Timeframe para cálculo de velas
                "poc_lookback_periods": 1,  # Cuántos períodos anteriores considerar para el POC
                "price_tolerance": 0.0002,  # Tolerancia para considerar que el precio ha tocado el POC
                "min_distance_percentage": 0.05,  # Distancia mínima del precio actual al POC en %
                "max_distance_percentage": 0.3,  # Distancia máxima del precio actual al POC en %
                "wait_for_confirmation": True,  # Esperar confirmación de rebote
                "confirmation_candles": 1,  # Número de velas para confirmar rebote
            },
            
            # Configuración de recolección de datos
            "data_collection": {
                "tick_buffer_size": 1000,  # Número máximo de ticks a almacenar en memoria
                "save_ticks_to_file": True,  # Guardar ticks en archivo
                "ticks_file_path": "data/ticks/",  # Ruta donde guardar los ticks
                "candles_file_path": "data/candles/",  # Ruta donde guardar las velas
                "poc_file_path": "data/poc/",  # Ruta donde guardar los POCs calculados
                "data_precision": 5,  # Número de decimales para redondear los precios
            },
            
            # Configuración de logging
            "logging": {
                "level": "INFO",  # Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "to_file": True,
                "file_path": "logs/bot.log",
                "max_file_size": 10 * 1024 * 1024,  # 10 MB
                "backup_count": 5,  # Número de archivos de respaldo
            },
            
            # Configuración general
            "timezone": "UTC",
            "load_historical_data": False,  # Cargar datos históricos al inicio
            "save_operation_history": True,  # Guardar historial de operaciones
            
            # Directorios
            "directories": {
                "data": "data/",
                "logs": "logs/",
                "backups": "backups/"
            },
            
            # Configuración de notificaciones (opcional para futuras implementaciones)
            "notifications": {
                "enabled": False,
                "email_notifications": False,
                "telegram_notifications": False,
                "webhook_notifications": False,
            },
            
            # Parámetros específicos para reconstructor de velas
            "candle_constructor": {
                "price_levels": 100,  # Niveles de precio para analizar en la reconstrucción
                "min_volume_threshold": 5,  # Volumen mínimo para nivel significativo
                "poc_detection_method": "volume_profile",  # Método para detectar el POC
                "smoothing_factor": 2,  # Factor de suavizado para el perfil de volumen
            }
        }

    def get(self, key, default=None):
        """
        Obtiene un valor de las configuraciones con un valor por defecto si no existe.

        Args:
            key (str): Clave del setting a buscar.
            default: Valor por defecto si la clave no existe.

        Returns:
            El valor correspondiente a la clave o el valor por defecto.
        """
        return self._settings.get(key, default)

    def __getitem__(self, key):
        """
        Permite acceder a las configuraciones usando la sintaxis de diccionario.

        Args:
            key (str): Clave del setting.

        Returns:
            El valor correspondiente a la clave.
        """
        return self._settings[key]

# Instanciar SETTINGS como un objeto de la clase Settings
SETTINGS = Settings()

# Exportar variables individuales para compatibilidad con módulos existentes
SETTINGS = Settings()
DATA_COLLECTION_CONFIG = SETTINGS['data_collection']
TIMEZONE = SETTINGS['timezone']
DIRECTORIES = SETTINGS['directories']
CANDLE_CONSTRUCTOR_CONFIG = SETTINGS['candle_constructor']
POC_STRATEGY_CONFIG = SETTINGS['poc_strategy']
TRADING_CONFIG = SETTINGS['trading']
LOGGING_CONFIG = SETTINGS['logging']