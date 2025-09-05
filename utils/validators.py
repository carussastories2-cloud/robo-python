# -*- coding: utf-8 -*-
"""
Validators - Utils Module
"""

# TODO: Implementar validators
# -*- coding: utf-8 -*-
"""
Validators - Validações do Sistema
Funções para validar dados e configurações
"""

import re
import time
from typing import Any, Dict, List, Optional, Union
from core.data_models import SignalData, ContractInfo, CandleData

def validate_signal(signal_data: Dict[str, Any]) -> bool:
    """
    Valida dados de um sinal
    
    Args:
        signal_data: Dados do sinal para validar
        
    Returns:
        bool: True se válido, False caso contrário
    """
    try:
        # Campos obrigatórios
        required_fields = ['symbol', 'direction', 'timestamp']
        for field in required_fields:
            if field not in signal_data:
                return False
        
        # Validar símbolo
        if not isinstance(signal_data['symbol'], str) or len(signal_data['symbol']) < 3:
            return False
        
        # Validar direção
        if signal_data['direction'] not in ['CALL', 'PUT']:
            return False
        
        # Validar timestamp
        timestamp = signal_data['timestamp']
        if not isinstance(timestamp, (int, float)) or timestamp <= 0:
            return False
        
        # Timestamp não pode ser muito antigo (mais de 1 hora)
        current_time = time.time()
        if current_time - timestamp > 3600:
            return False
        
        # Timestamp não pode ser do futuro (mais de 5 minutos)
        if timestamp - current_time > 300:
            return False
        
        # Validar confiança (opcional)
        if 'confidence' in signal_data:
            confidence = signal_data['confidence']
            if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 100:
                return False
        
        return True
        
    except Exception:
        return False

def validate_symbol(symbol: str) -> bool:
    """
    Valida formato de símbolo
    
    Args:
        symbol: Símbolo para validar
        
    Returns:
        bool: True se válido, False caso contrário
    """
    if not isinstance(symbol, str):
        return False
    
    # Símbolos devem ter pelo menos 3 caracteres
    if len(symbol) < 3:
        return False
    
    # Símbolos comuns da Deriv
    valid_patterns = [
        r'^[A-Z]{3,6}$',           # Forex: EURUSD, GBPJPY
        r'^stpRNG\d+$',            # Synthetics: stpRNG5, stpRNG10
        r'^R_\d+$',                # Volatility: R_10, R_25
        r'^BOOM\d+$',              # Boom: BOOM1000
        r'^CRASH\d+$',             # Crash: CRASH500
        r'^[A-Z]+\d*$',            # Outros: BTC, US30
    ]
    
    return any(re.match(pattern, symbol) for pattern in valid_patterns)

def validate_amount(amount: Union[int, float], min_amount: float = 0.35, max_amount: float = 2000.0) -> bool:
    """
    Valida valor de entrada
    
    Args:
        amount: Valor para validar
        min_amount: Valor mínimo permitido
        max_amount: Valor máximo permitido
        
    Returns:
        bool: True se válido, False caso contrário
    """
    try:
        amount = float(amount)
        return min_amount <= amount <= max_amount
    except (ValueError, TypeError):
        return False

def validate_contract_id(contract_id: str) -> bool:
    """
    Valida ID de contrato
    
    Args:
        contract_id: ID do contrato para validar
        
    Returns:
        bool: True se válido, False caso contrário
    """
    if not isinstance(contract_id, str):
        return False
    
    # IDs de contrato da Deriv são números longos
    if not contract_id.isdigit():
        return False
    
    # Devem ter pelo menos 8 dígitos
    if len(contract_id) < 8:
        return False
    
    return True

def validate_timeframe(timeframe: int) -> bool:
    """
    Valida timeframe de análise
    
    Args:
        timeframe: Timeframe em minutos
        
    Returns:
        bool: True se válido, False caso contrário
    """
    valid_timeframes = [1, 5, 15, 30, 60, 240, 1440]  # M1, M5, M15, M30, H1, H4, D1
    return timeframe in valid_timeframes

