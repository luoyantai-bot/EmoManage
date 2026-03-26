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
- Calculate derived metrics using algorithm engine
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
from app.services.algorithm_engine import (
    MockAlgorithmEngine,
    RawDataPoint,
    DerivedMetrics
)


class RealtimeDataService:
    """
    Manage device real-time data flow
    
    Handles:
    - Fetching latest/recent data from Redis
    - Checking device active status
    - Managing measurement sessions
    - Calculating derived health metrics
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
        self.algorithm_engine = MockAlgorithmEngine()
    
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
        
        1. Get all data from Redis Stream for this session
        2. Convert to List[RawDataPoint]
        3. Call MockAlgorithmEngine.calculate() for derived metrics
        4. Store raw_data_summary and derived_metrics
        5. Update status to "processing"
        6. Trigger AI analysis task (Phase 4)
        
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
        
        # Get session data from Redis
        if record.start_time:
            session_data = await self.get_data_for_session(device_code, record.start_time)
        else:
            session_data = []
        
        # Convert to RawDataPoint list for algorithm engine
        raw_data_points = self._convert_to_raw_data_points(session_data)
        
        # Calculate derived metrics using algorithm engine
        derived_metrics = None
        try:
            if len(raw_data_points) >= self.algorithm_engine.MIN_DATA_POINTS:
                derived_metrics = self.algorithm_engine.calculate(raw_data_points)
                logger.info(f"Calculated derived metrics: HRV={derived_metrics.hrv_score}, "
                           f"Stress={derived_metrics.stress_index}, "
                           f"Score={derived_metrics.overall_health_score}")
            else:
                logger.warning(f"Insufficient data points: {len(raw_data_points)} < "
                              f"{self.algorithm_engine.MIN_DATA_POINTS}")
        except Exception as e:
            logger.error(f"Failed to calculate derived metrics: {e}")
        
        # Calculate raw_data_summary (basic aggregation)
        raw_data_summary = self._aggregate_session_data(session_data)
        
        # Update record
        record.end_time = datetime.utcnow()
        record.raw_data_summary = raw_data_summary
        record.status = "processing"
        
        if record.start_time:
            duration = record.end_time - record.start_time
            record.duration_minutes = int(duration.total_seconds() / 60)
        
        # Store derived metrics if calculated
        if derived_metrics:
            record.derived_metrics = derived_metrics.to_dict()
            record.health_score = derived_metrics.overall_health_score
        
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
        
        # TODO: Trigger AI analysis task (Phase 4)
        # await trigger_ai_analysis(str(record.id))
        
        return record
    
    def _convert_to_raw_data_points(
        self,
        session_data: List[Dict[str, Any]]
    ) -> List[RawDataPoint]:
        """
        Convert session data dicts to RawDataPoint objects
        
        Args:
            session_data: List of data dictionaries from Redis
        
        Returns:
            List of RawDataPoint objects
        """
        points = []
        
        for entry in session_data:
            try:
                # Extract values, handling both snake_case and camelCase keys
                heart_rate = self._parse_int(
                    entry.get("heart_rate") or entry.get("heartRate")
                )
                breathing = self._parse_int(entry.get("breathing"))
                bed_status = self._parse_int(
                    entry.get("bed_status") or entry.get("bedStatus"),
                    default=1
                )
                sleep_status = self._parse_int(
                    entry.get("sleep_status") or entry.get("sleepStatus"),
                    default=1
                )
                signal = self._parse_int(entry.get("signal"))
                sos_type = entry.get("sos_type") or entry.get("sosType")
                timestamp = entry.get("timestamp") or entry.get("received_at") or ""
                
                # Skip invalid entries
                if heart_rate is None or heart_rate <= 0:
                    continue
                
                point = RawDataPoint(
                    heart_rate=heart_rate,
                    breathing=breathing or 0,
                    bed_status=bed_status,
                    sleep_status=sleep_status,
                    timestamp=timestamp,
                    signal=signal,
                    sos_type=sos_type
                )
                points.append(point)
                
            except Exception as e:
                logger.warning(f"Failed to parse data point: {e}")
                continue
        
        return points
    
    def _parse_int(self, value: Any, default: int = 0) -> int:
        """Parse integer from various formats"""
        if value is None:
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
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
            br = entry.get("breathing")
            
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
    # Report-based Calculation
    # ===========================================
    
    async def process_manufacturer_report(
        self,
        device_code: str,
        report_data: dict
    ) -> Optional[MeasurementRecord]:
        """
        Process a manufacturer's report and calculate derived metrics
        
        Used when receiving reports via Webhook instead of raw data.
        
        Args:
            device_code: Device code
            report_data: Report data from manufacturer
        
        Returns:
            Created or updated MeasurementRecord
        """
        # Get device
        result = await self.db.execute(
            select(Device).where(Device.device_code == device_code)
        )
        device = result.scalar_one_or_none()
        
        if not device:
            logger.warning(f"Device not found for report: {device_code}")
            return None
        
        # Check for existing active measurement
        active_measurement = await self.get_active_measurement(device_code)
        
        if active_measurement:
            record = active_measurement
        else:
            # Create new record
            record = MeasurementRecord(
                device_id=device.id,
                status="processing"
            )
            self.db.add(record)
            await self.db.flush()
        
        # Calculate derived metrics from report
        try:
            derived_metrics = self.algorithm_engine.calculate_from_report(report_data)
            record.derived_metrics = derived_metrics.to_dict()
            record.health_score = derived_metrics.overall_health_score
            logger.info(f"Calculated derived metrics from report: Score={derived_metrics.overall_health_score}")
        except Exception as e:
            logger.error(f"Failed to calculate metrics from report: {e}")
        
        # Store raw report data
        record.raw_data_summary = report_data
        
        # Parse times
        if report_data.get("startTime"):
            try:
                record.start_time = datetime.strptime(
                    report_data["startTime"], "%Y-%m-%d %H:%M:%S"
                )
            except ValueError:
                pass
        
        if report_data.get("endTime"):
            try:
                record.end_time = datetime.strptime(
                    report_data["endTime"], "%Y-%m-%d %H:%M:%S"
                )
            except ValueError:
                pass
        
        if report_data.get("totalTimes"):
            record.duration_minutes = int(report_data["totalTimes"])
        
        if report_data.get("score"):
            try:
                record.health_score = int(report_data["score"])
            except (ValueError, TypeError):
                pass
        
        record.status = "processing"
        
        await self.db.commit()
        await self.db.refresh(record)
        
        return record
    
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
