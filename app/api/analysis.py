# ===========================================
# Analysis API Endpoints
# ===========================================
"""
Analysis API endpoints for health metrics

Endpoints:
- GET /{measurement_id}/metrics: Get derived metrics for a measurement
- GET /{measurement_id}/report: Get complete report with metrics and AI analysis
- GET /user/{user_id}/history: Get user's historical metrics trends
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.measurement import MeasurementRecord
from app.models.user import User
from app.models.device import Device
from app.schemas import BaseResponse, DataResponse
from app.schemas.measurement import MeasurementResponse


router = APIRouter()


# ===========================================
# Get Derived Metrics
# ===========================================

@router.get(
    "/{measurement_id}/metrics",
    response_model=DataResponse,
    summary="Get derived metrics",
    description="Retrieve derived health metrics for a specific measurement"
)
async def get_measurement_metrics(
    measurement_id: str,
    db: AsyncSession = Depends(get_db)
) -> DataResponse:
    """
    Get derived health metrics for a measurement
    
    Returns all calculated metrics including:
    - HRV (Heart Rate Variability)
    - Stress Index
    - Anxiety Index
    - Fatigue Index
    - TCM Constitution Analysis
    - Overall Health Score
    - Risk Items
    
    Args:
        measurement_id: Measurement record UUID
    
    Returns:
        Derived metrics dictionary
    """
    try:
        record_id = UUID(measurement_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid measurement ID format")
    
    # Get measurement record
    result = await db.execute(
        select(MeasurementRecord).where(MeasurementRecord.id == record_id)
    )
    record = result.scalar_one_or_none()
    
    if not record:
        raise HTTPException(status_code=404, detail="Measurement record not found")
    
    # Check if derived metrics are available
    if not record.derived_metrics:
        return DataResponse(
            code=200,
            msg="No derived metrics available",
            data={
                "measurement_id": str(record.id),
                "status": record.status,
                "message": "Derived metrics have not been calculated yet"
            }
        )
    
    return DataResponse(
        code=200,
        msg="success",
        data={
            "measurement_id": str(record.id),
            "status": record.status,
            "duration_minutes": record.duration_minutes,
            "health_score": record.health_score,
            "derived_metrics": record.derived_metrics,
            "raw_data_summary": record.raw_data_summary
        }
    )


# ===========================================
# Get Complete Report
# ===========================================

@router.get(
    "/{measurement_id}/report",
    response_model=DataResponse,
    summary="Get complete health report",
    description="Retrieve complete health report with metrics and AI analysis"
)
async def get_measurement_report(
    measurement_id: str,
    db: AsyncSession = Depends(get_db)
) -> DataResponse:
    """
    Get complete health report for a measurement
    
    Includes:
    - Basic measurement info
    - Raw data summary
    - Derived health metrics
    - AI-generated analysis (if available)
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
    
    # Get measurement record with user and device info
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
    
    # Build report
    report = {
        "measurement_id": str(record.id),
        "status": record.status,
        "start_time": record.start_time.isoformat() if record.start_time else None,
        "end_time": record.end_time.isoformat() if record.end_time else None,
        "duration_minutes": record.duration_minutes,
        "health_score": record.health_score,
    }
    
    # User info
    if record.user:
        report["user"] = {
            "id": str(record.user.id),
            "name": record.user.name,
            "gender": record.user.gender,
            "age": record.user.age
        }
    
    # Device info
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
    if record.ai_analysis:
        report["ai_analysis"] = record.ai_analysis
    else:
        report["ai_analysis"] = None
        report["ai_analysis_status"] = "pending" if record.status == "processing" else "not_available"
    
    return DataResponse(
        code=200,
        msg="success",
        data=report
    )


# ===========================================
# Get User History
# ===========================================

