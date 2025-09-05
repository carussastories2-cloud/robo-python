# risk_management/base_risk.py

import os
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from core.data_models import AssetState
from utils.logger import get_logger

logger = get_logger(__name__)

class BaseRiskManager(ABC):
    """Classe base abstrata para gerenciadores de risco"""
    
    def __init__(self, config):
        """
        Inicializa gerenciador base lendo diretamente do ambiente para robustez.
        """
        self.config = config
        self.name = self.__class__.__name__
        
        # AQUI: Lendo as configurações diretamente do ambiente para garantir que estão corretas.
        # Isso espelha a lógica do seu código monolítico funcional e evita erros de carregamento.
        self.min_amount = float(os.getenv('MIN_AMOUNT', 0.35))
        self.max_amount = float(os.getenv('MAX_AMOUNT', 2000.00))
        
        # Carrega o tipo e o valor da entrada inicial do .env, com `.upper()` para segurança
        self.amount_type = os.getenv('INITIAL_AMOUNT_TYPE', 'FIXED').upper()
        self.amount_value = float(os.getenv('INITIAL_AMOUNT', 0.35))
        
        # Stop conditions
        self.stop_loss_value = float(os.getenv('STOP_LOSS_VALUE', 100.0))
        self.stop_win_value = float(os.getenv('STOP_WIN_VALUE', 100.0))
        self.stop_loss_type = os.getenv('STOP_LOSS_TYPE', 'FIXED').upper()
        self.stop_win_type = os.getenv('STOP_WIN_TYPE', 'FIXED').upper()
        
        logger.info(f"🎯 {self.name} inicializado")
        logger.info(f"   💰 Valores: Min=${self.min_amount:.2f} | Max=${self.max_amount:.2f}")
        logger.info(f"   🛑 Stop Loss: ${self.stop_loss_value:.2f} ({self.stop_loss_type})")
        logger.info(f"   🎯 Stop Win: ${self.stop_win_value:.2f} ({self.stop_win_type})")

    @abstractmethod
    def calculate_amount(self, asset_state: AssetState, current_balance: float, initial_balance: float) -> float:
        """
        Calcula valor da próxima entrada
        """
        pass
        
    @abstractmethod
    def process_operation_result(self, asset_state: AssetState, won: bool, profit: float) -> bool:
        """
        Processa o resultado de uma operação e retorna True se a sequência de operações terminou.
        """
        pass
    
    @abstractmethod
    def should_continue_after_loss(self, asset_state: AssetState) -> bool:
        """
        Verifica se deve continuar após uma perda
        """
        pass
    
    @abstractmethod
    def reset_sequence(self, asset_state: AssetState):
        """
        Reseta sequência de operações do ativo
        """
        pass

    def validate_amount(self, amount: float) -> float:
        """
        Valida e ajusta valor dentro dos limites (incluindo o mínimo configurado)
        """
        original_amount = amount
        
        amount = max(self.min_amount, amount)
        amount = min(self.max_amount, amount)
        
        amount = round(amount, 2)
        
        if amount != round(original_amount, 2):
            logger.debug(f"💰 Valor ajustado: ${original_amount:.2f} → ${amount:.2f}")
        
        return amount
    
    def check_stop_conditions(self, current_balance: float, initial_balance: float) -> Optional[str]:
        """
        Verifica condições de parada (Stop Loss/Win)
        """
        if initial_balance <= 0:
            return None
        
        profit = current_balance - initial_balance
        
        # Verificar Stop Loss
        if self.stop_loss_value > 0:
            loss = initial_balance - current_balance
            if self.stop_loss_type == "FIXED" and loss >= self.stop_loss_value:
                return f"Stop Loss Fixo atingido: Perda de ${loss:.2f} >= ${self.stop_loss_value:.2f}"
            elif self.stop_loss_type == "PERCENTAGE":
                loss_pct = (loss / initial_balance * 100)
                if loss_pct >= self.stop_loss_value:
                    return f"Stop Loss Percentual atingido: Perda de {loss_pct:.2f}% >= {self.stop_loss_value:.2f}%"

        # Verificar Stop Win
        if self.stop_win_value > 0:
            if self.stop_win_type == "FIXED" and profit >= self.stop_win_value:
                return f"Stop Win Fixo atingido: Lucro de ${profit:.2f} >= ${self.stop_win_value:.2f}"
            elif self.stop_win_type == "PERCENTAGE":
                win_pct = (profit / initial_balance * 100)
                if win_pct >= self.stop_win_value:
                    return f"Stop Win Percentual atingido: Lucro de {win_pct:.2f}% >= {self.stop_win_value:.2f}%"
        
        return None

    def get_risk_info(self) -> Dict[str, Any]:
        """
        Retorna informações do gerenciador de risco
        """
        return {
            'name': self.name,
            'type': self.__class__.__name__.replace('Risk', '').upper(),
            'min_amount': self.min_amount,
            'max_amount': self.max_amount,
            'initial_amount': self.amount_value, 
            'initial_amount_type': self.amount_type,
            'stop_loss_value': self.stop_loss_value,
            'stop_loss_type': self.stop_loss_type,
            'stop_win_value': self.stop_win_value,
            'stop_win_type': self.stop_win_type
        }
    
    def get_next_sequence_info(self, asset_state: AssetState, current_balance: float, initial_balance: float) -> Dict[str, Any]:
        """
        Retorna informações sobre a próxima sequência
        """
        next_amount = self.calculate_amount(asset_state, current_balance, initial_balance)
        can_continue = self.should_continue_after_loss(asset_state)
        
        return {
            'current_sequence': asset_state.current_sequence,
            'next_amount': next_amount,
            'can_continue': can_continue,
            'loss_accumulator': asset_state.loss_accumulator,
            'balance_before_operation': getattr(asset_state, 'balance_before_operation', current_balance)
        }
    
    def log_operation_result(self, symbol: str, won: bool, profit: float, sequence: int):
        """
        Log do resultado da operação
        """
        result_emoji = "✅" if won else "❌"
        result_text = "VITÓRIA" if won else "DERROTA"
        
        logger.info(f"{result_emoji} {symbol} {self.name} S{sequence}: {result_text} ${profit:+.2f}")
    
    def calculate_potential_loss(self, asset_state: AssetState, current_balance: float, initial_balance: float, levels: int = 3) -> Dict[str, Any]:
        """
        Calcula perda potencial para próximos níveis
        """
        potential_losses = {}
        temp_state = AssetState(asset_state.symbol)
        temp_state.current_sequence = asset_state.current_sequence
        temp_state.loss_accumulator = asset_state.loss_accumulator
        
        cumulative_loss = asset_state.loss_accumulator
        
        for _ in range(levels):
            amount = self.calculate_amount(temp_state, current_balance, initial_balance)
            if amount == 0:
                break

            cumulative_loss -= amount
            
            potential_losses[f'level_{temp_state.current_sequence}'] = {
                'amount': amount,
                'cumulative_loss': cumulative_loss
            }
            
            if self.should_continue_after_loss(temp_state):
                temp_state.current_sequence += 1
            else:
                break
        
        return potential_losses
    
    def format_risk_summary(self, asset_state: AssetState, current_balance: float, initial_balance: float) -> str:
        """
        Formata resumo do risco atual
        """
        info = self.get_next_sequence_info(asset_state, current_balance, initial_balance)
        
        summary = f"🎯 {asset_state.symbol} - {self.name}\n"
        summary += f"   📊 Sequência: S{info['current_sequence']}\n"
        summary += f"   💰 Próximo valor: ${info['next_amount']:.2f}\n"
        summary += f"   📉 Acumulado: ${info['loss_accumulator']:+.2f}\n"
        summary += f"   ✅ Pode continuar: {'Sim' if info['can_continue'] else 'Não'}"
        
        return summary
    
    @abstractmethod
    def get_specific_config(self) -> Dict[str, Any]:
        """
        Retorna configurações específicas do gerenciador
        """
        pass
    
    def validate_config(self) -> bool:
        """
        Valida configurações do gerenciador
        """
        errors = []
        
        if self.min_amount <= 0:
            errors.append("MIN_AMOUNT deve ser maior que 0")
        if self.max_amount <= self.min_amount:
            errors.append("MAX_AMOUNT deve ser maior que MIN_AMOUNT")
        
        if self.amount_type == 'FIXED' and self.amount_value < self.min_amount:
            errors.append(f"INITIAL_AMOUNT (${self.amount_value}) deve ser pelo menos MIN_AMOUNT (${self.min_amount})")
        elif self.amount_type == 'PERCENTAGE' and self.amount_value <= 0:
            errors.append("INITIAL_AMOUNT como PERCENTAGE deve ser maior que 0")

        if self.stop_loss_value <= 0:
            errors.append("STOP_LOSS_VALUE deve ser maior que 0")
        if self.stop_win_value < 0:
            errors.append("STOP_WIN_VALUE não pode ser negativo")
        if self.stop_loss_type not in ["FIXED", "PERCENTAGE"]:
            errors.append("STOP_LOSS_TYPE deve ser FIXED ou PERCENTAGE")
        if self.stop_win_type not in ["FIXED", "PERCENTAGE"]:
            errors.append("STOP_WIN_TYPE deve ser FIXED ou PERCENTAGE")
        
        if errors:
            logger.error(f"❌ Erros na configuração do {self.name}:")
            for error in errors:
                logger.error(f"   • {error}")
            return False
        
        return True