# ===========================================
# Realtime Data Service
# ===========================================
"""
Manage device real-time data flow

Provides:
- Get latest data from Redis
- Get recent data from Redis Stream
- Check device active status
- Start/end measurement sessions
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from loguru import logger
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device
from app.models.measurement import MeasurementRecord
from app.services.redis_client import RedisClient, RedisKeys


class RealtimeDataService:
    """
    Manage device real-time data flow
    
    Handles:
    - Fetching latest/recent data from Redis
    - Checking device active status
    - Managing measurement sessions
    """
    
    def __init__(self, db: AsyncSession, redis: RedisClient):
        """
        Initialize service
        
        Args:
            db: Database session
            redis: Redis client
        """
        self.db = db
        self.redis = redis
    
    # ===========================================
    # Data Retrieval
    # ===========================================
    
    async def get_latest_data(self, device_code: str) -> Optional[Dict[str, Any]]:
        """
        Get latest data for a device from Redis
        
        Args:
            device_code: Device code
        
        Returns:
            Latest data dictionary or None
        """
        return await self.redis.get_device_latest(device_code)
    
    async def get_recent_data(
        self,
        device_code: str,
        minutes: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get recent data from Redis Stream
        
        Args:
            device_code: Device code
            minutes: Number of minutes to look back
        
        Returns:
            List of data entries
        """
        # Calculate start time for stream
        start_time = datetime.utcnow() - timedelta(minutes=minutes)
        
        # Get all entries from stream (we'll filter by time)
        entries = await self.redis.get_device_data_range(device_code)
        
        # Filter by time
        result = []
        for entry in entries:
            timestamp_str = entry.get("timestamp") or entry.get("received_at")
            if timestamp_str:
                try:
                    entry_time = datetime.fromisoformat(timestamp_str)
                    if entry_time >= start_time:
                        result.append(entry)
                except (ValueError, TypeError):
                    # Include entries with invalid timestamps
                    result.append(entry)
        
        return result
    
    async def get_data_for_session(
        self,
        device_code: str,
        start_time: datetime
    ) -> List[Dict[str, Any]]:
        """
        Get all data for a measurement session
        
        Args:
            device_code: Device code
            start_time: Session start time
        
        Returns:
            List of data entries
        """
        entries = await self.redis.get_device_data_range(device_code)
        
        result = []
        for entry in entries:
            timestamp_str = entry.get("timestamp") or entry.get("received_at")
            if timestamp_str:
                try:
                    entry_time = datetime.fromisoformat(timestamp_str)
                    if entry_time >= start_time:
                        result.append(entry)
                except (ValueError, TypeError):
                    pass
        
        return result
    
    # ===========================================
    # Device Status
    # ===========================================
    
    async def is_device_active(
        self,
        device_code: str,
        threshold_seconds: int = 60
    ) -> bool:
        """
        Check if device has reported data recently
        
        Args:
            device_code: Device code
            threshold_seconds: Threshold in seconds
        
        Returns:
            True if device is active
        """
        latest = await self.get_latest_data(device_code)
        if not latest:
            return False
        
        updated_at = latest.get("updated_at")
        if not updated_at:
            return False
        
        try:
            last_update = datetime.fromisoformat(updated_at)
            return datetime.utcnow() - last_update < timedelta(seconds=threshold_seconds)
        except (ValueError, TypeError):
            return False
    
    async def get_measurement_duration(self, device_code: str) -> int:
        """
        Get continuous data duration in seconds
        
        Calculates how long the device has been continuously
        reporting valid data.
        
        Args:
            device_code: Device code
        
        Returns:
            Duration in seconds (0 if no active session)
        """
        session_id = await self.redis.get_device_session(device_code)
        if not session_id:
            return 0
        
        # Get measurement record
        try:
            record_id = UUID(session_id)
        except ValueError:
            return 0
        
        result = await self.db.execute(
            select(MeasurementRecord).where(MeasurementRecord.id == record_id)
        )
        record = result.scalar_one_or_none()
        
        if not record or not record.start_time:
            return 0
        
        duration = datetime.utcnow() - record.start_time
        return int(duration.total_seconds())
    
    async def get_session_status(self, device_code: str) -> Dict[str, Any]:
        """
        Get current session status for a device
        
        Args:
            device_code: Device code
        
        Returns:
            Status dictionary with:
            - is_measuring: bool
            - session_id: Optional[str]
            - duration_seconds: int
            - start_time: Optional[datetime]
        """
        session_id = await self.redis.get_device_session(device_code)
        
        if not session_id:
            return {
                "is_measuring": False,
                "session_id": None,
                "duration_seconds": 0,
                "start_time": None
            }
        
        try:
            record_id = UUID(session_id)
        except ValueError:
            return {
                "is_measuring": False,
                "session_id": None,
                "duration_seconds": 0,
                "start_time": None
            }
        
        result = await self.db.execute(
            select(MeasurementRecord).where(MeasurementRecord.id == record_id)
        )
        record = result.scalar_one_or_none()
        
        if not record:
            return {
                "is_measuring": False,
                "session_id": None,
                "duration_seconds": 0,
                "start_time": None
            }
        
        duration = 0
        if record.start_time:
            duration = int((datetime.utcnow() - record.start_time).total_seconds())
        
        return {
            "is_measuring": record.status == "measuring",
            "session_id": str(record.id),
            "duration_seconds": duration,
            "start_time": record.start_time,
            "status": record.status
        }
    
    # ===========================================
    # Measurement Sessions
    # ===========================================
    
    async def start_measurement_session(
        self,
        device_code: str,
        user_id: UUID
    ) -> UUID:
        """
        Start a measurement session
        
        1. Create MeasurementRecord with status="measuring"
        2. Store session ID in Redis
        3. Return measurement_record_id
        
        Args:
            device_code: Device code
            user_id: User ID
        
        Returns:
            Measurement record ID
        
        Raises:
            ValueError: Device not found or session already exists
        """
        # Check for existing session
        existing_session = await self.redis.get_device_session(device_code)
        if existing_session:
            logger.warning(f"Session already exists for device: {device_code}")
            raise ValueError("Measurement session already in progress")
        
        # Get device
        result = await self.db.execute(
            select(Device).where(Device.device_code == device_code)
        )
        device = result.scalar_one_or_none()
        
        if not device:
            raise ValueError(f"Device not found: {device_code}")
        
        # Create measurement record
        record = MeasurementRecord(
            user_id=user_id,
            device_id=device.id,
            start_time=datetime.utcnow(),
            status="measuring"
        )
        
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)
        
        # Store session in Redis
        await self.redis.set_device_session(device_code, str(record.id))
        
        # Update device status
        device.status = "in_use"
        await self.db.commit()
        
        logger.info(f"Started measurement session: {record.id} for device: {device_code}")
        return record.id
    
    async def end_measurement_session(
        self,
        device_code: str
    ) -> Optional[MeasurementRecord]:
        """
        End a measurement session
        
        1. Aggregate all data from Redis Stream
        2. Calculate raw_data_summary
        3. Update MeasurementRecord
        4. Return updated record
        
        Args:
            device_code: Device code
        
        Returns:
            Updated MeasurementRecord or None
        """
        # Get session ID
        session_id = await self.redis.get_device_session(device_code)
        if not session_id:
            logger.warning(f"No active session for device: {device_code}")
            return None
        
        try:
            record_id = UUID(session_id)
        except ValueError:
            logger.error(f"Invalid session ID: {session_id}")
            return None
        
        # Get measurement record
        result = await self.db.execute(
            select(MeasurementRecord).where(MeasurementRecord.id == record_id)
        )
        record = result.scalar_one_or_none()
        
        if not record:
            logger.error(f"Measurement record not found: {record_id}")
            return None
        
        # Get session data
        if record.start_time:
            session_data = await self.get_data_for_session(device_code, record.start_time)
        else:
            session_data = []
        
        # Calculate raw_data_summary
        raw_data_summary = self._aggregate_session_data(session_data)
        
        # Update record
        record.end_time = datetime.utcnow()
        record.raw_data_summary = raw_data_summary
        record.status = "processing"
        
        if record.start_time:
            duration = record.end_time - record.start_time
            record.duration_minutes = int(duration.total_seconds() / 60)
        
        # Update device status
        device_result = await self.db.execute(
            select(Device).where(Device.id == record.device_id)
        )
        device = device_result.scalar_one_or_none()
        if device:
            device.status = "online"
        
        await self.db.commit()
        await self.db.refresh(record)
        
        # Delete session from Redis
        await self.redis.delete_device_session(device_code)
        
        logger.info(f"Ended measurement session: {record.id}, duration: {record.duration_minutes} min")
        return record
    
    def _aggregate_session_data(
        self,
        session_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Aggregate session data into summary statistics
        
        Args:
            session_data: List of data entries
        
        Returns:
            Summary dictionary with statistics
        """
        if not session_data:
            return {
                "data_count": 0,
                "message": "No data available"
            }
        
        # Extract heart rate and breathing values
        heart_rates = []
        breathings = []
        
        for entry in session_data:
            hr = entry.get("heart_rate") or entry.get("heartRate")
            br = entry.get("breathing") or entry.get("breathing")
            
            # Convert to int if string
            if hr:
                try:
                    hr_val = int(hr) if int(hr) > 0 else None
                    if hr_val:
                        heart_rates.append(hr_val)
                except (ValueError, TypeError):
                    pass
            
            if br:
                try:
                    br_val = int(br) if int(br) > 0 else None
                    if br_val:
                        breathings.append(br_val)
                except (ValueError, TypeError):
                    pass
        
        # Count bed status
        in_bed_count = 0
        out_bed_count = 0
        
        for entry in session_data:
            bed_status = entry.get("bed_status") or entry.get("bedStatus")
            if bed_status == "1":
                in_bed_count += 1
            elif bed_status == "0":
                out_bed_count += 1
        
        # Count sleep events
        apnea_events = 0
        snore_events = 0
        
        for entry in session_data:
            sleep_status = entry.get("sleep_status") or entry.get("sleepStatus")
            if sleep_status == "4":  # Apnea
                apnea_events += 1
            elif sleep_status == "2":  # Snoring
                snore_events += 1
        
        # Build summary
        summary = {
            "data_count": len(session_data),
            "session_end_time": datetime.utcnow().isoformat(),
        }
        
        # Heart rate statistics
        if heart_rates:
            summary["heart_rate"] = {
                "avg": round(sum(heart_rates) / len(heart_rates), 1),
                "max": max(heart_rates),
                "min": min(heart_rates),
                "count": len(heart_rates)
            }
        
        # Breathing statistics
        if breathings:
            summary["breathing"] = {
                "avg": round(sum(breathings) / len(breathings), 1),
                "max": max(breathings),
                "min": min(breathings),
                "count": len(breathings)
            }
        
        # Bed status statistics
        summary["bed_status"] = {
            "in_bed_count": in_bed_count,
            "out_bed_count": out_bed_count
        }
        
        # Sleep events
        summary["sleep_events"] = {
            "apnea_events": apnea_events,
            "snore_events": snore_events
        }
        
        return summary
    
    # ===========================================
    # Active Measurement Record
    # ===========================================
    
    async def get_active_measurement(
        self,
        device_code: str
    ) -> Optional[MeasurementRecord]:
        """
        Get active measurement record for a device
        
        Args:
            device_code: Device code
        
        Returns:
            MeasurementRecord or None
        """
        result = await self.db.execute(
            select(MeasurementRecord)
            .join(Device)
            .where(
                and_(
                    Device.device_code == device_code,
                    MeasurementRecord.status == "measuring"
                )
            )
            .order_by(MeasurementRecord.start_time.desc())
        )
        return result.scalar_one_or_none()
