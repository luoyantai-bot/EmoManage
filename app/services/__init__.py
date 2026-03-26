# ===========================================
# Business Logic Services Package
# ===========================================
"""
Service layer module

Contains:
- CushionCloudClient: Cushion Cloud API client
- DeviceService: Device business service
- RedisClient: Redis connection and operations
- DeviceSyncService: Device sync from cloud
- RealtimeDataService: Real-time data management
- DataPersistenceService: Data persistence to PostgreSQL
- MockAlgorithmEngine: Algorithm engine for derived metrics calculation
"""

from app.services.cushion_cloud_client import CushionCloudClient, CushionCloudError
from app.services.device_service import DeviceService
from app.services.redis_client import RedisClient, RedisKeys, redis_client, get_redis
from app.services.device_sync_service import DeviceSyncService
from app.services.realtime_data_service import RealtimeDataService
from app.services.data_persistence_service import DataPersistenceService
from app.services.algorithm_engine import (
    MockAlgorithmEngine,
    RawDataPoint,
    DerivedMetrics,
    create_mock_data
)

__all__ = [
    "CushionCloudClient",
    "CushionCloudError",
    "DeviceService",
    "RedisClient",
    "RedisKeys",
    "redis_client",
    "get_redis",
    "DeviceSyncService",
    "RealtimeDataService",
    "DataPersistenceService",
    "MockAlgorithmEngine",
    "RawDataPoint",
    "DerivedMetrics",
    "create_mock_data",
]
