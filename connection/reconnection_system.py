# -*- coding: utf-8 -*-
"""
Reconnection System - Sistema de Reconexão Contextual com Modo Persistente
Sistema inteligente de reconexão que NUNCA desiste completamente
"""

import asyncio
import time
from typing import Optional, Callable, List
from enum import Enum
from utils.logger import get_logger

logger = get_logger(__name__)

class ReconnectionContext(Enum):
    """Contextos de reconexão baseados em operações ativas"""
    EMERGENCY_TICKS = "emergency_ticks"        # Operações em ticks ativas - ultra crítico
    PRIORITY_CONTRACTS = "priority_contracts"  # Contratos normais ativos - crítico
    NORMAL_IDLE = "normal_idle"               # Sem operações ativas - normal

class ReconnectionStrategy:
    """Estratégia de reconexão baseada no contexto"""
    
    def __init__(self, context: ReconnectionContext):
        self.context = context
        self.delays = self._get_delays_for_context()
        self.max_attempts = self._get_max_attempts_for_context()
        self.description = self._get_description()
        # NOVO: Delays para modo persistente (após esgotar tentativas iniciais)
        self.persistent_delays = self._get_persistent_delays()
    
    def _get_delays_for_context(self) -> List[float]:
        """Retorna delays de reconexão baseados no contexto"""
        if self.context == ReconnectionContext.EMERGENCY_TICKS:
            # Ultra agressivo para operações em ticks
            return [0.5, 1.0, 2.0, 3.0, 5.0, 8.0, 10.0]
        elif self.context == ReconnectionContext.PRIORITY_CONTRACTS:
            # Agressivo para contratos normais
            return [2.0, 4.0, 6.0, 10.0, 15.0, 20.0, 30.0]
        else:  # NORMAL_IDLE
            # Conservador quando idle
            return [10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0]
    
    def _get_max_attempts_for_context(self) -> int:
        """Retorna máximo de tentativas iniciais baseado no contexto"""
        if self.context == ReconnectionContext.EMERGENCY_TICKS:
            return 10  # Mais tentativas para emergência
        elif self.context == ReconnectionContext.PRIORITY_CONTRACTS:
            return 7   # Tentativas normais
        else:  # NORMAL_IDLE
            return 5   # Menos tentativas quando idle
    
    def _get_persistent_delays(self) -> List[float]:
        """Retorna delays para modo persistente (após tentativas iniciais)"""
        if self.context == ReconnectionContext.EMERGENCY_TICKS:
            return [10.0, 10.0, 10.0]  # 30s, 1m, 2m
        elif self.context == ReconnectionContext.PRIORITY_CONTRACTS:
            return [10.0, 10.0, 10.0]  # 1m, 2m, 5m
        else:  # NORMAL_IDLE
            return [10.0, 10.0, 10.0]  # 2m, 5m, 10m
    
    def _get_description(self) -> str:
        """Retorna descrição da estratégia"""
        descriptions = {
            ReconnectionContext.EMERGENCY_TICKS: "🚨 EMERGÊNCIA TICKS - Reconexão ultra agressiva",
            ReconnectionContext.PRIORITY_CONTRACTS: "⚡ PRIORITÁRIO - Reconexão agressiva",
            ReconnectionContext.NORMAL_IDLE: "😌 NORMAL - Reconexão conservadora"
        }
        return descriptions[self.context]
    
    def get_delay(self, attempt: int) -> float:
        """
        Retorna delay para tentativa específica
        
        Args:
            attempt: Número da tentativa (1-based)
            
        Returns:
            float: Delay em segundos
        """
        index = min(attempt - 1, len(self.delays) - 1)
        return self.delays[index]
    
    def get_persistent_delay(self, cycle: int) -> float:
        """
        Retorna delay para modo persistente
        
        Args:
            cycle: Número do ciclo persistente (1-based)
            
        Returns:
            float: Delay em segundos
        """
        index = min(cycle - 1, len(self.persistent_delays) - 1)
        return self.persistent_delays[index]

