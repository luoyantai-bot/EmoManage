# ===========================================
# Redis Connection Service
# ===========================================
"""
Redis connection and utility functions

Provides:
- Redis connection pool
- Key naming conventions
- Common Redis operations
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import redis.asyncio as redis
from loguru import logger

from app.config import settings


# ===========================================
# Redis Key Naming Convention
# ===========================================
# Format: emotion_cushion:{type}:{identifier}

class RedisKeys:
    """Redis key naming convention"""
    
    # Device data stream (real-time data)
    # emotion_cushion:data:{device_code}
    @staticmethod
    def device_data_stream(device_code: str) -> str:
        return f"emotion_cushion:data:{device_code}"
    
    # Device latest data (single record)
    # emotion_cushion:latest:{device_code}
    @staticmethod
    def device_latest_data(device_code: str) -> str:
        return f"emotion_cushion:latest:{device_code}"
    
    # Device session (active measurement)
    # emotion_cushion:session:{device_code}
    @staticmethod
    def device_session(device_code: str) -> str:
        return f"emotion_cushion:session:{device_code}"
    
    # Device status cache
    # emotion_cushion:status:{device_code}
    @staticmethod
    def device_status(device_code: str) -> str:
        return f"emotion_cushion:status:{device_code}"
    
    # Cushion cloud token
    CUSHION_CLOUD_TOKEN = "emotion_cushion:cushion_cloud_token"
    
    # Data persistence queue
    DATA_PERSISTENCE_QUEUE = "emotion_cushion:persistence:queue"


# ===========================================
# Redis Connection Pool
# ===========================================

class RedisClient:
    """
    Redis client wrapper with connection pool
    
    Usage:
        redis_client = RedisClient()
        await redis_client.connect()
        
        # Use the client
        await redis_client.set("key", "value")
        value = await redis_client.get("key")
        
        await redis_client.disconnect()
    """
    
    _instance: Optional["RedisClient"] = None
    _client: Optional[redis.Redis] = None
    
    def __new__(cls) -> "RedisClient":
        """Singleton pattern"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def connect(self) -> None:
        """Establish Redis connection"""
        if self._client is not None:
            return
        
        try:
            self._client = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
            )
            # Test connection
            await self._client.ping()
            logger.info(f"Redis connected: {settings.REDIS_URL}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def disconnect(self) -> None:
        """Close Redis connection"""
        if self._client:
            await self._client.close()
            self._client = None
            logger.info("Redis disconnected")
    
    @property
    def client(self) -> redis.Redis:
        """Get Redis client instance"""
        if self._client is None:
            raise RuntimeError("Redis not connected. Call connect() first.")
        return self._client
    
    # ===========================================
    # Basic Operations
    # ===========================================
    
    async def get(self, key: str) -> Optional[str]:
        """Get value by key"""
        return await self.client.get(key)
    
    async def set(
        self,
        key: str,
        value: Union[str, Dict, List],
        ex: Optional[int] = None
    ) -> bool:
        """
        Set key-value pair
        
        Args:
            key: Redis key
            value: Value (string, dict, or list)
            ex: Expiration time in seconds
        """
        if isinstance(value, (dict, list)):
            value = json.dumps(value, default=str)
        
        return await self.client.set(key, value, ex=ex)
    
    async def delete(self, *keys: str) -> int:
        """Delete keys"""
        return await self.client.delete(*keys)
    
    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        return await self.client.exists(key) > 0
    
    async def expire(self, key: str, seconds: int) -> bool:
        """Set key expiration"""
        return await self.client.expire(key, seconds)
    
    async def ttl(self, key: str) -> int:
        """Get key TTL"""
        return await self.client.ttl(key)
    
    # ===========================================
    # Hash Operations
    # ===========================================
    
    async def hset(
        self,
        name: str,
        key: str,
        value: Union[str, Dict, List]
    ) -> int:
        """Set hash field"""
        if isinstance(value, (dict, list)):
            value = json.dumps(value, default=str)
        return await self.client.hset(name, key, value)
    
    async def hget(self, name: str, key: str) -> Optional[str]:
        """Get hash field"""
        return await self.client.hget(name, key)
    
    async def hgetall(self, name: str) -> Dict[str, str]:
        """Get all hash fields"""
        return await self.client.hgetall(name)
    
    async def hdel(self, name: str, *keys: str) -> int:
        """Delete hash fields"""
        return await self.client.hdel(name, *keys)
    
    # ===========================================
    # Stream Operations
    # ===========================================
    
    async def xadd(
        self,
        stream: str,
        fields: Dict[str, Any],
        maxlen: Optional[int] = None
    ) -> str:
        """
        Add entry to stream
        
        Args:
            stream: Stream name
            fields: Field-value pairs
            maxlen: Maximum length of stream
        
        Returns:
            Entry ID
        """
        # Convert dict values to strings
        data = {k: json.dumps(v) if isinstance(v, (dict, list)) else str(v)
                for k, v in fields.items()}
        
        return await self.client.xadd(stream, data, maxlen=maxlen)
    
    async def xrange(
        self,
        stream: str,
        start: str = "-",
        end: str = "+",
        count: Optional[int] = None
    ) -> List[tuple]:
        """
        Read entries from stream
        
        Args:
            stream: Stream name
            start: Start ID (default: earliest)
            end: End ID (default: latest)
            count: Maximum number of entries
        
        Returns:
            List of (id, fields) tuples
        """
        return await self.client.xrange(stream, start, end, count=count)
    
    async def xread(
        self,
        streams: Dict[str, str],
        count: Optional[int] = None,
        block: Optional[int] = None
    ) -> Optional[List]:
        """
        Read from multiple streams
        
        Args:
            streams: Dict of {stream_name: last_id}
            count: Maximum entries per stream
            block: Block timeout in milliseconds
        
        Returns:
            List of stream data
        """
        return await self.client.xread(
            streams,
            count=count,
            block=block
        )
    
    async def xtrim(self, stream: str, maxlen: int) -> int:
        """Trim stream to maximum length"""
        return await self.client.xtrim(stream, maxlen=maxlen)
    
    async def xlen(self, stream: str) -> int:
        """Get stream length"""
        return await self.client.xlen(stream)
    
    # ===========================================
    # Device-specific Operations
    # ===========================================
    
    async def set_device_latest(
        self,
        device_code: str,
        data: Dict[str, Any],
        ttl: int = 3600
    ) -> bool:
        """
        Set device latest data
        
        Args:
            device_code: Device code
            data: Data dictionary
            ttl: Time to live in seconds (default: 1 hour)
        """
        key = RedisKeys.device_latest_data(device_code)
        data["updated_at"] = datetime.utcnow().isoformat()
        return await self.set(key, data, ex=ttl)
    
    async def get_device_latest(self, device_code: str) -> Optional[Dict]:
        """Get device latest data"""
        key = RedisKeys.device_latest_data(device_code)
        data = await self.get(key)
        if data:
            return json.loads(data)
        return None
    
    async def add_device_data(
        self,
        device_code: str,
        data: Dict[str, Any],
        maxlen: int = 1800
    ) -> str:
        """
        Add data to device stream
        
        Args:
            device_code: Device code
            data: Data dictionary
            maxlen: Maximum stream length (default: 1800 for 30 min at 1 entry/sec)
        
        Returns:
            Entry ID
        """
        stream = RedisKeys.device_data_stream(device_code)
        data["timestamp"] = datetime.utcnow().isoformat()
        return await self.xadd(stream, data, maxlen=maxlen)
    
    async def get_device_data_range(
        self,
        device_code: str,
        start: str = "-",
        end: str = "+",
        count: Optional[int] = None
    ) -> List[Dict]:
        """
        Get device data range from stream
        
        Args:
            device_code: Device code
            start: Start ID or "-" for earliest
            end: End ID or "+" for latest
            count: Maximum entries
        
        Returns:
            List of data entries
        """
        stream = RedisKeys.device_data_stream(device_code)
        entries = await self.xrange(stream, start, end, count=count)
        
        result = []
        for entry_id, fields in entries:
            data = {"id": entry_id}
            for k, v in fields.items():
                try:
                    data[k] = json.loads(v)
                except (json.JSONDecodeError, TypeError):
                    data[k] = v
            result.append(data)
        
        return result
    
    async def set_device_session(
        self,
        device_code: str,
        measurement_record_id: str,
        ttl: int = 86400
    ) -> bool:
        """
        Set active measurement session
        
        Args:
            device_code: Device code
            measurement_record_id: Measurement record UUID
            ttl: Time to live (default: 24 hours)
        """
        key = RedisKeys.device_session(device_code)
        return await self.set(key, measurement_record_id, ex=ttl)
    
    async def get_device_session(self, device_code: str) -> Optional[str]:
        """Get active measurement session ID"""
        key = RedisKeys.device_session(device_code)
        return await self.get(key)
    
    async def delete_device_session(self, device_code: str) -> int:
        """Delete measurement session"""
        key = RedisKeys.device_session(device_code)
        return await self.delete(key)


# ===========================================
# Global Redis Client Instance
# ===========================================

redis_client = RedisClient()


# ===========================================
# Dependency Injection
# ===========================================

async def get_redis() -> RedisClient:
    """Get Redis client for FastAPI dependency injection"""
    if redis_client._client is None:
        await redis_client.connect()
    return redis_client
