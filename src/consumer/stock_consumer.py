import os
import json
import logging
from kafka import KafkaConsumer
from typing import Optional, Dict, Any, List
from src.consumer.redis_handler import RedisHandler
from src.consumer.postgres_handler import PostgresHandler
from src.logger import get_logger  # Import the centralized logger


class KafkaMessageConsumer:
    def __init__(self, broker: str, topic: str, group_id: str = "default-group") -> None:
        """
        Initialize the Kafka consumer with the given broker, topic, and group ID.
        """
        self.broker: str = broker
        self.topic: str = topic
        self.group_id: str = group_id
        self.consumer: Optional[KafkaConsumer] = None
        self.logger: logging.Logger = get_logger(self.__class__.__name__)  # Use centralized logger
        self.redis_handler: RedisHandler = RedisHandler(host="redis")
        self.postgres_handler: PostgresHandler = PostgresHandler()
        self.redis_key: str = "stock_updates"

    def connect(self) -> None:
        """
        Connect to the Kafka broker and initialize the consumer.
        """
        self.logger.info(f"Connecting to Kafka broker at {self.broker} on topic '{self.topic}'...")
        self.consumer = KafkaConsumer(
            self.topic,
            bootstrap_servers=self.broker,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='latest',
            group_id=self.group_id
        )
        self.logger.info("Connected to Kafka successfully.")

    def consume_messages(self) -> None:
        """
        Consume messages from the Kafka topic and process them.
        """
        if not self.consumer:
            self.logger.error("Consumer is not connected. Call 'connect()' first.")
            return

        self.logger.info("Listening for messages...")
        try:
            for msg in self.consumer:
                self.process_message(msg.value)
        except Exception as e:
            self.logger.error(f"Error while consuming messages: {e}")
        finally:
            self.close()

    def process_message(self, message: Dict[str, Any]) -> None:
        """
        Process a single message. Maintain a rolling 100 messages in Redis and append all messages to PostgreSQL.
        """
        self.logger.info(f"Received message: {message}")

        # Ensure the PostgreSQL table exists
        self.postgres_handler.create_table()

        # Append the message to PostgreSQL for long-term storage
        self.postgres_handler.insert_messages([message])

        # Add the message to Redis for short-term storage
        self.redis_handler.store_message(self.redis_key, message)

        # Maintain a rolling 1000 messages in Redis
        self.redis_handler.trim_list(self.redis_key, -1000, -1)

    def close(self) -> None:
        """
        Close the Kafka consumer connection.
        """
        if self.consumer:
            self.logger.info("Closing Kafka consumer...")
            self.consumer.close()
            self.logger.info("Kafka consumer closed.")


if __name__ == "__main__":
    # Load environment variables for Kafka configuration
    KAFKA_BROKER: str = os.getenv("KAFKA_BROKER", "kafka:9092")
    KAFKA_TOPIC: str = os.getenv("KAFKA_TOPIC", "stock_prices")
    KAFKA_GROUP_ID: str = os.getenv("KAFKA_GROUP_ID", "kafka_group")
    # Initialize and run the Kafka consumer
    consumer = KafkaMessageConsumer(broker=KAFKA_BROKER, topic=KAFKA_TOPIC, group_id=KAFKA_GROUP_ID)
    consumer.connect()
    consumer.consume_messages()