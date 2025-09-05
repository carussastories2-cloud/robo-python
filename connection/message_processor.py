#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Message Processor - Processador de Mensagens WebSocket
Processa todas as mensagens recebidas do WebSocket da Deriv
"""

import asyncio
import json
import time
from typing import Dict, Any, Optional, Callable, Set
from utils.logger import get_logger

logger = get_logger(__name__)

class MessageProcessor:
    """Processador de mensagens WebSocket com vigilância contextual"""
    
    def __init__(self):
        self.is_running = False
        self.message_count = 0
        self.error_count = 0
        self.last_message_time = 0.0
        
        self.tick_callback: Optional[Callable] = None
        self.contract_callback: Optional[Callable] = None
        self.balance_callback: Optional[Callable] = None
        self.error_callback: Optional[Callable] = None
        
        self.ignored_message_types: Set[str] = {
            'website_status', 'msg_type', 'pong', 'ping'
        }
        
        self.message_stats: Dict[str, int] = {}
        
        self.has_tick_operations_callback: Optional[Callable] = None
        self.has_active_contracts_callback: Optional[Callable] = None
    
    def set_callbacks(self,
                      tick_callback: Optional[Callable] = None,
                      contract_callback: Optional[Callable] = None,
                      balance_callback: Optional[Callable] = None,
                      error_callback: Optional[Callable] = None):
        self.tick_callback = tick_callback
        self.contract_callback = contract_callback
        self.balance_callback = balance_callback
        self.error_callback = error_callback
    
    def set_context_callbacks(self,
                              has_tick_ops: Optional[Callable] = None,
                              has_contracts: Optional[Callable] = None):
        self.has_tick_operations_callback = has_tick_ops
        self.has_active_contracts_callback = has_contracts

    def stop_processing(self):
        """Para o processamento de mensagens"""
        logger.info("🛑 Parando processador de mensagens...")
        self.is_running = False

    async def process_message(self, data: Dict[str, Any]):
        """
        Método público para processar uma única mensagem
        Este método é chamado externamente (pelo WebSocketManager)
        
        Args:
            data: Mensagem já decodificada como dicionário
        """
        await self._process_single_message(data)

    async def _process_single_message(self, data: Dict[str, Any]):
        """
        Processa uma única mensagem
        
        Args:
            data: Mensagem já decodificada como dicionário
        """
        self.message_count += 1
        
        try:
            # A decodificação json.loads(message) foi removida daqui
            
            message_type = self._identify_message_type(data)
            
            self.message_stats[message_type] = self.message_stats.get(message_type, 0) + 1
            
            if message_type in self.ignored_message_types:
                return
            
            if message_type not in ['tick', 'balance']:
                logger.debug(f"📋 Mensagem {message_type} recebida")
            
            await self._dispatch_message(message_type, data)
            
        except Exception as e:
            self.error_count += 1
            logger.error(f"❌ Erro processando mensagem: {e}")
            logger.debug(f"📋 Conteúdo da mensagem: {str(data)[:100]}...")

    def _identify_message_type(self, data: Dict[str, Any]) -> str:
        if "tick" in data:
            return "tick"
        if "proposal_open_contract" in data:
            return "contract_update"
        if "balance" in data:
            return "balance"
        if "authorize" in data:
            return "authorize"
        if "error" in data:
            return "error"
        if "ping" in data or "pong" in data:
            return "ping_pong"
        if "website_status" in data:
            return "website_status"
        if "time" in data:
            return "server_time"
        if "buy" in data or "sell" in data or "proposal" in data:
            return "trading"
        if "msg_type" in data:
            return data["msg_type"]
        return "unknown"
    
    async def _dispatch_message(self, message_type: str, data: Dict[str, Any]):
        try:
            if message_type == "tick" and self.tick_callback:
                await self.tick_callback(data["tick"])
            elif message_type == "contract_update" and self.contract_callback:
                await self.contract_callback(data["proposal_open_contract"])
            elif message_type == "balance" and self.balance_callback:
                await self.balance_callback(data["balance"])
            elif message_type == "error" and self.error_callback:
                error_info = data["error"]
                error_msg = error_info.get("message", "Erro desconhecido")
                logger.error(f"❌ Erro da API: {error_msg}")
                await self.error_callback(error_info)
            elif message_type not in self.ignored_message_types:
                logger.debug(f"📋 Mensagem {message_type} não tem callback definido")
        except Exception as e:
            logger.error(f"❌ Erro no callback para {message_type}: {e}")
    
    def _get_context_description(self) -> str:
        if self.has_tick_operations_callback and self.has_tick_operations_callback():
            return " [TICKS ATIVOS - EMERGÊNCIA]"
        elif self.has_active_contracts_callback and self.has_active_contracts_callback():
            return " [CONTRATOS ATIVOS]"
        else:
            return " [IDLE]"
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            'is_running': self.is_running,
            'total_messages_processed': self.message_count,
            'total_errors': self.error_count,
            'last_message_age_seconds': time.time() - self.last_message_time if self.last_message_time else 0,
            'message_types_stats': dict(self.message_stats),
            'error_rate_percentage': (self.error_count / max(1, self.message_count)) * 100
        }
    
    def reset_stats(self):
        self.message_count = 0
        self.error_count = 0
        self.message_stats.clear()
        logger.info("🔄 Estatísticas do processador resetadas")
    
    def add_ignored_message_type(self, message_type: str):
        self.ignored_message_types.add(message_type)
        logger.debug(f"🔇 Tipo de mensagem '{message_type}' adicionado aos ignorados")
    
    def remove_ignored_message_type(self, message_type: str):
        self.ignored_message_types.discard(message_type)
        logger.debug(f"🔊 Tipo de mensagem '{message_type}' removido dos ignorados")