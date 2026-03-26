# ===========================================
# Webhook API Endpoints
# ===========================================
"""
Webhook endpoints for receiving data from Cushion Cloud

Endpoints:
- POST /realtime-data: Receive real-time device data
- POST /report: Receive sleep reports
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.alert import AlertRecord
from app.models.device import Device
from app.models.measurement import MeasurementRecord
from app.schemas.webhook import (
    RealtimeDataWebhook,
    ReportDataWebhook,
    WebhookResponse,
)
from app.services.redis_client import get_redis, RedisClient
from app.services.realtime_data_service import RealtimeDataService
from app.services.device_sync_service import DeviceSyncService
from app.utils.security import verify_webhook_sign


router = APIRouter()


# ===========================================
# Signature Verification
# ===========================================

def verify_webhook_signature(timestamp: Optional[str], sign: Optional[str]) -> bool:
    """
    Verify webhook signature from manufacturer
    
    Args:
        timestamp: Unix timestamp from payload
        sign: MD5 signature
    
    Returns:
        True if valid
    """
    if not timestamp or not sign:
        return False
    
    secret = settings.CUSHION_CLOUD_WEBHOOK_SECRET
    if not secret:
        logger.warning("CUSHION_CLOUD_WEBHOOK_SECRET not configured")
        return False
    
    return verify_webhook_sign(secret, timestamp, sign)


# ===========================================
# Real-time Data Webhook
# ===========================================

@router.post(
    "/realtime-data",
    response_model=WebhookResponse,
    summary="Receive real-time device data",
    description="Webhook endpoint for receiving real-time heart rate, breathing, and status data from Cushion Cloud"
)
async def receive_realtime_data(
    data: RealtimeDataWebhook,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
) -> WebhookResponse:
    """
    Receive real-time data from Cushion Cloud
    
    Processing:
    1. Verify signature
    2. Store in Redis Stream and Hash
    3. Check for alerts (SOS events)
    4. Update device status
    
    Returns:
        Standard webhook response
    """
    logger.debug(f"Received realtime data for device: {data.device_code}")
    
    # Verify signature
    if not verify_webhook_signature(data.timestamp, data.sign):
        logger.warning(f"Invalid webhook signature for device: {data.device_code}")
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    try:
        # Store data in Redis
        data_dict = data.to_dict()
        
        # Add to Redis Stream (keep last 30 min of data)
        await redis.add_device_data(data.device_code, data_dict, maxlen=1800)
        
        # Update latest data in Redis Hash
        await redis.set_device_latest(data.device_code, data_dict)
        
        # Check for alerts
        if data.is_alert():
            background_tasks.add_task(
                process_alert,
                data.device_code,
                data.sos_type,
                data_dict,
                db
            )
            logger.info(f"Alert detected: device={data.device_code}, sos_type={data.sos_type}")
        
        # Update device status based on bed_status
        if data.bed_status:
            sync_service = DeviceSyncService(db, redis)
            await sync_service.update_device_status_from_webhook(
                data.device_code,
                data.bed_status
            )
        
        logger.debug(f"Processed realtime data for device: {data.device_code}")
        
    except Exception as e:
        logger.error(f"Failed to process realtime data: {e}")
        # Still return success to avoid manufacturer retries for transient errors
    
    return WebhookResponse(code=200, msg="OK")


# ===========================================
# Report Webhook
# ===========================================

@router.post(
    "/report",
    response_model=WebhookResponse,
    summary="Receive sleep report",
    description="Webhook endpoint for receiving comprehensive sleep reports from Cushion Cloud"
)
async def receive_report(
    data: ReportDataWebhook,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
) -> WebhookResponse:
    """
    Receive sleep report from Cushion Cloud
    
    Processing:
    1. Verify signature
    2. Find associated device
    3. Find or create measurement record
    4. Store report data
    5. Trigger analysis
    
    Returns:
        Standard webhook response
    """
    logger.info(f"Received report for device: {data.device_code}, report_id: {data.report_id}")
    
    # Verify signature
    if not verify_webhook_signature(data.timestamp, data.sign):
        logger.warning(f"Invalid webhook signature for report: {data.device_code}")
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    try:
        # Find device
        result = await db.execute(
            select(Device).where(Device.device_code == data.device_code)
        )
        device = result.scalar_one_or_none()
        
        if not device:
            logger.warning(f"Device not found for report: {data.device_code}")
            # Create device if needed (with default tenant)
            # This is a fallback - normally devices should be pre-registered
            return WebhookResponse(code=200, msg="Device not registered")
        
        # Find active measurement record
        realtime_service = RealtimeDataService(db, redis)
        active_record = await realtime_service.get_active_measurement(data.device_code)
        
        if active_record:
            # Update existing record
            record = active_record
        else:
            # Create new record (if no active session, use device's last user or create orphan record)
            record = MeasurementRecord(
                device_id=device.id,
                start_time=datetime.utcnow(),
                status="processing"
            )
            db.add(record)
            await db.flush()  # Get ID
        
        # Store report data
        record.raw_data_summary = data.to_raw_data_summary()
        
        # Update end time and duration if available
        if data.end_time:
            try:
                record.end_time = datetime.strptime(data.end_time, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass
        
        if data.total_times:
            record.duration_minutes = data.get_total_times_int()
        
        # Set health score
        if data.score:
            record.health_score = data.get_score_int()
        
        # Set status to processing (waiting for AI analysis)
        record.status = "processing"
        
        await db.commit()
        await db.refresh(record)
        
        # Trigger background analysis
        background_tasks.add_task(
            trigger_analysis,
            str(record.id),
            db
        )
        
        logger.info(f"Stored report: record_id={record.id}, device={data.device_code}")
        
    except Exception as e:
        logger.error(f"Failed to process report: {e}")
        # Still return success
        return WebhookResponse(code=200, msg="Processed with warnings")
    
    return WebhookResponse(code=200, msg="OK")


# ===========================================
# Background Tasks
# ===========================================

async def process_alert(
    device_code: str,
    sos_type: str,
    raw_data: Dict[str, Any],
    db: AsyncSession
) -> None:
    """
    Process alert in background
    
    Creates AlertRecord for SOS events.
    
    Args:
        device_code: Device code
        sos_type: SOS type code
        raw_data: Raw webhook data
        db: Database session
    """
    try:
        # Find device
        result = await db.execute(
            select(Device).where(Device.device_code == device_code)
        )
        device = result.scalar_one_or_none()
        
        if not device:
            logger.warning(f"Device not found for alert: {device_code}")
            return
        
        # Get alert type and message
        alert_type, message = AlertRecord.get_alert_type(sos_type)
        
        # Create alert record
        alert = AlertRecord(
            device_id=device.id,
            tenant_id=device.tenant_id,
            alert_type=alert_type,
            alert_code=sos_type,
            message=message,
            raw_data=raw_data,
            status="pending"
        )
        
        db.add(alert)
        await db.commit()
        
        logger.info(f"Created alert: device={device_code}, type={alert_type}")
        
    except Exception as e:
        logger.error(f"Failed to process alert: {e}")


async def trigger_analysis(
    record_id: str,
    db: AsyncSession
) -> None:
    """
    Trigger analysis for a measurement record
    
    1. Calculate derived metrics using algorithm engine
    2. Generate AI analysis (placeholder for Phase 4)
    3. Update record status
    
    Args:
        record_id: Measurement record ID
        db: Database session
    """
    from uuid import UUID
    from app.services.algorithm_engine import MockAlgorithmEngine
    
    try:
        # Get record
        result = await db.execute(
            select(MeasurementRecord).where(MeasurementRecord.id == UUID(record_id))
        )
        record = result.scalar_one_or_none()
        
        if not record:
            logger.warning(f"Record not found for analysis: {record_id}")
            return
        
        # Calculate derived metrics using algorithm engine
        engine = MockAlgorithmEngine()
        
        if record.raw_data_summary:
            # Use report-based calculation
            try:
                derived = engine.calculate_from_report(record.raw_data_summary)
                record.derived_metrics = derived.to_dict()
                record.health_score = derived.overall_health_score
                logger.info(f"Calculated derived metrics: score={derived.overall_health_score}, "
                           f"stress={derived.stress_index}, HRV={derived.hrv_score}")
            except Exception as e:
                logger.error(f"Failed to calculate derived metrics: {e}")
        
        # Mark as completed for now
        record.status = "completed"
        
        # Generate placeholder AI analysis
        if record.derived_metrics:
            metrics = record.derived_metrics
            record.ai_analysis = f"""# Health Analysis Report

