#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Connection Monitor - Monitor de Saúde da Conexão
Sistema de monitoramento contínuo da qualidade e estabilidade da conexão
"""

import asyncio
import time
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
from utils.logger import get_logger

logger = get_logger(__name__)

class ConnectionQuality(Enum):
    """Níveis de qualidade da conexão"""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"

@dataclass
class ConnectionMetrics:
    """Métricas de conexão"""
    latency_ms: float = 0.0
    uptime_percentage: float = 100.0
    message_rate_per_minute: float = 0.0
    error_rate_percentage: float = 0.0
    reconnection_count: int = 0
    last_disconnection_duration: float = 0.0

class ConnectionMonitor:
    """Monitor de saúde da conexão WebSocket"""
    
    def __init__(self):
        self.is_monitoring = False
        self.monitor_task: Optional[asyncio.Task] = None
        
        self.is_connected_callback: Optional[Callable] = None
        self.get_stats_callback: Optional[Callable] = None
        self.reconnect_callback: Optional[Callable] = None
        
        self.latency_history: List[float] = []
        self.uptime_history: List[float] = []
        self.connection_events: List[Dict[str, Any]] = []
        
        self.check_interval = 30.0
        self.max_history_size = 100
        self.alert_thresholds = {
            'max_latency_ms': 2000.0,
            'min_uptime_percentage': 95.0,
            'max_error_rate_percentage': 5.0,
            'max_silence_seconds': 120.0
        }
        
        self.current_quality = ConnectionQuality.EXCELLENT
        self.last_quality_change = time.time()
        self.consecutive_poor_checks = 0
        self.quality_alerts_sent = set()
        
        self.session_start_time = time.time()
        self.total_uptime_seconds = 0.0
        self.total_downtime_seconds = 0.0
        self.connection_quality_log: List[Dict[str, Any]] = []
    
    def set_callbacks(self,
                      is_connected: Callable,
                      get_stats: Callable,
                      reconnect: Optional[Callable] = None):
        self.is_connected_callback = is_connected
        self.get_stats_callback = get_stats
        self.reconnect_callback = reconnect
    
    async def start_monitoring(self):
        if self.is_monitoring:
            logger.warning("⚠️ Monitor já está rodando")
            return
        
        logger.info("📊 Iniciando monitor de conexão...")
        self.is_monitoring = True
        self.session_start_time = time.time()
        
        self.monitor_task = asyncio.create_task(self._monitoring_loop())
        logger.info(f"📊 Monitor ativo - verificações a cada {self.check_interval}s")
    
    def stop_monitoring(self):
        logger.info("🛑 Parando monitor de conexão...")
        self.is_monitoring = False
        
        if self.monitor_task and not self.monitor_task.done():
            self.monitor_task.cancel()
    
    async def _monitoring_loop(self):
        """Loop principal de monitoramento"""
        try:
            while self.is_monitoring:
                # Coletar métricas atuais
                metrics = await self._collect_metrics()
                
                # Avaliar qualidade da conexão
                quality = self._evaluate_connection_quality(metrics)
                
                # Verificar mudança de qualidade
                if quality != self.current_quality:
                    await self._handle_quality_change(quality, metrics)
                
                # Verificar alertas
                await self._check_alerts(metrics)
                
                # Atualizar histórico
                self._update_history(metrics)
                
                # Log periódico (a cada 5 minutos)
                if int(time.time()) % 300 == 0:
                    self._log_periodic_status(metrics)
                
                # Aguardar próxima verificação
                await asyncio.sleep(self.check_interval)
        
        except asyncio.CancelledError:
            logger.info("📊 Monitor de conexão cancelado")
        except Exception as e:
            logger.error(f"❌ Erro no monitor de conexão: {e}")
        finally:
            self.is_monitoring = False
    
    async def _collect_metrics(self) -> ConnectionMetrics:
        """Coleta métricas atuais da conexão"""
        metrics = ConnectionMetrics()
        
        try:
            is_connected = False
            if self.is_connected_callback:
                is_connected = self.is_connected_callback()
            
            stats = {}
            if self.get_stats_callback:
                stats = self.get_stats_callback() or {}
            
            metrics.latency_ms = stats.get('average_latency_ms', 0.0)
            
            session_duration = time.time() - self.session_start_time
            
            # <<< CORREÇÃO AQUI >>>
            # Se a conexão estiver ativa, consideramos que o tempo de atividade
            # é igual à duração da sessão. Isso evita o falso alarme inicial.
            if is_connected:
                self.total_uptime_seconds = session_duration

            if session_duration > 0:
                metrics.uptime_percentage = (self.total_uptime_seconds / session_duration) * 100
            
            total_messages = stats.get('total_messages_received', 0)
            if session_duration > 0:
                metrics.message_rate_per_minute = (total_messages / session_duration) * 60
            
            total_errors = stats.get('total_errors', 0)
            if total_messages > 0:
                metrics.error_rate_percentage = (total_errors / total_messages) * 100
            
            metrics.reconnection_count = stats.get('reconnection_attempts', 0)
            
            metrics.last_disconnection_duration = stats.get('last_downtime_seconds', 0.0)
            
        except Exception as e:
            logger.error(f"❌ Erro coletando métricas: {e}")
        
        return metrics

    # ... (O restante do arquivo permanece exatamente o mesmo) ...

    # [COLE O RESTANTE DO CÓDIGO DE `connection_monitor.py` AQUI, DO MÉTODO `_evaluate_connection_quality` ATÉ O FIM]
    def _evaluate_connection_quality(self, metrics: ConnectionMetrics) -> ConnectionQuality:
        """
        Avalia qualidade da conexão baseada nas métricas
        """
        score = 100.0
        
        if metrics.latency_ms > 2000:
            score -= 30
        elif metrics.latency_ms > 1000:
            score -= 20
        elif metrics.latency_ms > 500:
            score -= 10
        elif metrics.latency_ms > 200:
            score -= 5
        
        if metrics.uptime_percentage < 95:
            score -= (95 - metrics.uptime_percentage) * 2
        
        if metrics.error_rate_percentage > 5:
            score -= metrics.error_rate_percentage * 3
        
        if metrics.reconnection_count > 5:
            score -= (metrics.reconnection_count - 5) * 5
        
        if metrics.last_disconnection_duration > 60:
            score -= min(30, metrics.last_disconnection_duration / 2)
        
        if score >= 90:
            return ConnectionQuality.EXCELLENT
        elif score >= 70:
            return ConnectionQuality.GOOD
        elif score >= 50:
            return ConnectionQuality.FAIR
        elif score >= 30:
            return ConnectionQuality.POOR
        else:
            return ConnectionQuality.CRITICAL
    
    async def _handle_quality_change(self, new_quality: ConnectionQuality, metrics: ConnectionMetrics):
        """
        Trata mudança na qualidade da conexão
        """
        old_quality = self.current_quality
        self.current_quality = new_quality
        self.last_quality_change = time.time()
        
        quality_emojis = {
            ConnectionQuality.EXCELLENT: "🟢",
            ConnectionQuality.GOOD: "🟡",
            ConnectionQuality.FAIR: "🟠",
            ConnectionQuality.POOR: "🔴",
            ConnectionQuality.CRITICAL: "💀"
        }
        
        old_emoji = quality_emojis.get(old_quality, "❓")
        new_emoji = quality_emojis.get(new_quality, "❓")
        
        logger.info(f"📊 Qualidade da conexão: {old_emoji} {old_quality.value.upper()} → {new_emoji} {new_quality.value.upper()}")
        
        self.connection_events.append({
            'timestamp': time.time(),
            'event_type': 'quality_change',
            'old_quality': old_quality.value,
            'new_quality': new_quality.value,
            'metrics': {
                'latency_ms': metrics.latency_ms,
                'uptime_percentage': metrics.uptime_percentage,
                'error_rate': metrics.error_rate_percentage
            }
        })
        
        if len(self.connection_events) > 50:
            self.connection_events = self.connection_events[-50:]
        
        if new_quality == ConnectionQuality.CRITICAL:
            logger.error("💀 CONEXÃO CRÍTICA - Considerando reconexão forçada...")
            self.consecutive_poor_checks += 1
            
            if self.consecutive_poor_checks >= 3 and self.reconnect_callback:
                logger.error("🚨 Forçando reconexão devido à qualidade crítica!")
                try:
                    await self.reconnect_callback()
                except Exception as e:
                    logger.error(f"❌ Erro na reconexão forçada: {e}")
        
        elif new_quality in [ConnectionQuality.POOR, ConnectionQuality.FAIR]:
            self.consecutive_poor_checks += 1
            logger.warning(f"⚠️ Conexão {new_quality.value.upper()} - monitoramento intensificado")
        
        else:
            self.consecutive_poor_checks = 0
    
    async def _check_alerts(self, metrics: ConnectionMetrics):
        """
        Verifica condições de alerta
        """
        alerts_to_send = []
        
        if metrics.latency_ms > self.alert_thresholds['max_latency_ms']:
            alert_key = 'high_latency'
            if alert_key not in self.quality_alerts_sent:
                alerts_to_send.append(f"🐌 Latência alta: {metrics.latency_ms:.1f}ms")
                self.quality_alerts_sent.add(alert_key)
        else:
            self.quality_alerts_sent.discard('high_latency')
        
        if metrics.uptime_percentage < self.alert_thresholds['min_uptime_percentage']:
            alert_key = 'low_uptime'
            if alert_key not in self.quality_alerts_sent:
                alerts_to_send.append(f"📉 Uptime baixo: {metrics.uptime_percentage:.1f}%")
                self.quality_alerts_sent.add(alert_key)
        else:
            self.quality_alerts_sent.discard('low_uptime')
        
        if metrics.error_rate_percentage > self.alert_thresholds['max_error_rate_percentage']:
            alert_key = 'high_error_rate'
            if alert_key not in self.quality_alerts_sent:
                alerts_to_send.append(f"❌ Taxa de erro alta: {metrics.error_rate_percentage:.1f}%")
                self.quality_alerts_sent.add(alert_key)
        else:
            self.quality_alerts_sent.discard('high_error_rate')
        
        for alert in alerts_to_send:
            logger.warning(f"🚨 ALERTA DE CONEXÃO: {alert}")
    
    def _update_history(self, metrics: ConnectionMetrics):
        """
        Atualiza histórico de métricas
        """
        self.latency_history.append(metrics.latency_ms)
        self.uptime_history.append(metrics.uptime_percentage)
        
        self.connection_quality_log.append({
            'timestamp': time.time(),
            'quality': self.current_quality.value,
            'latency_ms': metrics.latency_ms,
            'uptime_percentage': metrics.uptime_percentage
        })
        
        if len(self.latency_history) > self.max_history_size:
            self.latency_history = self.latency_history[-self.max_history_size:]
        if len(self.uptime_history) > self.max_history_size:
            self.uptime_history = self.uptime_history[-self.max_history_size:]
        if len(self.connection_quality_log) > self.max_history_size:
            self.connection_quality_log = self.connection_quality_log[-self.max_history_size:]
    
    def _log_periodic_status(self, metrics: ConnectionMetrics):
        """
        Log periódico do status da conexão
        """
        quality_emoji = {
            ConnectionQuality.EXCELLENT: "🟢",
            ConnectionQuality.GOOD: "🟡", 
            ConnectionQuality.FAIR: "🟠",
            ConnectionQuality.POOR: "🔴",
            ConnectionQuality.CRITICAL: "💀"
        }.get(self.current_quality, "❓")
        
        logger.info(f"📊 STATUS DA CONEXÃO {quality_emoji}")
        logger.info(f"   🏓 Latência: {metrics.latency_ms:.1f}ms")
        logger.info(f"   ⏱️ Uptime: {metrics.uptime_percentage:.1f}%")
        logger.info(f"   📨 Msg/min: {metrics.message_rate_per_minute:.1f}")
        logger.info(f"   ❌ Taxa erro: {metrics.error_rate_percentage:.1f}%")
        logger.info(f"   🔄 Reconexões: {metrics.reconnection_count}")
    
    def get_connection_health_report(self) -> Dict[str, Any]:
        """
        Retorna relatório completo de saúde da conexão
        """
        avg_latency = sum(self.latency_history) / len(self.latency_history) if self.latency_history else 0
        avg_uptime = sum(self.uptime_history) / len(self.uptime_history) if self.uptime_history else 100
        
        quality_distribution = {}
        for entry in self.connection_quality_log:
            quality = entry['quality']
            quality_distribution[quality] = quality_distribution.get(quality, 0) + 1
        
        time_since_last_change = time.time() - self.last_quality_change
        
        return {
            'current_quality': self.current_quality.value,
            'time_since_last_quality_change_seconds': round(time_since_last_change, 1),
            'consecutive_poor_checks': self.consecutive_poor_checks,
            'session_duration_seconds': round(time.time() - self.session_start_time, 1),
            'average_latency_ms': round(avg_latency, 1),
            'average_uptime_percentage': round(avg_uptime, 1),
            'quality_distribution': quality_distribution,
            'total_quality_changes': len(self.connection_events),
            'active_alerts': list(self.quality_alerts_sent),
            'monitoring_active': self.is_monitoring,
            'check_interval_seconds': self.check_interval,
            'history_size': len(self.latency_history)
        }
    
    def get_recent_events(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Retorna eventos recentes de conexão
        """
        return self.connection_events[-limit:] if self.connection_events else []
    
    def set_alert_threshold(self, metric: str, value: float):
        """
        Define threshold de alerta
        """
        if metric in self.alert_thresholds:
            old_value = self.alert_thresholds[metric]
            self.alert_thresholds[metric] = value
            logger.info(f"📊 Threshold {metric}: {old_value} → {value}")
        else:
            logger.warning(f"⚠️ Threshold desconhecido: {metric}")
    
    def reset_stats(self):
        """Reseta estatísticas do monitor"""
        self.latency_history.clear()
        self.uptime_history.clear()
        self.connection_events.clear()
        self.connection_quality_log.clear()
        self.quality_alerts_sent.clear()
        self.consecutive_poor_checks = 0
        self.session_start_time = time.time()
        self.total_uptime_seconds = 0.0
        self.total_downtime_seconds = 0.0
        
        logger.info("🔄 Estatísticas do monitor resetadas")