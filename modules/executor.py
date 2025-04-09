import os
import time
import logging
from datetime import datetime
from typing import Dict, Optional, Tuple, List

# Importamos los módulos necesarios
from core.connection import PocketOptionAPI
from core.settings import SETTINGS

class OperationExecutor:
    """
    Clase encargada de ejecutar operaciones en la plataforma Pocket Option
    basadas en las señales generadas por la estrategia.
    """
    
    def __init__(self, api_client: PocketOptionAPI):
        """
        Inicializa el ejecutor de operaciones.
        
        Args:
            api_client: Instancia del cliente API de Pocket Option
        """
        self.api = api_client
        self.logger = logging.getLogger('executor')
        self.active_operations = {}  # Operaciones activas: {operation_id: operation_details}
        self.operation_history = []  # Historial de operaciones
        self.is_trading_allowed = True  # Flag para habilitar/deshabilitar trading
        
        # Configuración desde settings
        self.amount = SETTINGS['trading']['amount']
        self.expiration = SETTINGS['trading']['expiration_time']  # En segundos (60 para 1 minuto)
        self.max_daily_operations = SETTINGS['trading']['max_daily_operations']
        self.max_consecutive_losses = SETTINGS['trading']['max_consecutive_losses']
        self.asset = SETTINGS['trading']['asset']
        
        # Contadores y estadísticas
        self.daily_operations_count = 0
        self.consecutive_losses = 0
        self.total_profit = 0
        self.wins = 0
        self.losses = 0
        
        # Reiniciar contadores diarios al inicio
        self._reset_daily_counters()
    
    def _reset_daily_counters(self) -> None:
        """Reinicia los contadores diarios de operaciones"""
        current_date = datetime.now().date()
        self.current_trading_day = current_date
        self.daily_operations_count = 0
    
    def check_trading_conditions(self) -> bool:
        """
        Verifica si se cumplen todas las condiciones para realizar operaciones
        
        Returns:
            bool: True si se puede operar, False en caso contrario
        """
        # Verificar si el trading está permitido globalmente
        if not self.is_trading_allowed:
            self.logger.info("Trading está deshabilitado globalmente")
            return False
        
        # Verificar si hemos cambiado de día para reiniciar contadores
        current_date = datetime.now().date()
        if current_date != self.current_trading_day:
            self._reset_daily_counters()
        
        # Verificar límite diario de operaciones
        if self.daily_operations_count >= self.max_daily_operations:
            self.logger.info(f"Límite diario de operaciones alcanzado ({self.max_daily_operations})")
            return False
        
        # Verificar pérdidas consecutivas
        if self.consecutive_losses >= self.max_consecutive_losses:
            self.logger.warning(f"Máximo de pérdidas consecutivas alcanzado ({self.max_consecutive_losses})")
            return False
        
        # Verificar horario de trading si está configurado
        if 'trading_hours' in SETTINGS['trading']:
            current_hour = datetime.now().hour
            start_hour, end_hour = SETTINGS['trading']['trading_hours']
            if not (start_hour <= current_hour < end_hour):
                self.logger.info(f"Fuera del horario de trading ({start_hour}:00-{end_hour}:00)")
                return False
        
        return True
    
    async def execute_operation(self, operation_type: str, reason: str = "") -> Optional[str]:
        if not self.check_trading_conditions():
            return None

        if operation_type not in ['CALL', 'PUT']:
            self.logger.error(f"Tipo de operación inválido: {operation_type}")
            return None

        try:
            operation_details = {
                'type': operation_type,
                'amount': self.amount,
                'asset': self.asset,
                'expiration': self.expiration,
                'timestamp': datetime.now(),
                'reason': reason,
                'status': 'pending',
                'result': None,
                'profit': None
            }

            api_operation_type = 'call' if operation_type == 'CALL' else 'put'
            self.logger.info(f"Preparando orden {operation_type} - Asset: {self.asset}, Monto: {self.amount}, Razón: {reason}")
            
            operation_id = await self.api.execute_trade(
                pair=self.asset,
                direction=api_operation_type,
                amount=self.amount,
                expiration=self.expiration
            )

            if not operation_id:
                self.logger.error("Fallo al enviar la orden al servidor")
                return None

            self.daily_operations_count += 1
            operation_details['id'] = operation_id
            self.active_operations[operation_id] = operation_details
            
            self.logger.info(f"Operación {operation_type} registrada localmente - ID: {operation_id}")
            return operation_id

        except Exception as e:
            self.logger.error(f"Error en execute_operation {operation_type}: {str(e)}")
            return None
    
    async def handle_operation_result(self, operation_id: str, result: str, profit: float) -> None:
        """
        Procesa el resultado de una operación
        
        Args:
            operation_id: ID de la operación
            result: Resultado ('win', 'loss', 'tie')
            profit: Ganancia/Pérdida en la moneda de la cuenta
        """
        if operation_id not in self.active_operations:
            self.logger.warning(f"Resultado recibido para operación desconocida: {operation_id}")
            return
        
        # Actualizamos los detalles de la operación
        operation = self.active_operations[operation_id]
        operation['status'] = 'completed'
        operation['result'] = result
        operation['profit'] = profit
        
        # Actualizamos estadísticas
        self.total_profit += profit
        
        if result == 'win':
            self.wins += 1
            self.consecutive_losses = 0
            self.logger.info(f"Operación ganada: {operation_id}, Ganancia: {profit}")
        elif result == 'loss':
            self.losses += 1
            self.consecutive_losses += 1
            self.logger.warning(f"Operación perdida: {operation_id}, Pérdida: {profit}")
        else:  # tie (empate)
            self.logger.info(f"Operación empatada: {operation_id}")
        
        # Movemos la operación al historial
        self.operation_history.append(operation)
        del self.active_operations[operation_id]
        
        # Guardamos historial en archivo si está configurado
        if SETTINGS.get('save_operation_history', False):
            self._save_operation_history()
    
    def _save_operation_history(self) -> None:
        """Guarda el historial de operaciones en un archivo CSV"""
        try:
            history_dir = os.path.join("data", "history")
            os.makedirs(history_dir, exist_ok=True)
            
            current_date = datetime.now().strftime("%Y-%m-%d")
            filename = os.path.join(history_dir, f"operations_{current_date}.csv")
            
            # Si el archivo no existe, creamos el encabezado
            if not os.path.exists(filename):
                with open(filename, 'w') as f:
                    f.write("id,timestamp,type,asset,amount,expiration,reason,result,profit\n")
            
            # Agregamos la última operación al archivo
            last_op = self.operation_history[-1]
            with open(filename, 'a') as f:
                f.write(f"{last_op['id']},{last_op['timestamp'].strftime('%Y-%m-%d %H:%M:%S')},"
                        f"{last_op['type']},{last_op['asset']},{last_op['amount']},"
                        f"{last_op['expiration']},{last_op['reason']},{last_op['result']},"
                        f"{last_op['profit']}\n")
                
        except Exception as e:
            self.logger.error(f"Error al guardar historial de operaciones: {str(e)}")
    
    def get_statistics(self) -> Dict:
        """
        Obtiene estadísticas del rendimiento del trading
        
        Returns:
            Dict: Diccionario con estadísticas
        """
        total_operations = self.wins + self.losses
        win_rate = (self.wins / total_operations) * 100 if total_operations > 0 else 0
        
        return {
            'total_operations': total_operations,
            'wins': self.wins,
            'losses': self.losses,
            'win_rate': win_rate,
            'total_profit': self.total_profit,
            'consecutive_losses': self.consecutive_losses,
            'daily_operations': self.daily_operations_count
        }
    
    async def check_operation_status(self) -> None:
        """Verifica el estado de las operaciones activas"""
        for operation_id in list(self.active_operations.keys()):
            try:
                # Obtenemos el estado actual de la operación
                result = await self.api.get_order_status(operation_id)
                
                if not result:
                    continue
                
                # Si la operación ya finalizó, procesamos el resultado
                if result['status'] == 'completed':
                    profit = float(result.get('profit', 0))
                    outcome = 'win' if profit > 0 else 'loss' if profit < 0 else 'tie'
                    await self.handle_operation_result(operation_id, outcome, profit)
                    
            except Exception as e:
                self.logger.error(f"Error al verificar estado de operación {operation_id}: {str(e)}")
    
    async def cancel_all_operations(self) -> None:
        """Cancela todas las operaciones activas si es posible"""
        for operation_id in list(self.active_operations.keys()):
            try:
                if await self.api.cancel_order(operation_id):
                    self.logger.info(f"Operación cancelada: {operation_id}")
                    # Movemos la operación al historial con estado cancelado
                    self.active_operations[operation_id]['status'] = 'cancelled'
                    self.operation_history.append(self.active_operations[operation_id])
                    del self.active_operations[operation_id]
            except Exception as e:
                self.logger.error(f"Error al cancelar operación {operation_id}: {str(e)}")
    
    def enable_trading(self, enabled: bool = True) -> None:
        """
        Habilita o deshabilita el trading
        
        Args:
            enabled: True para habilitar, False para deshabilitar
        """
        self.is_trading_allowed = enabled
        status = "habilitado" if enabled else "deshabilitado"
        self.logger.info(f"Trading {status}")