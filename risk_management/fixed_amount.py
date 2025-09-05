# -*- coding: utf-8 -*-
"""
Fixed Amount Risk - Gerenciamento de Valor Fixo
Sempre opera com o mesmo valor, sem martingale
"""

from typing import Dict, Any
from core.data_models import AssetState
from .base_risk import BaseRiskManager
from utils.logger import get_logger

logger = get_logger(__name__)

class FixedAmountRisk(BaseRiskManager):
    """Gerenciamento de risco com valor fixo - sem martingale"""
    
    def __init__(self, config):
        """
        Inicializa gerenciamento de valor fixo
        
        Args:
            config: Configurações do sistema
        """
        super().__init__(config)
        
        # Para valor fixo, usar INITIAL_AMOUNT como valor constante
        self.fixed_amount = self.validate_amount(self.initial_amount)
        
        logger.info(f"💰 VALOR FIXO configurado: ${self.fixed_amount:.2f}")
        logger.info("   🎯 Sem martingale - mesmo valor sempre")
    
    def calculate_amount(self, asset_state: AssetState, current_balance: float) -> float:
        """
        Calcula valor da próxima entrada (sempre o mesmo)
        
        Args:
            asset_state: Estado atual do ativo (não usado no valor fixo)
            current_balance: Saldo atual (usado apenas para verificação)
            
        Returns:
            float: Valor fixo configurado
        """
        # Verificar se há saldo suficiente
        if current_balance < self.fixed_amount:
            logger.warning(f"⚠️ {asset_state.symbol}: Saldo insuficiente para valor fixo")
            logger.warning(f"   💰 Necessário: ${self.fixed_amount:.2f} | Disponível: ${current_balance:.2f}")
            return 0.0
        
        return self.fixed_amount
    
    def should_continue_after_loss(self, asset_state: AssetState) -> bool:
        """
        Verifica se deve continuar após uma perda
        No valor fixo, sempre pode continuar (não há sequência de martingale)
        
        Args:
            asset_state: Estado atual do ativo
            
        Returns:
            bool: Sempre True para valor fixo
        """
        return True
    
    def reset_sequence(self, asset_state: AssetState):
        """
        Reseta sequência de operações do ativo
        No valor fixo, não há sequência para resetar
        
        Args:
            asset_state: Estado do ativo para resetar
        """
        # Para valor fixo, apenas resetar acumulador
        asset_state.current_sequence = 1
        asset_state.loss_accumulator = 0.0
        
        logger.debug(f"🔄 {asset_state.symbol}: Sequência resetada (valor fixo)")
    
    def process_operation_result(self, asset_state: AssetState, won: bool, profit: float):
        """
        Processa resultado da operação
        
        Args:
            asset_state: Estado do ativo
            won: Se a operação foi vitoriosa
            profit: Lucro/prejuízo da operação
        """
        # Atualizar estatísticas do ativo
        asset_state.total_operations += 1
        asset_state.total_profit += profit
        
        if won:
            asset_state.won_operations += 1
        else:
            asset_state.lost_operations += 1
        
        # Log do resultado
        self.log_operation_result(
            asset_state.symbol, 
            won, 
            profit, 
            1  # Sempre sequência 1 no valor fixo
        )
        
        # Para valor fixo, sempre resetar (não há martingale)
        self.reset_sequence(asset_state)
    
    def get_specific_config(self) -> Dict[str, Any]:
        """
        Retorna configurações específicas do valor fixo
        
        Returns:
            Dict: Configurações específicas
        """
        return {
            'fixed_amount': self.fixed_amount,
            'has_martingale': False,
            'max_sequence': 1,
            'multiplier': 1.0
        }
    
    def get_next_sequence_info(self, asset_state: AssetState, current_balance: float) -> Dict[str, Any]:
        """
        Retorna informações sobre a próxima sequência
        
        Args:
            asset_state: Estado do ativo
            current_balance: Saldo atual
            
        Returns:
            Dict: Informações da próxima sequência
        """
        next_amount = self.calculate_amount(asset_state, current_balance)
        
        return {
            'current_sequence': 1,  # Sempre 1 no valor fixo
            'next_amount': next_amount,
            'can_continue': next_amount > 0,  # Só se tiver saldo
            'loss_accumulator': 0.0,  # Sempre 0 no valor fixo
            'balance_before_operation': current_balance,
            'is_fixed_amount': True
        }
    
    def calculate_potential_loss(self, asset_state: AssetState, current_balance: float, levels: int = 1) -> Dict[str, float]:
        """
        Calcula perda potencial (no valor fixo, apenas 1 nível)
        
        Args:
            asset_state: Estado do ativo
            current_balance: Saldo atual
            levels: Ignorado no valor fixo
            
        Returns:
            Dict: Perda potencial (apenas 1 nível)
        """
        return {
            'level_1': {
                'amount': self.fixed_amount,
                'cumulative_loss': -self.fixed_amount  # Perda máxima possível
            }
        }
    
    def format_risk_summary(self, asset_state: AssetState, current_balance: float) -> str:
        """
        Formata resumo do risco atual
        
        Args:
            asset_state: Estado do ativo
            current_balance: Saldo atual
            
        Returns:
            str: Resumo formatado
        """
        can_operate = current_balance >= self.fixed_amount
        
        summary = f"💰 {asset_state.symbol} - VALOR FIXO\n"
        summary += f"   🎯 Valor: ${self.fixed_amount:.2f} (sempre)\n"
        summary += f"   💵 Saldo: ${current_balance:.2f}\n"
        summary += f"   ✅ Pode operar: {'Sim' if can_operate else 'Não'}\n"
        summary += f"   📊 Operações: {asset_state.total_operations} | WR: {asset_state.win_rate:.1f}%"
        
        return summary
    
    def get_risk_level(self) -> str:
        """
        Retorna nível de risco do gerenciamento
        
        Returns:
            str: Nível de risco
        """
        return "BAIXO"  # Valor fixo é sempre baixo risco
    
    def validate_config(self) -> bool:
        """
        Valida configurações específicas do valor fixo
        
        Returns:
            bool: True se configuração válida
        """
        # Validações da classe base
        if not super().validate_config():
            return False
        
        # Validações específicas do valor fixo
        errors = []
        
        if self.fixed_amount <= 0:
            errors.append("Valor fixo deve ser maior que 0")
        
        if self.fixed_amount < self.min_amount:
            errors.append(f"Valor fixo (${self.fixed_amount:.2f}) deve ser pelo menos o valor mínimo (${self.min_amount:.2f})")
        
        if self.fixed_amount > self.max_amount:
            errors.append(f"Valor fixo (${self.fixed_amount:.2f}) não pode exceder o valor máximo (${self.max_amount:.2f})")
        
        # Log erros se encontrados
        if errors:
            logger.error(f"❌ Erros na configuração do VALOR FIXO:")
            for error in errors:
                logger.error(f"   • {error}")
            return False
        
        return True
    
    def get_strategy_description(self) -> str:
        """
        Retorna descrição da estratégia
        
        Returns:
            str: Descrição da estratégia
        """
        return f"Valor fixo de ${self.fixed_amount:.2f} por operação, sem martingale"
    
    def is_conservative(self) -> bool:
        """
        Verifica se é uma estratégia conservadora
        
        Returns:
            bool: True (valor fixo é sempre conservador)
        """
        return True
    
    def get_max_possible_loss_per_operation(self) -> float:
        """
        Retorna perda máxima possível por operação
        
        Returns:
            float: Perda máxima (valor fixo)
        """
        return self.fixed_amount
    
    def estimate_operations_until_stop_loss(self, current_balance: float, initial_balance: float) -> int:
        """
        Estima quantas operações até atingir stop loss
        
        Args:
            current_balance: Saldo atual
            initial_balance: Saldo inicial
            
        Returns:
            int: Número estimado de operações
        """
        if self.stop_loss_type == "FIXED":
            remaining_until_stop = self.stop_loss_value - (initial_balance - current_balance)
        else:  # PERCENTAGE
            target_loss = (self.stop_loss_value / 100) * initial_balance
            remaining_until_stop = target_loss - (initial_balance - current_balance)
        
        if remaining_until_stop <= 0:
            return 0
        
        # Assumir taxa de perda (pior caso = 100% de perdas)
        operations_until_stop = int(remaining_until_stop / self.fixed_amount)
        
        return max(0, operations_until_stop)