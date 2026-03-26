# ===========================================
# Realtime Data API Endpoints
# ===========================================
"""
Realtime data API endpoints for frontend

Endpoints:
- GET /{device_code}/latest: Get latest device data
- GET /{device_code}/stream: SSE real-time stream
- POST /{device_code}/start: Start measurement session
- POST /{device_code}/stop: End measurement session
- GET /{device_code}/status: Get current session status
"""

import asyncio
import json
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import BaseResponse, DataResponse
from app.services.redis_client import get_redis, RedisClient
from app.services.realtime_data_service import RealtimeDataService


router = APIRouter()


# ===========================================
# Get Latest Data
# ===========================================

@router.get(
    "/{device_code}/latest",
    response_model=DataResponse,
    summary="Get latest device data",
    description="Retrieve the most recent data from a device"
)
async def get_latest_data(
    device_code: str,
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
) -> DataResponse:
    """
    Get latest data for a device
    
    Returns the most recent data point from Redis cache.
    Data includes heart rate, breathing, bed status, etc.
    
    Args:
        device_code: Device code (SN number)
    
    Returns:
        Latest data dictionary
    """
    realtime_service = RealtimeDataService(db, redis)
    data = await realtime_service.get_latest_data(device_code)
    
    if not data:
        raise HTTPException(status_code=404, detail="No data available for this device")
    
    return DataResponse(
        code=200,
        msg="success",
        data=data
    )


# ===========================================
# SSE Stream
# ===========================================

@router.get(
    "/{device_code}/stream",
    summary="Stream device data (SSE)",
    description="Server-Sent Events stream for real-time device data"
)
async def stream_device_data(
    device_code: str,
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
) -> StreamingResponse:
    """
    Stream real-time device data via Server-Sent Events (SSE)
    
    Frontend can connect to this endpoint to receive real-time updates.
    Each event contains the latest device data as JSON.
    
    Event format:
        data: {"heart_rate": "78", "breathing": "16", ...}
    
    Args:
        device_code: Device code (SN number)
    
    Returns:
        StreamingResponse with SSE content type
    """
    realtime_service = RealtimeDataService(db, redis)
    
    async def event_generator():
        """Generate SSE events"""
        while True:
            try:
                data = await realtime_service.get_latest_data(device_code)
                if data:
                    yield f"data: {json.dumps(data, default=str)}\n\n"
                else:
                    # Send heartbeat if no data
                    yield f": heartbeat\n\n"
                
                await asyncio.sleep(1)  # Update every second
                
            except Exception as e:
                logger.error(f"SSE error: {e}")
                yield f": error\n\n"
                await asyncio.sleep(5)  # Wait before retry
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


# ===========================================
# Start Measurement
# ===========================================

@router.post(
    "/{device_code}/start",
    response_model=DataResponse,
    summary="Start measurement session",
    description="Start a new measurement session for a device"
)
async def start_measurement(
    device_code: str,
    user_id: str = Query(..., description="User ID for the measurement"),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
) -> DataResponse:
    """
    Start a new measurement session
    
    Creates a new MeasurementRecord and marks the device as in use.
    
    Args:
        device_code: Device code (SN number)
        user_id: User ID for this measurement
    
    Returns:
        Session ID and status
    """
    from uuid import UUID
    
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")
    
    realtime_service = RealtimeDataService(db, redis)
    
    try:
        session_id = await realtime_service.start_measurement_session(
            device_code, user_uuid
        )
        
        return DataResponse(
            code=200,
            msg="Measurement session started",
            data={
                "session_id": str(session_id),
                "device_code": device_code,
                "start_time": realtime_service.get_session_status(device_code).get("start_time")
            }
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ===========================================
# Stop Measurement
# ===========================================

@router.post(
    "/{device_code}/stop",
    response_model=DataResponse,
    summary="End measurement session",
    description="End the current measurement session and generate report"
)
async def stop_measurement(
    device_code: str,
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
) -> DataResponse:
    """
    End measurement session
    
    Aggregates all session data, calculates summary statistics,
    and triggers report generation.
    
    Args:
        device_code: Device code (SN number)
    
    Returns:
        Measurement record summary
    """
    realtime_service = RealtimeDataService(db, redis)
    
    record = await realtime_service.end_measurement_session(device_code)
    
    if not record:
        raise HTTPException(
            status_code=404,
            detail="No active measurement session found for this device"
        )
    
    return DataResponse(
        code=200,
        msg="Measurement session ended",
        data={
            "record_id": str(record.id),
            "device_code": device_code,
            "start_time": record.start_time.isoformat() if record.start_time else None,
            "end_time": record.end_time.isoformat() if record.end_time else None,
            "duration_minutes": record.duration_minutes,
            "status": record.status,
            "raw_data_summary": record.raw_data_summary
        }
    )


# ===========================================
# Get Session Status
# ===========================================

@router.get(
    "/{device_code}/status",
    response_model=DataResponse,
    summary="Get session status",
    description="Get current measurement session status for a device"
)
async def get_session_status(
    device_code: str,
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
) -> DataResponse:
    """
    Get current session status
    
    Returns whether the device is currently in a measurement session,
    session duration, and other status information.
    
    Args:
        device_code: Device code (SN number)
    
    Returns:
        Session status information
    """
    realtime_service = RealtimeDataService(db, redis)
    status = await realtime_service.get_session_status(device_code)
    
    # Also check device activity
    is_active = await realtime_service.is_device_active(device_code)
    status["device_active"] = is_active
    
    return DataResponse(
        code=200,
        msg="success",
        data=status
    )


# ===========================================
# Get Recent Data
# ===========================================

@router.get(
    "/{device_code}/recent",
    response_model=DataResponse,
    summary="Get recent device data",
    description="Get recent data points for a device"
)
async def get_recent_data(
    device_code: str,
    minutes: int = Query(default=5, ge=1, le=60, description="Minutes to look back"),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
) -> DataResponse:
    """
    Get recent data for a device
    
    Returns a list of recent data points from Redis Stream.
    
    Args:
        device_code: Device code (SN number)
        minutes: Number of minutes to look back (1-60)
    
    Returns:
        List of recent data points
    """
    realtime_service = RealtimeDataService(db, redis)
    data = await realtime_service.get_recent_data(device_code, minutes)
    
    return DataResponse(
        code=200,
        msg="success",
        data={
            "device_code": device_code,
            "minutes": minutes,
            "count": len(data),
            "items": data
        }
    )


# ===========================================
# Check Device Active
# ===========================================

@router.get(
    "/{device_code}/active",
    response_model=DataResponse,
    summary="Check if device is active",
    description="Check if device has reported data recently"
)
async def check_device_active(
    device_code: str,
    threshold_seconds: int = Query(default=60, ge=10, le=300, description="Inactivity threshold in seconds"),
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis)
) -> DataResponse:
    """
    Check if device is actively reporting data
    
    A device is considered active if it has reported data
    within the threshold seconds.
    
    Args:
        device_code: Device code (SN number)
        threshold_seconds: Threshold for considering device active
    
    Returns:
        Active status and last update time
    """
    realtime_service = RealtimeDataService(db, redis)
    is_active = await realtime_service.is_device_active(device_code, threshold_seconds)
    latest = await realtime_service.get_latest_data(device_code)
    
    return DataResponse(
        code=200,
        msg="success",
        data={
            "device_code": device_code,
            "is_active": is_active,
            "threshold_seconds": threshold_seconds,
            "last_update": latest.get("updated_at") if latest else None
        }
    )
