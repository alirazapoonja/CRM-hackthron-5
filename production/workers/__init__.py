"""
Worker processes for Customer Success FTE.

This package contains background workers and processors:
- message_processor: Unified message processor from Kafka
- metrics_collector: Background metrics aggregation
"""

from production.workers.message_processor import (
    UnifiedMessageProcessor,
    KafkaMessage,
    ProcessingContext,
    ProcessingResult,
    MessageSource,
    check_processor_health,
)

__all__ = [
    "UnifiedMessageProcessor",
    "KafkaMessage",
    "ProcessingContext",
    "ProcessingResult",
    "MessageSource",
    "check_processor_health",
]
