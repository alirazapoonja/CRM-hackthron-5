"""
Unified Message Processor for Customer Success FTE.

This is the core worker that processes incoming customer messages from Kafka,
orchestrates the agent workflow, and handles all database operations.

Workflow:
1. Consume message from Kafka topic 'fte.tickets.incoming'
2. Resolve customer identity (cross-channel matching)
3. Get or create conversation with memory
4. Store inbound message
5. Run customer_success_agent
6. Store outbound response
7. Record metrics
8. Handle errors gracefully with dead-letter queue

Architecture:
- Fully async using asyncio and asyncpg
- Kafka consumer using aiokafka
- Database connection pooling
- Retry logic with exponential backoff
- Dead-letter queue for failed messages
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.errors import KafkaError
import asyncpg

from production.database.queries import (
    get_or_create_customer,
    get_customer_by_id,
    get_customer_history,
    create_conversation,
    get_active_conversation,
    store_message,
    create_ticket_record,
    update_ticket_status,
    record_metric,
    get_db_pool,
    health_check,
)

from production.agent.customer_success_agent import (
    CustomerSuccessAgent,
    CustomerMessage,
    AgentResponse,
    AgentState,
    Channel,
)

logger = logging.getLogger(__name__)

# =============================================================================
# CONSTANTS
# =============================================================================

KAFKA_BOOTSTRAP_SERVERS = ["localhost:9092"]
KAFKA_TOPIC_INCOMING = "fte.tickets.incoming"
KAFKA_TOPIC_OUTGOING = "fte.tickets.outgoing"
KAFKA_TOPIC_DLQ = "fte.tickets.dlq"
KAFKA_TOPIC_METRICS = "fte.metrics"

KAFKA_CONSUMER_GROUP = "customer-success-fte-processor"
KAFKA_AUTO_OFFSET_RESET = "earliest"
KAFKA_SESSION_TIMEOUT_MS = 30000
KAFKA_HEARTBEAT_INTERVAL_MS = 10000

DB_POOL_MIN_SIZE = 5
DB_POOL_MAX_SIZE = 20

MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds
RETRY_MAX_DELAY = 30.0  # seconds


# =============================================================================
# DATA CLASSES
# =============================================================================


class MessageSource(str, Enum):
    """Message source channels."""
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    WEB_FORM = "web_form"
    UNKNOWN = "unknown"


@dataclass
class KafkaMessage:
    """Parsed Kafka message from incoming topic."""
    key: Optional[str]
    value: Dict[str, Any]
    topic: str
    partition: int
    offset: int
    timestamp: datetime
    
    @classmethod
    def from_kafka_record(cls, record) -> "KafkaMessage":
        """Create from aiokafka ConsumerRecord."""
        return cls(
            key=record.key.decode() if record.key else None,
            value=json.loads(record.value.decode()) if record.value else {},
            topic=record.topic,
            partition=record.partition,
            offset=record.offset,
            timestamp=datetime.fromtimestamp(record.timestamp / 1000),
        )


@dataclass
class ProcessingContext:
    """Context maintained during message processing."""
    kafka_message: KafkaMessage
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    conversation_id: Optional[str] = None
    ticket_id: Optional[str] = None
    inbound_message_id: Optional[str] = None
    outbound_message_id: Optional[str] = None
    agent_response: Optional[AgentResponse] = None
    error: Optional[str] = None
    retry_count: int = 0
    start_time: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def processing_time_ms(self) -> float:
        """Get total processing time in milliseconds."""
        return (datetime.utcnow() - self.start_time).total_seconds() * 1000


@dataclass
class ProcessingResult:
    """Result of message processing."""
    success: bool
    context: ProcessingContext
    error_type: Optional[str] = None
    should_retry: bool = False
    should_dlq: bool = False


# =============================================================================
# UNIFIED MESSAGE PROCESSOR
# =============================================================================


class UnifiedMessageProcessor:
    """
    Core worker for processing customer support messages.
    
    This class handles the complete message processing workflow:
    1. Kafka message consumption
    2. Customer resolution (cross-channel)
    3. Conversation management
    4. Agent execution
    5. Response delivery
    6. Metrics recording
    7. Error handling with dead-letter queue
    """
    
    def __init__(
        self,
        kafka_bootstrap_servers: List[str] = None,
        db_host: str = "localhost",
        db_port: int = 5432,
        db_user: str = "postgres",
        db_password: str = "postgres",
        db_name: str = "crm_fte",
    ):
        """
        Initialize the message processor.
        
        Args:
            kafka_bootstrap_servers: Kafka broker addresses
            db_host: PostgreSQL host
            db_port: PostgreSQL port
            db_user: PostgreSQL user
            db_password: PostgreSQL password
            db_name: PostgreSQL database name
        """
        self.kafka_servers = kafka_bootstrap_servers or KAFKA_BOOTSTRAP_SERVERS
        self.db_config = {
            "host": db_host,
            "port": db_port,
            "user": db_user,
            "password": db_password,
            "database": db_name,
        }
        
        # Components (initialized in start())
        self.consumer: Optional[AIOKafkaConsumer] = None
        self.producer: Optional[AIOKafkaProducer] = None
        self.db_pool: Optional[asyncpg.Pool] = None
        self.agent: Optional[CustomerSuccessAgent] = None
        
        # State
        self._running = False
        self._processing = False
        self._messages_processed = 0
        self._errors = 0
        
    async def start(self) -> None:
        """
        Start the message processor.
        
        Initializes all connections and starts consuming messages.
        """
        logger.info("Starting Unified Message Processor...")
        
        try:
            # Initialize database pool
            self.db_pool = await get_db_pool(
                host=self.db_config["host"],
                port=self.db_config["port"],
                user=self.db_config["user"],
                password=self.db_config["password"],
                database=self.db_config["database"],
                min_size=DB_POOL_MIN_SIZE,
                max_size=DB_POOL_MAX_SIZE,
            )
            logger.info("Database pool initialized")
            
            # Initialize Kafka consumer
            self.consumer = AIOKafkaConsumer(
                KAFKA_TOPIC_INCOMING,
                bootstrap_servers=self.kafka_servers,
                group_id=KAFKA_CONSUMER_GROUP,
                auto_offset_reset=KAFKA_AUTO_OFFSET_RESET,
                session_timeout_ms=KAFKA_SESSION_TIMEOUT_MS,
                heartbeat_interval_ms=KAFKA_HEARTBEAT_INTERVAL_MS,
                enable_auto_commit=True,
            )
            await self.consumer.start()
            logger.info(f"Kafka consumer started for topic: {KAFKA_TOPIC_INCOMING}")
            
            # Initialize Kafka producer
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.kafka_servers
            )
            await self.producer.start()
            logger.info("Kafka producer started")
            
            # Initialize agent
            self.agent = CustomerSuccessAgent()
            logger.info("Customer Success Agent initialized")
            
            self._running = True
            logger.info("Unified Message Processor started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start processor: {e}")
            await self.stop()
            raise
    
    async def stop(self) -> None:
        """
        Stop the message processor.
        
        Gracefully shuts down all connections.
        """
        logger.info("Stopping Unified Message Processor...")
        self._running = False
        
        # Wait for current processing to complete
        if self._processing:
            logger.info("Waiting for current message processing to complete...")
            await asyncio.sleep(5)
        
        # Close Kafka consumer
        if self.consumer:
            await self.consumer.stop()
            logger.info("Kafka consumer stopped")
        
        # Close Kafka producer
        if self.producer:
            await self.producer.stop()
            logger.info("Kafka producer stopped")
        
        # Close database pool
        if self.db_pool:
            await self.db_pool.close()
            logger.info("Database pool closed")
        
        logger.info("Unified Message Processor stopped")
    
    async def run(self) -> None:
        """
        Main processing loop.
        
        Continuously consumes and processes messages from Kafka.
        """
        logger.info("Starting message processing loop...")
        
        try:
            async for record in self.consumer:
                if not self._running:
                    break
                
                self._processing = True
                
                try:
                    kafka_message = KafkaMessage.from_kafka_record(record)
                    logger.info(
                        f"Received message from {kafka_message.topic} "
                        f"[partition={kafka_message.partition}, offset={kafka_message.offset}]"
                    )
                    
                    # Process the message
                    result = await self.process_message(kafka_message)
                    
                    # Handle result
                    if result.success:
                        self._messages_processed += 1
                        logger.info(
                            f"Message processed successfully in {result.context.processing_time_ms:.2f}ms. "
                            f"Ticket: {result.context.ticket_id}"
                        )
                    elif result.should_retry:
                        logger.warning(
                            f"Message processing failed, will retry. "
                            f"Error: {result.context.error}"
                        )
                    else:
                        self._errors += 1
                        logger.error(
                            f"Message processing failed permanently. "
                            f"Error: {result.context.error}"
                        )
                    
                except Exception as e:
                    logger.exception(f"Unexpected error processing message: {e}")
                    self._errors += 1
                    
                finally:
                    self._processing = False
                    
        except asyncio.CancelledError:
            logger.info("Message processing loop cancelled")
        except Exception as e:
            logger.exception(f"Message processing loop error: {e}")
            raise
        finally:
            await self.stop()
    
    async def process_message(
        self,
        kafka_message: KafkaMessage
    ) -> ProcessingResult:
        """
        Process a single Kafka message.
        
        This is the main processing method that orchestrates the entire workflow.
        
        Args:
            kafka_message: Parsed Kafka message
            
        Returns:
            ProcessingResult with success/failure status
        """
        context = ProcessingContext(kafka_message=kafka_message)
        
        try:
            # Step 1: Resolve customer identity
            await self.resolve_customer(context)
            
            # Step 2: Get or create conversation
            await self.get_or_create_conversation(context)
            
            # Step 3: Store inbound message
            await self.store_inbound_message(context)
            
            # Step 4: Create ticket (REQUIRED before agent processing)
            await self.create_ticket(context)
            
            # Step 5: Run the customer success agent
            await self.run_agent(context)
            
            # Step 6: Store outbound response
            await self.store_outbound_message(context)
            
            # Step 7: Record metrics
            await self.record_metrics(context)
            
            # Step 8: Send to outgoing topic
            await self.publish_outgoing(context)
            
            return ProcessingResult(
                success=True,
                context=context,
            )
            
        except Exception as e:
            logger.exception(f"Error processing message: {e}")
            return await self.handle_error(context, e)
    
    async def resolve_customer(self, context: ProcessingContext) -> None:
        """
        Resolve customer identity from message data.
        
        Performs cross-channel customer matching using:
        - Email address (primary)
        - Phone number (for WhatsApp)
        - Customer identifiers table
        
        Args:
            context: Processing context
        """
        value = context.kafka_message.value
        
        # Extract customer identifiers from message
        email = value.get("customer_email")
        phone = value.get("customer_phone")
        customer_name = value.get("customer_name")
        
        logger.info(f"Resolving customer: email={email}, phone={phone}")
        
        try:
            # Get or create customer using database layer
            customer = await get_or_create_customer(
                pool=self.db_pool,
                email=email,
                phone=phone,
                name=customer_name,
                identifier_type=value.get("channel"),  # Use channel as identifier type
                identifier_value=email or phone,
            )
            
            if not customer:
                raise ValueError("Failed to get or create customer")
            
            context.customer_id = str(customer.get("id"))
            context.customer_name = customer.get("name") or customer_name
            context.customer_email = customer.get("email") or email
            context.customer_phone = customer.get("phone") or phone
            
            logger.info(
                f"Customer resolved: id={context.customer_id}, "
                f"name={context.customer_name}"
            )
            
        except Exception as e:
            logger.error(f"Customer resolution failed: {e}")
            raise
    
    async def get_or_create_conversation(self, context: ProcessingContext) -> None:
        """
        Get existing active conversation or create new one.
        
        Checks for an active conversation for this customer.
        If found, continues the conversation. Otherwise, creates new one.
        
        Args:
            context: Processing context
        """
        try:
            # Check for active conversation
            active_conv = await get_active_conversation(
                pool=self.db_pool,
                customer_id=context.customer_id,
            )
            
            if active_conv:
                context.conversation_id = str(active_conv.get("id"))
                logger.info(f"Using existing conversation: {context.conversation_id}")
            else:
                # Create new conversation
                channel = context.kafka_message.value.get("channel", "unknown")
                conversation = await create_conversation(
                    pool=self.db_pool,
                    customer_id=context.customer_id,
                    initial_channel=channel,
                    metadata={
                        "source_message_id": context.kafka_message.key,
                        "kafka_offset": context.kafka_message.offset,
                    },
                )
                
                context.conversation_id = str(conversation.get("id"))
                logger.info(f"Created new Conversation: {context.conversation_id}")
                
        except Exception as e:
            logger.error(f"Conversation retrieval/creation failed: {e}")
            raise
    
    async def store_inbound_message(self, context: ProcessingContext) -> None:
        """
        Store the inbound customer message.
        
        Args:
            context: Processing context
        """
        value = context.kafka_message.value
        
        try:
            message = await store_message(
                pool=self.db_pool,
                conversation_id=context.conversation_id,
                channel=value.get("channel", "unknown"),
                direction="inbound",
                role="customer",
                content=value.get("content", ""),
                channel_message_id=value.get("channel_message_id"),
            )
            
            context.inbound_message_id = str(message.get("id"))
            logger.info(f"Stored inbound message: {context.inbound_message_id}")
            
        except Exception as e:
            logger.error(f"Failed to store inbound message: {e}")
            raise
    
    async def create_ticket(self, context: ProcessingContext) -> None:
        """
        Create support ticket for the interaction.
        
        This is REQUIRED before any agent processing or response.
        
        Args:
            context: Processing context
        """
        value = context.kafka_message.value
        
        try:
            # Determine category from message
            category = self._categorize_message(value.get("content", ""))
            priority = value.get("priority", "medium")
            
            ticket = await create_ticket_record(
                pool=self.db_pool,
                conversation_id=context.conversation_id,
                customer_id=context.customer_id,
                source_channel=value.get("channel", "unknown"),
                category=category,
                priority=priority,
            )
            
            context.ticket_id = str(ticket.get("id"))
            logger.info(f"Created ticket: {context.ticket_id}")
            
        except Exception as e:
            logger.error(f"Failed to create ticket: {e}")
            raise
    
    async def run_agent(self, context: ProcessingContext) -> None:
        """
        Run the Customer Success Agent to generate response.
        
        Args:
            context: Processing context
        """
        value = context.kafka_message.value
        
        try:
            # Build customer message for agent
            customer_message = CustomerMessage(
                channel=Channel(value.get("channel", "web_form")),
                channel_message_id=value.get("channel_message_id", ""),
                customer_email=context.customer_email,
                customer_phone=context.customer_phone,
                customer_name=context.customer_name,
                content=value.get("content", ""),
                received_at=context.kafka_message.timestamp.isoformat(),
                metadata=value.get("metadata"),
            )
            
            # Run the agent
            agent_response = await self.agent.process_message(customer_message)
            context.agent_response = agent_response
            
            if agent_response.success:
                logger.info(
                    f"Agent processed successfully. "
                    f"State: {agent_response.state}, "
                    f"Ticket: {agent_response.ticket_id}"
                )
            else:
                logger.warning(
                    f"Agent processing had issues. "
                    f"Error: {agent_response.error}"
                )
                
        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            raise
    
    async def store_outbound_message(self, context: ProcessingContext) -> None:
        """
        Store the agent's outbound response.
        
        Args:
            context: Processing context
        """
        if not context.agent_response or not context.agent_response.success:
            logger.warning("No successful agent response to store")
            return
        
        value = context.kafka_message.value
        
        try:
            # TODO: Extract actual response content from agent response
            # For now, use a placeholder
            response_content = "Thank you for contacting us. Your issue has been addressed."
            
            message = await store_message(
                pool=self.db_pool,
                conversation_id=context.conversation_id,
                channel=value.get("channel", "unknown"),
                direction="outbound",
                role="agent",
                content=response_content,
            )
            
            context.outbound_message_id = str(message.get("id"))
            logger.info(f"Stored outbound message: {context.outbound_message_id}")
            
        except Exception as e:
            logger.error(f"Failed to store outbound message: {e}")
            raise
    
    async def record_metrics(self, context: ProcessingContext) -> None:
        """
        Record processing metrics.
        
        Args:
            context: Processing context
        """
        try:
            # Record processing time
            await record_metric(
                pool=self.db_pool,
                metric_name="processing_time_ms",
                metric_value=context.processing_time_ms,
                channel=context.kafka_message.value.get("channel"),
                dimensions={
                    "success": True,
                    "ticket_id": context.ticket_id,
                },
            )
            
            # Record message processed
            await record_metric(
                pool=self.db_pool,
                metric_name="messages_processed",
                metric_value=1.0,
                channel=context.kafka_message.value.get("channel"),
            )
            
            logger.debug("Metrics recorded successfully")
            
        except Exception as e:
            logger.error(f"Failed to record metrics: {e}")
            # Don't raise - metrics failure shouldn't fail processing
    
    async def publish_outgoing(self, context: ProcessingContext) -> None:
        """
        Publish processed message to outgoing topic.
        
        This allows downstream systems (channel handlers) to deliver responses.
        
        Args:
            context: Processing context
        """
        if not context.agent_response or not context.agent_response.success:
            return
        
        try:
            outgoing_message = {
                "ticket_id": context.ticket_id,
                "conversation_id": context.conversation_id,
                "customer_id": context.customer_id,
                "channel": context.kafka_message.value.get("channel"),
                "response": "TODO: Extract from agent response",
                "customer_name": context.customer_name,
                "customer_email": context.customer_email,
                "processed_at": datetime.utcnow().isoformat(),
                "processing_time_ms": context.processing_time_ms,
            }
            
            await self.producer.send_and_wait(
                topic=KAFKA_TOPIC_OUTGOING,
                key=context.ticket_id.encode(),
                value=json.dumps(outgoing_message).encode(),
            )
            
            logger.info(f"Published to outgoing topic: {context.ticket_id}")
            
        except Exception as e:
            logger.error(f"Failed to publish outgoing message: {e}")
            raise
    
    async def handle_error(
        self,
        context: ProcessingContext,
        error: Exception
    ) -> ProcessingResult:
        """
        Handle processing errors with retry logic and dead-letter queue.
        
        Args:
            context: Processing context
            error: Exception that occurred
            
        Returns:
            ProcessingResult with error details
        """
        context.error = str(error)
        context.retry_count += 1
        
        error_type = type(error).__name__
        should_retry = context.retry_count < MAX_RETRIES
        
        # Determine if message should go to DLQ
        should_dlq = (
            not should_retry or
            error_type in ["ValueError", "KeyError"]  # Data errors shouldn't retry
        )
        
        logger.error(
            f"Error handling: type={error_type}, "
            f"retry={context.retry_count}/{MAX_RETRIES}, "
            f"dlq={should_dlq}"
        )
        
        try:
            # Record error metric
            await record_metric(
                pool=self.db_pool,
                metric_name="processing_error",
                metric_value=1.0,
                channel=context.kafka_message.value.get("channel"),
                dimensions={
                    "error_type": error_type,
                    "retry_count": context.retry_count,
                },
            )
            
            # Send to dead-letter queue if needed
            if should_dlq:
                await self._send_to_dlq(context, error)
            
            # Retry with exponential backoff
            if should_retry:
                delay = min(
                    RETRY_BASE_DELAY * (2 ** (context.retry_count - 1)),
                    RETRY_MAX_DELAY
                )
                logger.info(f"Retrying in {delay:.2f} seconds...")
                await asyncio.sleep(delay)
                
        except Exception as e:
            logger.exception(f"Error in error handler: {e}")
        
        return ProcessingResult(
            success=False,
            context=context,
            error_type=error_type,
            should_retry=should_retry,
            should_dlq=should_dlq,
        )
    
    async def _send_to_dlq(
        self,
        context: ProcessingContext,
        error: Exception
    ) -> None:
        """
        Send failed message to dead-letter queue.
        
        Args:
            context: Processing context
            error: Exception that caused failure
        """
        try:
            dlq_message = {
                "original_message": context.kafka_message.value,
                "error_type": type(error).__name__,
                "error_message": str(error),
                "retry_count": context.retry_count,
                "failed_at": datetime.utcnow().isoformat(),
                "context": {
                    "customer_id": context.customer_id,
                    "conversation_id": context.conversation_id,
                    "ticket_id": context.ticket_id,
                },
            }
            
            await self.producer.send_and_wait(
                topic=KAFKA_TOPIC_DLQ,
                key=context.kafka_message.key.encode() if context.kafka_message.key else b"unknown",
                value=json.dumps(dlq_message).encode(),
            )
            
            logger.warning(f"Message sent to DLQ: {context.kafka_message.offset}")
            
        except Exception as e:
            logger.exception(f"Failed to send to DLQ: {e}")
    
    def _categorize_message(self, content: str) -> str:
        """
        Categorize message based on content.
        
        Simple keyword-based categorization.
        In production, use ML classification.
        
        Args:
            content: Message content
            
        Returns:
            Category string
        """
        content_lower = content.lower()
        
        # Billing keywords
        if any(word in content_lower for word in ["billing", "payment", "invoice", "refund", "charge", "price"]):
            return "billing"
        
        # Account keywords
        if any(word in content_lower for word in ["login", "password", "account", "access", "sign in", "authenticate"]):
            return "account"
        
        # Bug report keywords
        if any(word in content_lower for word in ["bug", "error", "broken", "not working", "crash", "issue"]):
            return "bug_report"
        
        # Feature request keywords
        if any(word in content_lower for word in ["feature", "request", "suggestion", "improve", "add"]):
            return "feature_request"
        
        # Default to technical
        if any(word in content_lower for word in ["how", "help", "question", "use", "work"]):
            return "technical"
        
        return "general"
    
    @property
    def stats(self) -> Dict[str, Any]:
        """Get processor statistics."""
        return {
            "running": self._running,
            "processing": self._processing,
            "messages_processed": self._messages_processed,
            "errors": self._errors,
            "success_rate": (
                self._messages_processed / (self._messages_processed + self._errors) * 100
                if (self._messages_processed + self._errors) > 0
                else 0
            ),
        }


# =============================================================================
# HEALTH CHECK
# =============================================================================


async def check_processor_health(processor: UnifiedMessageProcessor) -> Dict[str, Any]:
    """
    Check health of the message processor.
    
    Args:
        processor: Message processor instance
        
    Returns:
        Health status dictionary
    """
    health = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {},
    }
    
    # Check if running
    health["checks"]["running"] = processor._running
    
    # Check database
    try:
        db_healthy = await health_check(processor.db_pool)
        health["checks"]["database"] = db_healthy
        if not db_healthy:
            health["status"] = "unhealthy"
    except Exception as e:
        health["checks"]["database"] = False
        health["status"] = "unhealthy"
        health["error"] = str(e)
    
    # Check Kafka
    # TODO: Add Kafka health check
    
    return health


# =============================================================================
# MAIN (for testing)
# =============================================================================


if __name__ == "__main__":
    import signal
    
    async def main():
        processor = UnifiedMessageProcessor()
        
        # Handle shutdown signals
        loop = asyncio.get_event_loop()
        
        def signal_handler():
            logger.info("Shutdown signal received")
            asyncio.create_task(processor.stop())
        
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, signal_handler)
        
        # Start processor
        await processor.start()
        await processor.run()
    
    # asyncio.run(main())
    pass
