# ===========================================
# Redis Client Configuration
# ===========================================
"""
Redis client configuration for caching and message queues.

Provides:
- Redis client singleton
- Connection pool management
- Key naming conventions
"""

import json
from typing import Any, Dict, List, Optional, Union

import redis.asyncio as redis
from loguru import logger

from app.config import settings


# ===========================================
# Redis Key Naming Convention
# ===========================================

class RedisKeys:
    """
    Redis key naming convention.
    Format: emotion_cushion:{type}:{identifier}
    """
    
    # Prefix for all keys
    PREFIX = "emotion_cushion"
    
    # Device data stream (for recent 30 min data)
    # Key: emotion_cushion:device_data:{device_code}
    # Type: Stream
    @classmethod
    def device_data_stream(cls, device_code: str) -> str:
        """Stream for device real-time data."""
        return f"{cls.PREFIX}:device_data:{device_code}"
    
    # Device latest data (single record)
    # Key: emotion_cushion:device_latest:{device_code}
    # Type: Hash
    @classmethod
    def device_latest(cls, device_code: str) -> str:
        """Latest data for a device."""
        return f"{cls.PREFIX}:device_latest:{device_code}"
    
    # Measurement session
    # Key: emotion_cushion:session:{device_code}
    # Type: String (measurement_record_id)
    @classmethod
    def measurement_session(cls, device_code: str) -> str:
        """Current measurement session for a device."""
        return f"{cls.PREFIX}:session:{device_code}"
    
    # Cushion cloud token cache
    # Key: emotion_cushion:cushion_token
    # Type: String
    @classmethod
    def cushion_token(cls) -> str:
        """Cached token for CushionCloud API."""
        return f"{cls.PREFIX}:cushion_token"
    
    # Device status cache
    # Key: emotion_cushion:device_status:{device_code}
    # Type: Hash
    @classmethod
    def device_status(cls, device_code: str) -> str:
        """Cached status for a device."""
        return f"{cls.PREFIX}:device_status:{device_code}"
    
    # Alert counter
    # Key: emotion_cushion:alert_count:{device_code}:{date}
    # Type: String (integer)
    @classmethod
    def alert_count(cls, device_code: str, date: str) -> str:
        """Alert count for a device on a specific date."""
        return f"{cls.PREFIX}:alert_count:{device_code}:{date}"


# ===========================================
# Redis Client
# ===========================================

class RedisClient:
    """
    Async Redis client wrapper.
    
    Provides high-level methods for common Redis operations.
    Uses connection pooling for efficiency.
    """
    
    _instance: Optional["RedisClient"] = None
    _client: Optional[redis.Redis] = None
    
    def __new__(cls) -> "RedisClient":
        """Singleton pattern for Redis client."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def connect(self) -> None:
        """Initialize Redis connection."""
        if self._client is None:
            self._client = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
            )
            logger.info(f"Redis client connected: {settings.REDIS_URL}")
    
    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("Redis client disconnected")
    
    @property
    def client(self) -> redis.Redis:
        """Get Redis client instance."""
        if self._client is None:
            raise RuntimeError("Redis client not connected. Call connect() first.")
        return self._client
    
    # ===========================================
    # Basic Operations
    # ===========================================
    
    async def get(self, key: str) -> Optional[str]:
        """Get value by key."""
        return await self.client.get(key)
    
    async def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        """Set key-value pair with optional expiration."""
        return await self.client.set(key, value, ex=ex)
    
    async def delete(self, key: str) -> int:
        """Delete key."""
        return await self.client.delete(key)
    
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        return await self.client.exists(key) > 0
    
    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiration on key."""
        return await self.client.expire(key, seconds)
    
    async def ttl(self, key: str) -> int:
        """Get time to live for key."""
        return await self.client.ttl(key)
    
    # ===========================================
    # Hash Operations
    # ===========================================
    
    async def hget(self, name: str, key: str) -> Optional[str]:
        """Get hash field value."""
        return await self.client.hget(name, key)
    
    async def hgetall(self, name: str) -> Dict[str, str]:
        """Get all hash fields."""
        return await self.client.hgetall(name)
    
    async def hset(self, name: str, key: str, value: str) -> int:
        """Set hash field value."""
        return await self.client.hset(name, key, value)
    
    async def hsetall(self, name: str, mapping: Dict[str, str]) -> int:
        """Set multiple hash fields."""
        return await self.client.hset(name, mapping=mapping)
    
    async def hdel(self, name: str, key: str) -> int:
        """Delete hash field."""
        return await self.client.hdel(name, key)
    
    # ===========================================
    # Stream Operations
    # ===========================================
    
    async def xadd(
        self,
        stream: str,
        fields: Dict[str, Any],
        maxlen: Optional[int] = None
    ) -> str:
        """Add entry to stream."""
        # Convert values to strings
        str_fields = {k: json.dumps(v) if isinstance(v, (dict, list)) else str(v)
                      for k, v in fields.items()}
        
        if maxlen:
            return await self.client.xadd(stream, str_fields, maxlen=maxlen)
        return await self.client.xadd(stream, str_fields)
    
    async def xrange(
        self,
        stream: str,
        start: str = "-",
        end: str = "+",
        count: Optional[int] = None
    ) -> List[tuple]:
        """Read entries from stream."""
        if count:
            return await self.client.xrange(stream, start, end, count=count)
        return await self.client.xrange(stream, start, end)
    
    async def xread(
        self,
        streams: Dict[str, str],
        count: Optional[int] = None,
        block: Optional[int] = None
    ) -> Optional[List]:
        """Read from multiple streams."""
        return await self.client.xread(streams, count=count, block=block)
    
    async def xlen(self, stream: str) -> int:
        """Get stream length."""
        return await self.client.xlen(stream)
    
    async def xtrim(self, stream: str, maxlen: int) -> int:
        """Trim stream to max length."""
        return await self.client.xtrim(stream, maxlen=maxlen)
    
    # ===========================================
    # JSON Helpers
    # ===========================================
    
    async def get_json(self, key: str) -> Optional[Any]:
        """Get and deserialize JSON value."""
        value = await self.get(key)
        if value:
            return json.loads(value)
        return None
    
    async def set_json(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        """Serialize and set JSON value."""
        return await self.set(key, json.dumps(value), ex=ex)
    
    async def hget_json(self, name: str, key: str) -> Optional[Any]:
        """Get and deserialize hash field JSON value."""
        value = await self.hget(name, key)
        if value:
            return json.loads(value)
        return None
    
    async def hset_json(self, name: str, key: str, value: Any) -> int:
        """Serialize and set hash field JSON value."""
        return await self.hset(name, key, json.dumps(value))


# Global Redis client instance
redis_client = RedisClient()


# ===========================================
# Dependency Injection
# ===========================================

async def get_redis() -> RedisClient:
    """Get Redis client for FastAPI dependency injection."""
    if redis_client._client is None:
        await redis_client.connect()
    return redis_client
