import os
from typing import Optional, Type, Dict, Any
from .market_data.base import MarketDataProvider, ProviderInfo
from .market_data.polygon_s3 import PolygonS3Provider
from .ai.base import AIProvider
from .ai.claude import ClaudeProvider
from .ai.openai import OpenAIProvider

def get_market_data_provider(provider_type: str = "polygon_s3", **kwargs) -> MarketDataProvider:
    """
    Factory function to get a market data provider instance.
    
    Args:
        provider_type: Type of provider to create. Defaults to "polygon_s3".
        **kwargs: Additional arguments to pass to the provider's constructor.
        
    Returns:
        An instance of the specified market data provider.
    """
    providers = {
        "polygon_s3": PolygonS3Provider
    }
    
    provider_class = providers.get(provider_type.lower())
    if not provider_class:
        raise ValueError(f"Unknown market data provider: {provider_type}")
    
    # Filter kwargs to only include parameters that the provider accepts
    import inspect
    provider_params = inspect.signature(provider_class.__init__).parameters
    filtered_kwargs = {k: v for k, v in kwargs.items() if k in provider_params}
    
    return provider_class(**filtered_kwargs)

def get_ai_provider(provider_type: str = "anthropic", **kwargs) -> AIProvider:
    """
    Factory function to get an AI provider instance.
    
    Args:
        provider_type: Type of provider to create. Defaults to "claude".
        **kwargs: Additional arguments to pass to the provider's constructor.
        
    Returns:
        An instance of the specified AI provider.
    """
    providers = {
        "anthropic": ClaudeProvider,
        "openai": OpenAIProvider,
    }
    
    provider_key = provider_type.lower()
    provider_class = providers.get(provider_key)
    if not provider_class:
        raise ValueError(f"Unknown AI provider: {provider_type}")
    
    # Filter kwargs to only include parameters that the provider accepts
    import inspect
    provider_params = inspect.signature(provider_class.__init__).parameters
    filtered_kwargs = {k: v for k, v in kwargs.items() if k in provider_params}
    
    return provider_class(**filtered_kwargs)

# Re-export types for easier imports
__all__ = [
    # Factory functions
    'get_market_data_provider',
    'get_ai_provider',
    
    # Base classes
    'MarketDataProvider',
    'AIProvider',
    'ProviderInfo',
    
    # Provider implementations
    'PolygonS3Provider',
    'ClaudeProvider',
    'OpenAIProvider'
]
