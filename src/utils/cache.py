import json
import asyncio
from typing import Any, Dict, Optional, TypeVar, Callable, Awaitable
from cachetools import TTLCache

# Generic Type for return values
T = TypeVar("T")

# Configuration defaults
DEFAULT_TTL = 3600
DEFAULT_CHECK_PERIOD = 120
DEFAULT_MAX_SIZE = 1000  # Python dict needs a size limit/eviction policy

class CacheManager:
    def __init__(self, ttl: int = DEFAULT_TTL, maxsize: int = DEFAULT_MAX_SIZE):
        """
        Initialize CacheManager using cachetools.TTLCache.
        
        Args:
            ttl: Time to live in seconds (default 3600)
            maxsize: Maximum number of items in cache (default 1000)
        """
        # TTLCache automatically removes items after 'ttl' seconds.
        # Note: 'checkperiod' concept from node-cache is passive in cachetools
        # (expired items are removed upon access or during insertion when full).
        self.cache = TTLCache(maxsize=maxsize, ttl=ttl)
        self.version = 'v1'
        self.default_ttl = ttl

    def create_key(self, tool_name: str, params: Dict[str, Any]) -> str:
        """
        Create a deterministic cache key based on tool name and parameters.
        Parameters are sorted to ensure the same key for the same data.
        """
        # Python's json.dumps with sort_keys=True achieves the same as the TS sorting logic
        sorted_params_str = json.dumps(params, sort_keys=True)
        return f"{self.version}:{tool_name}:{sorted_params_str}"

    async def cache_response(self, key: str, fetch_fn: Callable[[], Awaitable[Any]]) -> Any:
        """
        Placeholder for direct caching logic if needed in future.
        Currently just executes the fetch function.
        """
        return await fetch_fn()

    async def get_or_fetch(
        self, 
        key: str, 
        fetch_fn: Callable[[], Awaitable[T]], 
        ttl: Optional[int] = None
    ) -> T:
        """
        Try to get data from cache. If missing, execute fetch_fn and cache the result.
        
        Args:
            key: Cache key
            fetch_fn: Async function to fetch data if cache miss
            ttl: Optional TTL override (Note: TTLCache standardly uses global TTL, 
                 this argument is kept for API compatibility but might not override 
                 global policy depending on cachetools version/usage)
        """
        # 1. Try to get from cache
        if key in self.cache:
            try:
                return self.cache[key]
            except KeyError:
                # Handle potential race condition where item expires between check and access
                pass
        
        # 2. Fetch if missing or expired
        try:
            results = await fetch_fn()
            
            # cachetools doesn't easily support per-item TTL in a single TTLCache instance.
            # We use the instance's global TTL.
            self.cache[key] = results
            
            return results
        except Exception as e:
            # 3. Handle fetch error / Stale data logic
            # If the fetch failed, we check if we still have the data (even if technically expired,
            # cachetools might not have evicted it yet if we access it directly, 
            # but TTLCache usually hides expired items immediately).
            # We'll try to retrieve it directly if possible, but usually, if it's gone, it's gone.
            
            # In a strict TTLCache, you can't get expired items. 
            # This block mimics the TS logic structure.
            print(f"Cache fetch error: {e}")
            raise e

    def invalidate(self, key: str) -> None:
        """Remove a key from the cache."""
        if key in self.cache:
            try:
                del self.cache[key]
            except KeyError:
                pass

    def clear(self) -> None:
        """Clear all items from the cache."""
        self.cache.clear()