def validate_duration(duration: int, duration_unit: str) -> bool:
    """
    Valida duração de expiração
    
    Args:
        duration: Duração numérica
        duration_unit: Unidade (t, s, m)
        
    Returns:
        bool: True se válido, False caso contrário
    """
    if not isinstance(duration, int) or duration <= 0:
        return False
    
    if duration_unit not in ['t', 's', 'm']:
        return False
    
    # Limites por unidade
    limits = {
        't': (1, 10),      # 1 a 10 ticks
        's': (15, 3600),   # 15 segundos a 1 hora
        'm': (1, 1440)     # 1 minuto a 1 dia
    }
    
    min_val, max_val = limits[duration_unit]
    return min_val <= duration <= max_val

def validate_candle_data(candle: CandleData) -> bool:
    """
    Valida dados de uma vela
    
    Args:
        candle: Dados da vela para validar
        
    Returns:
        bool: True se válido, False caso contrário
    """
    try:
        # Preços devem ser positivos
        if any(price <= 0 for price in [candle.open_price, candle.high_price, candle.low_price, candle.close_price]):
            return False
        
        # High deve ser o maior preço
        if candle.high_price < max(candle.open_price, candle.close_price):
            return False
        
        # Low deve ser o menor preço
        if candle.low_price > min(candle.open_price, candle.close_price):
            return False
        
        # Timestamp deve ser válido
        if candle.timestamp <= 0:
            return False
        
        return True
        
    except (AttributeError, TypeError):
        return False

def validate_candle_pattern(pattern: List[str]) -> bool:
    """
    Valida padrão de cores de velas
    
    Args:
        pattern: Lista com cores das velas
        
    Returns:
        bool: True se válido, False caso contrário
    """
    if not isinstance(pattern, list) or len(pattern) == 0:
        return False
    
    valid_colors = ['RED', 'GREEN', 'ANY']
    
    # Todas as cores devem ser válidas
    if not all(color in valid_colors for color in pattern):
        return False
    
    # Deve ter pelo menos uma cor específica (não só ANY)
    if all(color == 'ANY' for color in pattern):
        return False
    
    # Máximo 10 velas
    if len(pattern) > 10:
        return False
    
    return True

def validate_confluence_config(config: Dict[str, Any]) -> List[str]:
    """
    Valida configurações de confluências
    
    Args:
        config: Dicionário com configurações
        
    Returns:
        List[str]: Lista de erros encontrados (vazia se válido)
    """
    errors = []
    
    # Validar filtro de média móvel
    if config.get('CANDLE_FILTER_MA_ENABLED', False):
        ma_type = config.get('CANDLE_FILTER_MA_TYPE', 'SMA')
        if ma_type not in ['SMA', 'EMA']:
            errors.append("CANDLE_FILTER_MA_TYPE deve ser SMA ou EMA")
        
        ma_period = config.get('CANDLE_FILTER_MA_PERIOD', 20)
        if not isinstance(ma_period, int) or ma_period < 2 or ma_period > 200:
            errors.append("CANDLE_FILTER_MA_PERIOD deve ser entre 2 e 200")
        
        ma_condition = config.get('CANDLE_FILTER_MA_CONDITION', 'ABOVE')
        if ma_condition not in ['ABOVE', 'BELOW', 'CROSS_UP', 'CROSS_DOWN']:
            errors.append("CANDLE_FILTER_MA_CONDITION deve ser ABOVE, BELOW, CROSS_UP ou CROSS_DOWN")
    
    # Validar filtro de tamanho
    if config.get('CANDLE_FILTER_MIN_SIZE_ENABLED', False):
        min_size = config.get('CANDLE_FILTER_MIN_SIZE_POINTS', 5)
        if not isinstance(min_size, (int, float)) or min_size <= 0:
            errors.append("CANDLE_FILTER_MIN_SIZE_POINTS deve ser maior que 0")
        
        size_type = config.get('CANDLE_FILTER_MIN_SIZE_TYPE', 'BODY')
        if size_type not in ['BODY', 'TOTAL']:
            errors.append("CANDLE_FILTER_MIN_SIZE_TYPE deve ser BODY ou TOTAL")
    
    # Validar filtro de pavio
    if config.get('CANDLE_FILTER_MAX_WICK_ENABLED', False):
        upper_wick = config.get('CANDLE_FILTER_MAX_WICK_UPPER', 30)
        if not isinstance(upper_wick, (int, float)) or upper_wick < 0 or upper_wick > 1000:
            errors.append("CANDLE_FILTER_MAX_WICK_UPPER deve ser entre 0 e 1000")
        
        lower_wick = config.get('CANDLE_FILTER_MAX_WICK_LOWER', 30)
        if not isinstance(lower_wick, (int, float)) or lower_wick < 0 or lower_wick > 1000:
            errors.append("CANDLE_FILTER_MAX_WICK_LOWER deve ser entre 0 e 1000")
    
    # Validar filtro de proporção
    if config.get('CANDLE_FILTER_BODY_RATIO_ENABLED', False):
        body_ratio = config.get('CANDLE_FILTER_BODY_RATIO_MIN', 60)
        if not isinstance(body_ratio, (int, float)) or body_ratio < 0 or body_ratio > 100:
            errors.append("CANDLE_FILTER_BODY_RATIO_MIN deve ser entre 0 e 100")
    
    return errors

