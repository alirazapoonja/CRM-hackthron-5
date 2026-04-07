"""
Kafka Event Streaming for Customer Success FTE.

This module provides Kafka producer and client functionality for the
unified ticket ingestion system. It handles event streaming from all
channels (Gmail, WhatsApp, Web Form) into a centralized processing pipeline.

Topics Architecture:
┌─────────────────────────────────────────────────────────────────────────────┐
│                        KAFKA TOPICS ARCHITECTURE                             │
│                                                                              │
│   CHANNEL TOPICS (Raw Intake)                                                │
│   ─────────────────────────────                                              │
│   fte.channel.email        ← Gmail messages                                 │
│   fte.channel.whatsapp     ← WhatsApp messages via Twilio                   │
│   fte.channel.web_form     ← Web form submissions                           │
│                                                                              │
│   PROCESSING TOPICS (Unified)                                                │
│   ───────────────────────────────                                            │
│   fte.tickets.incoming     ← Unified ticket ingestion (main processor)      │
│   fte.tickets.outgoing     ← Processed responses ready for delivery         │
│   fte.tickets.escalated    ← Escalated tickets for human review             │
│                                                                              │
│   SYSTEM TOPICS                                                              │
│   ─────────────                                                              │
│   fte.metrics              ← Agent and system metrics                       │
│   fte.dlq                  ← Dead-letter queue for failed messages          │
│   fte.events               ← General system events                          │
│                                                                              │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                 │
│   │    Gmail     │    │   WhatsApp   │    │   Web Form   │                 │
│   └──────┬───────┘    └──────┬───────┘    └──────┬───────┘                 │
│          │                   │                   │                          │
│          ▼                   ▼                   ▼                          │
│   ┌─────────────────────────────────────────────────────────┐               │
│   │              fte.tickets.incoming                        │               │
│   │           (Unified Ticket Ingestion)                     │               │
│   └────────────────────────┬────────────────────────────────┘               │
│                            │                                                 │
│                            ▼                                                 │
│   ┌─────────────────────────────────────────────────────────┐               │
│   │         Message Processor (Customer Success FTE)         │               │
│   └────────────────────────┬────────────────────────────────┘               │
│                            │                                                 │
│              ┌─────────────┼─────────────┐                                  │
│              ▼             ▼             ▼                                  │
│   ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                       │
│   │  fte.tickets │ │ fte.tickets  │ │  fte.tickets │                       │
│   │   .outgoing  │ │  .escalated  │ │     .dlq     │                       │
│   └──────────────┘ └──────────────┘ └──────────────┘                       │
└─────────────────────────────────────────────────────────────────────────────┘
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum

from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from aiokafka.errors import KafkaError, KafkaTimeoutError
from aiokafka.structs import ConsumerRecord, TopicPartition

logger = logging.getLogger(__name__)

# =============================================================================
# TOPIC DEFINITIONS
# =============================================================================

# All Kafka topics used by the Customer Success FTE system
TOPICS = {
    # Channel intake topics (raw messages from each channel)
    "channel_email": "fte.channel.email",
    "channel_whatsapp": "fte.channel.whatsapp",
    "channel_web_form": "fte.channel.web_form",
    
    # Main processing topics
    "tickets_incoming": "fte.tickets.incoming",
    "tickets_outgoing": "fte.tickets.outgoing",
    "tickets_escalated": "fte.tickets.escalated",
    
    # System topics
    "metrics": "fte.metrics",
    "dlq": "fte.dlq",
    "events": "fte.events",
}

# Topic configurations
TOPIC_CONFIGS = {
    "fte.tickets.incoming": {
        "partitions": 6,
        "replication_factor": 3,
        "retention_ms": 604800000,  # 7 days
        "max_message_bytes": 1048576,  # 1MB
    },
    "fte.tickets.outgoing": {
        "partitions": 6,
        "replication_factor": 3,
        "retention_ms": 259200000,  # 3 days
    },
    "fte.tickets.escalated": {
        "partitions": 3,
        "replication_factor": 3,
        "retention_ms": 604800000,  # 7 days
    },
    "fte.metrics": {
        "partitions": 3,
        "replication_factor": 3,
        "retention_ms": 2592000000,  # 30 days
    },
    "fte.dlq": {
        "partitions": 3,
        "replication_factor": 3,
        "retention_ms": 2592000000,  # 30 days
    },
    "fte.events": {
        "partitions": 6,
        "replication_factor": 3,
        "retention_ms": 604800000,  # 7 days
    },
}

# Default Kafka configuration
DEFAULT_BOOTSTRAP_SERVERS = ["localhost:9092"]
DEFAULT_TIMEOUT_MS = 30000
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY_S = 1.0


# =============================================================================
# EVENT TYPES
# =============================================================================


class EventType(str, Enum):
    """Types of events in the system."""
    # Ticket lifecycle events
    TICKET_CREATED = "ticket.created"
    TICKET_UPDATED = "ticket.updated"
    TICKET_RESOLVED = "ticket.resolved"
    TICKET_ESCALATED = "ticket.escalated"
    TICKET_CLOSED = "ticket.closed"
    
    # Message events
    MESSAGE_RECEIVED = "message.received"
    MESSAGE_SENT = "message.sent"
    MESSAGE_DELIVERED = "message.delivered"
    MESSAGE_FAILED = "message.failed"
    
    # Customer events
    CUSTOMER_IDENTIFIED = "customer.identified"
    CUSTOMER_CREATED = "customer.created"
    
    # Agent events
    AGENT_STARTED = "agent.started"
    AGENT_STOPPED = "agent.stopped"
    AGENT_ERROR = "agent.error"
    
    # System events
    SYSTEM_STARTED = "system.started"
    SYSTEM_STOPPED = "system.stopped"
    SYSTEM_HEALTH_CHECK = "system.health_check"


@dataclass
class KafkaEvent:
    """
    Standard event structure for Kafka messages.
    
    All events published to Kafka should follow this structure
    for consistency and easier processing.
    """
    event_type: EventType
    payload: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    event_id: Optional[str] = None
    source: Optional[str] = None
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for JSON serialization."""
        return {
            "event_type": self.event_type.value,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "event_id": self.event_id,
            "source": self.source,
            "correlation_id": self.correlation_id,
            "metadata": self.metadata,
        }
    
    def to_json(self) -> str:
        """Convert event to JSON string."""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KafkaEvent":
        """Create event from dictionary."""
        return cls(
            event_type=EventType(data.get("event_type", "")),
            payload=data.get("payload", {}),
            timestamp=data.get("timestamp", datetime.utcnow().isoformat()),
            event_id=data.get("event_id"),
            source=data.get("source"),
            correlation_id=data.get("correlation_id"),
            metadata=data.get("metadata", {}),
        )