## Summary
This is an automated health analysis based on the detected physiological parameters.

## Key Metrics

### Heart Rate Analysis
- Average Heart Rate: {metrics.get('avg_heart_rate', 'N/A')} bpm
- Heart Rate Range: {metrics.get('min_heart_rate', 'N/A')} - {metrics.get('max_heart_rate', 'N/A')} bpm

### Breathing Analysis
- Average Breathing Rate: {metrics.get('avg_breathing', 'N/A')} breaths/min

### HRV (Heart Rate Variability)
- HRV Score: {metrics.get('hrv_score', 'N/A')} ms ({metrics.get('hrv_level', 'N/A')})

### Stress Level
- Stress Index: {metrics.get('stress_index', 'N/A')}% ({metrics.get('stress_level', 'N/A')})

### Fatigue Level
- Fatigue Index: {metrics.get('fatigue_index', 'N/A')}% ({metrics.get('fatigue_level', 'N/A')})

## TCM Constitution Analysis
- Primary Constitution: {metrics.get('tcm_primary_constitution', 'N/A')} (Score: {metrics.get('tcm_primary_score', 'N/A')})
- Secondary Constitution: {metrics.get('tcm_secondary_constitution', 'N/A')} (Score: {metrics.get('tcm_secondary_score', 'N/A')})

## Overall Health Score
**{metrics.get('overall_health_score', 'N/A')}/100**

## Recommendations
1. Maintain regular sleep schedule
2. Stay hydrated
3. Follow up with healthcare provider for any concerns

*Note: This is an automated analysis. Please consult a healthcare professional for medical advice.*
"""
        
        await db.commit()
        
        logger.info(f"Completed analysis for record: {record_id}")
        
    except Exception as e:
        logger.error(f"Failed to trigger analysis: {e}")


# ===========================================
# Webhook Test Endpoint (Development)
# ===========================================

@router.post(
    "/test/realtime-data",
    response_model=WebhookResponse,
    summary="Test real-time data webhook (no signature verification)",
    include_in_schema=False
)
async def test_realtime_data(
    data: RealtimeDataWebhook,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
) -> WebhookResponse:
    """Test endpoint without signature verification (development only)"""
    if not settings.DEBUG:
        raise HTTPException(status_code=404, detail="Not found")
    
    # Same processing as regular endpoint
    data_dict = data.to_dict()
    await redis.add_device_data(data.device_code, data_dict, maxlen=1800)
    await redis.set_device_latest(data.device_code, data_dict)
    
    return WebhookResponse(code=200, msg="OK")
