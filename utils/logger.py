# -*- coding: utf-8 -*-
"""
Logger - Utils Module
"""

# TODO: Implementar logger
# -*- coding: utf-8 -*-
"""
Logger - Sistema de Logs Profissional
Sistema de logging otimizado para debugging e monitoramento
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

# Cores para terminal (opcional)
class Colors:
    """Cores ANSI para terminal"""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'

class ColoredFormatter(logging.Formatter):
    """Formatter com cores para diferentes níveis de log"""
    
    COLORS = {
        'DEBUG': Colors.CYAN,
        'INFO': Colors.GREEN,
        'WARNING': Colors.YELLOW,
        'ERROR': Colors.RED,
        'CRITICAL': Colors.RED + Colors.BOLD
    }
    
    def format(self, record):
        # Formato básico
        log_message = super().format(record)
        
        # Adicionar cor se suportado
        if hasattr(sys.stderr, 'isatty') and sys.stderr.isatty():
            color = self.COLORS.get(record.levelname, Colors.RESET)
            log_message = f"{color}{log_message}{Colors.RESET}"
        
        return log_message

def setup_logger(level="INFO", debug_mode=False, log_to_file=True):
    """
    Configura sistema de logging global
    
    Args:
        level: Nível de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        debug_mode: Se True, mostra logs mais detalhados
        log_to_file: Se True, salva logs em arquivo
    """
    
    # Converter string para nível
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Limpar handlers existentes
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Formato dos logs
    if debug_mode:
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    else:
        log_format = '%(asctime)s - %(levelname)s - %(message)s'
    
    date_format = '%Y-%m-%d %H:%M:%S'
    
    # Handler para console (sempre ativo)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    
    # Usar formatter colorido para console
    colored_formatter = ColoredFormatter(log_format, date_format)
    console_handler.setFormatter(colored_formatter)
    
    # Configurar logger raiz
    root_logger.setLevel(numeric_level)
    root_logger.addHandler(console_handler)
    
    # Handler para arquivo (opcional)
    if log_to_file:
        try:
            # Criar diretório de logs
            log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)
            
            # Nome do arquivo com data
            log_filename = f"trading_bot_{datetime.now().strftime('%Y%m%d')}.log"
            log_filepath = log_dir / log_filename
            
            # Handler de arquivo
            file_handler = logging.FileHandler(log_filepath, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)  # Arquivo sempre DEBUG
            
            # Formatter sem cores para arquivo
            file_formatter = logging.Formatter(log_format, date_format)
            file_handler.setFormatter(file_formatter)
            
            root_logger.addHandler(file_handler)
            
            # Log inicial
            logger = logging.getLogger(__name__)
            logger.info(f"📝 Logs salvos em: {log_filepath}")
            
        except Exception as e:
            # Se falhar, continua sem arquivo
            logger = logging.getLogger(__name__)
            logger.warning(f"⚠️ Não foi possível criar arquivo de log: {e}")
    
    # Log de inicialização
    logger = logging.getLogger(__name__)
    logger.info("🚀 Sistema de logging inicializado")
    logger.info(f"📊 Nível: {level} | Debug: {debug_mode} | Arquivo: {log_to_file}")

def get_logger(name):
    """
    Obtém logger para módulo específico
    
    Args:
        name: Nome do módulo (geralmente __name__)
    
    Returns:
        Logger configurado
    """
    return logging.getLogger(name)

# Configuração de logs para bibliotecas externas
def configure_external_loggers():
    """Configura logs de bibliotecas externas para reduzir spam"""
    
    # Websockets - reduzir verbosidade
    logging.getLogger('websockets').setLevel(logging.WARNING)
    
    # Flask - reduzir verbosidade (caso seja usado futuramente)
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    
    # Urllib3 - reduzir verbosidade
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    # Requests - reduzir verbosidade  
    logging.getLogger('requests').setLevel(logging.WARNING)

# Context manager para logs de operações
class LogOperation:
    """Context manager para logar início e fim de operações"""
    
    def __init__(self, operation_name, logger):
        self.operation_name = operation_name
        self.logger = logger
        self.start_time = None
    
    def __enter__(self):
        self.start_time = datetime.now()
        self.logger.info(f"🔄 Iniciando: {self.operation_name}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = datetime.now() - self.start_time
        
        if exc_type is None:
            self.logger.info(f"✅ Concluído: {self.operation_name} ({duration.total_seconds():.2f}s)")
        else:
            self.logger.error(f"❌ Falhou: {self.operation_name} ({duration.total_seconds():.2f}s) - {exc_val}")

# Decorador para logar funções automaticamente
def log_function_calls(logger=None):
    """
    Decorador para logar entrada e saída de funções
    
    Args:
        logger: Logger específico (opcional)
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            func_logger = logger or get_logger(func.__module__)
            
            with LogOperation(f"{func.__name__}()", func_logger):
                return func(*args, **kwargs)
        
        return wrapper
    return decorator

# Função para log de performance
def log_performance(operation_name, start_time, logger):
    """
    Loga performance de uma operação
    
    Args:
        operation_name: Nome da operação
        start_time: Tempo de início (datetime)
        logger: Logger para usar
    """
    duration = datetime.now() - start_time
    duration_ms = duration.total_seconds() * 1000
    
    if duration_ms < 100:
        emoji = "⚡"  # Muito rápido
    elif duration_ms < 1000:
        emoji = "🚀"  # Rápido
    elif duration_ms < 5000:
        emoji = "⏳"  # Normal
    else:
        emoji = "🐌"  # Lento
        
    logger.info(f"{emoji} {operation_name}: {duration_ms:.1f}ms")

# Inicialização automática com configuração básica
if not logging.getLogger().handlers:
    setup_logger()
    configure_external_loggers()