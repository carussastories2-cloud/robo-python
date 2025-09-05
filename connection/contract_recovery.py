# -*- coding: utf-8 -*-
"""
Contract Recovery - Sistema de Recuperação de Contratos
Sistema robusto para recuperar contratos perdidos durante desconexões
"""

import asyncio
import time
from typing import Dict, List, Optional, Callable, Set
from core.data_models import ContractInfo, ContractStatus
from utils.logger import get_logger

logger = get_logger(__name__)

class ContractRecovery:
    """Sistema de recuperação de contratos perdidos"""
    
    def __init__(self):
        # Cache de contratos monitorados
        self.monitored_contracts: Dict[str, ContractInfo] = {}
        self.lost_contracts: Set[str] = set()
        
        # Callbacks
        self.send_request_callback: Optional[Callable] = None
        self.contract_update_callback: Optional[Callable] = None
        
        # Configurações de recuperação
        self.max_recovery_attempts = 3
        self.recovery_timeout = 10.0
        self.retry_delay = 2.0
        
        # Estatísticas
        self.total_recoveries_attempted = 0
        self.successful_recoveries = 0
        self.failed_recoveries = 0
        self.contracts_forced_as_loss = 0
        
        # Estado antes da desconexão
        self.balance_before_disconnection = 0.0
        self.disconnection_time = 0.0
    
    def set_callbacks(self, 
                     send_request: Callable,
                     contract_update: Optional[Callable] = None):
        """
        Define callbacks necessários
        
        Args:
            send_request: Callback para enviar requisições
            contract_update: Callback para processar atualizações de contrato
        """
        self.send_request_callback = send_request
        self.contract_update_callback = contract_update
    
    def backup_state_before_disconnection(self, 
                                        active_contracts: Dict[str, List[ContractInfo]], 
                                        current_balance: float):
        """
        Faz backup do estado antes da desconexão
        
        Args:
            active_contracts: Contratos ativos por símbolo
            current_balance: Saldo atual
        """
        logger.info("💾 Fazendo backup do estado antes da desconexão...")
        
        self.balance_before_disconnection = current_balance
        self.disconnection_time = time.time()
        self.monitored_contracts.clear()
        
        # Adicionar todos os contratos ativos ao monitoramento
        total_contracts = 0
        for symbol, contracts in active_contracts.items():
            for contract in contracts:
                if not contract.is_finished:
                    self.monitored_contracts[contract.id] = contract
                    total_contracts += 1
        
        logger.info(f"💾 {total_contracts} contratos adicionados ao monitoramento")
        logger.info(f"💰 Saldo antes da desconexão: ${current_balance:.2f}")
    
    async def recover_lost_contracts(self) -> Dict[str, any]:
        """
        Recupera contratos perdidos durante desconexão
        
        Returns:
            Dict: Resultado da recuperação
        """
        if not self.monitored_contracts:
            logger.info("✅ Nenhum contrato para recuperar")
            return {
                'total_contracts': 0,
                'recovered': 0,
                'failed': 0,
                'total_profit': 0.0
            }
        
        logger.info(f"🔍 Iniciando recuperação de {len(self.monitored_contracts)} contratos...")
        
        recovered_count = 0
        failed_count = 0
        total_profit = 0.0
        
        # Processar cada contrato
        for contract_id, contract in self.monitored_contracts.items():
            logger.info(f"🔎 Verificando contrato: {contract_id} ({contract.type})")
            
            # Tentar recuperar o contrato
            recovery_result = await self._recover_single_contract(contract)
            
            if recovery_result['success']:
                recovered_count += 1
                total_profit += recovery_result['profit']
                
                # Callback de atualização se definido
                if self.contract_update_callback:
                    try:
                        await self.contract_update_callback(contract, recovery_result['data'])
                    except Exception as e:
                        logger.error(f"❌ Erro no callback de atualização: {e}")
            else:
                failed_count += 1
                
                # Forçar como perda para manter consistência
                original_amount = contract.amount
                contract.status = ContractStatus.FINISHED
                contract.profit = -original_amount
                total_profit -= original_amount
                
                self.contracts_forced_as_loss += 1
                logger.error(f"🚨 Contrato {contract_id} forçado como PERDA: ${-original_amount:.2f}")
        
        # Relatório final
        self._log_recovery_report(recovered_count, failed_count, total_profit)
        
        return {
            'total_contracts': len(self.monitored_contracts),
            'recovered': recovered_count,
            'failed': failed_count,
            'total_profit': total_profit,
            'recovery_time_seconds': time.time() - self.disconnection_time
        }
    
    async def _recover_single_contract(self, contract: ContractInfo) -> Dict[str, any]:
        """
        Tenta recuperar um único contrato
        
        Args:
            contract: Informações do contrato
            
        Returns:
            Dict: Resultado da recuperação
        """
        self.total_recoveries_attempted += 1
        
        for attempt in range(self.max_recovery_attempts):
            try:
                logger.debug(f"🔄 Tentativa {attempt + 1}/{self.max_recovery_attempts} para {contract.id}")
                
                # Enviar requisição de status do contrato
                if not self.send_request_callback:
                    logger.error("❌ Callback de requisição não definido")
                    break
                
                response = await self.send_request_callback(
                    {"proposal_open_contract": 1, "contract_id": contract.id},
                    timeout=self.recovery_timeout
                )
                
                if response and "proposal_open_contract" in response:
                    contract_data = response["proposal_open_contract"]
                    status = contract_data.get("status")
                    
                    logger.debug(f"📊 Contrato {contract.id}: Status = {status}")
                    
                    if status in ["sold", "won", "lost"]:
                        # Contrato finalizado - processar resultado
                        profit = self._calculate_contract_profit(contract, contract_data)
                        
                        # Atualizar contrato
                        contract.status = ContractStatus.WON if profit > 0 else ContractStatus.LOST
                        contract.profit = profit
                        contract.end_time = time.time()
                        
                        if hasattr(contract_data, 'payout'):
                            contract.payout = contract_data.get('payout', 0)
                        if hasattr(contract_data, 'sell_price'):
                            contract.sell_price = contract_data.get('sell_price', 0)
                        
                        result_emoji = "✅" if profit > 0 else "❌"
                        result_text = "GANHOU" if profit > 0 else "PERDEU"
                        
                        logger.info(f"{result_emoji} Contrato {contract.id} recuperado: {result_text} ${profit:+.2f}")
                        
                        self.successful_recoveries += 1
                        return {
                            'success': True,
                            'profit': profit,
                            'data': contract_data
                        }
                    
                    elif status == "open":
                        logger.info(f"⏳ Contrato {contract.id} ainda está ativo - aguardando...")
                        # Contrato ainda ativo, não é erro
                        return {
                            'success': True,
                            'profit': 0.0,
                            'data': contract_data,
                            'still_active': True
                        }
                    
                    else:
                        logger.warning(f"⚠️ Status desconhecido para {contract.id}: {status}")
                
                else:
                    logger.warning(f"⚠️ Resposta inválida para contrato {contract.id} (tentativa {attempt + 1})")
                
                # Aguardar antes da próxima tentativa
                if attempt < self.max_recovery_attempts - 1:
                    await asyncio.sleep(self.retry_delay)
            
            except Exception as e:
                logger.error(f"❌ Erro na tentativa {attempt + 1} para {contract.id}: {e}")
                
                if attempt < self.max_recovery_attempts - 1:
                    await asyncio.sleep(self.retry_delay)
        
        # Todas as tentativas falharam
        self.failed_recoveries += 1
        return {
            'success': False,
            'profit': 0.0,
            'data': None
        }
    
    def _calculate_contract_profit(self, contract: ContractInfo, contract_data: Dict) -> float:
        """
        Calcula lucro do contrato baseado nos dados recebidos
        
        Args:
            contract: Informações originais do contrato
            contract_data: Dados atualizados do contrato
            
        Returns:
            float: Lucro calculado
        """
        try:
            buy_price = float(contract_data.get("buy_price", contract.amount))
            
            if contract_data.get("status") == "won":
                payout = float(contract_data.get("payout", 0))
                return payout - buy_price
            else:
                return -buy_price
        
        except (ValueError, TypeError) as e:
            logger.error(f"❌ Erro calculando lucro: {e}")
            # Em caso de erro, assumir perda do valor original
            return -contract.amount
    
    def _log_recovery_report(self, recovered: int, failed: int, total_profit: float):
        """
        Log do relatório de recuperação
        
        Args:
            recovered: Contratos recuperados
            failed: Contratos falhados
            total_profit: Lucro total
        """
        logger.info("=" * 60)
        logger.info("📊 RELATÓRIO DE RECUPERAÇÃO DE CONTRATOS")
        logger.info("=" * 60)
        logger.info(f"✅ Contratos recuperados: {recovered}")
        logger.info(f"❌ Falhas na recuperação: {failed}")
        logger.info(f"🚨 Contratos forçados como perda: {self.contracts_forced_as_loss}")
        logger.info(f"💰 Lucro total recuperado: ${total_profit:+.2f}")
        
        if self.balance_before_disconnection > 0:
            expected_balance = self.balance_before_disconnection + total_profit
            logger.info(f"💰 Saldo antes da desconexão: ${self.balance_before_disconnection:.2f}")
            logger.info(f"🎯 Saldo esperado após recuperação: ${expected_balance:.2f}")
        
        recovery_time = time.time() - self.disconnection_time
        logger.info(f"⏱️ Tempo de recuperação: {recovery_time:.1f}s")
        logger.info("=" * 60)
    
    async def verify_contract_status(self, contract_id: str) -> Optional[Dict]:
        """
        Verifica status de um contrato específico
        
        Args:
            contract_id: ID do contrato
            
        Returns:
            Dict: Dados do contrato ou None se erro
        """
        if not self.send_request_callback:
            return None
        
        try:
            response = await self.send_request_callback(
                {"proposal_open_contract": 1, "contract_id": contract_id},
                timeout=self.recovery_timeout
            )
            
            if response and "proposal_open_contract" in response:
                return response["proposal_open_contract"]
        
        except Exception as e:
            logger.error(f"❌ Erro verificando contrato {contract_id}: {e}")
        
        return None
    
    def add_contract_to_monitor(self, contract: ContractInfo):
        """
        Adiciona contrato ao monitoramento
        
        Args:
            contract: Contrato para monitorar
        """
        if not contract.is_finished:
            self.monitored_contracts[contract.id] = contract
            logger.debug(f"👁️ Contrato {contract.id} adicionado ao monitoramento")
    
    def remove_contract_from_monitor(self, contract_id: str):
        """
        Remove contrato do monitoramento
        
        Args:
            contract_id: ID do contrato
        """
        if contract_id in self.monitored_contracts:
            del self.monitored_contracts[contract_id]
            logger.debug(f"👁️ Contrato {contract_id} removido do monitoramento")
    
    def get_monitored_contracts_count(self) -> int:
        """
        Retorna quantidade de contratos monitorados
        
        Returns:
            int: Quantidade de contratos
        """
        return len(self.monitored_contracts)
    
    def get_recovery_stats(self) -> Dict[str, any]:
        """
        Retorna estatísticas de recuperação
        
        Returns:
            Dict: Estatísticas
        """
        success_rate = 0.0
        if self.total_recoveries_attempted > 0:
            success_rate = (self.successful_recoveries / self.total_recoveries_attempted) * 100
        
        return {
            'total_attempts': self.total_recoveries_attempted,
            'successful_recoveries': self.successful_recoveries,
            'failed_recoveries': self.failed_recoveries,
            'success_rate_percentage': round(success_rate, 1),
            'contracts_forced_as_loss': self.contracts_forced_as_loss,
            'currently_monitored': len(self.monitored_contracts),
            'last_disconnection_time': self.disconnection_time,
            'balance_before_disconnection': self.balance_before_disconnection
        }
    
    def reset_stats(self):
        """Reseta estatísticas de recuperação"""
        self.total_recoveries_attempted = 0
        self.successful_recoveries = 0
        self.failed_recoveries = 0
        self.contracts_forced_as_loss = 0
        logger.info("🔄 Estatísticas de recuperação resetadas")
    
    def clear_monitored_contracts(self):
        """Limpa todos os contratos monitorados"""
        count = len(self.monitored_contracts)
        self.monitored_contracts.clear()
        self.lost_contracts.clear()
        logger.info(f"🧹 {count} contratos removidos do monitoramento")