#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Trading Bot - Classe Principal (VERSÃO CORRIGIDA - Recuperação de Contratos)
"""

import asyncio
import time
from typing import Dict, List, Optional, Any
from collections import deque

from config.settings import settings
from core.data_models import AssetState, SessionStats, CandleData, TickData, SignalData, ContractInfo, ContractStatus, SignalDirection
from connection.websocket_manager import WebSocketManager
from connection.reconnection_system import ReconnectionSystem
from connection.message_processor import MessageProcessor
from connection.contract_recovery import ContractRecovery
from strategies.candle_pattern import CandlePatternStrategy
from risk_management.base_risk import BaseRiskManager
from risk_management.fixed_amount import FixedAmountRisk
from risk_management.martingale import MartingaleRisk
from trading.operation_executor import OperationExecutor
from utils.logger import get_logger

logger = get_logger(__name__)

class TradingBot:
    """Classe principal do Trading Bot modular"""
    
    def __init__(self):
        logger.info("🤖 Inicializando Trading Bot Modular...")
        self.config = settings
        self.is_running = False
        self.balance = 0.0
        self.initial_balance = 0.0
        self.session_stats = SessionStats()
        self.bot_start_time = 0.0
        self.asset_states: Dict[str, AssetState] = {s: AssetState(s) for s in self.config.SYMBOLS}
        self.time_offset = 0.0
        self.websocket_manager = WebSocketManager(self.config.DERIV_APP_ID)
        self.reconnection_system = ReconnectionSystem()
        self.message_processor = MessageProcessor()
        self.contract_recovery = ContractRecovery()
        self.strategy = CandlePatternStrategy(self.config)
        self.risk_manager = self._initialize_risk_manager()
        self.operation_executor = OperationExecutor(self.config)
        self.last_signal_times: Dict[str, float] = {}
        self.signal_debounce = self.config.SIGNAL_DEBOUNCE
        self.has_any_active_operation = False
        self.current_operating_symbol = None
        self.main_task: Optional[asyncio.Task] = None
        self.result_checker_task: Optional[asyncio.Task] = None
        
        # CORREÇÃO: Flag para evitar entrada em padrões já formados na inicialização
        self.initialization_complete = False
        self.first_complete_candle_time = 0.0
        
        self._setup_callbacks()
        logger.info("✅ Trading Bot inicializado com sucesso!")
        # CORREÇÃO: Chamar apenas uma vez
        self._log_bot_configuration()

    @property
    def synced_time(self) -> float:
        return time.time() + self.time_offset

    def _initialize_risk_manager(self) -> BaseRiskManager:
        if self.config.RISK_MANAGEMENT_TYPE == "MARTINGALE":
            return MartingaleRisk(self.config)
        else:
            return FixedAmountRisk(self.config)

    def _setup_callbacks(self):
        self.websocket_manager.set_message_callback(self.message_processor.process_message)
        self.websocket_manager.set_disconnection_callback(self._handle_disconnection)
        self.message_processor.set_callbacks(tick_callback=self._process_tick, contract_callback=self._process_contract_update, balance_callback=self._process_balance_update, error_callback=self._process_api_error)
        self.reconnection_system.set_context_callbacks(has_tick_ops=self._has_tick_operations, has_contracts=self._has_active_contracts, reconnect_func=self._perform_reconnection)
        self.contract_recovery.set_callbacks(send_request=self.websocket_manager.send_request, contract_update=self._process_contract_recovery_update)
        self.operation_executor.set_callbacks(send_request=self.websocket_manager.send_request, subscribe_contract=self._subscribe_to_contract)
    
    async def _handle_disconnection(self):
        logger.warning("💔 Desconexão detectada - iniciando sistema de recuperação")
        active_contracts = {symbol: state.active_contracts for symbol, state in self.asset_states.items()}
        self.contract_recovery.backup_state_before_disconnection(active_contracts, self.balance)
        if await self.reconnection_system.start_persistent_reconnection():
            logger.info("🎉 Reconectado com sucesso - iniciando recuperação de contratos")
            if not self.is_running:
                logger.info("🔄 Reativando bot após reconexão bem-sucedida")
                self.is_running = True
            recovery_result = await self.contract_recovery.recover_lost_contracts()
            logger.info(f"📊 Recuperação: {recovery_result['recovered']}/{recovery_result['total_contracts']} contratos")
            await self._update_balance()
            # CORREÇÃO: Re-inscrever nos ticks após reconexão
            await self._subscribe_to_ticks()
        else:
            logger.critical("💀 Falha crítica no sistema de reconexão - encerrando bot")
            self.is_running = False
    
    async def _perform_reconnection(self) -> bool:
        try:
            if self.websocket_manager.is_connected: await self.websocket_manager.disconnect()
            await asyncio.sleep(2)
            if await self.websocket_manager.connect():
                if await self.websocket_manager.authorize(self.config.DERIV_API_TOKEN):
                    logger.info("✅ Reconexão e autorização bem-sucedidas")
                    return True
                else: logger.error("❌ Falha na autorização após reconexão")
            else: logger.error("❌ Falha na reconexão WebSocket")
        except Exception as e: logger.error(f"❌ Erro durante reconexão: {e}")
        return False
    
    def _has_tick_operations(self) -> bool:
        if self.config.DURATION_UNIT != "t": return False
        return self._has_active_contracts()
    
    def _has_any_active_operation(self) -> bool:
        return any(state.has_active_contracts for state in self.asset_states.values())
    
    async def _process_contract_recovery_update(self, contract: ContractInfo, contract_data: Dict):
        target_asset_state = None
        original_contract = None
        for asset_state in self.asset_states.values():
            for existing_contract in asset_state.active_contracts:
                if existing_contract.id == contract.id:
                    target_asset_state = asset_state
                    original_contract = existing_contract
                    break
            if target_asset_state: break
        if not target_asset_state or not original_contract:
            return

        # Verificar se o resultado foi previamente forçado
        was_forced_loss = getattr(original_contract, 'forced_result', False)
        
        # Atualizar com resultado real
        original_contract.status = contract.status
        original_contract.profit = contract.profit
        original_contract.end_time = contract.end_time
        original_contract.payout = getattr(contract, 'payout', 0)
        original_contract.sell_price = getattr(contract, 'sell_price', 0)
        original_contract.forced_result = False

        # Se todos os contratos estão finalizados e houve forcing, aplicar correção
        if self._all_contracts_finished(target_asset_state) and was_forced_loss:
            await self._correct_results_after_recovery(target_asset_state)
    
    async def _correct_results_after_recovery(self, asset_state: AssetState):
        """
        CORREÇÃO: Corrige saldo apenas quando há diferença entre resultado forçado e real
        """
        # Só executar se há um valor forçado para corrigir
        if not hasattr(asset_state, 'forced_total_loss'):
            return
            
        # Calcular resultado real atual
        real_total = sum(c.profit for c in asset_state.active_contracts)
        forced_total = asset_state.forced_total_loss
        delattr(asset_state, 'forced_total_loss')
        
        # Calcular correção necessária
        balance_correction = real_total - forced_total
        
        logger.info(f"💰 {asset_state.symbol}: Resultado forçado: ${forced_total:.2f} → Real: ${real_total:.2f}")
        logger.info(f"🔧 {asset_state.symbol}: Aplicando correção de saldo: ${balance_correction:+.2f}")
        
        # Aplicar correção ao saldo
        self.balance += balance_correction
        self.session_stats.current_balance = self.balance
        
        # Determinar se a operação realmente ganhou
        operation_won = any(c.profit > 0 for c in asset_state.active_contracts) if self.config.DUAL_ENTRY else real_total > 0
        
        # Corrigir estado do martingale se necessário
        if operation_won and asset_state.current_sequence > 1:
            logger.info(f"✅ {asset_state.symbol}: Martingale S{asset_state.current_sequence} → S1 (correção)")
            asset_state.current_sequence = 1
            asset_state.loss_accumulator = 0.0
    
    def _get_max_martingale_sequence(self) -> int:
        if self.config.RISK_MANAGEMENT_TYPE == "FIXED_AMOUNT": return 1
        else: return getattr(self.config, 'MARTINGALE_MAX_SEQUENCE', 2)
    
    async def run(self):
        try:
            self.is_running = True
            logger.info("🚀 Iniciando Trading Bot...")
            await self._connect_and_setup()
            self.bot_start_time = self.synced_time
            self.session_stats.start_time = self.synced_time
            
            # CORREÇÃO: Definir tempo para primeira vela completa
            current_time = self.synced_time
            timeframe_seconds = self.config.analysis_timeframe_seconds
            next_candle_start = (int(current_time // timeframe_seconds) + 1) * timeframe_seconds
            self.first_complete_candle_time = next_candle_start + timeframe_seconds
            
            logger.info(f"🕐 Aguardando primeira vela completa em: {time.strftime('%H:%M:%S', time.localtime(self.first_complete_candle_time))}")
            
            self.main_task = asyncio.create_task(self._main_loop())
            self.result_checker_task = asyncio.create_task(self._result_checker_loop())
            await asyncio.gather(self.main_task, self.result_checker_task)
        except KeyboardInterrupt:
            logger.info("👋 Bot interrompido pelo usuário")
        except Exception as e:
            logger.critical(f"💥 Erro crítico no bot: {e}", exc_info=self.config.DEBUG_MODE)
        finally:
            await self._cleanup()
            
    async def _connect_and_setup(self):
        max_attempts = 3
        for attempt in range(max_attempts):
            if await self.websocket_manager.connect():
                logger.info("✅ Conectado ao WebSocket")
                try:
                    await self._initialize_session()
                    await self._synchronize_time()
                    await self._load_historical_data()
                    await self._subscribe_to_ticks()
                    logger.info("🎉 Setup completo - robô operacional!")
                    return
                except Exception as e:
                    logger.error(f"❌ Falha durante o setup após conectar: {e}")
                    await self.websocket_manager.disconnect()
            if attempt < max_attempts - 1: await asyncio.sleep(5)
        raise Exception("Falha na conexão após todas as tentativas")

    async def _synchronize_time(self):
        logger.info("⌛ Sincronizando relógio com o servidor da corretora...")
        try:
            local_time_before = time.time()
            server_time_response = await self.websocket_manager.send_request({"time": 1})
            local_time_after = time.time()
            if server_time_response and "time" in server_time_response:
                server_time = float(server_time_response["time"])
                rtt = local_time_after - local_time_before
                effective_local_time = local_time_before + (rtt / 2)
                self.time_offset = server_time - effective_local_time
                offset_ms = self.time_offset * 1000
                logger.info(f"✅ Sincronização completa. Atraso local: {offset_ms:+.2f}ms (Latência: {rtt*1000:.2f}ms)")
            else:
                self.time_offset = 0.0
        except Exception as e:
            logger.error(f"❌ Erro ao sincronizar o tempo: {e}. Usando relógio local.")
            self.time_offset = 0.0

    async def _initialize_session(self):
        if not await self.websocket_manager.authorize(self.config.DERIV_API_TOKEN):
            raise Exception("Falha na autorização")
        await self._update_balance()
        if self.initial_balance == 0.0:
            self.initial_balance = self.balance
        self.session_stats.initial_balance = self.initial_balance
        logger.info(f"💰 Sessão inicializada - Saldo: ${self.balance:.2f}")

    async def _load_historical_data(self):
        logger.info("📊 Carregando dados históricos...")
        tasks = [self._load_symbol_history(symbol) for symbol in self.config.SYMBOLS]
        await asyncio.gather(*tasks, return_exceptions=True)
        ready_symbols = [s for s, state in self.asset_states.items() if len(state.candle_cache) > 10]
        logger.info(f"📊 Histórico carregado: {len(ready_symbols)}/{len(self.config.SYMBOLS)} ativos prontos")
    
    async def _load_symbol_history(self, symbol: str):
        try:
            request = {"ticks_history": symbol, "adjust_start_time": 1, "count": 200, "end": "latest", "granularity": self.config.analysis_timeframe_seconds, "style": "candles"}
            response = await self.websocket_manager.send_request(request, timeout=15)
            if response and "candles" in response:
                asset_state = self.asset_states[symbol]
                asset_state.candle_cache.clear()
                for candle_data in response["candles"]:
                    candle = CandleData(timestamp=float(candle_data["epoch"]), open_price=float(candle_data["open"]), high_price=float(candle_data["high"]), low_price=float(candle_data["low"]), close_price=float(candle_data["close"]), symbol=symbol)
                    asset_state.add_candle(candle)
        except Exception as e:
            logger.warning(f"⚠️ Erro carregando histórico de {symbol}: {e}")
    
    async def _subscribe_to_ticks(self):
        logger.info("📡 Inscrevendo-se no stream de ticks...")
        for symbol in self.config.SYMBOLS:
            try:
                await self.websocket_manager.send_message({"ticks": symbol, "subscribe": 1})
            except Exception as e:
                logger.error(f"❌ Falha ao inscrever-se em {symbol}: {e}")

    async def _main_loop(self):
        logger.info("🔄 Iniciando loop principal de análise...")
        while self.is_running:
            try:
                current_time = self.synced_time
                
                # CORREÇÃO: Verificar se inicialização está completa
                if not self.initialization_complete:
                    if current_time >= self.first_complete_candle_time:
                        self.initialization_complete = True
                        logger.info("✅ Inicialização completa - robô pronto para operar!")
                    else:
                        await asyncio.sleep(1.0)
                        continue
                
                # CORREÇÃO: Para NEXT_CANDLE, esperar início da próxima vela
                if self.config.RISK_MANAGEMENT_TYPE == "MARTINGALE" and self.config.MARTINGALE_TYPE == "NEXT_CANDLE":
                    timeframe_seconds = self.config.analysis_timeframe_seconds
                    next_candle_start_time = (int(current_time // timeframe_seconds) + 1) * timeframe_seconds
                    wait_time = max(0.1, next_candle_start_time - current_time + 0.5)
                    await asyncio.sleep(wait_time)
                elif self.config.RISK_MANAGEMENT_TYPE == "MARTINGALE" and self.config.MARTINGALE_TYPE == "IMMEDIATE":
                    # CORREÇÃO: Para IMMEDIATE, executar imediatamente após perda, sem esperar vela
                    await asyncio.sleep(1.0)
                else:
                    await asyncio.sleep(1.0)
                
                if not self.websocket_manager.is_connected:
                    if not self.reconnection_system.is_reconnecting:
                        logger.warning("⚠️ Conexão perdida detectada no loop principal")
                        asyncio.create_task(self._handle_disconnection())
                    continue
                
                stop_reason = self.risk_manager.check_stop_conditions(self.balance, self.initial_balance)
                if stop_reason:
                    logger.info(f"🛑 Condição de parada ativada: {stop_reason}")
                    self.is_running = False
                    break
                
                self.has_any_active_operation = self._has_any_active_operation()
                if self.has_any_active_operation:
                    operating_symbols = [symbol for symbol, state in self.asset_states.items() if state.has_active_contracts]
                    self.current_operating_symbol = operating_symbols[0] if operating_symbols else None
                else:
                    self.current_operating_symbol = None
                
                signals = await self._analyze_signals()
                if signals:
                    for symbol, signal in signals.items():
                        if self.has_any_active_operation: break
                        if await self._should_process_signal(symbol, signal):
                            await self._process_signal(symbol, signal)
                            break
            except asyncio.CancelledError:
                logger.info("🔄 Loop principal de análise cancelado.")
                break
            except Exception as e:
                logger.error(f"❌ Erro no loop principal de análise: {e}", exc_info=self.config.DEBUG_MODE)
                await asyncio.sleep(5)
        logger.info("🔄 Loop principal de análise finalizado.")

    async def _result_checker_loop(self):
        logger.info("✅ Loop de verificação de resultados iniciado.")
        while self.is_running:
            try:
                if self._has_active_contracts():
                    await self._check_pending_results()
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                logger.info("🔄 Loop de verificação de resultados cancelado.")
                break
            except Exception as e:
                logger.error(f"❌ Erro no loop de verificação de resultados: {e}", exc_info=self.config.DEBUG_MODE)
                await asyncio.sleep(5)
        logger.info("🔄 Loop de verificação de resultados finalizado.")

    async def _analyze_signals(self) -> Dict[str, SignalData]:
        signals = {}
        if isinstance(self.risk_manager, MartingaleRisk):
            for symbol, asset_state in self.asset_states.items():
                if not self._is_asset_busy(asset_state) and asset_state.current_sequence > 1:
                    original_direction = asset_state.last_entry_direction
                    martingale_direction = self.risk_manager.get_martingale_direction(original_direction, asset_state.current_sequence)
                    logger.info(f"⚙️ {symbol}: Disparando Martingale S{asset_state.current_sequence} na direção: {martingale_direction}")
                    signals[symbol] = SignalData(symbol=symbol, direction=SignalDirection(martingale_direction), timestamp=self.synced_time, source="MARTINGALE")
                    return signals
        
        for symbol, asset_state in self.asset_states.items():
            if self.has_any_active_operation: continue
            if self._is_asset_busy(asset_state): continue
            if len(asset_state.candle_cache) < 5: continue
            try:
                candles = list(asset_state.candle_cache)
                signal = self.strategy.analyze_signal(symbol, candles, self.bot_start_time, self.synced_time)
                if signal: 
                    signals[symbol] = signal
                    return signals
            except Exception as e:
                logger.error(f"❌ Erro analisando {symbol}: {e}")
        return signals
    
    async def _should_process_signal(self, symbol: str, signal: SignalData) -> bool:
        # CORREÇÃO: Verificar se inicialização está completa
        if not self.initialization_complete:
            logger.debug(f"🕐 {symbol}: Sinal ignorado - aguardando inicialização completa")
            return False
            
        if not self._check_signal_debounce(symbol) and signal.source != "MARTINGALE": 
            return False
        if signal.age_seconds > self.config.MAX_SIGNAL_AGE:
            logger.debug(f"🕐 {symbol}: Sinal muito antigo ({signal.age_seconds:.1f}s)")
            return False
        if self._is_asset_busy(self.asset_states[symbol]): return False
        
        # CORREÇÃO: Verificar timing da vela baseado no tipo de sinal e configuração
        if signal.source != "MARTINGALE":
            # Para sinais normais (estratégia), sempre verificar início da vela
            current_time = self.synced_time
            timeframe_seconds = self.config.analysis_timeframe_seconds
            seconds_into_candle = current_time % timeframe_seconds
            
            if seconds_into_candle > 10:  # Se passou dos primeiros 10 segundos da vela
                logger.debug(f"🕐 {symbol}: Sinal fora do início da vela (segundo {seconds_into_candle:.0f})")
                return False
        elif signal.source == "MARTINGALE" and self.config.MARTINGALE_TYPE == "NEXT_CANDLE":
            # Para martingale NEXT_CANDLE, verificar início da vela
            current_time = self.synced_time
            timeframe_seconds = self.config.analysis_timeframe_seconds
            seconds_into_candle = current_time % timeframe_seconds
            
            if seconds_into_candle > 10:  # Se passou dos primeiros 10 segundos da vela
                logger.debug(f"🕐 {symbol}: Martingale NEXT_CANDLE fora do início da vela (segundo {seconds_into_candle:.0f})")
                return False
        # Para martingale IMMEDIATE, não verificar timing da vela - executar imediatamente
        
        return True
    
    async def _process_signal(self, symbol: str, signal: SignalData):
        asset_state = self.asset_states[symbol]
        
        if asset_state.current_sequence == 1:
            asset_state.last_entry_direction = signal.direction.value
            # CORREÇÃO: Definir saldo inicial para cálculos de martingale
            asset_state.initial_balance_for_sequence = self.initial_balance
        
        if self.has_any_active_operation:
            logger.debug(f"🚫 {symbol}: Operação bloqueada - já existe operação ativa em {self.current_operating_symbol}")
            return
        
        # CORREÇÃO: Log apropriado baseado no tipo de sinal
        if signal.source != "MARTINGALE":
            current_time = self.synced_time
            timeframe_seconds = self.config.analysis_timeframe_seconds
            seconds_into_candle = current_time % timeframe_seconds
            logger.info(f"🎯 {symbol}: Processando sinal {signal.direction.value} (S{asset_state.current_sequence}) - Entrada no segundo {seconds_into_candle:.0f} da vela")
        elif signal.source == "MARTINGALE" and self.config.MARTINGALE_TYPE == "IMMEDIATE":
            logger.info(f"🎯 {symbol}: Processando sinal {signal.direction.value} (S{asset_state.current_sequence}) - MARTINGALE IMEDIATO")
        elif signal.source == "MARTINGALE" and self.config.MARTINGALE_TYPE == "NEXT_CANDLE":
            current_time = self.synced_time
            timeframe_seconds = self.config.analysis_timeframe_seconds
            seconds_into_candle = current_time % timeframe_seconds
            logger.info(f"🎯 {symbol}: Processando sinal {signal.direction.value} (S{asset_state.current_sequence}) - MARTINGALE NEXT_CANDLE (segundo {seconds_into_candle:.0f})")
        else:
            logger.info(f"🎯 {symbol}: Processando sinal {signal.direction.value} (S{asset_state.current_sequence})")
        
        self.last_signal_times[symbol] = self.synced_time
        
        amount = self.risk_manager.calculate_amount(asset_state, self.balance, self.initial_balance)
        if amount <= 0: return

        asset_state.balance_before_operation = self.balance
        
        success = False
        if self.config.DUAL_ENTRY:
            success = await self.operation_executor.execute_dual_operation(asset_state, signal, amount)
        else:
            success = await self.operation_executor.execute_single_operation(asset_state, signal, amount)
        
        if success:
            logger.info(f"✅ {symbol}: Operação iniciada com sucesso")
            self.has_any_active_operation = True
            self.current_operating_symbol = symbol
        else:
            logger.error(f"❌ {symbol}: Falha na execução da operação")
            asset_state.active_contracts.clear()

    async def _check_pending_results(self):
        for symbol, asset_state in self.asset_states.items():
            if not asset_state.active_contracts: continue
            for contract in asset_state.active_contracts[:]:
                if contract.is_finished: continue
                if self._is_contract_expired(contract):
                    await self._verify_contract_result(contract, asset_state)
    
    def _is_contract_expired(self, contract: ContractInfo) -> bool:
        if self.config.DURATION_UNIT == "t": expected_duration = self.config.DURATION * 2.5
        elif self.config.DURATION_UNIT == "s": expected_duration = self.config.DURATION
        else: expected_duration = self.config.DURATION * 60
        tolerance = 5.0 if self.websocket_manager.is_connected else 60.0
        return self.synced_time - contract.start_time >= (expected_duration + tolerance)
    
    async def _verify_contract_result(self, contract: ContractInfo, asset_state: AssetState):
        if not self.websocket_manager.is_connected: return
        try:
            request = {"proposal_open_contract": 1, "contract_id": int(contract.id)}
            response = await self.websocket_manager.send_request(request, timeout=10)
            if response and "proposal_open_contract" in response:
                await self._process_contract_update_internal(response["proposal_open_contract"], asset_state)
            else:
                self._force_contract_as_loss(contract, asset_state)
        except Exception as e:
            logger.error(f"❌ Erro verificando contrato {contract.id}: {e}")
            self._force_contract_as_loss(contract, asset_state)
    
    def _force_contract_as_loss(self, contract: ContractInfo, asset_state: AssetState):
        """
        Força contrato como perda temporária para timeout
        """
        logger.warning(f"🚨 {asset_state.symbol}: Timeout - forçando contrato {contract.id} como perda temporária")
        
        # Marcar como resultado forçado
        contract.forced_result = True
        contract.status = ContractStatus.LOST
        contract.profit = -contract.amount
        contract.end_time = self.synced_time
        
        # Se todos contratos finalizados, processar e salvar estado para correção
        if self._all_contracts_finished(asset_state):
            # Salvar total forçado para correção posterior
            asset_state.forced_total_loss = sum(c.profit for c in asset_state.active_contracts)
            logger.warning(f"⚠️ {asset_state.symbol}: Forçando resultado temporário: ${asset_state.forced_total_loss:.2f}")
            
            # Processar resultado normalmente (será corrigido se necessário na recuperação)
            self._process_sequence_result(asset_state)
    
    async def _process_tick(self, tick_data: Dict[str, Any]):
        symbol = tick_data["symbol"]
        if symbol in self.asset_states:
            tick = TickData(timestamp=float(tick_data["epoch"]), price=float(tick_data["quote"]), symbol=symbol)
            asset_state = self.asset_states[symbol]
            asset_state.add_tick(tick)
            self._update_candle_from_tick(asset_state, tick)
    
    def _update_candle_from_tick(self, asset_state: AssetState, tick: TickData):
        candle_start = int(tick.timestamp // self.config.analysis_timeframe_seconds) * self.config.analysis_timeframe_seconds
        if not asset_state.candle_cache or asset_state.candle_cache[-1].timestamp != candle_start:
            if asset_state.candle_cache:
                asset_state.candle_cache[-1].close_price = tick.price
            new_candle = CandleData(timestamp=candle_start, open_price=tick.price, high_price=tick.price, low_price=tick.price, close_price=tick.price, symbol=asset_state.symbol)
            asset_state.add_candle(new_candle)
        else:
            current_candle = asset_state.candle_cache[-1]
            current_candle.high_price = max(current_candle.high_price, tick.price)
            current_candle.low_price = min(current_candle.low_price, tick.price)
            current_candle.close_price = tick.price
    
    async def _process_contract_update(self, contract_data: Dict[str, Any]):
        contract_id, status = contract_data.get("contract_id"), contract_data.get("status")
        if not contract_id or status not in ["sold", "won", "lost"]: return
        for asset_state in self.asset_states.values():
            for contract in asset_state.active_contracts:
                if contract.id == contract_id and not contract.is_finished:
                    await self._process_contract_update_internal(contract_data, asset_state)
                    return
    
    async def _process_contract_update_internal(self, contract_data: Dict[str, Any], asset_state: AssetState):
        contract_id = contract_data.get("contract_id")
        contract = next((c for c in asset_state.active_contracts if c.id == contract_id), None)
        if not contract or contract.is_finished: return
        status, buy_price = contract_data.get("status"), float(contract_data.get("buy_price", contract.amount))
        if status == "won":
            payout = float(contract_data.get("payout", 0))
            profit, contract.status = payout - buy_price, ContractStatus.WON
        else:
            profit, contract.status = -buy_price, ContractStatus.LOST
        contract.profit, contract.end_time = profit, self.synced_time
        if self._all_contracts_finished(asset_state):
            self._process_sequence_result(asset_state)
    
    def _all_contracts_finished(self, asset_state: AssetState) -> bool:
        return all(contract.is_finished for contract in asset_state.active_contracts)
    
    def _process_sequence_result(self, asset_state: AssetState):
        if not asset_state.active_contracts: return
        
        # Log dos resultados individuais
        for contract in asset_state.active_contracts:
            profit = contract.profit
            forced_text = " (TEMPORÁRIO)" if getattr(contract, 'forced_result', False) else ""
            log_msg = (f"{'✅' if profit >= 0 else '❌'} {asset_state.symbol} {contract.type} "
                       f"{'GANHOU' if profit >= 0 else 'PERDEU'}: ${profit:+.2f}{forced_text}")
            logger.info(log_msg)
        
        # Processar resultado da operação
        total_profit = sum(contract.profit for contract in asset_state.active_contracts)
        won = any(c.profit > 0 for c in asset_state.active_contracts) if self.config.DUAL_ENTRY else total_profit > 0
        
        # Processar resultado normalmente
        self._process_operation_result(asset_state, won, total_profit)
        
        asset_state.clear_finished_contracts()
        self.has_any_active_operation = False
        self.current_operating_symbol = None
    
    def _process_operation_result(self, asset_state: AssetState, won: bool, profit: float):
        # CORREÇÃO: Passar initial_balance para martingale se necessário
        if hasattr(self.risk_manager, '__class__') and 'MartingaleRisk' in self.risk_manager.__class__.__name__:
            sequence_is_over = self.risk_manager.process_operation_result(asset_state, won, profit, self.initial_balance)
        else:
            sequence_is_over = self.risk_manager.process_operation_result(asset_state, won, profit)
        
        # Atualizar estatísticas da sessão
        self.session_stats.add_operation_result(asset_state.symbol, won, profit, asset_state.current_sequence)
        
        # Atualizar saldo
        self.balance += profit
        self.session_stats.current_balance = self.balance
        
        if sequence_is_over:
            self._put_asset_in_cooldown(asset_state)
            self._log_session_summary()
    
    async def _process_balance_update(self, balance_data: Dict[str, Any]):
        new_balance = float(balance_data["balance"])
        if abs(new_balance - self.balance) > 0.01:
            self.balance = new_balance
            self.session_stats.current_balance = new_balance
    
    async def _process_api_error(self, error_data: Dict[str, Any]):
        error_msg, error_code = error_data.get("message", "Erro desconhecido"), error_data.get("code", "unknown")
        logger.error(f"🚨 Erro da API [{error_code}]: {error_msg}")
        if error_code in ["InvalidToken", "AuthorizationRequired"]:
            if not self.reconnection_system.is_reconnecting:
                await self._handle_disconnection()
    
    def _is_asset_busy(self, asset_state: AssetState) -> bool:
        if asset_state.in_cooldown and self.synced_time >= asset_state.cooldown_end_time:
            asset_state.in_cooldown = False
            logger.info(f"✅ {asset_state.symbol}: Cooldown finalizado.")
        return asset_state.in_cooldown or asset_state.has_active_contracts
    
    def _check_signal_debounce(self, symbol: str) -> bool:
        return (self.synced_time - self.last_signal_times.get(symbol, 0)) >= self.signal_debounce
    
    def _put_asset_in_cooldown(self, asset_state: AssetState):
        if self.config.COOLDOWN_MINUTES > 0:
            asset_state.in_cooldown = True
            asset_state.cooldown_end_time = self.synced_time + (self.config.COOLDOWN_MINUTES * 60)
            logger.info(f"🧊 {asset_state.symbol}: Cooldown por {self.config.COOLDOWN_MINUTES}min")
    
    def _has_active_contracts(self) -> bool:
        return any(state.has_active_contracts for state in self.asset_states.values())
    
    async def _subscribe_to_contract(self, contract_id: str):
        try:
            request = {"proposal_open_contract": 1, "contract_id": int(contract_id), "subscribe": 1}
            await self.websocket_manager.send_message(request)
        except Exception as e:
            logger.warning(f"⚠️ Erro inscrevendo contrato {contract_id}: {e}")
    
    async def _update_balance(self):
        response = await self.websocket_manager.send_request({"balance": 1}, timeout=10)
        if response and "balance" in response:
            self.balance = float(response["balance"]["balance"])
    
    def _log_bot_configuration(self):
        logger.info("=" * 70)
        logger.info("🤖 TRADING BOT MODULAR - CONFIGURAÇÃO")
        logger.info("=" * 70)
        logger.info(f"📊 Ativos: {', '.join(self.config.SYMBOLS)}")
        logger.info(f"⏰ Timeframe: M{self.config.ANALYSIS_TIMEFRAME} | Exp: {self.config.DURATION}{self.config.DURATION_UNIT}")
        logger.info(f"💰 Risk Management: {self.config.RISK_MANAGEMENT_TYPE}")
        logger.info(f"🔄 Dual Entry: {'✅' if self.config.DUAL_ENTRY else '❌'}")
        logger.info(f"🛑 Stop Loss: ${self.config.STOP_LOSS_VALUE} | Stop Win: ${self.config.STOP_WIN_VALUE}")
        logger.info(f"🕯️ Estratégia: Candle Pattern ({self.strategy.get_active_confluences_count()} confluências)")
        logger.info(f"🎯 Controle de Ativos: APENAS 1 ATIVO SIMULTÂNEO")
        logger.info(f"🔄 Recuperação de Contratos: HABILITADA")
        logger.info(f"🚨 Sistema de Reconexão: PERSISTENTE (NUNCA DESISTE)")
        logger.info("=" * 70)
    
    def _log_session_summary(self):
        profit = self.balance - self.initial_balance
        profit_pct = (profit / self.initial_balance * 100) if self.initial_balance > 0 else 0
        logger.info("=" * 70)
        logger.info("📊 RESUMO DA SESSÃO:")
        logger.info(f"   💰 Saldo: ${self.initial_balance:.2f} → ${self.balance:.2f} ({profit:+.2f} | {profit_pct:+.2f}%)")
        logger.info(f"   🎯 Operações: {self.session_stats.operations_total} | WR: {self.session_stats.win_rate:.1f}%")
        logger.info(f"   ⏱️ Sessão: {self.session_stats.session_duration_formatted}")
        logger.info("=" * 70)
    
    async def _cleanup(self):
        logger.info("🧹 Finalizando bot...")
        self.is_running = False
        tasks_to_cancel = [self.main_task, self.result_checker_task]
        for task in tasks_to_cancel:
            if task and not task.done():
                task.cancel()
        await asyncio.sleep(0.1)
        if self.websocket_manager.is_connected:
            await self.websocket_manager.disconnect()
        if self.session_stats.operations_total > 0:
            self._log_session_summary()
        logger.info("👋 Trading Bot finalizado")