@router.get(
    "/user/{user_id}/history",
    response_model=DataResponse,
    summary="Get user history",
    description="Retrieve historical measurement metrics for a user"
)
async def get_user_history(
    user_id: str,
    days: int = Query(default=30, ge=1, le=365, description="Number of days to look back"),
    limit: int = Query(default=20, ge=1, le=100, description="Maximum number of records"),
    db: AsyncSession = Depends(get_db)
) -> DataResponse:
    """
    Get user's historical measurement metrics
    
    Returns trend data for:
    - Health scores over time
    - Stress levels
    - HRV trends
    - Sleep quality
    
    Args:
        user_id: User UUID
        days: Number of days to look back (1-365)
        limit: Maximum number of records (1-100)
    
    Returns:
        Historical metrics and trends
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
    
    # Calculate date range
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Get measurement records
    result = await db.execute(
        select(MeasurementRecord)
        .where(
            and_(
                MeasurementRecord.user_id == user_uuid,
                MeasurementRecord.start_time >= start_date,
                MeasurementRecord.status == "completed"
            )
        )
        .order_by(desc(MeasurementRecord.start_time))
        .limit(limit)
    )
    records = result.scalars().all()
    
    # Build history list
    history = []
    for record in records:
        if record.derived_metrics:
            history.append({
                "measurement_id": str(record.id),
                "start_time": record.start_time.isoformat() if record.start_time else None,
                "duration_minutes": record.duration_minutes,
                "health_score": record.health_score,
                "hrv_score": record.derived_metrics.get("hrv_score"),
                "stress_index": record.derived_metrics.get("stress_index"),
                "anxiety_index": record.derived_metrics.get("anxiety_index"),
                "fatigue_index": record.derived_metrics.get("fatigue_index"),
                "tcm_primary": record.derived_metrics.get("tcm_primary_constitution"),
            })
    
    # Calculate trends if enough data
    trends = None
    if len(history) >= 2:
        trends = _calculate_trends(history)
    
    return DataResponse(
        code=200,
        msg="success",
        data={
            "user_id": str(user_uuid),
            "user_name": user.name,
            "query_period_days": days,
            "total_records": len(history),
            "history": history,
            "trends": trends
        }
    )


def _calculate_trends(history: List[dict]) -> dict:
    """
    Calculate trend statistics from historical data
    
    Args:
        history: List of measurement history entries
    
    Returns:
        Trend statistics dictionary
    """
    if len(history) < 2:
        return None
    
    # Extract values
    health_scores = [h["health_score"] for h in history if h.get("health_score")]
    hrv_scores = [h["hrv_score"] for h in history if h.get("hrv_score")]
    stress_indices = [h["stress_index"] for h in history if h.get("stress_index")]
    
    trends = {
        "measurement_count": len(history),
        "date_range": {
            "latest": history[0]["start_time"] if history else None,
            "earliest": history[-1]["start_time"] if history else None
        }
    }
    
    # Health score trend
    if health_scores:
        trends["health_score"] = {
            "average": round(sum(health_scores) / len(health_scores), 1),
            "max": max(health_scores),
            "min": min(health_scores),
            "latest": health_scores[0] if health_scores else None,
            "trend": "improving" if len(health_scores) >= 2 and health_scores[0] > health_scores[-1] 
                     else "declining" if len(health_scores) >= 2 and health_scores[0] < health_scores[-1]
                     else "stable"
        }
    
    # HRV trend
    if hrv_scores:
        trends["hrv"] = {
            "average": round(sum(hrv_scores) / len(hrv_scores), 1),
            "latest": hrv_scores[0],
            "trend": "improving" if len(hrv_scores) >= 2 and hrv_scores[0] > hrv_scores[-1]
                     else "declining" if len(hrv_scores) >= 2 and hrv_scores[0] < hrv_scores[-1]
                     else "stable"
        }
    
    # Stress trend
    if stress_indices:
        trends["stress"] = {
            "average": round(sum(stress_indices) / len(stress_indices), 1),
            "latest": stress_indices[0],
            "trend": "decreasing" if len(stress_indices) >= 2 and stress_indices[0] < stress_indices[-1]
                     else "increasing" if len(stress_indices) >= 2 and stress_indices[0] > stress_indices[-1]
                     else "stable"
        }
    
    return trends


# ===========================================
# Get TCM Constitution Analysis
# ===========================================

@router.get(
    "/{measurement_id}/tcm",
    response_model=DataResponse,
    summary="Get TCM constitution analysis",
    description="Retrieve Traditional Chinese Medicine constitution analysis"
)
async def get_tcm_analysis(
    measurement_id: str,
    db: AsyncSession = Depends(get_db)
) -> DataResponse:
    """
    Get TCM constitution analysis for a measurement
    
    Returns detailed TCM constitution scores:
    - Primary constitution type
    - Secondary constitution type
    - All 9 constitution scores
    
    Args:
        measurement_id: Measurement record UUID
    
    Returns:
        TCM constitution analysis
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
    
    if not record.derived_metrics:
        raise HTTPException(
            status_code=400, 
            detail="TCM analysis not available - derived metrics not calculated"
        )
    
    # Extract TCM data
    tcm_detail = record.derived_metrics.get("tcm_constitution_detail", {})
    
    # Build constitution descriptions
    constitution_descriptions = {
        "平和质": "正常体质，阴阳气血调和，体态适中、面色红润",
        "气虚质": "元气不足，易疲乏、气短懒言",
        "阳虚质": "阳气不足，怕冷、手足不温",
        "阴虚质": "阴液亏少，口燥咽干、手足心热",
        "痰湿质": "痰湿蕴结，体形肥胖、腹部肥满",
        "湿热质": "湿热内蕴，面垢油光、易生痤疮",
        "血瘀质": "血行不畅，肤色晦暗、易有瘀斑",
        "气郁质": "气机郁滞，情绪低落、易焦虑",
        "特禀质": "先天失常，易过敏、有遗传倾向"
    }
    
    # Build response
    tcm_analysis = {
        "primary": {
            "name": record.derived_metrics.get("tcm_primary_constitution"),
            "score": record.derived_metrics.get("tcm_primary_score"),
            "description": constitution_descriptions.get(
                record.derived_metrics.get("tcm_primary_constitution"), ""
            )
        },
        "secondary": {
            "name": record.derived_metrics.get("tcm_secondary_constitution"),
            "score": record.derived_metrics.get("tcm_secondary_score"),
            "description": constitution_descriptions.get(
                record.derived_metrics.get("tcm_secondary_constitution"), ""
            )
        },
        "all_constitutions": []
    }
    
    # Add all constitution scores with descriptions
    for name, score in tcm_detail.items():
        tcm_analysis["all_constitutions"].append({
            "name": name,
            "score": score,
            "description": constitution_descriptions.get(name, "")
        })
    
    # Sort by score descending
    tcm_analysis["all_constitutions"].sort(
        key=lambda x: x["score"], 
        reverse=True
    )
    
    return DataResponse(
        code=200,
        msg="success",
        data=tcm_analysis
    )


