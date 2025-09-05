#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Position Manager - Gerenciador de Posições
Gerencia contratos ativos e aguarda resultados
"""

import asyncio
import time
from typing import Dict, List, Optional, Callable
from core.data_models import AssetState, ContractInfo, ContractStatus
from utils.logger import get_logger

logger = get_logger(__name__)

class PositionManager:
    """Gerenciador de posições e contratos ativos"""
    
    def __init__(self, config):
        """
        Inicializa gerenciador de posições
        
        Args:
            config: Configurações do sistema
        """
        self.config = config
        
        self.duration = config.DURATION
        self.duration_unit = config.DURATION_UNIT
        self.is_tick_mode = (self.duration_unit == "t")
        
        self.max_verification_attempts = config.MAX_VERIFICATION_ATTEMPTS
        self.verification_timeout = config.VERIFICATION_TIMEOUT
        
        self.send_request_callback: Optional[Callable] = None
        
        logger.info(f"📊 Position Manager inicializado:")
        logger.info(f"   ⏰ Duração: {self.duration}{self.duration_unit}")
        logger.info(f"   🔍 Verificações: {self.max_verification_attempts} tentativas")
        logger.info(f"   ⏱️ Timeout: {self.verification_timeout}s")
    
    def set_callbacks(self, send_request: Callable):
        """
        Define callback para enviar requisições
        """
        self.send_request_callback = send_request
    
    async def wait_for_results(self, asset_state: AssetState) -> bool:
        """
        Aguarda resultados dos contratos ativos com um loop de verificação simples e eficiente.
        """
        if not asset_state.active_contracts:
            return True

        expected_duration = self._calculate_expected_duration()
        
        # <<< MELHORIA FINAL AQUI >>>
        # Define uma janela de tempo total para esperar (expiração + 8s de tolerância para a API)
        total_wait_time = expected_duration + 8.0
        start_time = time.time()
        
        logger.info(f"⏳ {asset_state.symbol}: Aguardando resultado da operação de {expected_duration:.1f}s...")
        
        # Loop de verificação simples
        while time.time() - start_time < total_wait_time:
            # Se a notificação do resultado chegar via websocket, todos os contratos estarão finalizados
            if all(c.is_finished for c in asset_state.active_contracts):
                elapsed = time.time() - start_time
                logger.info(f"✅ {asset_state.symbol}: Resultado recebido em {elapsed:.1f}s")
                return True
            
            # Pausa curta antes de verificar novamente
            await asyncio.sleep(0.5)

        # Se o loop terminar (timeout), força uma verificação final para garantir que não perdemos o resultado
        logger.warning(f"⚠️ {asset_state.symbol}: Timeout na espera passiva. Forçando verificação final...")
        return await self._force_verify_all_contracts(asset_state)

    def _calculate_expected_duration(self) -> float:
        """
        Calcula duração esperada baseada na configuração
        """
        if self.duration_unit == "t":
            # Ticks: aproximadamente 2-3 segundos por tick
            return self.duration * 2.5
        elif self.duration_unit == "s":
            return self.duration
        elif self.duration_unit == "m":
            return self.duration * 60
        else:
            return self.duration
    
    async def _force_verify_all_contracts(self, asset_state: AssetState) -> bool:
        """
        Força verificação de todos os contratos que ainda não finalizaram.
        """
        all_verified = True
        
        tasks = []
        for contract in asset_state.active_contracts:
            if not contract.is_finished:
                tasks.append(self._verify_single_contract(contract, asset_state.symbol))
        
        if not tasks:
            return True

        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            if isinstance(result, Exception) or not result:
                pending_contracts = [c for c in asset_state.active_contracts if not c.is_finished]
                if i < len(pending_contracts):
                    failed_contract = pending_contracts[i]
                    logger.error(f"❌ Falha final na verificação de {failed_contract.id}")
                    self._force_contract_as_loss(failed_contract)
                    all_verified = False

        return all_verified
    
    async def _verify_single_contract(self, contract: ContractInfo, symbol: str) -> bool:
        """
        Verifica um único contrato (uma única tentativa, sem loop interno)
        """
        if not self.send_request_callback:
            return False
        
        try:
            response = await self.send_request_callback(
                {"proposal_open_contract": 1, "contract_id": contract.id},
                timeout=self.verification_timeout
            )
            
            if response and "proposal_open_contract" in response:
                contract_data = response["proposal_open_contract"]
                status = contract_data.get("status")
                
                if status in ["sold", "won", "lost"]:
                    self._process_contract_result(contract, contract_data, symbol)
                    return True
                
        except Exception as e:
            logger.error(f"❌ Erro na tentativa de verificação para {contract.id}: {e}")
            return False
        
        return False
    
    def _process_contract_result(self, contract: ContractInfo, contract_data: Dict, symbol: str):
        if contract.is_finished:
            return
        
        status = contract_data.get("status")
        buy_price = float(contract_data.get("buy_price", contract.amount))
        
        if status == "won":
            payout = float(contract_data.get("payout", 0))
            profit, contract.status = payout - buy_price, ContractStatus.WON
        else:
            profit, contract.status = -buy_price, ContractStatus.LOST
        
        contract.profit, contract.end_time = profit, time.time()
        contract.payout, contract.sell_price = contract_data.get("payout", 0), contract_data.get("sell_price", 0)
        contract.buy_price = buy_price
    
    def _force_contract_as_loss(self, contract: ContractInfo):
        if contract.is_finished:
            return
        
        contract.status = ContractStatus.FINISHED
        contract.profit = -contract.amount
        contract.end_time = time.time()
        
        logger.error(f"🚨 Contrato {contract.id} forçado como PERDA: ${-contract.amount:.2f}")

    def get_active_contracts_summary(self, asset_states: Dict[str, AssetState]) -> Dict[str, any]:
        total_active, total_value, active_by_symbol = 0, 0.0, {}
        for symbol, asset_state in asset_states.items():
            active_contracts = [c for c in asset_state.active_contracts if not c.is_finished]
            if active_contracts:
                contract_value = sum(c.amount for c in active_contracts)
                active_by_symbol[symbol] = {
                    'count': len(active_contracts), 'value': contract_value,
                    'contracts': [{'id': c.id, 'type': c.type, 'amount': c.amount, 'duration': time.time() - c.start_time} for c in active_contracts]
                }
                total_active += len(active_contracts)
                total_value += contract_value
        return {'total_active_contracts': total_active, 'total_active_value': total_value, 'active_by_symbol': active_by_symbol}
    
    def has_active_contracts(self, asset_states: Dict[str, AssetState]) -> bool:
        return any(asset_state.has_active_contracts for asset_state in asset_states.values())
    
    def has_active_tick_operations(self, asset_states: Dict[str, AssetState]) -> bool:
        if not self.is_tick_mode: return False
        return self.has_active_contracts(asset_states)

    def cleanup_finished_contracts(self, asset_states: Dict[str, AssetState]):
        total_cleaned = 0
        for asset_state in asset_states.values():
            before_count = len(asset_state.active_contracts)
            asset_state.clear_finished_contracts()
            total_cleaned += (before_count - len(asset_state.active_contracts))
        if total_cleaned > 0:
            logger.debug(f"🧹 {total_cleaned} contratos finalizados removidos")

    def get_position_summary(self, asset_state: AssetState) -> str:
        active_contracts = [c for c in asset_state.active_contracts if not c.is_finished]
        if not active_contracts: return f"📊 {asset_state.symbol}: Sem posições ativas"
        
        total_value = sum(c.amount for c in active_contracts)
        contract_types = [c.type for c in active_contracts]
        oldest_contract = min(active_contracts, key=lambda c: c.start_time)
        duration = time.time() - oldest_contract.start_time
        
        summary = f"📊 {asset_state.symbol}: {len(active_contracts)} posições ativas\n"
        summary += f"   💰 Valor total: ${total_value:.2f}\n"
        summary += f"   🎯 Tipos: {', '.join(contract_types)}\n"
        summary += f"   ⏱️ Mais antiga: {duration:.0f}s"
        return summary
    
    def estimate_time_to_results(self, asset_state: AssetState) -> float:
        if not asset_state.active_contracts: return 0.0
        oldest_contract = min(asset_state.active_contracts, key=lambda c: c.start_time)
        elapsed = time.time() - oldest_contract.start_time
        expected_duration = self._calculate_expected_duration()
        return max(0, expected_duration - elapsed)