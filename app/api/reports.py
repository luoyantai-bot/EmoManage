# ===========================================
# Report API Endpoints
# ===========================================
"""
Report API endpoints for AI-generated health analysis reports

Endpoints:
- GET /reports/{measurement_id} - Get complete report (metrics + AI text)
- GET /reports/{measurement_id}/ai-text - Get AI-generated text only
- POST /reports/{measurement_id}/regenerate - Regenerate AI analysis
- GET /reports/user/{user_id} - Get user's reports (paginated)
- GET /reports/device/{device_code} - Get device's reports (paginated)
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from sqlalchemy import select, and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.measurement import MeasurementRecord
from app.models.user import User
from app.models.device import Device
from app.schemas import BaseResponse, DataResponse
from app.services.report_generation_service import report_generation_service


router = APIRouter()


# ===========================================
# Get Complete Report
# ===========================================

@router.get(
    "/{measurement_id}",
    response_model=DataResponse,
    summary="Get complete health report",
    description="Retrieve complete health report with derived metrics and AI analysis"
)
async def get_complete_report(
    measurement_id: str,
    db: AsyncSession = Depends(get_db)
) -> DataResponse:
    """
    Get complete health report for a measurement record
    
    Returns:
    - Basic measurement info
    - Raw data summary
    - Derived metrics (HRV, stress, anxiety, fatigue, TCM constitution)
    - AI-generated analysis report
    - Risk assessment
    
    Args:
        measurement_id: Measurement record UUID
    
    Returns:
        Complete health report
    """
    try:
        record_id = UUID(measurement_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid measurement ID format")
    
    # Get record with related entities
    result = await db.execute(
        select(MeasurementRecord)
        .options(
            selectinload(MeasurementRecord.user),
            selectinload(MeasurementRecord.device)
        )
        .where(MeasurementRecord.id == record_id)
    )
    record = result.scalar_one_or_none()
    
    if not record:
        raise HTTPException(status_code=404, detail="Measurement record not found")
    
    # Build report response
    report = {
        "id": str(record.id),
        "status": record.status,
        "start_time": record.start_time.isoformat() if record.start_time else None,
        "end_time": record.end_time.isoformat() if record.end_time else None,
        "duration_minutes": record.duration_minutes,
        "health_score": record.health_score,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }
    
    # User info (if available)
    if record.user:
        report["user"] = {
            "id": str(record.user.id),
            "name": record.user.name,
            "gender": record.user.gender,
            "age": record.user.age,
            "bmi": record.user.bmi
        }
    
    # Device info (if available)
    if record.device:
        report["device"] = {
            "id": str(record.device.id),
            "device_code": record.device.device_code,
            "device_type": record.device.device_type
        }
    
    # Raw data summary
    report["raw_data_summary"] = record.raw_data_summary
    
    # Derived metrics
    report["derived_metrics"] = record.derived_metrics
    
    # AI analysis
    report["ai_analysis"] = record.ai_analysis
    
    # Risk items (from derived_metrics)
    if record.derived_metrics:
        report["risk_items"] = record.derived_metrics.get("risk_items", [])
    else:
        report["risk_items"] = []
    
    return DataResponse(
        code=200,
        msg="success",
        data=report
    )


# ===========================================
# Get AI Analysis Text Only
# ===========================================

@router.get(
    "/{measurement_id}/ai-text",
    response_model=DataResponse,
    summary="Get AI-generated analysis text",
    description="Retrieve only the AI-generated health analysis report text"
)
async def get_ai_analysis_text(
    measurement_id: str,
    db: AsyncSession = Depends(get_db)
) -> DataResponse:
    """
    Get only the AI-generated analysis text
    
    Args:
        measurement_id: Measurement record UUID
    
    Returns:
        AI analysis text (Markdown format)
    """
    try:
        record_id = UUID(measurement_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid measurement ID format")
    
    result = await db.execute(
        select(MeasurementRecord).where(MeasurementRecord.id == record_id)
    )
    record = result.scalar_one_or_none()
    
    if not record:
        raise HTTPException(status_code=404, detail="Measurement record not found")
    
    if not record.ai_analysis:
        return DataResponse(
            code=200,
            msg="AI analysis not available",
            data={
                "measurement_id": str(record.id),
                "status": record.status,
                "ai_analysis": None,
                "message": "AI analysis has not been generated yet. Please try again later."
            }
        )
    
    return DataResponse(
        code=200,
        msg="success",
        data={
            "measurement_id": str(record.id),
            "status": record.status,
            "ai_analysis": record.ai_analysis,
            "generated_at": record.updated_at.isoformat() if record.updated_at else None
        }
    )


# ===========================================
# Regenerate AI Analysis
# ===========================================

@router.post(
    "/{measurement_id}/regenerate",
    response_model=DataResponse,
    summary="Regenerate AI analysis",
    description="Trigger regeneration of AI health analysis report"
)
async def regenerate_ai_analysis(
    measurement_id: str,
    db: AsyncSession = Depends(get_db)
) -> DataResponse:
    """
    Regenerate AI analysis for a measurement record
    
    This endpoint allows users to request a fresh AI analysis
    when they feel the initial report was not accurate or sufficient.
    
    Args:
        measurement_id: Measurement record UUID
    
    Returns:
        Updated record with new AI analysis
    """
    try:
        record_id = UUID(measurement_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid measurement ID format")
    
    # Get record
    result = await db.execute(
        select(MeasurementRecord)
        .options(
            selectinload(MeasurementRecord.user),
            selectinload(MeasurementRecord.device)
        )
        .where(MeasurementRecord.id == record_id)
    )
    record = result.scalar_one_or_none()
    
    if not record:
        raise HTTPException(status_code=404, detail="Measurement record not found")
    
    # Check if derived metrics exist
    if not record.derived_metrics:
        raise HTTPException(
            status_code=400,
            detail="No derived metrics available. Cannot generate AI analysis without health metrics."
        )
    
    # Get user info
    user_info = {}
    if record.user:
        user_info = {
            "name": record.user.name or "未知用户",
            "gender": record.user.gender or "unknown",
            "age": record.user.age or 0,
            "height": record.user.height or 0,
            "weight": record.user.weight or 0,
            "bmi": record.user.bmi
        }
    
    try:
        # Generate new AI report
        ai_analysis = await report_generation_service.generate_full_report(
            str(record.id),
            user_info,
            record.derived_metrics
        )
        
        record.ai_analysis = ai_analysis
        record.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(record)
        
        logger.info(f"Regenerated AI analysis for measurement: {measurement_id}")
        
        return DataResponse(
            code=200,
            msg="AI analysis regenerated successfully",
            data={
                "measurement_id": str(record.id),
                "ai_analysis": record.ai_analysis,
                "regenerated_at": record.updated_at.isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to regenerate AI analysis: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to regenerate AI analysis: {str(e)}"
        )


# ===========================================
# Get User's Reports
# ===========================================

@router.get(
    "/user/{user_id}",
    response_model=DataResponse,
    summary="Get user's reports",
    description="Retrieve paginated list of health reports for a user"
)
async def get_user_reports(
    user_id: str,
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=10, ge=1, le=50, description="Page size"),
    status: Optional[str] = Query(default=None, description="Filter by status"),
    db: AsyncSession = Depends(get_db)
) -> DataResponse:
    """
    Get paginated list of health reports for a user
    
    Args:
        user_id: User UUID
        page: Page number (1-indexed)
        page_size: Number of records per page
        status: Optional status filter
    
    Returns:
        Paginated list of reports
    """
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")
    
    # Verify user exists
    user_result = await db.execute(
        select(User).where(User.id == user_uuid)
    )
    user = user_result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Build query
    query = select(MeasurementRecord).where(MeasurementRecord.user_id == user_uuid)
    
    if status:
        query = query.where(MeasurementRecord.status == status)
    
    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Get paginated records
    query = query.order_by(desc(MeasurementRecord.created_at))
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    records = result.scalars().all()
    
    # Build response
    reports = []
    for record in records:
        reports.append({
            "id": str(record.id),
            "start_time": record.start_time.isoformat() if record.start_time else None,
            "end_time": record.end_time.isoformat() if record.end_time else None,
            "duration_minutes": record.duration_minutes,
            "status": record.status,
            "health_score": record.health_score,
            "has_ai_analysis": bool(record.ai_analysis),
            "created_at": record.created_at.isoformat() if record.created_at else None
        })
    
    return DataResponse(
        code=200,
        msg="success",
        data={
            "user_id": str(user_uuid),
            "user_name": user.name,
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": (total + page_size - 1) // page_size,
            "reports": reports
        }
    )


# ===========================================
# Get Device's Reports
# ===========================================

@router.get(
    "/device/{device_code}",
    response_model=DataResponse,
    summary="Get device's reports",
    description="Retrieve paginated list of health reports for a device"
)
async def get_device_reports(
    device_code: str,
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=10, ge=1, le=50, description="Page size"),
    status: Optional[str] = Query(default=None, description="Filter by status"),
    db: AsyncSession = Depends(get_db)
) -> DataResponse:
    """
    Get paginated list of health reports for a device
    
    Args:
        device_code: Device code
        page: Page number (1-indexed)
        page_size: Number of records per page
        status: Optional status filter
    
    Returns:
        Paginated list of reports
    """
    # Find device
    device_result = await db.execute(
        select(Device).where(Device.device_code == device_code)
    )
    device = device_result.scalar_one_or_none()
    
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    # Build query
    query = select(MeasurementRecord).where(MeasurementRecord.device_id == device.id)
    
    if status:
        query = query.where(MeasurementRecord.status == status)
    
    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Get paginated records
    query = query.order_by(desc(MeasurementRecord.created_at))
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    records = result.scalars().all()
    
    # Build response
    reports = []
    for record in records:
        reports.append({
            "id": str(record.id),
            "start_time": record.start_time.isoformat() if record.start_time else None,
            "end_time": record.end_time.isoformat() if record.end_time else None,
            "duration_minutes": record.duration_minutes,
            "status": record.status,
            "health_score": record.health_score,
            "has_ai_analysis": bool(record.ai_analysis),
            "created_at": record.created_at.isoformat() if record.created_at else None
        })
    
    return DataResponse(
        code=200,
        msg="success",
        data={
            "device_id": str(device.id),
            "device_code": device.device_code,
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": (total + page_size - 1) // page_size,
            "reports": reports
        }
    )
