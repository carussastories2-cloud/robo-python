#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Martingale Risk - Gerenciamento Martingale
Suporta IMMEDIATE (imediato após expiração) e NEXT_CANDLE (início da próxima vela)
"""

from typing import Dict, Any, Optional
from core.data_models import AssetState
from .base_risk import BaseRiskManager
from utils.logger import get_logger

logger = get_logger(__name__)

class MartingaleRisk(BaseRiskManager):
    """Gerenciamento de risco Martingale com suporte a valor fixo ou percentual."""
    
    def __init__(self, config):
        """Inicializa gerenciamento Martingale."""
        super().__init__(config)
        
        self.martingale_type = getattr(config, 'MARTINGALE_TYPE', 'IMMEDIATE')
        self.multiplier = getattr(config, 'MARTINGALE_MULTIPLIER', 2.0)
        self.max_sequence = getattr(config, 'MARTINGALE_MAX_SEQUENCE', 2)
        self.analysis_timeframe_minutes = getattr(config, 'ANALYSIS_TIMEFRAME', 1)
        self.call_directions = getattr(config, 'MARTINGALE_DIRECTIONS_CALL', [])
        self.put_directions = getattr(config, 'MARTINGALE_DIRECTIONS_PUT', [])

        logger.info(f"🎲 MARTINGALE configurado:")
        if self.amount_type == 'PERCENTAGE':
            logger.info(f"   💰 Entrada Inicial: {self.amount_value}% da banca inicial da sessão.")
        else:
            logger.info(f"   💰 Entrada Inicial: Valor fixo de ${self.amount_value:.2f}")

        logger.info(f"   📊 Tipo: {self.martingale_type}")
        logger.info(f"   📈 Multiplicador: {self.multiplier}x")
        logger.info(f"   🔢 Máx Sequência: {self.max_sequence}")
    
    def _get_entry_amount(self, sequence: int, initial_balance_for_sequence: float) -> float:
        """
        Calcula o valor da entrada para uma dada sequência, baseado na regra de negócio correta.
        """
        base_amount = 0.0
        
        if self.amount_type == 'PERCENTAGE':
            # CORREÇÃO: Multiplica o PERCENTUAL, não o valor.
            current_percentage = self.amount_value * (self.multiplier ** (sequence - 1))
            base_amount = (current_percentage / 100) * initial_balance_for_sequence
            logger.debug(f"Cálculo S{sequence}: {current_percentage:.4f}% de ${initial_balance_for_sequence:.2f} = ${base_amount:.2f}")
        else: # amount_type == 'FIXED'
            base_amount = self.amount_value * (self.multiplier ** (sequence - 1))
        
        return self.validate_amount(base_amount)

    def calculate_amount(self, asset_state: AssetState, current_balance: float, initial_balance: float) -> float:
        """
        Calcula o valor para a próxima entrada.
        """
        # CORREÇÃO: Usar initial_balance se não tiver o campo específico
        initial_balance_for_seq = getattr(asset_state, 'initial_balance_for_sequence', initial_balance)
        final_amount = self._get_entry_amount(asset_state.current_sequence, initial_balance_for_seq)
        
        if current_balance < final_amount:
            logger.warning(f"⚠️ {asset_state.symbol} S{asset_state.current_sequence}: Saldo insuficiente")
            logger.warning(f"   💰 Necessário: ${final_amount:.2f} | Disponível: ${current_balance:.2f}")
            return 0.0
            
        return final_amount

    def should_continue_after_loss(self, asset_state: AssetState) -> bool:
        return asset_state.current_sequence < self.max_sequence
    
    def reset_sequence(self, asset_state: AssetState):
        old_sequence = asset_state.current_sequence
        asset_state.current_sequence = 1
        asset_state.loss_accumulator = 0.0
        asset_state.last_entry_direction = ""
        if old_sequence > 1:
            logger.info(f"🔄 {asset_state.symbol}: Sequência resetada S{old_sequence} → S1")
    
    def advance_sequence(self, asset_state: AssetState, loss_amount: float, initial_balance: float):
        """Avança a sequência de martingale e loga o próximo valor correto."""
        asset_state.current_sequence += 1
        asset_state.loss_accumulator += loss_amount
        logger.info(f"📈 {asset_state.symbol}: Martingale → S{asset_state.current_sequence}")
        logger.info(f"   💸 Perda acumulada: ${asset_state.loss_accumulator:+.2f}")
        
        # CORREÇÃO: Usar initial_balance como fallback se não tiver o campo específico
        initial_balance_for_seq = getattr(asset_state, 'initial_balance_for_sequence', initial_balance)
        next_amount = self._get_entry_amount(asset_state.current_sequence, initial_balance_for_seq)
        logger.info(f"   🎯 Próximo valor: ${next_amount:.2f}")

    def process_operation_result(self, asset_state: AssetState, won: bool, profit: float, initial_balance: float = None) -> bool:
        """
        CORREÇÃO: Adicionar parâmetro inicial_balance para usar como fallback
        """
        self.log_operation_result(asset_state.symbol, won, profit, asset_state.current_sequence)
        
        if won:
            if asset_state.loss_accumulator < 0:
                final_result = profit + asset_state.loss_accumulator
                logger.info(f"🎉 {asset_state.symbol}: VITÓRIA! Resultado final da sequência: ${final_result:+.2f}")
            else:
                logger.info(f"🎉 {asset_state.symbol}: VITÓRIA! Lucro: ${profit:+.2f}")
            self.reset_sequence(asset_state)
            return True
        else:
            if self.should_continue_after_loss(asset_state):
                # CORREÇÃO: Usar initial_balance como fallback adequado
                initial_balance_for_seq = getattr(asset_state, 'initial_balance_for_sequence', initial_balance or 0)
                self.advance_sequence(asset_state, profit, initial_balance_for_seq)
                return False
            else:
                final_result = profit + asset_state.loss_accumulator
                logger.warning(f"🛑 {asset_state.symbol}: Limite martingale atingido! Perda total: ${final_result:+.2f}")
                self.reset_sequence(asset_state)
                return True

    def get_specific_config(self) -> Dict[str, Any]:
        return {
            'martingale_type': self.martingale_type,
            'multiplier': self.multiplier,
            'max_sequence': self.max_sequence,
            'has_martingale': True,
        }

    def get_martingale_direction(self, original_direction: str, sequence: int) -> str:
        if sequence <= 1:
            return original_direction
        
        directions = self.call_directions if original_direction == 'CALL' else self.put_directions
        if not directions:
            return original_direction
        
        direction_index = sequence - 2
        if direction_index < len(directions):
            return directions[direction_index]
        else:
            return directions[-1]

    def calculate_potential_loss(self, asset_state: AssetState, current_balance: float, initial_balance: float, levels: Optional[int] = None) -> Dict[str, Any]:
        if levels is None:
            levels = self.max_sequence - asset_state.current_sequence + 1
        potential_losses = {}
        cumulative_loss = asset_state.loss_accumulator
        initial_balance_for_seq = getattr(asset_state, 'initial_balance_for_sequence', initial_balance)
        for i in range(levels):
            current_seq_level = asset_state.current_sequence + i
            if current_seq_level > self.max_sequence: break
            amount = self._get_entry_amount(current_seq_level, initial_balance_for_seq)
            cumulative_loss -= amount
            potential_losses[f'level_{current_seq_level}'] = {'amount': amount, 'cumulative_loss': cumulative_loss}
        return potential_losses

    def format_risk_summary(self, asset_state: AssetState, current_balance: float, initial_balance: float) -> str:
        return f"Resumo de Risco para {asset_state.symbol}"

    def get_risk_level(self) -> str:
        if self.max_sequence <= 2: return "MÉDIO"
        elif self.max_sequence <= 4: return "ALTO"
        else: return "MUITO ALTO"
    
    def is_conservative(self) -> bool:
        return False
    
    def get_max_possible_loss_per_sequence(self, initial_balance: float) -> float:
        total_loss = 0.0
        for sequence in range(1, self.max_sequence + 1):
            total_loss += self._get_entry_amount(sequence, initial_balance)
        return total_loss
    
    def validate_config(self) -> bool:
        if not super().validate_config():
            return False
        return True
    
    def get_strategy_description(self) -> str:
        timing_desc = "imediato" if self.martingale_type == 'IMMEDIATE' else f"início da próxima vela (M{self.analysis_timeframe_minutes})"
        return f"Martingale {self.multiplier}x até S{self.max_sequence}, entrada {timing_desc}"