# =============================================================================
# KAFKA PRODUCER
# =============================================================================


class FTEKafkaProducer:
    """
    Async Kafka producer for Customer Success FTE.
    
    Provides methods for publishing messages to various topics
    with proper error handling, retries, and serialization.
    
    Usage:
        producer = FTEKafkaProducer(bootstrap_servers=["localhost:9092"])
        await producer.start()
        
        # Publish to specific topic
        await producer.publish(
            topic="fte.tickets.incoming",
            key="ticket-123",
            value={"customer_email": "user@example.com", "content": "..."}
        )
        
        # Publish typed event
        await producer.publish_event(
            topic="fte.events",
            event_type=EventType.TICKET_CREATED,
            payload={"ticket_id": "123", ...}
        )
        
        await producer.stop()
    """
    
    def __init__(
        self,
        bootstrap_servers: List[str] = None,
        client_id: str = "fte-producer",
        acks: str = "all",
        retries: int = DEFAULT_MAX_RETRIES,
        retry_delay: float = DEFAULT_RETRY_DELAY_S,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
        max_batch_size: int = 16384,
        linger_ms: int = 10,
    ):
        """
        Initialize Kafka producer.
        
        Args:
            bootstrap_servers: List of Kafka broker addresses
            client_id: Client identifier for Kafka
            acks: Acknowledgment level ("all", "1", "0")
            retries: Number of retries on failure
            retry_delay: Delay between retries in seconds
            timeout_ms: Request timeout in milliseconds
            max_batch_size: Maximum batch size in bytes
            linger_ms: Time to wait for batch accumulation
        """
        self.bootstrap_servers = bootstrap_servers or DEFAULT_BOOTSTRAP_SERVERS
        self.client_id = client_id
        self.acks = acks
        self.retries = retries
        self.retry_delay = retry_delay
        self.timeout_ms = timeout_ms
        self.max_batch_size = max_batch_size
        self.linger_ms = linger_ms
        
        self._producer: Optional[AIOKafkaProducer] = None
        self._started = False
        
    async def start(self) -> None:
        """
        Start the Kafka producer.
        
        Establishes connection to Kafka cluster.
        """
        if self._started:
            logger.warning("Producer already started")
            return
        
        try:
            self._producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                client_id=self.client_id,
                acks=self.acks,
                retries=self.retries,
                request_timeout_ms=self.timeout_ms,
                max_batch_size=self.max_batch_size,
                linger_ms=self.linger_ms,
                value_serializer=lambda v: json.dumps(v).encode() if isinstance(v, dict) else v,
                key_serializer=lambda k: k.encode() if isinstance(k, str) else k,
            )
            
            await self._producer.start()
            self._started = True
            
            logger.info(
                f"Kafka producer started. Servers: {self.bootstrap_servers}"
            )
            
        except Exception as e:
            logger.error(f"Failed to start Kafka producer: {e}")
            raise
    
    async def stop(self) -> None:
        """
        Stop the Kafka producer.
        
        Gracefully closes connections and flushes pending messages.
        """
        if not self._started:
            return
        
        try:
            if self._producer:
                await self._producer.stop()
            self._started = False
            logger.info("Kafka producer stopped")
        except Exception as e:
            logger.error(f"Error stopping Kafka producer: {e}")
    
    async def publish(
        self,
        topic: str,
        value: Dict[str, Any],
        key: Optional[str] = None,
        headers: Optional[List[tuple]] = None,
        partition: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Publish a message to a Kafka topic.
        
        Args:
            topic: Topic name to publish to
            value: Message value (will be JSON serialized)
            key: Optional message key for partitioning
            headers: Optional message headers
            partition: Optional specific partition
            
        Returns:
            Dict with topic, partition, offset, and timestamp
            
        Raises:
            KafkaError: If publishing fails after retries
        """
        if not self._started:
            raise RuntimeError("Producer not started. Call start() first.")
        
        for attempt in range(self.retries):
            try:
                future = await self._producer.send(
                    topic=topic,
                    value=value,
                    key=key,
                    headers=headers,
                    partition=partition,
                )
                
                record_metadata = await future
                
                result = {
                    "topic": record_metadata.topic,
                    "partition": record_metadata.partition,
                    "offset": record_metadata.offset,
                    "timestamp": record_metadata.timestamp,
                    "key": key,
                }
                
                logger.debug(
                    f"Published to {topic} [partition={record_metadata.partition}, "
                    f"offset={record_metadata.offset}]"
                )
                
                return result
                
            except KafkaTimeoutError as e:
                logger.warning(f"Publish timeout (attempt {attempt + 1}/{self.retries}): {e}")
                if attempt < self.retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                else:
                    raise
            except KafkaError as e:
                logger.error(f"Kafka error (attempt {attempt + 1}/{self.retries}): {e}")
                if attempt < self.retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                else:
                    raise
            except Exception as e:
                logger.exception(f"Unexpected error publishing: {e}")
                raise
        
        raise KafkaError("Failed to publish after all retries")
    
    async def publish_event(
        self,
        topic: str,
        event_type: EventType,
        payload: Dict[str, Any],
        key: Optional[str] = None,
        correlation_id: Optional[str] = None,
        source: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Publish a typed event to Kafka.
        
        Args:
            topic: Topic name
            event_type: Type of event
            payload: Event payload data
            key: Optional message key
            correlation_id: Optional correlation ID for tracing
            source: Optional source identifier
            metadata: Optional additional metadata
            
        Returns:
            Publish result
        """
        import uuid
        
        event = KafkaEvent(
            event_type=event_type,
            payload=payload,
            event_id=str(uuid.uuid4()),
            correlation_id=correlation_id,
            source=source,
            metadata=metadata or {},
        )
        
        return await self.publish(
            topic=topic,
            value=event.to_dict(),
            key=key,
        )
    
    async def publish_to_channel(
        self,
        channel: str,
        message: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Publish message to channel-specific topic.
        
        Args:
            channel: Channel name ('email', 'whatsapp', 'web_form')
            message: Message data
            
        Returns:
            Publish result
        """
        topic_map = {
            "email": TOPICS["channel_email"],
            "whatsapp": TOPICS["channel_whatsapp"],
            "web_form": TOPICS["channel_web_form"],
        }
        
        topic = topic_map.get(channel, TOPICS["channel_web_form"])
        
        return await self.publish(
            topic=topic,
            value=message,
            key=message.get("channel_message_id"),
        )
    
    async def publish_ticket(
        self,
        ticket_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Publish unified ticket to incoming topic.
        
        This is the main method for channel handlers to submit
        tickets for processing.
        
        Args:
            ticket_data: Ticket data with customer info, content, channel
            
        Returns:
            Publish result
        """
        # Ensure required fields
        if "channel" not in ticket_data:
            raise ValueError("Ticket data must include 'channel'")
        if "content" not in ticket_data:
            raise ValueError("Ticket data must include 'content'")
        
        # Add timestamp if not present
        if "received_at" not in ticket_data:
            ticket_data["received_at"] = datetime.utcnow().isoformat()
        
        return await self.publish(
            topic=TOPICS["tickets_incoming"],
            value=ticket_data,
            key=ticket_data.get("channel_message_id") or ticket_data.get("customer_email"),
        )
    
    async def publish_escalation(
        self,
        escalation_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Publish escalated ticket to escalated topic.
        
        Args:
            escalation_data: Escalation data with ticket_id, reason, etc.
            
        Returns:
            Publish result
        """
        return await self.publish(
            topic=TOPICS["tickets_escalated"],
            value=escalation_data,
            key=escalation_data.get("ticket_id"),
        )
    
    async def publish_metric(
        self,
        metric_name: str,
        metric_value: float,
        dimensions: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Publish metric to metrics topic.
        
        Args:
            metric_name: Name of the metric
            metric_value: Metric value
            dimensions: Optional dimension data
            
        Returns:
            Publish result
        """
        metric_data = {
            "metric_name": metric_name,
            "metric_value": metric_value,
            "timestamp": datetime.utcnow().isoformat(),
            "dimensions": dimensions or {},
        }
        
        return await self.publish(
            topic=TOPICS["metrics"],
            value=metric_data,
            key=metric_name,
        )
    
    @property
    def is_started(self) -> bool:
        """Check if producer is started."""
        return self._started


# =============================================================================
# KAFKA CONSUMER
# =============================================================================


class FTEKafkaConsumer:
    """
    Async Kafka consumer for Customer Success FTE.
    
    Provides methods for consuming messages from Kafka topics
    with proper error handling, commit management, and rebalancing.
    
    Usage:
        consumer = FTEKafkaConsumer(
            topics=["fte.tickets.incoming"],
            group_id="fte-processor",
        )
        await consumer.start()
        
        async for message in consumer.consume():
            try:
                await process_message(message)
                await consumer.commit()
            except Exception as e:
                logger.error(f"Processing failed: {e}")
                await consumer.publish_to_dlq(message, str(e))
        
        await consumer.stop()
    """
    
    def __init__(
        self,
        topics: List[str] = None,
        group_id: str = "fte-consumer",
        bootstrap_servers: List[str] = None,
        auto_commit: bool = False,
        auto_offset_reset: str = "earliest",
        session_timeout_ms: int = 30000,
        heartbeat_interval_ms: int = 10000,
        max_poll_records: int = 500,
        max_poll_interval_ms: int = 300000,
    ):
        """
        Initialize Kafka consumer.
        
        Args:
            topics: List of topics to consume
            group_id: Consumer group ID
            bootstrap_servers: Kafka broker addresses
            auto_commit: Whether to auto-commit offsets
            auto_offset_reset: Where to start reading ("earliest", "latest")
            session_timeout_ms: Session timeout in milliseconds
            heartbeat_interval_ms: Heartbeat interval in milliseconds
            max_poll_records: Maximum records per poll
            max_poll_interval_ms: Maximum interval between polls
        """
        self.topics = topics or [TOPICS["tickets_incoming"]]
        self.group_id = group_id
        self.bootstrap_servers = bootstrap_servers or DEFAULT_BOOTSTRAP_SERVERS
        self.auto_commit = auto_commit
        self.auto_offset_reset = auto_offset_reset
        self.session_timeout_ms = session_timeout_ms
        self.heartbeat_interval_ms = heartbeat_interval_ms
        self.max_poll_records = max_poll_records
        self.max_poll_interval_ms = max_poll_interval_ms
        
        self._consumer: Optional[AIOKafkaConsumer] = None
        self._started = False
        self._running = False
        
    async def start(self) -> None:
        """
        Start the Kafka consumer.
        
        Establishes connection and subscribes to topics.
        """
        if self._started:
            logger.warning("Consumer already started")
            return
        
        try:
            self._consumer = AIOKafkaConsumer(
                *self.topics,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.group_id,
                auto_commit=self.auto_commit,
                auto_offset_reset=self.auto_offset_reset,
                session_timeout_ms=self.session_timeout_ms,
                heartbeat_interval_ms=self.heartbeat_interval_ms,
                max_poll_records=self.max_poll_records,
                max_poll_interval_ms=self.max_poll_interval_ms,
                value_deserializer=lambda v: json.loads(v.decode()) if v else None,
                key_deserializer=lambda k: k.decode() if k else None,
            )
            
            await self._consumer.start()
            self._started = True
            self._running = True
            
            logger.info(
                f"Kafka consumer started. Group: {self.group_id}, "
                f"Topics: {self.topics}"
            )
            
        except Exception as e:
            logger.error(f"Failed to start Kafka consumer: {e}")
            raise
    
    async def stop(self) -> None:
        """
        Stop the Kafka consumer.
        
        Gracefully closes connections.
        """
        if not self._started:
            return
        
        self._running = False
        
        try:
            if self._consumer:
                await self._consumer.stop()
            self._started = False
            logger.info("Kafka consumer stopped")
        except Exception as e:
            logger.error(f"Error stopping Kafka consumer: {e}")
    
    async def consume(self) -> AsyncGenerator[ConsumerRecord, None]:
        """
        Consume messages from subscribed topics.
        
        Yields:
            ConsumerRecord objects with message data
            
        Usage:
            async for record in consumer.consume():
                value = record.value
                key = record.key
                await consumer.commit()
        """
        if not self._started:
            raise RuntimeError("Consumer not started. Call start() first.")
        
        self._running = True
        
        try:
            async for record in self._consumer:
                if not self._running:
                    break
                yield record
        except asyncio.CancelledError:
            logger.info("Consumer cancelled")
        except Exception as e:
            logger.exception(f"Error consuming messages: {e}")
            raise
        finally:
            self._running = False
    
    async def commit(self) -> None:
        """
        Commit consumed offsets.
        
        Call this after successfully processing a message.
        """
        if self._consumer and self._started:
            await self._consumer.commit()
    
    async def seek_to_beginning(self, *partitions: TopicPartition) -> None:
        """
        Seek to the beginning of partitions.
        
        Args:
            partitions: Optional specific partitions, or all if none provided
        """
        if self._consumer:
            if partitions:
                await self._consumer.seek_to_beginning(*partitions)
            else:
                await self._consumer.seek_to_beginning()
    
    async def seek_to_end(self, *partitions: TopicPartition) -> None:
        """
        Seek to the end of partitions.
        
        Args:
            partitions: Optional specific partitions, or all if none provided
        """
        if self._consumer:
            if partitions:
                await self._consumer.seek_to_end(*partitions)
            else:
                await self._consumer.seek_to_end()
    
    async def seek(self, partition: TopicPartition, offset: int) -> None:
        """
        Seek to specific offset in partition.
        
        Args:
            partition: Topic partition
            offset: Offset to seek to
        """
        if self._consumer:
            await self._consumer.seek(partition, offset)
    
    def subscribe(
        self,
        topics: List[str],
        on_assign: Optional[Callable[[List[TopicPartition]], Awaitable[None]]] = None,
        on_revoke: Optional[Callable[[List[TopicPartition]], Awaitable[None]]] = None,
    ) -> None:
        """
        Subscribe to topics dynamically.
        
        Args:
            topics: List of topic names
            on_assign: Callback when partitions are assigned
            on_revoke: Callback when partitions are revoked
        """
        if self._consumer:
            self._consumer.subscribe(
                set(topics),
                on_assign=on_assign,
                on_revoke=on_revoke,
            )
            self.topics = topics
    
    def unsubscribe(self) -> None:
        """Unsubscribe from all topics."""
        if self._consumer:
            self._consumer.unsubscribe()
    
    @property
    def is_started(self) -> bool:
        """Check if consumer is started."""
        return self._started
    
    @property
    def is_running(self) -> bool:
        """Check if consumer is running."""
        return self._running


# =============================================================================
# KAFKA CLIENT (Combined Producer + Consumer)
# =============================================================================


class FTEKafkaClient:
    """
    Combined Kafka client for Customer Success FTE.
    
    Provides both producer and consumer functionality in a single class
    for convenience.
    
    Usage:
        client = FTEKafkaClient(
            bootstrap_servers=["localhost:9092"],
            consumer_group="fte-processor",
        )
        await client.start()
        
        # Publish
        await client.publish_ticket({...})
        
        # Consume
        async for msg in client.consume(["fte.tickets.incoming"]):
            await process(msg)
            await client.commit()
        
        await client.stop()
    """
    
    def __init__(
        self,
        bootstrap_servers: List[str] = None,
        consumer_group: str = "fte-processor",
    ):
        """
        Initialize Kafka client.
        
        Args:
            bootstrap_servers: Kafka broker addresses
            consumer_group: Consumer group ID
        """
        self.bootstrap_servers = bootstrap_servers or DEFAULT_BOOTSTRAP_SERVERS
        self.consumer_group = consumer_group
        
        self._producer: Optional[FTEKafkaProducer] = None
        self._consumer: Optional[FTEKafkaConsumer] = None
        
    async def start(self) -> None:
        """Start both producer and consumer."""
        self._producer = FTEKafkaProducer(bootstrap_servers=self.bootstrap_servers)
        await self._producer.start()
        
        logger.info("Kafka client producer started")
    
    async def start_consumer(self, topics: List[str] = None) -> None:
        """
        Start consumer for specific topics.
        
        Args:
            topics: Topics to consume from
        """
        self._consumer = FTEKafkaConsumer(
            topics=topics or [TOPICS["tickets_incoming"]],
            group_id=self.consumer_group,
            bootstrap_servers=self.bootstrap_servers,
        )
        await self._consumer.start()
        
        logger.info(f"Kafka client consumer started for topics: {topics}")
    
    async def stop(self) -> None:
        """Stop both producer and consumer."""
        if self._consumer:
            await self._consumer.stop()
        if self._producer:
            await self._producer.stop()
        logger.info("Kafka client stopped")
    
    async def publish(self, topic: str, value: Dict[str, Any], key: Optional[str] = None) -> Dict[str, Any]:
        """Publish message to topic."""
        if not self._producer:
            raise RuntimeError("Producer not started")
        return await self._producer.publish(topic, value, key)
    
    async def publish_ticket(self, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """Publish ticket to incoming topic."""
        if not self._producer:
            raise RuntimeError("Producer not started")
        return await self._producer.publish_ticket(ticket_data)
    
    async def consume(self) -> AsyncGenerator[ConsumerRecord, None]:
        """Consume messages."""
        if not self._consumer:
            raise RuntimeError("Consumer not started")
        async for record in self._consumer.consume():
            yield record
    
    async def commit(self) -> None:
        """Commit offsets."""
        if self._consumer:
            await self._consumer.commit()
    
    @property
    def producer(self) -> Optional[FTEKafkaProducer]:
        """Get producer instance."""
        return self._producer
    
    @property
    def consumer(self) -> Optional[FTEKafkaConsumer]:
        """Get consumer instance."""
        return self._consumer


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


async def create_topics(
    bootstrap_servers: List[str],
    topics: Dict[str, Dict[str, Any]] = None,
) -> None:
    """
    Create Kafka topics if they don't exist.
    
    Note: This requires admin privileges on the Kafka cluster.
    In production, topics are typically created by infrastructure team.
    
    Args:
        bootstrap_servers: Kafka broker addresses
        topics: Topic configurations (uses TOPIC_CONFIGS if None)
    """
    from aiokafka.admin import AIOKafkaAdminClient, NewTopic
    
    admin_client = AIOKafkaAdminClient(bootstrap_servers=bootstrap_servers)
    
    topics_to_create = topics or TOPIC_CONFIGS
    new_topics = []
    
    for topic_name, config in topics_to_create.items():
        new_topic = NewTopic(
            name=topic_name,
            num_partitions=config.get("partitions", 3),
            replication_factor=config.get("replication_factor", 1),
            topic_configs={
                "retention.ms": str(config.get("retention_ms", 604800000)),
                "max.message.bytes": str(config.get("max_message_bytes", 1048576)),
            }
        )
        new_topics.append(new_topic)
    
    try:
        await admin_client.create_topics(new_topics)
        logger.info(f"Created {len(new_topics)} topics")
    except Exception as e:
        logger.warning(f"Could not create topics (may already exist): {e}")
    finally:
        await admin_client.close()


def get_all_topics() -> List[str]:
    """Get list of all topic names."""
    return list(TOPICS.values())


def get_topic_for_channel(channel: str) -> str:
    """Get topic name for a channel."""
    channel_map = {
        "email": TOPICS["channel_email"],
        "whatsapp": TOPICS["channel_whatsapp"],
        "web_form": TOPICS["channel_web_form"],
    }
    return channel_map.get(channel, TOPICS["channel_web_form"])


# =============================================================================
# MAIN (for testing)
# =============================================================================


if __name__ == "__main__":
    async def test_kafka():
        # Test producer
        producer = FTEKafkaProducer()
        await producer.start()
        
        # Publish test message
        result = await producer.publish_ticket({
            "channel": "email",
            "channel_message_id": "test-123",
            "customer_email": "test@example.com",
            "customer_name": "Test User",
            "content": "This is a test message",
        })
        print(f"Published: {result}")
        
        await producer.stop()
        
        # Test consumer
        consumer = FTEKafkaConsumer(
            topics=[TOPICS["tickets_incoming"]],
            group_id="test-consumer",
        )
        await consumer.start()
        
        # Consume one message
        async for record in consumer.consume():
            print(f"Received: {record.value}")
            await consumer.commit()
            break
        
        await consumer.stop()
    
    # asyncio.run(test_kafka())
    pass
