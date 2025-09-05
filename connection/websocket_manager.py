#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WebSocket Manager - Gerenciador Principal de Conexão WebSocket
Sistema "fortaleza" para conexão imbatível com a Deriv API
"""

import asyncio
import json
import time
import websockets
from typing import Optional, Dict, Any, Callable
from utils.logger import get_logger

logger = get_logger(__name__)

class WebSocketManager:
    """Gerenciador principal de conexão WebSocket com a Deriv"""
    
    def __init__(self, app_id: int = 1089):
        self.app_id = app_id
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.is_connected = False
        self.is_authorized = False
        self.connection_start_time = 0.0
        
        self.pending_requests: Dict[int, asyncio.Future] = {}
        self.request_timeout = 15.0
        
        self.message_callback: Optional[Callable] = None
        self.connection_callback: Optional[Callable] = None
        self.disconnection_callback: Optional[Callable] = None
        
        self.total_messages_sent = 0
        self.total_messages_received = 0
        self.last_message_time = 0.0
        self.average_latency = 0.0
        
        self.last_ping_time = 0.0
        self.last_pong_time = 0.0
        self.ping_interval = 30.0
        
        # CORREÇÃO: Controle de loop de mensagens
        self.message_loop_task: Optional[asyncio.Task] = None
    
    @property
    def connection_age_seconds(self) -> float:
        if self.connection_start_time == 0:
            return 0
        return time.time() - self.connection_start_time
    
    @property
    def is_stable(self) -> bool:
        if not self.is_connected or not self.websocket:
            return False
        
        if self.websocket.closed:
            return False
        
        silence_duration = time.time() - self.last_message_time
        max_silence = 120.0
        
        return silence_duration <= max_silence
    
    async def connect(self) -> bool:
        url = f"wss://ws.binaryws.com/websockets/v3?app_id={self.app_id}"
        
        try:
            logger.info(f"🔗 Conectando WebSocket: {url}")
            
            self.websocket = await websockets.connect(
                url,
                ping_interval=30,
                ping_timeout=20,
                close_timeout=10,
                max_size=2**20,
                compression=None
            )
            
            self.is_connected = True
            self.connection_start_time = time.time()
            self.last_message_time = time.time()
            
            logger.info("✅ WebSocket conectado com sucesso!")
            
            # CORREÇÃO: Iniciar loop de mensagens como task controlável
            self.message_loop_task = asyncio.create_task(self._message_loop())
            
            if self.connection_callback:
                await self.connection_callback()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro na conexão WebSocket: {e}")
            self.is_connected = False
            return False
    
    async def _message_loop(self):
        logger.debug("🔄 Iniciando loop de mensagens do WebSocket")
        
        try:
            while self.is_connected and self.websocket and not self.websocket.closed:
                try:
                    # CORREÇÃO: Timeout no recv para permitir verificação periódica
                    message = await asyncio.wait_for(self.websocket.recv(), timeout=1.0)
                    self.last_message_time = time.time()
                    self.total_messages_received += 1
                    
                    await self.process_message(message)
                    
                except asyncio.TimeoutError:
                    # Timeout normal - continuar verificando
                    continue
                except websockets.exceptions.ConnectionClosed:
                    logger.warning("💔 WebSocket fechado durante o recebimento de mensagens.")
                    break
                except Exception as e:
                    logger.error(f"❌ Erro no loop de mensagens: {e}")
                    await asyncio.sleep(0.1)
                    
        except asyncio.CancelledError:
            logger.debug("🔄 Loop de mensagens cancelado")
        except Exception as e:
            logger.error(f"💥 Erro crítico no loop de mensagens: {e}")
        finally:
            logger.debug("🔄 Loop de mensagens finalizado.")
            # CORREÇÃO: Marcar como desconectado e chamar callback de desconexão
            if self.is_connected:
                self.is_connected = False
                self.is_authorized = False
                if self.disconnection_callback:
                    try:
                        await self.disconnection_callback()
                    except Exception as e:
                        logger.error(f"❌ Erro no callback de desconexão: {e}")

    async def process_message(self, message: str):
        self.last_message_time = time.time()
        self.total_messages_received += 1
        
        data = None
        try:
            data = json.loads(message)
            
            if 'req_id' in data:
                req_id = data['req_id']
                if req_id in self.pending_requests:
                    future = self.pending_requests.pop(req_id)
                    if not future.done():
                        future.set_result(data)
                    return
            
            if "msg_type" in data:
                msg_type = data["msg_type"]
                if msg_type == "ping":
                    await self._handle_ping()
                elif msg_type == "pong":
                    self._handle_pong()
            
            if self.message_callback:
                await self.message_callback(data)
                
        except json.JSONDecodeError:
            logger.debug(f"📋 Mensagem não-JSON ignorada: {message[:50]}...")
        except Exception as e:
            log_content = str(data) if data else message
            logger.error(f"❌ Erro processando mensagem: {e}")
            logger.debug(f"📋 Conteúdo problemático: {log_content[:100]}...")

    async def disconnect(self):
        logger.info("🔌 Desconectando WebSocket...")
        
        self.is_connected = False
        self.is_authorized = False
        
        # CORREÇÃO: Cancelar loop de mensagens
        if self.message_loop_task and not self.message_loop_task.done():
            self.message_loop_task.cancel()
            try:
                await asyncio.wait_for(self.message_loop_task, timeout=2.0)
            except asyncio.TimeoutError:
                logger.warning("⚠️ Timeout cancelando loop de mensagens")
            except asyncio.CancelledError:
                pass
        
        for future in self.pending_requests.values():
            if not future.done():
                future.cancel()
        self.pending_requests.clear()
        
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception as e:
                logger.warning(f"⚠️ Erro ao fechar WebSocket: {e}")
            finally:
                self.websocket = None
        
        logger.info("🔌 WebSocket desconectado")
    
    async def send_request(self, request: Dict[str, Any], timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        if not self.is_connected or not self.websocket:
            logger.warning("⚠️ Tentativa de enviar requisição sem conexão")
            return None
        
        # CORREÇÃO: Verificar se WebSocket não está fechado
        if self.websocket.closed:
            logger.warning("⚠️ WebSocket está fechado")
            self.is_connected = False
            return None
        
        req_id = int(time.time() * 1000000) + len(self.pending_requests)
        request['req_id'] = req_id
        
        request_type = self._get_request_type(request)
        timeout_value = timeout or self.request_timeout
        
        logger.debug(f"📤 Enviando {request_type} (req_id: {req_id}, timeout: {timeout_value}s)")
        
        try:
            future = asyncio.Future()
            self.pending_requests[req_id] = future
            
            message_json = json.dumps(request)
            logger.debug(f"📤 JSON enviado: {message_json}")
            
            await self.websocket.send(message_json)
            self.total_messages_sent += 1
            
            start_time = time.time()
            logger.debug(f"⏳ Aguardando resposta para req_id {req_id}...")
            
            response = await asyncio.wait_for(future, timeout=timeout_value)
            
            latency = (time.time() - start_time) * 1000
            self._update_latency_stats(latency)
            
            logger.debug(f"✅ Resposta {request_type} recebida ({latency:.1f}ms)")
            return response
            
        except asyncio.TimeoutError:
            logger.error(f"⏰ Timeout em {request_type} após {timeout_value}s")
            logger.error(f"🔍 Requests pendentes: {len(self.pending_requests)}")
            logger.error(f"🔍 WebSocket conectado: {self.is_connected and self.websocket and not self.websocket.closed}")
            return None
        except websockets.exceptions.ConnectionClosed:
            logger.error(f"❌ Conexão fechada durante {request_type}")
            self.is_connected = False
            return None
        except Exception as e:
            logger.error(f"❌ Erro enviando {request_type}: {e}")
            return None
        finally:
            self.pending_requests.pop(req_id, None)
    
    async def send_message(self, message: Dict[str, Any]) -> bool:
        if not self.is_connected or not self.websocket:
            logger.warning("⚠️ Tentativa de enviar mensagem sem conexão")
            return False
        
        # CORREÇÃO: Verificar se WebSocket não está fechado
        if self.websocket.closed:
            logger.warning("⚠️ WebSocket está fechado")
            self.is_connected = False
            return False
        
        try:
            await self.websocket.send(json.dumps(message))
            self.total_messages_sent += 1
            return True
        except websockets.exceptions.ConnectionClosed:
            logger.error("❌ Conexão fechada durante envio de mensagem")
            self.is_connected = False
            return False
        except Exception as e:
            logger.error(f"❌ Erro enviando mensagem: {e}")
            return False
    
    async def authorize(self, api_token: str) -> bool:
        logger.info("🔐 Iniciando autorização...")
        logger.debug(f"🔐 Token: {api_token[:10]}...{api_token[-4:]}")
        
        response = await self.send_request({"authorize": api_token}, timeout=15.0)
        
        if not response:
            logger.error("❌ Falha na autorização - sem resposta")
            return False
        
        if "error" in response:
            error_msg = response.get('error', {}).get('message', 'Erro desconhecido')
            error_code = response.get('error', {}).get('code', 'N/A')
            logger.error(f"❌ Erro na autorização: {error_msg} (Código: {error_code})")
            return False
        
        if "authorize" in response:
            self.is_authorized = True
            user_info = response["authorize"]
            user_id = user_info.get("loginid", "N/A")
            currency = user_info.get("currency", "USD")
            logger.info(f"✅ Autorização bem-sucedida - User: {user_id} | Currency: {currency}")
            return True
        
        logger.error("❌ Resposta de autorização inválida")
        logger.debug(f"❌ Resposta recebida: {response}")
        return False
    
    async def test_connection(self) -> bool:
        if not self.is_connected or not self.websocket:
            return False
        
        if self.websocket.closed:
            self.is_connected = False
            return False
        
        try:
            pong_waiter = await self.websocket.ping()
            await asyncio.wait_for(pong_waiter, timeout=5.0)
            logger.debug("🏓 Ping/pong test passou")
            return True
        except Exception as e:
            logger.error(f"❌ Teste de conexão falhou: {e}")
            return False

    async def get_server_time(self) -> Optional[float]:
        logger.debug("🕐 Obtendo tempo do servidor...")
        response = await self.send_request({"time": 1}, timeout=10.0)
        
        if response and "time" in response:
            server_time = float(response["time"])
            logger.debug(f"🕐 Tempo do servidor: {server_time}")
            return server_time
        
        logger.warning("⚠️ Não foi possível obter tempo do servidor")
        return None
    
    def set_message_callback(self, callback: Callable):
        self.message_callback = callback
    
    def set_connection_callback(self, callback: Callable):
        self.connection_callback = callback
    
    def set_disconnection_callback(self, callback: Callable):
        self.disconnection_callback = callback
    
    async def _handle_ping(self):
        try:
            await self.websocket.send(json.dumps({"pong": 1}))
            logger.debug("🏓 Pong enviado em resposta ao ping")
        except Exception as e:
            logger.error(f"❌ Erro enviando pong: {e}")
    
    def _handle_pong(self):
        self.last_pong_time = time.time()
        logger.debug("🏓 Pong recebido do servidor")
    
    async def send_ping(self):
        if not self.is_connected:
            return
        
        try:
            self.last_ping_time = time.time()
            await self.websocket.send(json.dumps({"ping": 1}))
            logger.debug("🏓 Ping enviado para servidor")
        except Exception as e:
            logger.error(f"❌ Erro enviando ping: {e}")
    
    def _get_request_type(self, request: Dict[str, Any]) -> str:
        for key in request.keys():
            if key != 'req_id':
                return key
        return "unknown"
    
    def _update_latency_stats(self, latency_ms: float):
        if self.average_latency == 0:
            self.average_latency = latency_ms
        else:
            self.average_latency = (self.average_latency * 0.9) + (latency_ms * 0.1)
    
    def get_connection_stats(self) -> Dict[str, Any]:
        return {
            'is_connected': self.is_connected,
            'is_authorized': self.is_authorized,
            'is_stable': self.is_stable,
            'connection_age_seconds': self.connection_age_seconds,
            'total_messages_sent': self.total_messages_sent,
            'total_messages_received': self.total_messages_received,
            'average_latency_ms': round(self.average_latency, 1),
            'pending_requests': len(self.pending_requests),
            'last_message_age_seconds': time.time() - self.last_message_time if self.last_message_time else 0,
            'websocket_closed': self.websocket.closed if self.websocket else True
        }
    
    def reset_stats(self):
        self.total_messages_sent = 0
        self.total_messages_received = 0
        self.average_latency = 0.0
        self.connection_start_time = time.time()