def validate_risk_management_config(config: Dict[str, Any]) -> List[str]:
    """
    Valida configurações de gerenciamento de risco
    
    Args:
        config: Dicionário com configurações
        
    Returns:
        List[str]: Lista de erros encontrados (vazia se válido)
    """
    errors = []
    
    # Tipo de gerenciamento
    risk_type = config.get('RISK_MANAGEMENT_TYPE', 'FIXED_AMOUNT')
    if risk_type not in ['FIXED_AMOUNT', 'MARTINGALE']:
        errors.append("RISK_MANAGEMENT_TYPE deve ser FIXED_AMOUNT ou MARTINGALE")
    
    # Valores base
    initial_amount = config.get('INITIAL_AMOUNT', 0.35)
    if not isinstance(initial_amount, (int, float)) or initial_amount <= 0:
        errors.append("INITIAL_AMOUNT deve ser maior que 0")
    
    min_amount = config.get('MIN_AMOUNT', 0.35)
    if not isinstance(min_amount, (int, float)) or min_amount <= 0:
        errors.append("MIN_AMOUNT deve ser maior que 0")
    
    max_amount = config.get('MAX_AMOUNT', 2000)
    if not isinstance(max_amount, (int, float)) or max_amount <= min_amount:
        errors.append("MAX_AMOUNT deve ser maior que MIN_AMOUNT")
    
    # Configurações de martingale
    if risk_type == 'MARTINGALE':
        martingale_type = config.get('MARTINGALE_TYPE', 'IMMEDIATE')
        if martingale_type not in ['IMMEDIATE', 'NEXT_CANDLE']:
            errors.append("MARTINGALE_TYPE deve ser IMMEDIATE ou NEXT_CANDLE")
        
        multiplier = config.get('MARTINGALE_MULTIPLIER', 2.0)
        if not isinstance(multiplier, (int, float)) or multiplier <= 1.0 or multiplier > 10.0:
            errors.append("MARTINGALE_MULTIPLIER deve ser entre 1.0 e 10.0")
        
        max_sequence = config.get('MARTINGALE_MAX_SEQUENCE', 2)
        if not isinstance(max_sequence, int) or max_sequence < 1 or max_sequence > 10:
            errors.append("MARTINGALE_MAX_SEQUENCE deve ser entre 1 e 10")
    
    # Stop conditions
    stop_loss = config.get('STOP_LOSS_VALUE', 100)
    if not isinstance(stop_loss, (int, float)) or stop_loss <= 0:
        errors.append("STOP_LOSS_VALUE deve ser maior que 0")
    
    stop_win = config.get('STOP_WIN_VALUE', 100)
    if not isinstance(stop_win, (int, float)) or stop_win <= 0:
        errors.append("STOP_WIN_VALUE deve ser maior que 0")
    
    return errors

