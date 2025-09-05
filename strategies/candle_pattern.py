# -*- coding: utf-8 -*-
"""
Candle Pattern Strategy - Estratégia de Padrões de Candles
VERSÃO FINAL COM LÓGICA DE VERIFICAÇÃO DO CÓDIGO MONOLÍTICO
"""

import time
from typing import List, Optional, Tuple, Dict, Any
from core.data_models import CandleData, SignalData, SignalDirection
from utils.logger import get_logger

logger = get_logger(__name__)

class CandlePatternStrategy:
    """Estratégia de Padrão de Candles com a lógica original e funcional"""
    
    def __init__(self, config):
        self.config = config
        self.call_patterns = self._load_color_pattern('CALL')
        self.put_patterns = self._load_color_pattern('PUT')
        self.initial_analysis_complete = False
        self.ma_enabled = config.CANDLE_FILTER_MA_ENABLED
        self.ma_type = config.CANDLE_FILTER_MA_TYPE
        self.ma_period = config.CANDLE_FILTER_MA_PERIOD
        self.ma_condition = config.CANDLE_FILTER_MA_CONDITION
        self.min_size_enabled = config.CANDLE_FILTER_MIN_SIZE_ENABLED
        self.min_size_points = config.CANDLE_FILTER_MIN_SIZE_POINTS
        self.min_size_type = config.CANDLE_FILTER_MIN_SIZE_TYPE
        self.min_size_candles = config.CANDLE_FILTER_MIN_SIZE_CANDLES
        self.max_wick_enabled = config.CANDLE_FILTER_MAX_WICK_ENABLED
        self.max_wick_upper = config.CANDLE_FILTER_MAX_WICK_UPPER
        self.max_wick_lower = config.CANDLE_FILTER_MAX_WICK_LOWER
        self.max_wick_candles = config.CANDLE_FILTER_MAX_WICK_CANDLES
        self.body_ratio_enabled = config.CANDLE_FILTER_BODY_RATIO_ENABLED
        self.body_ratio_min = config.CANDLE_FILTER_BODY_RATIO_MIN
        self.body_ratio_candles = config.CANDLE_FILTER_BODY_RATIO_CANDLES
        self._log_strategy_config()
    
    def _load_color_pattern(self, signal_type: str) -> List[str]:
        pattern = []
        for i in range(1, 11):
            color = getattr(self.config, f'{signal_type}_CANDLE_{i}', 'ANY').upper()
            if color != 'ANY':
                pattern.append(color)
            else:
                break
        return pattern

    def _log_strategy_config(self):
        active_confluences = []
        if self.ma_enabled: active_confluences.append(f"MA({self.ma_type}{self.ma_period})")
        if self.min_size_enabled: active_confluences.append(f"MinSize({self.min_size_points}pts)")
        if self.max_wick_enabled: active_confluences.append(f"MaxWick({self.max_wick_upper}%)")
        if self.body_ratio_enabled: active_confluences.append(f"BodyRatio({self.body_ratio_min}%)")
        logger.info("🕯️ ESTRATÉGIA CANDLE PATTERN (LÓGICA ORIGINAL) CONFIGURADA:")
        logger.info(f"   📈 CALL: {' → '.join(self.call_patterns)}")
        logger.info(f"   📉 PUT: {' → '.join(self.put_patterns)}")
        logger.info(f"   🔀 Confluências: {', '.join(active_confluences) if active_confluences else 'Nenhuma'}")
        logger.info(f"   ✅ Vela 1 = mais recente | Vela 2 = penúltima")

    def analyze_signal(self, symbol: str, candles: List[CandleData], bot_start_time: float, current_synced_time: float) -> Optional[SignalData]:
        if not self.initial_analysis_complete:
            self.initial_analysis_complete = True
            if candles and (candles[-1].timestamp + self.config.analysis_timeframe_seconds < bot_start_time):
                return None

        if not candles or len(candles) < 2:
            return None
        
        closed_candles = candles[:-1]

        is_match, matched_colors = self._check_pattern_original(closed_candles, self.call_patterns)
        if is_match:
            return SignalData(
                symbol=symbol, direction=SignalDirection.CALL, timestamp=current_synced_time,
                pattern_matched=matched_colors
            )
            
        is_match, matched_colors = self._check_pattern_original(closed_candles, self.put_patterns)
        if is_match:
            return SignalData(
                symbol=symbol, direction=SignalDirection.PUT, timestamp=current_synced_time,
                pattern_matched=matched_colors
            )
            
        return None

    def _check_pattern_original(self, closed_candles: List[CandleData], pattern: List[str]) -> Tuple[bool, List[str]]:
        specific_pattern = [p for p in pattern if p != 'ANY']
        if not specific_pattern:
            return False, []

        if len(closed_candles) < len(specific_pattern):
            return False, []
        
        recent_candles = closed_candles[-len(specific_pattern):]
        
        actual_candle_colors = []
        
        for i, expected_color in enumerate(specific_pattern):
            candle_index = -(i + 1)
            candle = recent_candles[candle_index]
            actual_candle_colors.append(candle.color_str)
            
            if (expected_color == 'GREEN' and not candle.is_green) or \
               (expected_color == 'RED' and not candle.is_red):
                return False, []
                
        return True, actual_candle_colors[::-1]

    # As funções abaixo são mantidas para integridade do arquivo, caso você reative os filtros.
    def _check_moving_average_filter(self, candles: List[CandleData], signal_type: str) -> bool:
        if len(candles) < self.ma_period + 1: return False
        try:
            close_prices = [c.close_price for c in reversed(candles[:self.ma_period+1])]
            ma_value = self._calculate_sma(close_prices, self.ma_period) if self.ma_type == 'SMA' else self._calculate_ema(close_prices, self.ma_period)
            if not ma_value: return False
            current_price = candles[0].close_price
            if self.ma_condition == 'ABOVE': return current_price > ma_value if signal_type == 'CALL' else current_price < ma_value
            elif self.ma_condition == 'BELOW': return current_price < ma_value if signal_type == 'CALL' else current_price > ma_value
            return False
        except Exception: return False

    def _calculate_sma(self, prices: List[float], period: int) -> float:
        if len(prices) < period: return 0.0
        return sum(prices[-period:]) / period
    
    def _calculate_ema(self, prices: List[float], period: int) -> float:
        if len(prices) < period: return 0.0
        multiplier = 2.0 / (period + 1.0)
        ema = prices[0]
        for price in prices[1:]: ema = (price * multiplier) + (ema * (1.0 - multiplier))
        return ema

    def _check_minimum_size_filter(self, candles: List[CandleData]) -> bool:
        try:
            for candle_index in self.min_size_candles:
                if not (0 < candle_index <= len(candles)): continue
                candle = candles[candle_index - 1]
                size = candle.body_size if self.min_size_type == 'BODY' else candle.total_size
                min_size_value = self.min_size_points * 0.0001
                if size < min_size_value: return False
            return True
        except Exception: return False
    
    def _check_wick_filter(self, candles: List[CandleData]) -> bool:
        try:
            for candle_index in self.max_wick_candles:
                if not (0 < candle_index <= len(candles)): continue
                candle = candles[candle_index - 1]
                if candle.upper_wick_percentage > self.max_wick_upper: return False
                if candle.lower_wick_percentage > self.max_wick_lower: return False
            return True
        except Exception: return False
    
    def _check_body_ratio_filter(self, candles: List[CandleData]) -> bool:
        try:
            for candle_index in self.body_ratio_candles:
                if not (0 < candle_index <= len(candles)): continue
                candle = candles[candle_index - 1]
                if candle.body_ratio_percentage < self.body_ratio_min: return False
            return True
        except Exception: return False
    
    def _calculate_confidence(self, filters_passed_count: int, pattern_length: int) -> float:
        base_confidence = 50.0
        additional_filters = filters_passed_count - 1
        filter_bonus = additional_filters * 10.0
        pattern_bonus = min(pattern_length * 5.0, 20.0)
        total_confidence = base_confidence + filter_bonus + pattern_bonus
        return min(100.0, total_confidence)

    def get_strategy_info(self) -> Dict[str, Any]:
        active_confluences = []
        if self.ma_enabled: active_confluences.append({'name': 'moving_average', 'config': f"{self.ma_type}{self.ma_period} {self.ma_condition}"})
        if self.min_size_enabled: active_confluences.append({'name': 'minimum_size', 'config': f"{self.min_size_points}pts {self.min_size_type}"})
        if self.max_wick_enabled: active_confluences.append({'name': 'maximum_wick', 'config': f"Upper:{self.max_wick_upper}% Lower:{self.max_wick_lower}%"})
        if self.body_ratio_enabled: active_confluences.append({'name': 'body_ratio', 'config': f"Min:{self.body_ratio_min}%"})
        return {'name': 'Candle Pattern Strategy', 'call_pattern': self.call_patterns, 'put_pattern': self.put_patterns, 'confluences': active_confluences, 'total_confluences': len(active_confluences)}
    
    def get_active_confluences_count(self) -> int:
        count = 0
        if self.ma_enabled: count += 1
        if self.min_size_enabled: count += 1
        if self.max_wick_enabled: count += 1
        if self.body_ratio_enabled: count += 1
        return count

    def validate_configuration(self) -> List[str]:
        errors = []
        if not self.call_patterns and not self.put_patterns: errors.append("Nenhum padrão de cores configurado")
        if self.ma_enabled:
            if self.ma_period <= 0: errors.append("Período da média móvel deve ser maior que 0")
            if self.ma_condition not in ['ABOVE', 'BELOW', 'CROSS_UP', 'CROSS_DOWN']: errors.append("Condição da média móvel inválida")
        return errors