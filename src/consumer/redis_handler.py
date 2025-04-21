import redis
import json
import logging
from typing import List, Dict
from src.logger import get_logger  # Use centralized logger

class RedisHandler:
    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0) -> None:
        """
        Initialize the Redis client.
        """
        self.logger = get_logger(self.__class__.__name__)  # Use centralized logger
        try:
            self.client: redis.StrictRedis = redis.StrictRedis(host=host, port=port, db=db, decode_responses=True)
            self.client.ping()  # Test connection
            self.logger.info(f"Connected to Redis at {host}:{port}, DB: {db}")
        except redis.ConnectionError as e:
            self.logger.error(f"Failed to connect to Redis at {host}:{port}, DB: {db}. Error: {e}")
            raise

    def store_message(self, key: str, message: Dict) -> None:
        """
        Store a message in Redis under the given key.
        """
        try:
            self.client.rpush(key, json.dumps(message))
            self.logger.info(f"Stored message in Redis under key '{key}': {message}")
        except Exception as e:
            self.logger.error(f"Failed to store message in Redis under key '{key}'. Error: {e}")

    def get_messages(self, key: str) -> List[Dict]:
        """
        Retrieve all messages stored under the given key.
        """
        try:
            messages = [json.loads(msg) for msg in self.client.lrange(key, 0, -1)]
            self.logger.info(f"Retrieved {len(messages)} messages from Redis under key '{key}'")
            return messages
        except Exception as e:
            self.logger.error(f"Failed to retrieve messages from Redis under key '{key}'. Error: {e}")
            return []

    def trim_list(self, key: str, start: int, end: int) -> None:
        """
        Trim the Redis list to only keep elements within the specified range.
        """
        try:
            self.client.ltrim(key, start, end)
            self.logger.info(f"Trimmed Redis list under key '{key}' to range {start}:{end}")
        except Exception as e:
            self.logger.error(f"Failed to trim Redis list under key '{key}'. Error: {e}")

    def clear_messages(self, key: str) -> None:
        """
        Clear all messages stored under the given key.
        """
        try:
            self.client.delete(key)
            self.logger.info(f"Cleared all messages from Redis under key '{key}'")
        except Exception as e:
            self.logger.error(f"Failed to clear messages from Redis under key '{key}'. Error: {e}")