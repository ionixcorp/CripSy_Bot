# Ruta del módulo: modules\collector.py

import os
import json
import logging
import asyncio
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from collections import deque
import pytz
from core.settings import TRADING_CONFIG

from core.settings import DATA_COLLECTION_CONFIG, TIMEZONE, DIRECTORIES

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("TickCollector")

class TickCollector:
    def __init__(self, pair=None, candle_constructor=None):
        self.pair = pair or "EURUSD"
        self.timezone = pytz.timezone(TIMEZONE)
        self.tick_buffer = deque(maxlen=DATA_COLLECTION_CONFIG["tick_buffer_size"])
        self.tick_df = pd.DataFrame(columns=["timestamp", "pair", "bid", "ask", "volume"])
        self.last_tick_time = None
        self.last_candle_time = None
        self.tick_counter = 0
        self.candle_constructor = candle_constructor
        self.precision = TRADING_CONFIG["asset_precision"].get(self.pair, TRADING_CONFIG["asset_precision"]["default"])
        self._create_directories()
        logger.info(f"Inicializado TickCollector para el par {self.pair} con precisión de {self.precision} decimales")

    def _create_directories(self):
        dirs_to_create = [
            DIRECTORIES["data"],
            DATA_COLLECTION_CONFIG["ticks_file_path"],
            DATA_COLLECTION_CONFIG["candles_file_path"],
            DATA_COLLECTION_CONFIG["poc_file_path"],
            DIRECTORIES["logs"]
        ]
        for directory in dirs_to_create:
            os.makedirs(directory, exist_ok=True)
        pair_tick_dir = os.path.join(DATA_COLLECTION_CONFIG["ticks_file_path"], self.pair)
        os.makedirs(pair_tick_dir, exist_ok=True)
        logger.debug("Directorios creados para almacenamiento de datos")
    
    async def process_tick(self, tick_data):
            try:
                if 'pair' in tick_data and tick_data['pair'] != self.pair:
                    return None
                self.tick_counter += 1
                timestamp = tick_data.get('timestamp', datetime.now(self.timezone).timestamp())
                if isinstance(timestamp, (int, float)):
                    tick_time = datetime.fromtimestamp(timestamp, self.timezone)
                else:
                    tick_time = datetime.now(self.timezone)
                if 'bid' in tick_data and 'ask' in tick_data:
                    bid = float(tick_data['bid'])
                    ask = float(tick_data['ask'])
                elif 'price' in tick_data:
                    price = float(tick_data['price'])
                    spread = 0.00002
                    bid = price - spread/2
                    ask = price + spread/2
                else:
                    logger.warning(f"Tick recibido sin información de precio: {tick_data}")
                    return None
                volume = tick_data.get('volume', 1)
                processed_tick = {
                    "timestamp": tick_time,
                    "pair": self.pair,
                    "bid": round(bid, self.precision),
                    "ask": round(ask, self.precision),
                    "mid": round((bid + ask) / 2, self.precision),
                    "volume": volume,
                    "tick_count": self.tick_counter
                }
                self.tick_buffer.append(processed_tick)
                self.last_tick_time = tick_time
                if DATA_COLLECTION_CONFIG["save_ticks_to_file"]:
                    await self._save_tick_to_file(processed_tick)
                await self._check_candle_completion(tick_time)
                return processed_tick
            except Exception as e:
                logger.error(f"Error al procesar tick: {e}")
                return None
    
    async def _save_tick_to_file(self, tick):
        try:
            date_str = tick["timestamp"].strftime("%Y-%m-%d")
            file_path = os.path.join(
                DATA_COLLECTION_CONFIG["ticks_file_path"],
                self.pair,
                f"{self.pair}_ticks_{date_str}.csv"
            )
            tick_row = {
                "timestamp": tick["timestamp"].timestamp(),
                "datetime": tick["timestamp"].strftime("%Y-%m-%d %H:%M:%S.%f"),
                "pair": tick["pair"],
                "bid": tick["bid"],
                "ask": tick["ask"],
                "mid": tick["mid"],
                "volume": tick["volume"],
                "tick_count": tick["tick_count"]
            }
            file_exists = os.path.isfile(file_path)
            tick_df = pd.DataFrame([tick_row])
            if file_exists:
                tick_df.to_csv(file_path, mode='a', header=False, index=False)
            else:
                tick_df.to_csv(file_path, index=False)
        except Exception as e:
            logger.error(f"Error al guardar tick en archivo: {e}")
    
    async def save_ticks_to_file(self):
        """Guarda todos los ticks actuales del buffer en un archivo."""
        try:
            if not self.tick_buffer:
                logger.info("No hay ticks en el buffer para guardar")
                return
            date_str = datetime.now(self.timezone).strftime("%Y-%m-%d")
            file_path = os.path.join(
                DATA_COLLECTION_CONFIG["ticks_file_path"],
                self.pair,
                f"{self.pair}_ticks_{date_str}.csv"
            )
            ticks_list = list(self.tick_buffer)
            ticks_df = pd.DataFrame(ticks_list)
            ticks_df["timestamp"] = ticks_df["timestamp"].apply(lambda x: x.timestamp())
            ticks_df["datetime"] = ticks_df["timestamp"].apply(
                lambda x: datetime.fromtimestamp(x, self.timezone).strftime("%Y-%m-%d %H:%M:%S.%f")
            )
            file_exists = os.path.isfile(file_path)
            if file_exists:
                ticks_df.to_csv(file_path, mode='a', header=False, index=False)
            else:
                ticks_df.to_csv(file_path, index=False)
            logger.info(f"Ticks guardados en {file_path}")
        except Exception as e:
            logger.error(f"Error al guardar ticks en archivo: {e}")
    
    async def _check_candle_completion(self, tick_time):
        current_candle_time = tick_time.replace(
            minute=(tick_time.minute // 5) * 5,
            second=0,
            microsecond=0
        )
        if self.last_candle_time is None:
            self.last_candle_time = current_candle_time
            logger.debug(f"Primer tiempo de vela establecido: {current_candle_time}")
            return
        if current_candle_time > self.last_candle_time:
            candle_ticks = self.get_ticks_for_timeframe(
                self.last_candle_time, 
                self.last_candle_time + timedelta(minutes=5)
            )
            if candle_ticks and len(candle_ticks) > 0:
                logger.info(f"Construyendo vela para {self.last_candle_time} con {len(candle_ticks)} ticks")
                if self.candle_constructor:
                    await self.candle_constructor.construct_candle(candle_ticks)
                else:
                    logger.error("CandleConstructor no está inicializado")
            else:
                logger.warning(f"No hay ticks suficientes para construir vela en {self.last_candle_time}")
            self.last_candle_time = current_candle_time
    
    def get_latest_ticks(self, n=1):
        n = min(n, len(self.tick_buffer))
        return list(self.tick_buffer)[-n:]
    
    def get_ticks_for_timeframe(self, start_time, end_time):
        return [tick for tick in self.tick_buffer if start_time <= tick["timestamp"] < end_time]
    
    def get_current_price(self):
        if len(self.tick_buffer) > 0:
            latest_tick = self.tick_buffer[-1]
            return {
                "bid": latest_tick["bid"],
                "ask": latest_tick["ask"],
                "mid": latest_tick["mid"],
                "timestamp": latest_tick["timestamp"]
            }
        return None
    
    async def export_ticks_to_dataframe(self, start_time=None, end_time=None):
        if start_time and end_time:
            ticks = self.get_ticks_for_timeframe(start_time, end_time)
        else:
            ticks = list(self.tick_buffer)
        if not ticks:
            return pd.DataFrame()
        df = pd.DataFrame(ticks)
        if 'timestamp' in df.columns:
            df['datetime'] = pd.to_datetime(df['timestamp'])
            df.set_index('datetime', inplace=True)
        return df
    
    def clear_old_data(self, hours=24):
        if not self.tick_buffer:
            return
        cutoff_time = datetime.now(self.timezone) - timedelta(hours=hours)
        new_buffer = deque(
            [tick for tick in self.tick_buffer if tick["timestamp"] > cutoff_time],
            maxlen=self.tick_buffer.maxlen
        )
        self.tick_buffer = new_buffer
        logger.info(f"Eliminados datos de ticks con más de {hours} horas de antigüedad")