# ===========================================
# Data Persistence Service
# ===========================================
"""
Persist real-time data from Redis to PostgreSQL

Provides:
- Batch persist device data
- Background task for periodic persistence
- Data cleanup
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.raw_data import RawDeviceData
from app.services.redis_client import RedisClient, RedisKeys


class DataPersistenceService:
    """
    Persist real-time data from Redis to PostgreSQL
    
    Runs as a background task to:
    - Batch read data from Redis Streams
    - Write to RawDeviceData table
    - Clean up old data
    """
    
    # Interval between persistence runs (seconds)
    PERSISTENCE_INTERVAL = 60
    
    # Maximum batch size per run
    MAX_BATCH_SIZE = 1000
    
    # Data retention period (days)
    DATA_RETENTION_DAYS = 30
    
    def __init__(self, redis: RedisClient):
        """
        Initialize service
        
        Args:
            redis: Redis client
        """
        self.redis = redis
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    async def start_background_task(self) -> None:
        """Start the background persistence task"""
        if self._running:
            logger.warning("Data persistence task already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._run_periodically())
        logger.info("Data persistence background task started")
    
    async def stop_background_task(self) -> None:
        """Stop the background persistence task"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Data persistence background task stopped")
    
    async def _run_periodically(self) -> None:
        """Run persistence task periodically"""
        while self._running:
            try:
                await self.persist_all_devices()
            except Exception as e:
                logger.error(f"Error in persistence task: {e}")
            
            await asyncio.sleep(self.PERSISTENCE_INTERVAL)
    
    async def persist_all_devices(self) -> Dict[str, int]:
        """
        Persist data for all devices with active streams
        
        Returns:
            Statistics dictionary
        """
        stats = {
            "devices_processed": 0,
            "total_records": 0,
            "errors": 0
        }
        
        try:
            # Get all device data stream keys
            # Pattern: emotion_cushion:data:*
            keys = await self._get_device_data_keys()
            
            for key in keys:
                try:
                    device_code = key.split(":")[-1]
                    count = await self.persist_device_data(device_code)
                    stats["devices_processed"] += 1
                    stats["total_records"] += count
                except Exception as e:
                    stats["errors"] += 1
                    logger.error(f"Failed to persist data for {key}: {e}")
            
            if stats["total_records"] > 0:
                logger.info(f"Persisted {stats['total_records']} records from {stats['devices_processed']} devices")
            
        except Exception as e:
            logger.error(f"Failed to get device keys: {e}")
        
        return stats
    
    async def _get_device_data_keys(self) -> List[str]:
        """
        Get all device data stream keys
        
        Returns:
            List of Redis keys
        """
        pattern = "emotion_cushion:data:*"
        keys = []
        
        async for key in self.redis.client.scan_iter(match=pattern):
            keys.append(key)
        
        return keys
    
    async def persist_device_data(
        self,
        device_code: str,
        batch_size: int = None
    ) -> int:
        """
        Persist data for a single device
        
        Args:
            device_code: Device code
            batch_size: Maximum records to persist
        
        Returns:
            Number of records persisted
        """
        batch_size = batch_size or self.MAX_BATCH_SIZE
        stream_key = RedisKeys.device_data_stream(device_code)
        
        # Read data from stream
        entries = await self.redis.xrange(stream_key, count=batch_size)
        
        if not entries:
            return 0
        
        # Prepare batch insert
        records = []
        entry_ids = []
        
        for entry_id, fields in entries:
            try:
                record = self._create_raw_data(device_code, fields)
                if record:
                    records.append(record)
                    entry_ids.append(entry_id)
            except Exception as e:
                logger.warning(f"Failed to create record for entry {entry_id}: {e}")
        
        if not records:
            return 0
        
        # Insert into database
        async with async_session_factory() as session:
            try:
                session.add_all(records)
                await session.commit()
                
                # Delete processed entries from stream
                if entry_ids:
                    await self.redis.client.xdel(stream_key, *entry_ids)
                
                return len(records)
                
            except Exception as e:
                logger.error(f"Failed to insert records: {e}")
                await session.rollback()
                raise
    
    def _create_raw_data(
        self,
        device_code: str,
        fields: Dict[str, str]
    ) -> Optional[RawDeviceData]:
        """
        Create RawDeviceData from stream entry
        
        Args:
            device_code: Device code
            fields: Stream entry fields
        
        Returns:
            RawDeviceData instance or None
        """
        # Parse field values
        heart_rate = self._parse_int(fields.get("heart_rate") or fields.get("heartRate"))
        breathing = self._parse_int(fields.get("breathing"))
        signal = self._parse_int(fields.get("signal"))
        sos_type = fields.get("sos_type") or fields.get("sosType")
        bed_status = fields.get("bed_status") or fields.get("bedStatus")
        sleep_status = fields.get("sleep_status") or fields.get("sleepStatus")
        snore = self._parse_int(fields.get("snore"))
        raw_timestamp = fields.get("create_time") or fields.get("createTime")
        
        return RawDeviceData(
            device_code=device_code,
            heart_rate=heart_rate,
            breathing=breathing,
            signal=signal,
            sos_type=sos_type,
            bed_status=bed_status,
            sleep_status=sleep_status,
            snore=snore,
            raw_timestamp=raw_timestamp,
            received_at=datetime.utcnow()
        )
    
    def _parse_int(self, value: Optional[str]) -> Optional[int]:
        """Parse integer from string"""
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None
    
    async def cleanup_old_data(self) -> int:
        """
        Delete old data from RawDeviceData table
        
        Returns:
            Number of records deleted
        """
        cutoff_date = datetime.utcnow() - timedelta(days=self.DATA_RETENTION_DAYS)
        
        async with async_session_factory() as session:
            try:
                from sqlalchemy import delete
                
                stmt = delete(RawDeviceData).where(
                    RawDeviceData.received_at < cutoff_date
                )
                result = await session.execute(stmt)
                await session.commit()
                
                deleted_count = result.rowcount
                if deleted_count > 0:
                    logger.info(f"Cleaned up {deleted_count} old records")
                
                return deleted_count
                
            except Exception as e:
                logger.error(f"Failed to cleanup old data: {e}")
                await session.rollback()
                return 0
    
    async def get_storage_stats(self) -> Dict[str, any]:
        """
        Get storage statistics
        
        Returns:
            Statistics dictionary
        """
        async with async_session_factory() as session:
            from sqlalchemy import func, select
            
            # Count total records
            count_result = await session.execute(
                select(func.count(RawDeviceData.id))
            )
            total_records = count_result.scalar() or 0
            
            # Count records per device
            device_counts = await session.execute(
                select(
                    RawDeviceData.device_code,
                    func.count(RawDeviceData.id)
                ).group_by(RawDeviceData.device_code)
            )
            device_stats = {row[0]: row[1] for row in device_counts.fetchall()}
            
            # Get oldest record
            oldest_result = await session.execute(
                select(func.min(RawDeviceData.received_at))
            )
            oldest_record = oldest_result.scalar()
            
            return {
                "total_records": total_records,
                "device_count": len(device_stats),
                "devices": device_stats,
                "oldest_record": oldest_record.isoformat() if oldest_record else None,
                "retention_days": self.DATA_RETENTION_DAYS
            }


# ===========================================
# Global Service Instance
# ===========================================

data_persistence_service: Optional[DataPersistenceService] = None


async def get_persistence_service(redis: RedisClient) -> DataPersistenceService:
    """Get or create persistence service instance"""
    global data_persistence_service
    if data_persistence_service is None:
        data_persistence_service = DataPersistenceService(redis)
    return data_persistence_service
