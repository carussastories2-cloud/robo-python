# -*- coding: utf-8 -*-
"""
Data Models - Estruturas de Dados do Sistema
Centraliza todas as estruturas de dados utilizadas no trading bot
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from collections import deque
import time
from enum import Enum

class SignalDirection(Enum):
    """Direções de sinal"""
    CALL = "CALL"
    PUT = "PUT"

class ContractStatus(Enum):
    """Status de contratos"""
    OPEN = "open"
    WON = "won"
    LOST = "lost"
    SOLD = "sold"
    FINISHED = "finished"

class RiskManagementType(Enum):
    """Tipos de gerenciamento de risco"""
    FIXED_AMOUNT = "FIXED_AMOUNT"
    MARTINGALE = "MARTINGALE"

class MartingaleType(Enum):
    """Tipos de martingale"""
    IMMEDIATE = "IMMEDIATE"
    NEXT_CANDLE = "NEXT_CANDLE"

@dataclass
class TickData:
    """Dados de tick para análise técnica"""
    timestamp: float
    price: float
    symbol: str = ""
    
    @property
    def datetime_str(self) -> str:
        """Retorna timestamp formatado"""
        return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.timestamp))

@dataclass
class CandleData:
    """Dados de candle para análise"""
    timestamp: float
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: int = 0
    symbol: str = ""
    
    @property
    def is_green(self) -> bool:
        """Verifica se é vela verde (alta)"""
        return self.close_price > self.open_price
    
    @property
    def is_red(self) -> bool:
        """Verifica se é vela vermelha (baixa)"""
        return self.close_price < self.open_price
    
    @property
    def is_doji(self) -> bool:
        """Verifica se é doji (abertura = fechamento)"""
        return abs(self.close_price - self.open_price) < 0.00001
    
    @property
    def color_str(self) -> str:
        """Retorna cor da vela como string"""
        if self.is_green: return "GREEN"
        if self.is_red: return "RED"
        return "DOJI"
    
    @property
    def body_size(self) -> float:
        """Tamanho do corpo da vela"""
        return abs(self.close_price - self.open_price)
    
    @property
    def total_size(self) -> float:
        """Tamanho total da vela (com pavios)"""
        return self.high_price - self.low_price
    
    @property
    def upper_wick_size(self) -> float:
        """Tamanho do pavio superior"""
        return self.high_price - max(self.open_price, self.close_price)
    
    @property
    def lower_wick_size(self) -> float:
        """Tamanho do pavio inferior"""
        return min(self.open_price, self.close_price) - self.low_price
    
    @property
    def upper_wick_percentage(self) -> float:
        """Percentual do pavio superior em relação ao corpo"""
        if self.body_size == 0:
            return 0.0
        return (self.upper_wick_size / self.body_size) * 100
    
    @property
    def lower_wick_percentage(self) -> float:
        """Percentual do pavio inferior em relação ao corpo"""
        if self.body_size == 0:
            return 0.0
        return (self.lower_wick_size / self.body_size) * 100
    
    @property
    def body_ratio_percentage(self) -> float:
        """Percentual do corpo em relação ao tamanho total"""
        if self.total_size == 0:
            return 0.0
        return (self.body_size / self.total_size) * 100

@dataclass
class SignalData:
    """Dados de um sinal detectado"""
    symbol: str
    direction: SignalDirection
    timestamp: float
    confidence: float = 0.0
    pattern_matched: List[str] = field(default_factory=list)
    filters_passed: List[str] = field(default_factory=list)
    source: str = "CANDLE_PATTERN"
    processed: bool = False
    candles_analyzed: int = 0
    
    @property
    def age_seconds(self) -> float:
        """Idade do sinal em segundos"""
        return time.time() - self.timestamp
    
    @property
    def is_valid(self) -> bool:
        """Verifica se sinal ainda é válido"""
        return not self.processed and self.age_seconds < 60.0

@dataclass
class ContractInfo:
    """Informações de um contrato ativo"""
    id: str
    symbol: str
    type: str
    amount: float
    status: ContractStatus = ContractStatus.OPEN
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    profit: float = 0.0
    payout: float = 0.0
    buy_price: float = 0.0
    sell_price: float = 0.0
    entry_price: float = 0.0
    exit_price: float = 0.0
    martingale_level: int = 0
    forced_result: bool = False
    
    @property
    def duration_seconds(self) -> float:
        """Duração do contrato em segundos"""
        end = self.end_time or time.time()
        return end - self.start_time
    
    @property
    def is_finished(self) -> bool:
        """Verifica se contrato está finalizado"""
        return self.status in [ContractStatus.WON, ContractStatus.LOST, ContractStatus.SOLD, ContractStatus.FINISHED]
    
    @property
    def is_winner(self) -> bool:
        """Verifica se contrato é ganhador"""
        return self.status == ContractStatus.WON or self.profit > 0

@dataclass
class AssetState:
    """Estado de um ativo individual"""
    symbol: str
    current_sequence: int = 1
    in_cooldown: bool = False
    cooldown_end_time: float = 0
    active_contracts: List[ContractInfo] = field(default_factory=list)
    balance_before_operation: float = 0
    loss_accumulator: float = 0.0
    
    # Direção original da sequência de martingale
    last_entry_direction: str = ""
    
    # Campos para recuperação de contratos e martingale
    initial_balance_for_sequence: float = 0.0  # Saldo inicial da sequência atual  
    forced_total_loss: Optional[float] = None  # Total forçado como perda (para correção)
    
    last_signal_time: float = 0
    last_signal_reason: str = ""
    current_call_direction: str = "CALL"
    current_put_direction: str = "PUT"
    tick_cache: deque = field(default_factory=lambda: deque(maxlen=1000))
    candle_cache: deque = field(default_factory=lambda: deque(maxlen=200))
    total_operations: int = 0
    won_operations: int = 0
    lost_operations: int = 0
    total_profit: float = 0.0
    best_sequence: int = 1
    worst_sequence: int = 1
    
    @property
    def win_rate(self) -> float:
        if self.total_operations == 0:
            return 0.0
        return (self.won_operations / self.total_operations) * 100
    
    @property
    def has_active_contracts(self) -> bool:
        return any(not contract.is_finished for contract in self.active_contracts)
    
    @property
    def active_contracts_count(self) -> int:
        return sum(1 for contract in self.active_contracts if not contract.is_finished)
    
    def add_tick(self, tick: TickData):
        self.tick_cache.append(tick)
    
    def add_candle(self, candle: CandleData):
        self.candle_cache.append(candle)
    
    def get_recent_candles(self, count: int) -> List[CandleData]:
        candles = list(self.candle_cache)
        return candles[-count:] if len(candles) >= count else candles
    
    def clear_finished_contracts(self):
        self.active_contracts = [c for c in self.active_contracts if not c.is_finished]

@dataclass
class SessionStats:
    start_time: float = field(default_factory=time.time)
    operations_total: int = 0
    operations_won: int = 0
    operations_lost: int = 0
    contracts_total: int = 0
    contracts_won: int = 0
    contracts_lost: int = 0
    initial_balance: float = 0.0
    current_balance: float = 0.0
    total_profit: float = 0.0
    best_profit: float = 0.0
    worst_loss: float = 0.0
    max_sequence_reached: int = 1
    total_martingale_sequences: int = 0
    asset_stats: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    @property
    def session_duration_seconds(self) -> float:
        return time.time() - self.start_time
    
    @property
    def session_duration_formatted(self) -> str:
        duration = int(self.session_duration_seconds)
        hours, remainder = divmod(duration, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0: return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0: return f"{minutes}m {seconds}s"
        else: return f"{seconds}s"
    
    @property
    def win_rate(self) -> float:
        if self.operations_total == 0: return 0.0
        return (self.operations_won / self.operations_total) * 100
    
    @property
    def profit_percentage(self) -> float:
        if self.initial_balance == 0: return 0.0
        return ((self.current_balance - self.initial_balance) / self.initial_balance) * 100
    
    def add_operation_result(self, symbol: str, won: bool, profit: float, sequence_level: int):
        self.operations_total += 1
        if won: self.operations_won += 1
        else: self.operations_lost += 1
        self.total_profit += profit
        if profit > self.best_profit: self.best_profit = profit
        if profit < self.worst_loss: self.worst_loss = profit
        if sequence_level > self.max_sequence_reached: self.max_sequence_reached = sequence_level
        if symbol not in self.asset_stats:
            self.asset_stats[symbol] = {'operations': 0, 'wins': 0, 'losses': 0, 'profit': 0.0, 'best_sequence': 1}
        asset_stat = self.asset_stats[symbol]
        asset_stat['operations'] += 1
        asset_stat['profit'] += profit
        if won: asset_stat['wins'] += 1
        else: asset_stat['losses'] += 1
        if sequence_level > asset_stat['best_sequence']: asset_stat['best_sequence'] = sequence_level

@dataclass
class ConnectionState:
    is_connected: bool = False
    is_stable: bool = False
    last_ping_time: float = 0
    last_message_time: float = 0
    reconnection_attempts: int = 0
    connection_start_time: float = 0
    average_latency: float = 0.0
    message_count: int = 0
    error_count: int = 0
    monitored_contracts: Dict[str, ContractInfo] = field(default_factory=dict)
    lost_contracts: List[str] = field(default_factory=list)

@dataclass
class CandlePatternConfig:
    call_pattern: List[str] = field(default_factory=list)
    put_pattern: List[str] = field(default_factory=list)
    ma_enabled: bool = False
    ma_type: str = "SMA"
    ma_period: int = 20
    ma_condition: str = "ABOVE"
    min_size_enabled: bool = False
    min_size_points: float = 5
    min_size_type: str = "BODY"
    min_size_candles: List[int] = field(default_factory=lambda: [1])
    max_wick_enabled: bool = False
    max_wick_upper: float = 30
    max_wick_lower: float = 30
    max_wick_candles: List[int] = field(default_factory=lambda: [1, 2])
    body_ratio_enabled: bool = False
    body_ratio_min: float = 60
    body_ratio_candles: List[int] = field(default_factory=lambda: [1, 2])

@dataclass
class RiskManagementConfig:
    type: RiskManagementType = RiskManagementType.FIXED_AMOUNT
    initial_amount: float = 0.35
    min_amount: float = 0.35
    max_amount: float = 2000.0
    martingale_type: MartingaleType = MartingaleType.IMMEDIATE
    martingale_multiplier: float = 2.0
    martingale_max_sequence: int = 2
    stop_loss_value: float = 100.0
    stop_win_value: float = 100.0
    stop_loss_type: str = "FIXED"
    stop_win_type: str = "FIXED"