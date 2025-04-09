import os
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import json
import asyncio
import pytz
from collections import defaultdict
from core.settings import TRADING_CONFIG

# Importar configuraciones
from core.settings import (
    DATA_COLLECTION_CONFIG, 
    CANDLE_CONSTRUCTOR_CONFIG,
    POC_STRATEGY_CONFIG,
    TIMEZONE,
    DIRECTORIES
)

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CandleConstructor")

class CandleConstructor:
    def __init__(self, pair=None, timeframe="5m"):
        self.pair = pair or "EURUSD"
        self.timeframe = timeframe
        self.timezone = pytz.timezone(TIMEZONE)
        self.precision = TRADING_CONFIG["asset_precision"].get(self.pair, TRADING_CONFIG["asset_precision"]["default"])
        self.timeframe_minutes = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60}
        self.minutes = self.timeframe_minutes.get(self.timeframe, 5)
        self.candles = {}
        self.poc_history = {}
        self.last_poc = None
        self.last_candle_color = None
        self._create_directories()
        logger.info(f"Inicializado CandleConstructor para {self.pair} en timeframe {self.timeframe} con precisión de {self.precision} decimales")
    
    def _create_directories(self):
        """Crea los directorios necesarios para almacenar datos."""
        # Crear directorio específico para este par y timeframe
        pair_candle_dir = os.path.join(
            DATA_COLLECTION_CONFIG["candles_file_path"], 
            f"{self.pair}_{self.timeframe}"
        )
        os.makedirs(pair_candle_dir, exist_ok=True)
        
        # Directorio para POCs
        pair_poc_dir = os.path.join(
            DATA_COLLECTION_CONFIG["poc_file_path"], 
            f"{self.pair}_{self.timeframe}"
        )
        os.makedirs(pair_poc_dir, exist_ok=True)
        
        logger.debug("Directorios creados para almacenamiento de velas y POCs")
    
    async def construct_candle(self, ticks):
        """
        Construye una vela a partir de una lista de ticks.
        
        Args:
            ticks (list): Lista de ticks para el período de la vela.
            
        Returns:
            dict: Vela construida con OHLCV y POC.
        """
        if not ticks or len(ticks) < 2:
            logger.warning("Insuficientes ticks para construir una vela válida")
            return None
            
        # Ordenar ticks por timestamp para asegurar secuencia correcta
        sorted_ticks = sorted(ticks, key=lambda x: x["timestamp"])
        
        # Obtener timestamp de inicio y fin de la vela
        first_tick = sorted_ticks[0]
        last_tick = sorted_ticks[-1]
        
        start_time = first_tick["timestamp"]
        
        # Normalizar el tiempo de inicio a intervalos del timeframe
        normalized_start_time = start_time.replace(
            minute=(start_time.minute // self.minutes) * self.minutes,
            second=0,
            microsecond=0
        )
        
        end_time = normalized_start_time + timedelta(minutes=self.minutes)
        
        # Extraer precios para cálculo OHLC
        prices = [tick["mid"] for tick in sorted_ticks]
        volumes = [tick["volume"] for tick in sorted_ticks]
        
        # Calcular OHLCV
        open_price = prices[0]
        high_price = max(prices)
        low_price = min(prices)
        close_price = prices[-1]
        volume = sum(volumes)
        
        # Determinar el color de la vela
        candle_color = 'green' if close_price >= open_price else 'red'
        self.last_candle_color = candle_color
        
        # Calcular el Point of Control (POC)
        poc_price, volume_profile = await self._calculate_poc(sorted_ticks)
        
        # Construir objeto de vela
        candle = {
            "timestamp": normalized_start_time,
            "end_time": end_time,
            "pair": self.pair,
            "timeframe": self.timeframe,
            "open": round(open_price, DATA_COLLECTION_CONFIG["data_precision"]),
            "high": round(high_price, DATA_COLLECTION_CONFIG["data_precision"]),
            "low": round(low_price, DATA_COLLECTION_CONFIG["data_precision"]),
            "close": round(close_price, DATA_COLLECTION_CONFIG["data_precision"]),
            "volume": volume,
            "tick_count": len(sorted_ticks),
            "color": candle_color,
            "poc": round(poc_price, DATA_COLLECTION_CONFIG["data_precision"]),
            "volume_profile": volume_profile
        }
        
        # Guardar la vela en nuestro historial
        candle_key = normalized_start_time.strftime("%Y-%m-%d %H:%M")
        self.candles[candle_key] = candle
        
        # Guardar el POC en el historial
        self.poc_history[candle_key] = poc_price
        self.last_poc = poc_price
        
        # Guardar vela en archivo
        await self._save_candle(candle)
        
        logger.info(f"Vela construida para {self.pair} en {normalized_start_time}: " +
                    f"O:{open_price} H:{high_price} L:{low_price} C:{close_price} POC:{poc_price}")
        
        return candle
    
    async def _calculate_poc(self, ticks):
        if not ticks:
            return None, {}
        prices = np.array([tick["mid"] for tick in ticks])
        min_price = np.min(prices)
        max_price = np.max(prices)
        if max_price - min_price < 0.0001:
            buffer = 0.0001
            min_price -= buffer
            max_price += buffer
        price_levels = CANDLE_CONSTRUCTOR_CONFIG["price_levels"]
        if CANDLE_CONSTRUCTOR_CONFIG["poc_detection_method"] == "volume_profile":
            bins = np.linspace(min_price, max_price, price_levels)
            volumes = np.array([tick["volume"] for tick in ticks])
            hist, bin_edges = np.histogram(prices, bins=bins, weights=volumes)
            if CANDLE_CONSTRUCTOR_CONFIG["smoothing_factor"] > 1:
                kernel_size = CANDLE_CONSTRUCTOR_CONFIG["smoothing_factor"]
                kernel = np.ones(kernel_size) / kernel_size
                hist = np.convolve(hist, kernel, mode='same')
            max_volume_idx = np.argmax(hist)
            poc_price = (bin_edges[max_volume_idx] + bin_edges[max_volume_idx + 1]) / 2
            poc_price = round(poc_price, DATA_COLLECTION_CONFIG["data_precision"])  # Redondeo aquí
            volume_profile = {}
            for i in range(len(hist)):
                price_level = round((bin_edges[i] + bin_edges[i + 1]) / 2, DATA_COLLECTION_CONFIG["data_precision"])
                volume_profile[str(price_level)] = float(hist[i])
        else:
            total_volume = sum(tick["volume"] for tick in ticks)
            weighted_price = sum(tick["mid"] * tick["volume"] for tick in ticks)
            poc_price = weighted_price / total_volume if total_volume > 0 else prices[-1]
            poc_price = round(poc_price, DATA_COLLECTION_CONFIG["data_precision"])  # Redondeo aquí
            bins = np.linspace(min_price, max_price, price_levels)
            hist, bin_edges = np.histogram(prices, bins=bins)
            volume_profile = {}
            for i in range(len(hist)):
                price_level = round((bin_edges[i] + bin_edges[i + 1]) / 2, DATA_COLLECTION_CONFIG["data_precision"])
                volume_profile[str(price_level)] = float(hist[i])
        return poc_price, volume_profile
    
    async def _save_candle(self, candle):
        """
        Guarda la vela construida en un archivo para posterior análisis.
        
        Args:
            candle (dict): Vela a guardar
        """
        try:
            # Obtener fecha como string para el nombre del archivo
            date_str = candle["timestamp"].strftime("%Y-%m-%d")
            
            # Definir la ruta del archivo
            file_path = os.path.join(
                DATA_COLLECTION_CONFIG["candles_file_path"],
                f"{self.pair}_{self.timeframe}",
                f"{self.pair}_{self.timeframe}_candles_{date_str}.csv"
            )
            
            # Convertir la vela a formato adecuado para CSV
            candle_row = {
                "timestamp": candle["timestamp"].timestamp(),
                "datetime": candle["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
                "pair": candle["pair"],
                "timeframe": candle["timeframe"],
                "open": candle["open"],
                "high": candle["high"],
                "low": candle["low"],
                "close": candle["close"],
                "volume": candle["volume"],
                "tick_count": candle["tick_count"],
                "color": candle["color"],
                "poc": candle["poc"]
            }
            
            # Verificar si el archivo ya existe
            file_exists = os.path.isfile(file_path)
            
            # Usar pandas para guardar en CSV de manera eficiente
            if file_exists:
                # Abrir en modo append si ya existe
                candle_df = pd.DataFrame([candle_row])
                candle_df.to_csv(file_path, mode='a', header=False, index=False)
            else:
                # Crear nuevo archivo si no existe
                candle_df = pd.DataFrame([candle_row])
                candle_df.to_csv(file_path, index=False)
            
            # Guardar también el perfil de volumen en un archivo JSON separado
            volume_profile_dir = os.path.join(
                DATA_COLLECTION_CONFIG["poc_file_path"],
                f"{self.pair}_{self.timeframe}",
                "volume_profiles"
            )
            os.makedirs(volume_profile_dir, exist_ok=True)
            
            volume_profile_file = os.path.join(
                volume_profile_dir,
                f"{date_str}_{candle['timestamp'].strftime('%H_%M')}_profile.json"
            )
            
            with open(volume_profile_file, 'w') as f:
                json.dump(candle["volume_profile"], f, indent=2)
                
        except Exception as e:
            logger.error(f"Error al guardar vela en archivo: {e}")
            
    def get_latest_candle(self):
        """
        Obtiene la vela más reciente construida.
        
        Returns:
            dict: Última vela construida
        """
        if not self.candles:
            return None
            
        # Obtener la clave más reciente
        latest_key = max(self.candles.keys())
        return self.candles[latest_key]
    
    def get_latest_poc(self):
        """
        Obtiene el POC más reciente calculado.
        
        Returns:
            float: Último valor de POC calculado
        """
        return self.last_poc
    
    def get_latest_candle_color(self):
        """
        Obtiene el color de la última vela construida.
        
        Returns:
            str: 'green' o 'red'
        """
        return self.last_candle_color
    
    def get_candles_dataframe(self, n=10):
        """
        Retorna las últimas n velas como DataFrame.
        
        Args:
            n (int): Número de velas a obtener
            
        Returns:
            pandas.DataFrame: DataFrame con las velas
        """
        if not self.candles:
            return pd.DataFrame()
            
        # Obtener las claves ordenadas por tiempo (más recientes al final)
        sorted_keys = sorted(self.candles.keys())
        
        # Tomar las últimas n claves
        recent_keys = sorted_keys[-n:] if len(sorted_keys) > n else sorted_keys
        
        # Obtener las velas correspondientes
        recent_candles = [self.candles[key] for key in recent_keys]
        
        # Convertir a DataFrame
        df = pd.DataFrame(recent_candles)
        
        return df
    
    def is_poc_touched(self, current_price, tolerance=None):
        """
        Verifica si el precio actual ha tocado el POC anterior.
        
        Args:
            current_price (float): Precio actual
            tolerance (float, optional): Tolerancia para considerar que el precio ha tocado el POC
            
        Returns:
            bool: True si el precio ha tocado el POC, False en caso contrario
        """
        if self.last_poc is None:
            return False
            
        # Usar la tolerancia configurada si no se especifica
        if tolerance is None:
            tolerance = POC_STRATEGY_CONFIG["price_tolerance"]
            
        # Verificar si el precio actual está dentro de la tolerancia del POC
        return abs(current_price - self.last_poc) <= tolerance
    
    async def load_historical_candles(self, days=1):
        """
        Carga velas históricas desde archivos CSV.
        
        Args:
            days (int): Número de días hacia atrás para cargar
            
        Returns:
            dict: Velas cargadas indexadas por timestamp
        """
        try:
            # Calcular fechas para el rango
            end_date = datetime.now(self.timezone)
            start_date = end_date - timedelta(days=days)
            
            loaded_candles = {}
            
            # Iterar por cada día en el rango
            current_date = start_date
            while current_date <= end_date:
                date_str = current_date.strftime("%Y-%m-%d")
                
                # Ruta del archivo para ese día
                file_path = os.path.join(
                    DATA_COLLECTION_CONFIG["candles_file_path"],
                    f"{self.pair}_{self.timeframe}",
                    f"{self.pair}_{self.timeframe}_candles_{date_str}.csv"
                )
                
                # Verificar si existe el archivo
                if os.path.isfile(file_path):
                    # Cargar datos con pandas
                    df = pd.read_csv(file_path)
                    
                    # Convertir a diccionario
                    for _, row in df.iterrows():
                        timestamp = datetime.fromtimestamp(row["timestamp"], self.timezone)
                        key = timestamp.strftime("%Y-%m-%d %H:%M")
                        
                        # Reconstruir la vela
                        candle = {
                            "timestamp": timestamp,
                            "end_time": timestamp + timedelta(minutes=self.minutes),
                            "pair": row["pair"],
                            "timeframe": row["timeframe"],
                            "open": row["open"],
                            "high": row["high"],
                            "low": row["low"],
                            "close": row["close"],
                            "volume": row["volume"],
                            "tick_count": row["tick_count"],
                            "color": row["color"],
                            "poc": row["poc"]
                        }
                        
                        loaded_candles[key] = candle
                        
                        # Actualizar también el historial de POCs
                        self.poc_history[key] = row["poc"]
                
                # Avanzar al siguiente día
                current_date += timedelta(days=1)
                
            # Actualizar nuestras velas
            self.candles.update(loaded_candles)
            
            # Actualizar último POC y color si hay datos cargados
            if loaded_candles:
                latest_key = max(loaded_candles.keys())
                latest_candle = loaded_candles[latest_key]
                self.last_poc = latest_candle["poc"]
                self.last_candle_color = latest_candle["color"]
                
            logger.info(f"Cargadas {len(loaded_candles)} velas históricas para {self.pair}")
            return loaded_candles
            
        except Exception as e:
            logger.error(f"Error al cargar velas históricas: {e}")
            return {}