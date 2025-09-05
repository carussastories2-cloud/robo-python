#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Operation Executor - Executor de Operações
Responsável por executar operações de trading na Deriv
"""

import asyncio
import time
from typing import Optional, Dict, Any, Callable
from core.data_models import AssetState, ContractInfo, ContractStatus, SignalData
from utils.logger import get_logger

logger = get_logger(__name__)

class OperationExecutor:
    """Executor de operações de trading"""
    
    def __init__(self, config):
        """
        Inicializa executor de operações
        
        Args:
            config: Configurações do sistema
        """
        self.config = config
        
        # Configurações de operação
        self.duration = config.DURATION
        self.duration_unit = config.DURATION_UNIT
        self.dual_entry = config.DUAL_ENTRY
        self.delay_between_ops = config.DELAY_BETWEEN_OPS
        
        # Timeouts otimizados
        self.is_tick_mode = (self.duration_unit == "t")
        if self.is_tick_mode:
            self.proposal_timeout = 8.0
            self.buy_timeout = 8.0
            logger.info("⚡ Modo TICK detectado - timeouts otimizados")
        else:
            self.proposal_timeout = 15.0
            self.buy_timeout = 15.0
        
        # Callbacks para comunicação
        self.send_request_callback: Optional[Callable] = None
        self.subscribe_contract_callback: Optional[Callable] = None
        
        # Estatísticas
        self.total_proposals_sent = 0
        self.successful_proposals = 0
        self.total_buys_sent = 0
        self.successful_buys = 0
        
        logger.info(f"🎯 Executor configurado:")
        logger.info(f"   ⏰ Expiração: {self.duration}{self.duration_unit}")
        logger.info(f"   🔄 Dual Entry: {'✅ Ativo' if self.dual_entry else '❌ Inativo'}")
        logger.info(f"   ⚡ Timeouts: Proposta={self.proposal_timeout}s | Compra={self.buy_timeout}s")
    
    def set_callbacks(self, 
                      send_request: Callable,
                      subscribe_contract: Optional[Callable] = None):
        self.send_request_callback = send_request
        self.subscribe_contract_callback = subscribe_contract
    
    async def execute_single_operation(self, 
                                       asset_state: AssetState, 
                                       signal: SignalData, 
                                       amount: float) -> bool:
        """
        Executa operação single entry
        """
        if not self._validate_execution_conditions(asset_state, amount):
            return False
        
        asset_state.active_contracts.clear()
        operation_start = time.time()
        
        logger.info(f"🎯 {signal.symbol} SINGLE S{asset_state.current_sequence}: {signal.direction.value} ${amount:.2f}")
        
        contract = await self._execute_contract(signal.symbol, signal.direction.value, amount)
        
        if contract:
            asset_state.active_contracts.append(contract)
            execution_time = time.time() - operation_start
            logger.info(f"🚀 {signal.symbol}: Operação executada em {execution_time:.2f}s")
            return True
        else:
            # Não é mais necessário logar aqui, o _execute_contract já o faz.
            return False
    
    async def execute_dual_operation(self, 
                                     asset_state: AssetState, 
                                     signal: SignalData, 
                                     amount: float) -> bool:
        """
        Executa operação dual entry (CALL + PUT)
        """
        total_needed = amount * 2
        
        if not self._validate_execution_conditions(asset_state, total_needed):
            return False
        
        asset_state.active_contracts.clear()
        operation_start = time.time()
        
        logger.info(f"🎯 {signal.symbol} DUAL S{asset_state.current_sequence}: CALL(${amount:.2f}) + PUT(${amount:.2f}) = ${total_needed:.2f}")
        
        call_contract = await self._execute_contract(signal.symbol, "CALL", amount)
        
        delay = min(self.delay_between_ops, 0.02) if self.is_tick_mode else self.delay_between_ops
        if delay > 0:
            await asyncio.sleep(delay)
        
        put_contract = await self._execute_contract(signal.symbol, "PUT", amount)
        
        success_count = 0
        if call_contract:
            asset_state.active_contracts.append(call_contract)
            success_count += 1
        if put_contract:
            asset_state.active_contracts.append(put_contract)
            success_count += 1
        
        execution_time = time.time() - operation_start
        
        if success_count >= 1:
            mode_desc = "DUAL TICK" if self.is_tick_mode else "DUAL"
            logger.info(f"🚀 {signal.symbol}: {mode_desc} ({success_count}/2) executado em {execution_time:.2f}s")
            return True
        else:
            return False
    
    async def _execute_contract(self, symbol: str, direction: str, amount: float) -> Optional[ContractInfo]:
        """
        Executa um contrato individual
        """
        if not self.send_request_callback:
            logger.error("❌ Callback de requisição não definido. Não é possível executar o contrato.")
            return None
        
        try:
            proposal_response = await self._get_proposal(symbol, direction, amount)
            if not proposal_response:
                return None
            
            contract_info = await self._buy_contract(proposal_response, symbol, direction, amount)
            if not contract_info:
                return None
            
            if self.subscribe_contract_callback:
                await self.subscribe_contract_callback(contract_info.id)
            
            return contract_info
            
        except Exception as e:
            logger.error(f"❌ Erro crítico executando contrato {symbol} {direction}: {e}")
            return None
    
    async def _get_proposal(self, symbol: str, direction: str, amount: float) -> Optional[Dict[str, Any]]:
        """
        Obtém proposta de contrato
        """
        self.total_proposals_sent += 1
        proposal_request = {
            "proposal": 1, "amount": amount, "basis": "stake",
            "contract_type": direction.upper(), "currency": "USD", "duration": self.duration,
            "duration_unit": self.duration_unit, "symbol": symbol
        }
        logger.debug(f"📤 Solicitando proposta: {symbol} {direction} ${amount:.2f}")
        
        response = await self.send_request_callback(proposal_request, timeout=self.proposal_timeout)
            
        if not response:
            logger.error(f"❌ {symbol} {direction}: Sem resposta da proposta (timeout ou conexão)")
            return None
        
        if "error" in response:
            error_msg = response["error"].get("message", "Erro desconhecido")
            logger.error(f"❌ {symbol} {direction}: Erro na proposta: {error_msg}")
            return None
        
        if "proposal" not in response:
            logger.error(f"❌ {symbol} {direction}: Resposta de proposta inválida")
            return None
        
        self.successful_proposals += 1
        logger.debug(f"✅ Proposta obtida: {symbol} {direction}")
        return response
            
    async def _buy_contract(self, 
                          proposal_response: Dict[str, Any], 
                          symbol: str, 
                          direction: str, 
                          amount: float) -> Optional[ContractInfo]:
        """
        Compra contrato baseado na proposta
        """
        self.total_buys_sent += 1
        proposal_id = proposal_response["proposal"]["id"]
        buy_request = {"buy": proposal_id, "price": amount}
        logger.debug(f"💰 Comprando contrato: {symbol} {direction}")
        
        response = await self.send_request_callback(buy_request, timeout=self.buy_timeout)
        
        if not response:
            logger.error(f"❌ {symbol} {direction}: Sem resposta da compra (timeout ou conexão)")
            return None
        
        if "error" in response:
            error_msg = response["error"].get("message", "Erro desconhecido")
            logger.error(f"❌ {symbol} {direction}: Erro na compra: {error_msg}")
            return None
        
        if "buy" not in response:
            logger.error(f"❌ {symbol} {direction}: Resposta de compra inválida")
            return None
        
        buy_data = response["buy"]
        contract_info = ContractInfo(
            id=buy_data["contract_id"], symbol=symbol, type=direction,
            amount=amount, status=ContractStatus.OPEN, start_time=time.time(),
            buy_price=amount
        )
        
        self.successful_buys += 1
        logger.info(f"✅ {symbol} {direction}: ${amount:.2f} | ID: {contract_info.id}")
        return contract_info
    
    def _validate_execution_conditions(self, asset_state: AssetState, required_amount: float) -> bool:
        """
        Valida condições para execução
        """
        if asset_state.has_active_contracts:
            logger.warning(f"⚠️ {asset_state.symbol}: Já há contratos ativos")
            return False
        
        if required_amount <= 0:
            logger.error(f"❌ {asset_state.symbol}: Valor inválido: ${required_amount:.2f}")
            return False
        
        if asset_state.in_cooldown:
            remaining = asset_state.cooldown_end_time - time.time()
            logger.debug(f"🧊 {asset_state.symbol}: Em cooldown por {remaining:.0f}s")
            return False
        
        return True
    def get_execution_stats(self) -> Dict[str, Any]:
        """
        Retorna estatísticas de execução
        
        Returns:
            Dict: Estatísticas
        """
        proposal_success_rate = 0.0
        if self.total_proposals_sent > 0:
            proposal_success_rate = (self.successful_proposals / self.total_proposals_sent) * 100
        
        buy_success_rate = 0.0
        if self.total_buys_sent > 0:
            buy_success_rate = (self.successful_buys / self.total_buys_sent) * 100
        
        return {
            'total_proposals_sent': self.total_proposals_sent,
            'successful_proposals': self.successful_proposals,
            'proposal_success_rate': round(proposal_success_rate, 1),
            'total_buys_sent': self.total_buys_sent,
            'successful_buys': self.successful_buys,
            'buy_success_rate': round(buy_success_rate, 1),
            'is_tick_mode': self.is_tick_mode,
            'dual_entry_enabled': self.dual_entry
        }
    
    def reset_stats(self):
        """Reseta estatísticas de execução"""
        self.total_proposals_sent = 0
        self.successful_proposals = 0
        self.total_buys_sent = 0
        self.successful_buys = 0
        logger.info("🔄 Estatísticas de execução resetadas")
    
    def get_operation_summary(self, asset_state: AssetState) -> str:
        """
        Retorna resumo das operações do ativo
        
        Args:
            asset_state: Estado do ativo
            
        Returns:
            str: Resumo formatado
        """
        active_count = asset_state.active_contracts_count
        
        summary = f"📊 {asset_state.symbol} - OPERAÇÕES\n"
        summary += f"   🎯 Contratos ativos: {active_count}\n"
        summary += f"   📈 Total operações: {asset_state.total_operations}\n"
        summary += f"   ✅ Vitórias: {asset_state.won_operations} ({asset_state.win_rate:.1f}%)\n"
        summary += f"   💰 Lucro total: ${asset_state.total_profit:+.2f}\n"
        summary += f"   🎲 Melhor sequência: S{asset_state.best_sequence}"
        
        return summary
    
    def estimate_operation_duration_seconds(self) -> float:
        """
        Estima duração da operação em segundos
        
        Returns:
            float: Duração estimada em segundos
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
    
    def is_high_frequency_mode(self) -> bool:
        """
        Verifica se está em modo de alta frequência
        
        Returns:
            bool: True se operações rápidas
        """
        estimated_duration = self.estimate_operation_duration_seconds()
        return estimated_duration <= 60  # Operações de até 1 minuto = alta frequência
    
    def get_recommended_delay_between_signals(self) -> float:
        """
        Retorna delay recomendado entre sinais
        
        Returns:
            float: Delay em segundos
        """
        if self.is_tick_mode:
            return 5.0  # 5 segundos para ticks
        elif self.is_high_frequency_mode():
            return 10.0  # 10 segundos para operações rápidas
        else:
            return 30.0  # 30 segundos para operações normais
    
    def validate_operation_params(self, symbol: str, direction: str, amount: float) -> bool:
        """
        Valida parâmetros da operação
        
        Args:
            symbol: Símbolo do ativo
            direction: Direção (CALL ou PUT)
            amount: Valor da operação
            
        Returns:
            bool: True se parâmetros válidos
        """
        # Validar símbolo
        if not symbol or len(symbol) < 3:
            logger.error(f"❌ Símbolo inválido: {symbol}")
            return False
        
        # Validar direção
        if direction not in ["CALL", "PUT"]:
            logger.error(f"❌ Direção inválida: {direction}")
            return False
        
        # Validar valor
        if amount <= 0:
            logger.error(f"❌ Valor inválido: ${amount:.2f}")
            return False
        
        if amount < self.config.MIN_AMOUNT:
            logger.error(f"❌ Valor abaixo do mínimo: ${amount:.2f} < ${self.config.MIN_AMOUNT:.2f}")
            return False
        
        if amount > self.config.MAX_AMOUNT:
            logger.error(f"❌ Valor acima do máximo: ${amount:.2f} > ${self.config.MAX_AMOUNT:.2f}")
            return False
        
        return True