def validate_api_token(token: str) -> bool:
    """
    Valida formato básico do token da API Deriv
    
    Args:
        token: Token para validar
        
    Returns:
        bool: True se válido, False caso contrário
    """
    if not isinstance(token, str):
        return False
    
    # Token deve ter pelo menos 10 caracteres
    if len(token) < 10:
        return False
    
    # Token deve conter apenas caracteres alfanuméricos e alguns símbolos
    if not re.match(r'^[a-zA-Z0-9_-]+$', token):
        return False
    
    return True

def sanitize_symbol(symbol: str) -> str:
    """
    Sanitiza símbolo removendo caracteres inválidos
    
    Args:
        symbol: Símbolo para sanitizar
        
    Returns:
        str: Símbolo sanitizado
    """
    if not isinstance(symbol, str):
        return ""
    
    # Remover espaços e converter para maiúsculo
    symbol = symbol.strip().upper()
    
    # Manter apenas caracteres alfanuméricos e underscore
    symbol = re.sub(r'[^A-Z0-9_]', '', symbol)
    
    return symbol

def validate_config(settings_dict: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    Valida todas as configurações do sistema
    
    Args:
        settings_dict: Dicionário com todas as configurações
        
    Returns:
        Dict[str, List[str]]: Dicionário com erros por categoria
    """
    all_errors = {
        'general': [],
        'confluence': [],
        'risk_management': []
    }
    
    # Validações gerais
    if not validate_api_token(settings_dict.get('DERIV_API_TOKEN', '')):
        all_errors['general'].append("DERIV_API_TOKEN inválido")
    
    symbols = settings_dict.get('SYMBOLS', [])
    if not isinstance(symbols, list) or len(symbols) == 0:
        all_errors['general'].append("SYMBOLS deve conter pelo menos um ativo")
    else:
        for symbol in symbols:
            if not validate_symbol(symbol):
                all_errors['general'].append(f"Símbolo inválido: {symbol}")
    
    # Validar timeframe
    timeframe = settings_dict.get('ANALYSIS_TIMEFRAME', 1)
    if not validate_timeframe(timeframe):
        all_errors['general'].append("ANALYSIS_TIMEFRAME inválido")
    
    # Validar duração
    duration = settings_dict.get('DURATION', 4)
    duration_unit = settings_dict.get('DURATION_UNIT', 't')
    if not validate_duration(duration, duration_unit):
        all_errors['general'].append("DURATION/DURATION_UNIT inválidos")
    
    # Validações de confluências
    confluence_errors = validate_confluence_config(settings_dict)
    all_errors['confluence'].extend(confluence_errors)
    
    # Validações de risk management
    risk_errors = validate_risk_management_config(settings_dict)
    all_errors['risk_management'].extend(risk_errors)
    
    # Remover categorias vazias
    return {k: v for k, v in all_errors.items() if v}

def is_market_open() -> bool:
    """
    Verifica se o mercado está aberto (básico)
    
    Returns:
        bool: True se mercado estiver aberto
    """
    # Para synthetics da Deriv, mercado está sempre aberto
    # Para outros ativos, seria necessário verificar horários específicos
    return True

def validate_connection_stability(last_message_time: float, max_silence_seconds: float = 60.0) -> bool:
    """
    Valida se a conexão está estável baseada no último tempo de mensagem
    
    Args:
        last_message_time: Timestamp da última mensagem recebida
        max_silence_seconds: Máximo de silêncio permitido em segundos
        
    Returns:
        bool: True se conexão estável, False caso contrário
    """
    if last_message_time == 0:
        return False
    
    silence_duration = time.time() - last_message_time
    return silence_duration <= max_silence_seconds