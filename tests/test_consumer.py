import pytest
from unittest.mock import Mock, MagicMock, patch, ANY

def test_consumer_initialization():
    """Test constructor without dependencies"""
    with patch('src.consumer.stock_consumer.PostgresHandler'), \
         patch('src.consumer.stock_consumer.RedisHandler'):
        
        from src.consumer.stock_consumer import KafkaMessageConsumer
        consumer = KafkaMessageConsumer(
            broker="kafka:9092",
            topic="test_topic",
            group_id="test_group"
        )
        assert consumer.broker == "kafka:9092"

def test_process_message_mocked():
    """Test message processing with full mocks"""
    with patch('src.consumer.stock_consumer.PostgresHandler') as mock_pg, \
         patch('src.consumer.stock_consumer.RedisHandler'):
        
        from src.consumer.stock_consumer import KafkaMessageConsumer
        consumer = KafkaMessageConsumer(
            broker="kafka:9092",
            topic="test_topic",
            group_id="test_group"
        )
        
        # Mock handler methods directly
        consumer.postgres_handler.create_table = Mock()
        consumer.postgres_handler.insert_messages = Mock()
        consumer.redis_handler.store_message = Mock()
        
        test_msg = {"symbol": "AAPL", "price": 150.25, "timestamp": 1234567890}
        consumer.process_message(test_msg)
        
        consumer.postgres_handler.create_table.assert_called_once()
        consumer.postgres_handler.insert_messages.assert_called_once_with([test_msg])
        consumer.redis_handler.store_message.assert_called_once_with("stock_updates", test_msg)

def test_consume_messages_mocked():
    """Test consumption flow with Kafka mock"""
    with patch('src.consumer.stock_consumer.KafkaConsumer'), \
         patch('src.consumer.stock_consumer.PostgresHandler'), \
         patch('src.consumer.stock_consumer.RedisHandler'):
        
        from src.consumer.stock_consumer import KafkaMessageConsumer
        consumer = KafkaMessageConsumer(
            broker="kafka:9092",
            topic="test_topic",
            group_id="test_group"
        )
        
        # Mock all handler methods
        consumer.postgres_handler.insert_messages = Mock()
        consumer.redis_handler.store_message = Mock()
        
        # Setup test message
        test_msg = {"symbol": "MSFT", "price": 330.50, "timestamp": 1234567890}
        mock_message = MagicMock(value=test_msg)
        consumer.consumer = MagicMock()
        consumer.consumer.__iter__.return_value = [mock_message]
        
        consumer.consume_messages()
        
        consumer.postgres_handler.insert_messages.assert_called_once_with([test_msg])
        consumer.redis_handler.store_message.assert_called_once_with("stock_updates", test_msg)