class ReconnectionSystem:
    """Sistema de reconexão contextual inteligente com modo persistente"""
    
    def __init__(self):
        self.attempt_count = 0
        self.persistent_cycle = 0
        self.current_strategy: Optional[ReconnectionStrategy] = None
        self.is_reconnecting = False
        self.is_persistent_mode = False  # NOVO: Flag para modo persistente
        self.last_disconnection_time = 0.0
        
        # Callbacks para verificar contexto
        self.has_tick_operations_callback: Optional[Callable] = None
        self.has_active_contracts_callback: Optional[Callable] = None
        self.reconnect_callback: Optional[Callable] = None
        
        # Estatísticas
        self.total_reconnections = 0
        self.successful_reconnections = 0
        self.failed_reconnections = 0
        self.persistent_recoveries = 0  # NOVO: Recuperações em modo persistente
        self.total_downtime_seconds = 0.0
        
        # Sistema de backup de estado
        self.state_backup_time = 0.0
        self.contracts_backup = {}
        self.balance_backup = 0.0
    
    def set_context_callbacks(self, 
                            has_tick_ops: Callable,
                            has_contracts: Callable,
                            reconnect_func: Callable):
        """
        Define callbacks para verificar contexto
        
        Args:
            has_tick_ops: Função que retorna True se há operações em ticks ativas
            has_contracts: Função que retorna True se há contratos ativos
            reconnect_func: Função de reconexão assíncrona
        """
        self.has_tick_operations_callback = has_tick_ops
        self.has_active_contracts_callback = has_contracts
        self.reconnect_callback = reconnect_func
    
    def determine_context(self) -> ReconnectionContext:
        """
        Determina contexto atual baseado nas operações ativas
        
        Returns:
            ReconnectionContext: Contexto atual
        """
        # Verificar operações em ticks (mais crítico)
        if self.has_tick_operations_callback and self.has_tick_operations_callback():
            return ReconnectionContext.EMERGENCY_TICKS
        
        # Verificar contratos normais ativos
        if self.has_active_contracts_callback and self.has_active_contracts_callback():
            return ReconnectionContext.PRIORITY_CONTRACTS
        
        # Sem operações ativas
        return ReconnectionContext.NORMAL_IDLE
    
    def backup_current_state(self):
        """Faz backup do estado antes da desconexão"""
        self.state_backup_time = time.time()
        logger.info("💾 Fazendo backup do estado antes da reconexão...")
        
        # Aqui seria feito backup dos contratos ativos, saldo, etc.
        # Por enquanto, apenas log do timestamp
        logger.debug(f"💾 Estado backupeado em {self.state_backup_time}")
    
    async def start_reconnection(self) -> bool:
        """
        MÉTODO LEGADO - Mantido para compatibilidade
        Redireciona para reconexão persistente
        """
        return await self.start_persistent_reconnection()
    
    async def start_persistent_reconnection(self) -> bool:
        """
        Inicia processo de reconexão contextual PERSISTENTE (nunca desiste)
        
        Returns:
            bool: True quando conseguir reconectar (sempre eventualmente)
        """
        if self.is_reconnecting:
            logger.warning("⚠️ Reconexão já em andamento")
            return False
        
        logger.warning("💔 Conexão perdida - iniciando reconexão PERSISTENTE...")
        
        self.is_reconnecting = True
        self.last_disconnection_time = time.time()
        self.attempt_count = 0
        self.persistent_cycle = 0
        self.is_persistent_mode = False
        self.total_reconnections += 1
        
        # Backup do estado atual
        self.backup_current_state()
        
        # Determinar contexto e estratégia
        context = self.determine_context()
        self.current_strategy = ReconnectionStrategy(context)
        
        logger.info(self.current_strategy.description)
        logger.info(f"🎯 Tentativas iniciais: {self.current_strategy.max_attempts}")
        logger.info(f"🔄 Modo persistente: Ativado (nunca desiste)")
        
        success = False
        
        try:
            # FASE 1: Tentativas iniciais (comportamento normal)
            success = await self._initial_reconnection_attempts(context)
            
            # FASE 2: Modo persistente (se tentativas iniciais falharam)
            if not success:
                logger.warning("🔄 Tentativas iniciais esgotadas - ativando MODO PERSISTENTE")
                self.is_persistent_mode = True
                success = await self._persistent_reconnection_loop(context)
            
        except Exception as e:
            logger.error(f"❌ Erro crítico durante reconexão: {e}")
            success = False
        
        finally:
            self.is_reconnecting = False
            self.is_persistent_mode = False
            self.current_strategy = None
        
        return success
    
    async def _initial_reconnection_attempts(self, context: ReconnectionContext) -> bool:
        """Executa tentativas iniciais de reconexão"""
        while self.attempt_count < self.current_strategy.max_attempts:
            self.attempt_count += 1
            
            # Calcular delay contextual
            delay = self.current_strategy.get_delay(self.attempt_count)
            
            # Log contextual
            context_emoji = "🚨" if context == ReconnectionContext.EMERGENCY_TICKS else \
                           "⚡" if context == ReconnectionContext.PRIORITY_CONTRACTS else "😌"
            
            logger.warning(f"{context_emoji} Tentativa {self.attempt_count}/{self.current_strategy.max_attempts} "
                         f"em {delay:.1f}s [{context.value.upper()}]")
            
            # Aguardar delay
            await asyncio.sleep(delay)
            
            # Tentar reconectar
            if await self._attempt_reconnection():
                return True
        
        return False
    
    async def _persistent_reconnection_loop(self, context: ReconnectionContext) -> bool:
        """Loop persistente de reconexão (nunca desiste)"""
        logger.warning("🔄 MODO PERSISTENTE ATIVADO - Tentando reconectar indefinidamente...")
        
        while True:
            self.persistent_cycle += 1
            
            # Calcular delay persistente
            delay = self.current_strategy.get_persistent_delay(self.persistent_cycle)
            
            logger.warning(f"🔄 Tentativa persistente #{self.persistent_cycle} em {delay:.0f}s")
            
            # Aguardar delay
            await asyncio.sleep(delay)
            
            # Tentar reconectar
            if await self._attempt_reconnection():
                # Sucesso em modo persistente
                downtime = time.time() - self.last_disconnection_time
                self.total_downtime_seconds += downtime
                self.successful_reconnections += 1
                self.persistent_recoveries += 1
                
                logger.info(f"🎉 RECUPERAÇÃO PERSISTENTE após {self.attempt_count + self.persistent_cycle} tentativas!")
                logger.info(f"⏱️ Downtime total: {downtime:.1f}s | Modo: PERSISTENTE")
                
                return True
            else:
                # Re-avaliar contexto periodicamente
                if self.persistent_cycle % 3 == 0:  # A cada 3 tentativas
                    new_context = self.determine_context()
                    if new_context != context:
                        logger.info(f"🔄 Contexto mudou: {context.value} → {new_context.value}")
                        context = new_context
                        self.current_strategy = ReconnectionStrategy(context)
    
    async def _attempt_reconnection(self) -> bool:
        """Executa uma única tentativa de reconexão"""
        if self.reconnect_callback:
            success = await self.reconnect_callback()
            
            if success:
                # Reconexão bem-sucedida
                if not self.is_persistent_mode:
                    # Sucesso em modo normal
                    downtime = time.time() - self.last_disconnection_time
                    self.total_downtime_seconds += downtime
                    self.successful_reconnections += 1
                    
                    logger.info(f"🎉 Reconectado após {self.attempt_count} tentativas!")
                    logger.info(f"⏱️ Downtime: {downtime:.1f}s | Contexto: {self.current_strategy.context.value}")
                
                return True
            else:
                if not self.is_persistent_mode:
                    logger.error(f"❌ Tentativa {self.attempt_count} falhou")
                else:
                    logger.debug(f"❌ Tentativa persistente #{self.persistent_cycle} falhou")
        
        return False
    
    def get_reconnection_delay(self, context: Optional[ReconnectionContext] = None) -> float:
        """
        Calcula delay de reconexão baseado no contexto
        
        Args:
            context: Contexto específico (usa atual se None)
            
        Returns:
            float: Delay em segundos
        """
        if context is None:
            context = self.determine_context()
        
        strategy = ReconnectionStrategy(context)
        return strategy.get_delay(self.attempt_count + 1)
    
    def should_attempt_reconnection(self) -> bool:
        """
        Verifica se deve tentar reconectar
        
        Returns:
            bool: True se deve tentar reconectar
        """
        if self.is_reconnecting:
            return False
        
        # Sempre tentar reconectar, mas usar contexto apropriado
        return True
    
    def get_stats(self) -> dict:
        """
        Retorna estatísticas do sistema de reconexão
        
        Returns:
            dict: Estatísticas
        """
        success_rate = 0.0
        if self.total_reconnections > 0:
            success_rate = (self.successful_reconnections / self.total_reconnections) * 100
        
        return {
            'total_reconnections': self.total_reconnections,
            'successful_reconnections': self.successful_reconnections,
            'failed_reconnections': self.failed_reconnections,
            'persistent_recoveries': self.persistent_recoveries,  # NOVO
            'success_rate_percentage': round(success_rate, 1),
            'total_downtime_seconds': round(self.total_downtime_seconds, 1),
            'average_downtime_seconds': round(
                self.total_downtime_seconds / max(1, self.successful_reconnections), 1
            ),
            'is_currently_reconnecting': self.is_reconnecting,
            'is_persistent_mode': self.is_persistent_mode,  # NOVO
            'current_attempt': self.attempt_count,
            'persistent_cycle': self.persistent_cycle,  # NOVO
            'current_context': self.current_strategy.context.value if self.current_strategy else None
        }
    
    def reset_stats(self):
        """Reseta estatísticas de reconexão"""
        self.total_reconnections = 0
        self.successful_reconnections = 0
        self.failed_reconnections = 0
        self.persistent_recoveries = 0
        self.total_downtime_seconds = 0.0
        logger.info("🔄 Estatísticas de reconexão resetadas")
    
    def get_context_description(self, context: Optional[ReconnectionContext] = None) -> str:
        """
        Retorna descrição do contexto
        
        Args:
            context: Contexto específico (usa atual se None)
            
        Returns:
            str: Descrição do contexto
        """
        if context is None:
            context = self.determine_context()
        
        descriptions = {
            ReconnectionContext.EMERGENCY_TICKS: "🚨 OPERAÇÕES EM TICKS ATIVAS - CRÍTICO",
            ReconnectionContext.PRIORITY_CONTRACTS: "⚡ CONTRATOS ATIVOS - PRIORITÁRIO", 
            ReconnectionContext.NORMAL_IDLE: "😌 SEM OPERAÇÕES - NORMAL"
        }
        
        return descriptions.get(context, "❓ CONTEXTO DESCONHECIDO")