#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Result Analyzer - Analisador de Resultados
Analisa resultados de operações single e dual entry
"""

import time
from typing import List, Dict, Any, Optional, Tuple
from core.data_models import AssetState, ContractInfo, ContractStatus, SessionStats
from utils.logger import get_logger

logger = get_logger(__name__)

class ResultAnalyzer:
    """Analisador de resultados de operações"""
    
    def __init__(self, config):
        """
        Inicializa analisador de resultados
        
        Args:
            config: Configurações do sistema
        """
        self.config = config
        self.dual_entry = config.DUAL_ENTRY
        
        # Timeouts para verificação
        self.verification_timeout = config.VERIFICATION_TIMEOUT
        self.max_verification_attempts = config.MAX_VERIFICATION_ATTEMPTS
        
        # Callback para verificar contratos
        self.verify_contract_callback: Optional[callable] = None
        
        logger.info(f"📊 Analisador de resultados configurado")
        logger.info(f"   🔄 Dual Entry: {'✅ Ativo' if self.dual_entry else '❌ Inativo'}")
        logger.info(f"   ⏰ Timeout verificação: {self.verification_timeout}s")
    
    def set_verify_callback(self, callback: callable):
        """
        Define callback para verificar contratos
        
        Args:
            callback: Função para verificar status de contrato
        """
        self.verify_contract_callback = callback
    
    def analyze_single_operation_result(self, asset_state: AssetState) -> Dict[str, Any]:
        """
        Analisa resultado de operação single entry
        
        Args:
            asset_state: Estado do ativo
            
        Returns:
            Dict: Resultado da análise
        """
        if not asset_state.active_contracts:
            return {'status': 'no_contracts', 'action': 'error'}
        
        # Verificar se todos os contratos estão finalizados
        if not all(contract.is_finished for contract in asset_state.active_contracts):
            return {'status': 'pending', 'action': 'wait'}
        
        # Calcular resultado
        total_profit = sum(contract.profit for contract in asset_state.active_contracts)
        operation_won = total_profit > 0
        
        # Calcular resultado final da sequência
        sequence_result = total_profit + asset_state.loss_accumulator
        
        # Log do resultado
        result_emoji = "✅" if operation_won else "❌"
        result_text = "VITÓRIA" if operation_won else "DERROTA"
        
        logger.info(f"{result_emoji} {asset_state.symbol} SINGLE S{asset_state.current_sequence}: {result_text}")
        logger.info(f"   💰 Lucro operação: ${total_profit:+.2f}")
        
        if asset_state.loss_accumulator != 0:
            logger.info(f"   📊 Resultado sequência: ${sequence_result:+.2f}")
            logger.info(f"   💸 (Perdas anteriores: ${asset_state.loss_accumulator:+.2f})")
        
        # Determinar próxima ação
        if operation_won:
            action = 'reset_sequence'  # Vitória -> resetar
        else:
            # Derrota -> verificar se continua martingale
            if asset_state.current_sequence < self._get_max_sequence():
                action = 'continue_martingale'
            else:
                action = 'max_sequence_reached'
        
        return {
            'status': 'completed',
            'action': action,
            'operation_won': operation_won,
            'operation_profit': total_profit,
            'sequence_result': sequence_result,
            'current_sequence': asset_state.current_sequence
        }
    
    def analyze_dual_operation_result(self, asset_state: AssetState) -> Dict[str, Any]:
        """
        Analisa resultado de operação dual entry
        
        Args:
            asset_state: Estado do ativo
            
        Returns:
            Dict: Resultado da análise
        """
        if not asset_state.active_contracts:
            return {'status': 'no_contracts', 'action': 'error'}
        
        if not all(contract.is_finished for contract in asset_state.active_contracts):
            return {'status': 'pending', 'action': 'wait'}
        
        call_contracts = [c for c in asset_state.active_contracts if c.type == "CALL"]
        put_contracts = [c for c in asset_state.active_contracts if c.type == "PUT"]
        
        call_profit = sum(c.profit for c in call_contracts)
        put_profit = sum(c.profit for c in put_contracts)
        total_profit = call_profit + put_profit
        
        call_won = call_profit > 0
        put_won = put_profit > 0
        operation_won = call_won or put_won
        
        sequence_result = total_profit + asset_state.loss_accumulator
        
        call_status = "WIN" if call_won else "LOSS"
        put_status = "WIN" if put_won else "LOSS"
        
        call_display = f"CALL={call_status}(${call_profit:+.2f})" if call_contracts else "CALL=NONE($0.00)"
        put_display = f"PUT={put_status}(${put_profit:+.2f})" if put_contracts else "PUT=NONE($0.00)"
        
        logger.info(f"📊 {asset_state.symbol} DUAL S{asset_state.current_sequence} RESULT:")
        logger.info(f"   {call_display} | {put_display}")
        logger.info(f"   💰 Total: ${total_profit:+.2f}")
        
        if asset_state.loss_accumulator != 0:
            logger.info(f"   📊 Resultado sequência: ${sequence_result:+.2f}")
            logger.info(f"   💸 (Perdas anteriores: ${asset_state.loss_accumulator:+.2f})")
        
        if operation_won:
            if call_won and put_won:
                logger.info(f"🎉 {asset_state.symbol}: DUAL VITÓRIA COMPLETA! Ambos ganharam")
            elif call_won:
                logger.info(f"🎉 {asset_state.symbol}: DUAL VITÓRIA via CALL!")
            else:
                logger.info(f"🎉 {asset_state.symbol}: DUAL VITÓRIA via PUT!")
            
            action = 'reset_sequence'
        else:
            logger.info(f"❌ {asset_state.symbol}: DUAL DERROTA - Ambos perderam")
            
            if asset_state.current_sequence < self._get_max_sequence():
                action = 'continue_martingale'
            else:
                action = 'max_sequence_reached'
        
        return {
            'status': 'completed', 'action': action, 'operation_won': operation_won,
            'operation_profit': total_profit, 'sequence_result': sequence_result,
            'current_sequence': asset_state.current_sequence, 'call_won': call_won, 'put_won': put_won,
            'call_profit': call_profit, 'put_profit': put_profit,
            'contracts_executed': len(asset_state.active_contracts)
        }
    
    async def verify_pending_contracts(self, asset_state: AssetState) -> bool:
        if not self.verify_contract_callback:
            logger.warning("⚠️ Callback de verificação não definido")
            return False
        
        verified_count, failed_count = 0, 0
        
        for contract in asset_state.active_contracts:
            if contract.is_finished: continue
            
            logger.debug(f"🔍 Verificando contrato {contract.id} ({contract.type})")
            
            if await self._verify_single_contract(contract):
                verified_count += 1
            else:
                failed_count += 1
                contract.status = ContractStatus.FINISHED
                contract.profit = -contract.amount
                contract.end_time = time.time()
                logger.error(f"🚨 Contrato {contract.id} forçado como PERDA: ${-contract.amount:.2f}")
        
        if verified_count + failed_count > 0:
            logger.info(f"📊 Verificação: {verified_count} recuperados, {failed_count} forçados como perda")
        
        return failed_count == 0
    
    async def _verify_single_contract(self, contract: ContractInfo) -> bool:
        for attempt in range(self.max_verification_attempts):
            try:
                logger.debug(f"🔄 Verificando {contract.id} (tentativa {attempt + 1}/{self.max_verification_attempts})")
                
                contract_data = await self.verify_contract_callback(contract.id)
                
                if contract_data:
                    status = contract_data.get("status")
                    if status in ["sold", "won", "lost"]:
                        self._process_contract_result(contract, contract_data)
                        return True
                    elif status == "open":
                        logger.debug(f"⏳ Contrato {contract.id} ainda ativo")
                        return True
                    else:
                        logger.warning(f"⚠️ Status desconhecido: {status}")
                
                if attempt < self.max_verification_attempts - 1:
                    await asyncio.sleep(2.0)
            
            except Exception as e:
                logger.error(f"❌ Erro verificando contrato {contract.id}: {e}")
                if attempt < self.max_verification_attempts - 1:
                    await asyncio.sleep(2.0)
        
        return False
    
    def _process_contract_result(self, contract: ContractInfo, contract_data: Dict[str, Any]):
        status = contract_data.get("status")
        buy_price = float(contract_data.get("buy_price", contract.amount))
        
        if status == "won":
            payout = float(contract_data.get("payout", 0))
            profit, contract.status = payout - buy_price, ContractStatus.WON
        else:
            profit, contract.status = -buy_price, ContractStatus.LOST
        
        contract.profit, contract.end_time = profit, time.time()
        contract.payout = contract_data.get("payout", 0)
        contract.sell_price = contract_data.get("sell_price", 0)
        contract.buy_price = buy_price
        
        logger.debug(f"{'✅' if profit > 0 else '❌'} Contrato {contract.id} ({contract.type}): {'GANHOU' if profit > 0 else 'PERDEU'} ${profit:+.2f}")
    
    def _get_max_sequence(self) -> int:
        if self.config.RISK_MANAGEMENT_TYPE == "FIXED_AMOUNT":
            return 1
        else:
            return getattr(self.config, 'MARTINGALE_MAX_SEQUENCE', 2)