# ===========================================
# Get Risk Assessment
# ===========================================

@router.get(
    "/{measurement_id}/risks",
    response_model=DataResponse,
    summary="Get risk assessment",
    description="Retrieve health risk assessment items"
)
async def get_risk_assessment(
    measurement_id: str,
    db: AsyncSession = Depends(get_db)
) -> DataResponse:
    """
    Get health risk assessment for a measurement
    
    Returns list of risk items with severity levels
    
    Args:
        measurement_id: Measurement record UUID
    
    Returns:
        Risk assessment items
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
    
    if not record.derived_metrics:
        raise HTTPException(
            status_code=400,
            detail="Risk assessment not available - derived metrics not calculated"
        )
    
    risk_items = record.derived_metrics.get("risk_items", [])
    
    # Calculate risk summary
    high_risks = [r for r in risk_items if r.get("level") == "high"]
    medium_risks = [r for r in risk_items if r.get("level") == "medium"]
    low_risks = [r for r in risk_items if r.get("level") == "low"]
    
    return DataResponse(
        code=200,
        msg="success",
        data={
            "measurement_id": str(record.id),
            "health_score": record.health_score,
            "risk_summary": {
                "total_risks": len(risk_items),
                "high_count": len(high_risks),
                "medium_count": len(medium_risks),
                "low_count": len(low_risks),
                "overall_risk_level": "high" if high_risks else "medium" if medium_risks else "low" if low_risks else "none"
            },
            "high_risks": high_risks,
            "medium_risks": medium_risks,
            "low_risks": low_risks
        }
    )
