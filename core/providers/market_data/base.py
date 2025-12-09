from abc import ABC, abstractmethod
from typing import Protocol, Optional
from datetime import date
from pydantic import BaseModel
import pandas as pd

class OptionsChain(BaseModel):
    symbol: str
    timestamp: str
    expirations: list[str]
    strikes: list[float]
    calls: list[dict]
    puts: list[dict]

class TechnicalData(BaseModel):
    symbol: str
    timestamp: str
    rsi: Optional[float] = None
    macd: Optional[dict] = None
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    ema_12: Optional[float] = None
    ema_26: Optional[float] = None
    bbands: Optional[dict] = None
    atr: Optional[float] = None

class ProviderInfo(BaseModel):
    name: str
    tier: str
    capabilities: list[str]

class MarketDataProvider(Protocol):
    @abstractmethod
    async def get_ohlcv(
        self, symbol: str, start: date, end: date, timeframe: str = '1d'
    ) -> pd.DataFrame:
        """
        Get OHLCV (Open, High, Low, Close, Volume) data for a symbol.
        
        Args:
            symbol: The trading symbol (e.g., 'AAPL')
            start: Start date
            end: End date
            timeframe: Timeframe for the data (e.g., '1d', '1h', '5m')
            
        Returns:
            DataFrame with columns: ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        """
        ...
    
    @abstractmethod
    async def get_options_chain(self, symbol: str, expiration: Optional[str] = None) -> OptionsChain:
        """
        Get options chain data for a symbol.
        
        Args:
            symbol: The trading symbol
            expiration: Optional expiration date in 'YYYY-MM-DD' format
            
        Returns:
            OptionsChain object with calls and puts
        """
        ...
    
    @abstractmethod
    async def get_technical_indicators(
        self, symbol: str, timeframe: str = '1d', lookback: int = 100
    ) -> TechnicalData:
        """
        Get technical indicators for a symbol.
        
        Args:
            symbol: The trading symbol
            timeframe: Timeframe for the data
            lookback: Number of periods to look back
            
        Returns:
            TechnicalData object with indicators
        """
        ...
    
    @abstractmethod
    def get_provider_info(self) -> ProviderInfo:
        """
        Get information about the data provider.
        
        Returns:
            ProviderInfo object with name, tier, and capabilities
        """
        ...
