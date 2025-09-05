#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Trading Bot Modular - Ponto de Entrada Principal
Versão Essencial: Valor Fixo + Martingale + Candle Pattern
"""

import asyncio
import sys
from pathlib import Path

# Adicionar diretório raiz ao path
sys.path.append(str(Path(__file__).parent))

def main():
    """Função principal"""
    try:
        from config.settings import settings
        from core.bot import TradingBot
        from utils.logger import setup_logger, get_logger
        
        # Configurar sistema de logs
        setup_logger(
            level=settings.LOG_LEVEL,
            debug_mode=settings.DEBUG_MODE
        )
        
        logger = get_logger(__name__)
        
        # Validar configurações
        logger.info("🔍 Validando configurações...")
        settings.validate()
        
        # Inicializar e executar bot
        logger.info("🚀 Iniciando Trading Bot Modular...")
        logger.info(f"📊 Estratégia: Candle Pattern")
        logger.info(f"💰 Risk Management: {settings.RISK_MANAGEMENT_TYPE}")
        logger.info(f"🎯 Ativos: {', '.join(settings.SYMBOLS)}")
        
        bot = TradingBot()
        asyncio.run(bot.run())
        
    except KeyboardInterrupt:
        print("\n👋 Bot encerrado pelo usuário")
    except Exception as e:
        print(f"❌ Erro crítico: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
