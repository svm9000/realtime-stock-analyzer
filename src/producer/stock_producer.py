import time
import json
from typing import List, Dict, Any
from os import getenv

import numpy as np
import yfinance as yf
from kafka import KafkaProducer
from kafka.errors import KafkaError

from src.logger import get_logger

logger = get_logger(__name__)

KAFKA_BROKER: str = getenv("KAFKA_BROKER", "kafka:9092")
KAFKA_TOPIC: str = getenv("KAFKA_TOPIC", "stock_prices")
STOCK_SYMBOLS: List[str] = getenv("STOCK_SYMBOLS", "AAPL,MSFT,GOOGL,NVDA").split(",")

def get_historical_volatility(symbol: str, window: int = 30) -> float:
    """
    Calculate annualized volatility using historical daily log returns.
    """
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period=f"{window+1}d")
    if hist.empty or len(hist['Close']) < window:
        logger.warning(f"Not enough data to calculate volatility for {symbol}")
        return 0.0
    log_returns = np.log(hist['Close'] / hist['Close'].shift(1)).dropna()
    daily_vol = log_returns.std()
    annual_vol = daily_vol * np.sqrt(252)
    return float(annual_vol)

def get_latest_price(symbol: str) -> float:
    """
    Fetch the most recent closing price for the given symbol.
    """
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period="2d")
    if hist.empty or len(hist['Close']) < 1:
        logger.warning(f"Could not fetch latest price for {symbol}")
        return 0.0
    return float(hist['Close'][-1])

def simulate_next_price(
    current_price: float,
    volatility: float,
    mu: float = 0.0,
    dt: float = 1/252
) -> float:
    """
    Simulate the next price using Geometric Brownian Motion.
    """
    z: float = np.random.normal()
    next_price: float = current_price * np.exp((mu - 0.5 * volatility ** 2) * dt + volatility * np.sqrt(dt) * z)
    return float(next_price)

class PriceCache:
    def __init__(self):
        self.cache: Dict[str, float] = {}

    def get_price(self, symbol: str) -> float:
        if symbol not in self.cache:
            price = get_latest_price(symbol)
            self.cache[symbol] = price
        return self.cache[symbol]
    
class StockProducer:
    def __init__(self) -> None:
        self.producer = KafkaProducer(
            bootstrap_servers=KAFKA_BROKER,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )

    def produce(self, message: Dict[str, Any]) -> None:
        """
        Send a message to the Kafka topic.
        """
        try:
            self.producer.send(KAFKA_TOPIC, value=message)
        except KafkaError as e:
            logger.error(f"Kafka error: {e}")
       
    def simulate_and_send(self, interval: int = 1) -> None:
        """
        Simulate stock prices and send them to Kafka at regular intervals.
        """
        price_cache = PriceCache()
        while True:
            for symbol in STOCK_SYMBOLS:
                try:
                    price = price_cache.get_price(symbol)
                    if price == 0.0:
                        continue
                    volatility = get_historical_volatility(symbol)
                    if volatility == 0.0:
                        continue
                    simulated_price = simulate_next_price(price, volatility)
                    message: Dict[str, Any] = {
                        "symbol": symbol,
                        "price": round(simulated_price, 2),
                        "timestamp": time.time()
                    }
                    self.produce(message)
                    logger.info(f"Produced: {message}")
                except Exception as e:
                    logger.error(f"Error processing {symbol}: {e}")
            self.producer.flush()
            time.sleep(interval)

if __name__ == "__main__":
    producer = StockProducer()
    producer.simulate_and_send()
