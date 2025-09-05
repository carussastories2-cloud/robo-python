# -*- coding: utf-8 -*-
"""
Settings - Config Module
"""

# TODO: Implementar settings
# -*- coding: utf-8 -*-
"""
Settings - Configurações Globais do Sistema
Carrega e valida todas as configurações do arquivo .env
"""

import os
from dotenv import load_dotenv
from typing import List, Dict, Any

# Carregar variáveis do .env
load_dotenv()

class Settings:
    """Configurações globais do sistema"""
    
    def __init__(self):
        # === CONFIGURAÇÕES DA API DERIV ===
        self.DERIV_API_TOKEN = os.getenv("DERIV_API_TOKEN")
        self.DERIV_APP_ID = int(os.getenv("DERIV_APP_ID", 1089))
        
        # === CONFIGURAÇÕES DE OPERAÇÃO ===
        symbols_str = os.getenv("SYMBOLS", "")
        self.SYMBOLS = [s.strip() for s in symbols_str.split(",") if s.strip()]
        self.MAX_CONCURRENT_OPERATIONS = int(os.getenv("MAX_CONCURRENT_OPERATIONS", 3))
        self.DUAL_ENTRY = os.getenv("DUAL_ENTRY", "false").lower() == "true"
        
        # === TIMEFRAME E EXPIRAÇÃO ===
        self.ANALYSIS_TIMEFRAME = int(os.getenv("ANALYSIS_TIMEFRAME", 1))
        self.DURATION = int(os.getenv("DURATION", 4))
        self.DURATION_UNIT = os.getenv("DURATION_UNIT", "t")
        
        # === SISTEMA DE RISK MANAGEMENT ===
        self.RISK_MANAGEMENT_TYPE = os.getenv("RISK_MANAGEMENT_TYPE", "FIXED_AMOUNT").upper()
        
        # Configurações Básicas de Valor
        self.INITIAL_AMOUNT = float(os.getenv("INITIAL_AMOUNT", 0.35))
        self.MIN_AMOUNT = float(os.getenv("MIN_AMOUNT", 0.35))
        self.MAX_AMOUNT = float(os.getenv("MAX_AMOUNT", 2000))
        
        # === CONFIGURAÇÕES MARTINGALE ===
        self.MARTINGALE_TYPE = os.getenv("MARTINGALE_TYPE", "IMMEDIATE").upper()  # IMMEDIATE ou NEXT_CANDLE
        self.MARTINGALE_MULTIPLIER = float(os.getenv("MARTINGALE_MULTIPLIER", 2.0))
        self.MARTINGALE_MAX_SEQUENCE = int(os.getenv("MARTINGALE_MAX_SEQUENCE", 2))
        
        # Direções do Martingale (para dual entry futuro)
        call_dirs_str = os.getenv("MARTINGALE_DIRECTIONS_CALL", "CALL,PUT,CALL,PUT")
        put_dirs_str = os.getenv("MARTINGALE_DIRECTIONS_PUT", "PUT,CALL,PUT,CALL")
        self.MARTINGALE_DIRECTIONS_CALL = [d.strip().upper() for d in call_dirs_str.split(",")]
        self.MARTINGALE_DIRECTIONS_PUT = [d.strip().upper() for d in put_dirs_str.split(",")]
        
        # === CONFIGURAÇÕES STOP LOSS/WIN ===
        self.STOP_LOSS_VALUE = float(os.getenv("STOP_LOSS_VALUE", 100))
        self.STOP_WIN_VALUE = float(os.getenv("STOP_WIN_VALUE", 100))
        self.STOP_LOSS_TYPE = os.getenv("STOP_LOSS_TYPE", "FIXED").upper()  # FIXED ou PERCENTAGE
        self.STOP_WIN_TYPE = os.getenv("STOP_WIN_TYPE", "FIXED").upper()    # FIXED ou PERCENTAGE
        
        # === CONFIGURAÇÕES DE TIMING ===
        self.COOLDOWN_MINUTES = int(os.getenv("COOLDOWN_MINUTES", 1))
        self.SIGNAL_DEBOUNCE = float(os.getenv("SIGNAL_DEBOUNCE", 5.0))
        self.DELAY_BETWEEN_OPS = float(os.getenv("DELAY_BETWEEN_OPS", 0.05))
        self.MAX_SIGNAL_AGE = float(os.getenv("MAX_SIGNAL_AGE", 5.0))
        
        # === CONFIGURAÇÕES DA ESTRATÉGIA CANDLE PATTERN ===
        
        # Padrões de Cores CALL
        self.CALL_CANDLE_1 = os.getenv("CALL_CANDLE_1", "GREEN").upper()
        self.CALL_CANDLE_2 = os.getenv("CALL_CANDLE_2", "ANY").upper()
        self.CALL_CANDLE_3 = os.getenv("CALL_CANDLE_3", "ANY").upper()
        self.CALL_CANDLE_4 = os.getenv("CALL_CANDLE_4", "ANY").upper()
        self.CALL_CANDLE_5 = os.getenv("CALL_CANDLE_5", "ANY").upper()
        self.CALL_CANDLE_6 = os.getenv("CALL_CANDLE_6", "ANY").upper()
        self.CALL_CANDLE_7 = os.getenv("CALL_CANDLE_7", "ANY").upper()
        self.CALL_CANDLE_8 = os.getenv("CALL_CANDLE_8", "ANY").upper()
        self.CALL_CANDLE_9 = os.getenv("CALL_CANDLE_9", "ANY").upper()
        self.CALL_CANDLE_10 = os.getenv("CALL_CANDLE_10", "ANY").upper()
        
        # Padrões de Cores PUT
        self.PUT_CANDLE_1 = os.getenv("PUT_CANDLE_1", "RED").upper()
        self.PUT_CANDLE_2 = os.getenv("PUT_CANDLE_2", "ANY").upper()
        self.PUT_CANDLE_3 = os.getenv("PUT_CANDLE_3", "ANY").upper()
        self.PUT_CANDLE_4 = os.getenv("PUT_CANDLE_4", "ANY").upper()
        self.PUT_CANDLE_5 = os.getenv("PUT_CANDLE_5", "ANY").upper()
        self.PUT_CANDLE_6 = os.getenv("PUT_CANDLE_6", "ANY").upper()
        self.PUT_CANDLE_7 = os.getenv("PUT_CANDLE_7", "ANY").upper()
        self.PUT_CANDLE_8 = os.getenv("PUT_CANDLE_8", "ANY").upper()
        self.PUT_CANDLE_9 = os.getenv("PUT_CANDLE_9", "ANY").upper()
        self.PUT_CANDLE_10 = os.getenv("PUT_CANDLE_10", "ANY").upper()
        
        # === CONFLUÊNCIAS AVANÇADAS ===
        
        # Filtro de Média Móvel
        self.CANDLE_FILTER_MA_ENABLED = os.getenv("CANDLE_FILTER_MA_ENABLED", "false").lower() == "true"
        self.CANDLE_FILTER_MA_TYPE = os.getenv("CANDLE_FILTER_MA_TYPE", "SMA").upper()  # SMA ou EMA
        self.CANDLE_FILTER_MA_PERIOD = int(os.getenv("CANDLE_FILTER_MA_PERIOD", 20))
        self.CANDLE_FILTER_MA_CONDITION = os.getenv("CANDLE_FILTER_MA_CONDITION", "ABOVE").upper()  # ABOVE, BELOW, CROSS_UP, CROSS_DOWN
        
        # Filtro de Tamanho Mínimo
        self.CANDLE_FILTER_MIN_SIZE_ENABLED = os.getenv("CANDLE_FILTER_MIN_SIZE_ENABLED", "false").lower() == "true"
        self.CANDLE_FILTER_MIN_SIZE_POINTS = float(os.getenv("CANDLE_FILTER_MIN_SIZE_POINTS", 5))
        self.CANDLE_FILTER_MIN_SIZE_TYPE = os.getenv("CANDLE_FILTER_MIN_SIZE_TYPE", "BODY").upper()  # BODY ou TOTAL
        candles_to_check = os.getenv("CANDLE_FILTER_MIN_SIZE_CANDLES", "1")
        self.CANDLE_FILTER_MIN_SIZE_CANDLES = [int(x.strip()) for x in candles_to_check.split(",") if x.strip().isdigit()]
        
        # Filtro de Pavio Máximo
        self.CANDLE_FILTER_MAX_WICK_ENABLED = os.getenv("CANDLE_FILTER_MAX_WICK_ENABLED", "false").lower() == "true"
        self.CANDLE_FILTER_MAX_WICK_UPPER = float(os.getenv("CANDLE_FILTER_MAX_WICK_UPPER", 30))  # % máximo pavio superior
        self.CANDLE_FILTER_MAX_WICK_LOWER = float(os.getenv("CANDLE_FILTER_MAX_WICK_LOWER", 30))  # % máximo pavio inferior
        wick_candles_to_check = os.getenv("CANDLE_FILTER_MAX_WICK_CANDLES", "1,2")
        self.CANDLE_FILTER_MAX_WICK_CANDLES = [int(x.strip()) for x in wick_candles_to_check.split(",") if x.strip().isdigit()]
        
        # Filtro de Proporção Corpo
        self.CANDLE_FILTER_BODY_RATIO_ENABLED = os.getenv("CANDLE_FILTER_BODY_RATIO_ENABLED", "false").lower() == "true"
        self.CANDLE_FILTER_BODY_RATIO_MIN = float(os.getenv("CANDLE_FILTER_BODY_RATIO_MIN", 60))  # % mínimo do corpo
        body_ratio_candles_to_check = os.getenv("CANDLE_FILTER_BODY_RATIO_CANDLES", "1,2")
        self.CANDLE_FILTER_BODY_RATIO_CANDLES = [int(x.strip()) for x in body_ratio_candles_to_check.split(",") if x.strip().isdigit()]
        
        # === CONFIGURAÇÕES DE CONEXÃO ===
        self.MAX_VERIFICATION_ATTEMPTS = int(os.getenv("MAX_VERIFICATION_ATTEMPTS", 10))
        self.VERIFICATION_TIMEOUT = int(os.getenv("VERIFICATION_TIMEOUT", 5))
        
        # === CONFIGURAÇÕES DE DEBUG ===
        self.DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
        
        # === PROPRIEDADES CALCULADAS ===
        self.is_tick_mode = (self.DURATION_UNIT == "t")
        self.analysis_timeframe_seconds = self.ANALYSIS_TIMEFRAME * 60
    
    def get_call_pattern(self) -> List[str]:
        """Retorna padrão de cores para CALL"""
        pattern = []
        for i in range(1, 11):
            color = getattr(self, f'CALL_CANDLE_{i}')
            if color != 'ANY':
                pattern.append(color)
            else:
                break  # Para quando encontrar ANY
        return pattern
    
    def get_put_pattern(self) -> List[str]:
        """Retorna padrão de cores para PUT"""
        pattern = []
        for i in range(1, 11):
            color = getattr(self, f'PUT_CANDLE_{i}')
            if color != 'ANY':
                pattern.append(color)
            else:
                break  # Para quando encontrar ANY
        return pattern
    
    def get_confluence_summary(self) -> Dict[str, bool]:
        """Retorna resumo das confluências ativadas"""
        return {
            'moving_average': self.CANDLE_FILTER_MA_ENABLED,
            'minimum_size': self.CANDLE_FILTER_MIN_SIZE_ENABLED,
            'maximum_wick': self.CANDLE_FILTER_MAX_WICK_ENABLED,
            'body_ratio': self.CANDLE_FILTER_BODY_RATIO_ENABLED
        }
    
    def get_active_confluences_count(self) -> int:
        """Retorna quantidade de confluências ativadas"""
        return sum(self.get_confluence_summary().values())
    
    def validate(self) -> bool:
        """Valida configurações obrigatórias"""
        errors = []
        
        # Validações obrigatórias
        if not self.DERIV_API_TOKEN:
            errors.append("DERIV_API_TOKEN é obrigatório!")
        
        if not self.SYMBOLS:
            errors.append("SYMBOLS é obrigatório!")
        
        # Validações de tipo de risk management
        valid_risk_types = ["FIXED_AMOUNT", "MARTINGALE"]
        if self.RISK_MANAGEMENT_TYPE not in valid_risk_types:
            errors.append(f"RISK_MANAGEMENT_TYPE deve ser um dos: {', '.join(valid_risk_types)}")
        
        # Validações de martingale
        valid_martingale_types = ["IMMEDIATE", "NEXT_CANDLE"]
        if self.MARTINGALE_TYPE not in valid_martingale_types:
            errors.append(f"MARTINGALE_TYPE deve ser um dos: {', '.join(valid_martingale_types)}")
        
        # Validações de valores
        if self.INITIAL_AMOUNT <= 0:
            errors.append("INITIAL_AMOUNT deve ser maior que 0")
        
        if self.MIN_AMOUNT <= 0:
            errors.append("MIN_AMOUNT deve ser maior que 0")
        
        if self.MAX_AMOUNT <= self.MIN_AMOUNT:
            errors.append("MAX_AMOUNT deve ser maior que MIN_AMOUNT")
        
        # Validações de timeframe
        if self.ANALYSIS_TIMEFRAME <= 0:
            errors.append("ANALYSIS_TIMEFRAME deve ser maior que 0")
        
        if self.DURATION <= 0:
            errors.append("DURATION deve ser maior que 0")
        
        valid_duration_units = ["t", "s", "m"]
        if self.DURATION_UNIT not in valid_duration_units:
            errors.append(f"DURATION_UNIT deve ser um dos: {', '.join(valid_duration_units)}")
        
        # Validações de confluências
        if self.CANDLE_FILTER_MA_ENABLED:
            if self.CANDLE_FILTER_MA_PERIOD <= 0:
                errors.append("CANDLE_FILTER_MA_PERIOD deve ser maior que 0")
        
        if self.CANDLE_FILTER_MIN_SIZE_ENABLED:
            if self.CANDLE_FILTER_MIN_SIZE_POINTS <= 0:
                errors.append("CANDLE_FILTER_MIN_SIZE_POINTS deve ser maior que 0")
        
        # Se há erros, mostrar todos
        if errors:
            error_msg = "Erros de configuração encontrados:\n" + "\n".join(f"❌ {error}" for error in errors)
            raise ValueError(error_msg)
        
        return True
    
    def get_summary(self) -> str:
        """Retorna resumo das configurações principais"""
        confluences = self.get_active_confluences_count()
        call_pattern = self.get_call_pattern()
        put_pattern = self.get_put_pattern()
        
        summary = f"""
🔧 CONFIGURAÇÕES DO TRADING BOT
═══════════════════════════════════════════════════
📊 Ativos: {', '.join(self.SYMBOLS)}
💰 Risk Management: {self.RISK_MANAGEMENT_TYPE}
🎯 Valor Inicial: ${self.INITIAL_AMOUNT:.2f}
⏱️  Timeframe: M{self.ANALYSIS_TIMEFRAME} | Expiração: {self.DURATION}{self.DURATION_UNIT}
🔄 Dual Entry: {'✅ Ativo' if self.DUAL_ENTRY else '❌ Inativo'}

🎲 MARTINGALE:
   Tipo: {self.MARTINGALE_TYPE}
   Multiplicador: {self.MARTINGALE_MULTIPLIER}x
   Máx Sequência: {self.MARTINGALE_MAX_SEQUENCE}

🕯️  ESTRATÉGIA CANDLE PATTERN:
   📈 CALL: {' → '.join(call_pattern[:3])}{'...' if len(call_pattern) > 3 else ''}
   📉 PUT: {' → '.join(put_pattern[:3])}{'...' if len(put_pattern) > 3 else ''}
   🔀 Confluências: {confluences} ativas

🛑 STOP CONDITIONS:
   Stop Loss: ${self.STOP_LOSS_VALUE} ({self.STOP_LOSS_TYPE})
   Stop Win: ${self.STOP_WIN_VALUE} ({self.STOP_WIN_TYPE})

🔧 DEBUG: {'✅ Ativo' if self.DEBUG_MODE else '❌ Inativo'} | Log Level: {self.LOG_LEVEL}
═══════════════════════════════════════════════════
        """
        return summary.strip()

# Instância global das configurações
settings = Settings()

# Função para recarregar configurações (útil para desenvolvimento)
def reload_settings():
    """Recarrega configurações do .env"""
    global settings
    load_dotenv(override=True)  # Força reload do .env
    settings = Settings()
    return settings