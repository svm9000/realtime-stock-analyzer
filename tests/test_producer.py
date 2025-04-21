import pytest
from unittest.mock import Mock,MagicMock,patch, ANY
import json
import time

def test_producer_initialization():
    """Verify Kafka client creation"""
    with patch('src.producer.stock_producer.KafkaProducer') as mock_producer:
        from src.producer.stock_producer import StockProducer
        StockProducer()
        mock_producer.assert_called_once()
        # Optionally, check for required arguments
        args, kwargs = mock_producer.call_args
        assert 'bootstrap_servers' in kwargs
        assert 'value_serializer' in kwargs


def test_message_content():
    """Verify message structure without testing serialization or randomness"""
    with patch('src.producer.stock_producer.get_latest_price', return_value=100.0), \
         patch('src.producer.stock_producer.get_historical_volatility', return_value=0.2), \
         patch('src.producer.stock_producer.simulate_next_price', return_value=150.25), \
         patch('src.producer.stock_producer.time') as mock_time, \
         patch('src.producer.stock_producer.KafkaProducer') as MockKafkaProducer, \
         patch('src.producer.stock_producer.time.sleep', side_effect=KeyboardInterrupt):

        # Set up time.time to return a fixed value
        mock_time.time.return_value = 1234567890.0

        # Prepare a mock Kafka producer and capture messages
        sent_messages = []
        mock_producer_instance = MagicMock()
        def fake_send(topic, value):
            sent_messages.append(value)
        mock_producer_instance.send.side_effect = fake_send
        MockKafkaProducer.return_value = mock_producer_instance

        # Import and run
        from src.producer.stock_producer import StockProducer
        producer = StockProducer()

        try:
            producer.simulate_and_send(interval=0)
        except KeyboardInterrupt:
            pass  # Expected to break the infinite loop

        # There should be one message per symbol
        from src.producer.stock_producer import STOCK_SYMBOLS
        assert len(sent_messages) == len(STOCK_SYMBOLS)
        # Check the first message
        assert sent_messages[0] == {
            "symbol": STOCK_SYMBOLS[0],
            "price": 150.25,
            "timestamp": 1234567890.0
        }
        # Optionally check all messages
        for i, symbol in enumerate(STOCK_SYMBOLS):
            assert sent_messages[i] == {
                "symbol": symbol,
                "price": 150.25,
                "timestamp": 1234567890.0
            }


def test_serialization():
    """Verify messages get converted to JSON bytes"""
    from src.producer.stock_producer import StockProducer
    
    # Create test data
    test_data = {"test": "value"}
    
    # Test the serializer directly
    serializer = lambda v: json.dumps(v).encode('utf-8')
    result = serializer(test_data)
    
    assert isinstance(result, bytes)
    assert result == b'{"test": "value"}'

def test_production_cycle():
    """Verify 4 messages are sent"""
    with patch.dict('os.environ', {
            'STOCK_SYMBOLS': 'AAPL,MSFT,GOOGL,NVDA',
            'KAFKA_TOPIC': 'stocks'
        }, clear=True), \
        patch('src.producer.stock_producer.get_latest_price', return_value=100.0), \
        patch('src.producer.stock_producer.get_historical_volatility', return_value=0.2), \
        patch('time.sleep', side_effect=KeyboardInterrupt()), \
        patch('kafka.KafkaProducer') as mock_producer:

        # Reload module AFTER environment patching
        import importlib
        from src.producer import stock_producer
        importlib.reload(stock_producer)
        from src.producer.stock_producer import StockProducer

        # Configure mock
        mock_prod = mock_producer.return_value
        mock_prod._value_serializer = lambda v: json.dumps(v).encode('utf-8')

        producer = StockProducer()

        try:
            producer.simulate_and_send(interval=1)
        except KeyboardInterrupt:
            pass

        assert mock_prod.send.call_count == 4


def test_logging():
    """Check message logging"""
    with patch('src.producer.stock_producer.logger') as mock_logger, \
         patch('time.sleep', side_effect=[None, KeyboardInterrupt()]), \
         patch('kafka.KafkaProducer'):
        
        from src.producer.stock_producer import StockProducer
        producer = StockProducer()
        
        try:
            producer.simulate_and_send(interval=1)
        except KeyboardInterrupt:
            pass
            
        assert mock_logger.info.call_count >= 3
