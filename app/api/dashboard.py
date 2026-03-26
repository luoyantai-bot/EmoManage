# ===========================================
# Dashboard API Endpoints
# ===========================================
"""
SaaS Dashboard API endpoints

提供 B端商家的数据概览和趋势分析 API。
"""

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from sqlalchemy import select, and_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.measurement import MeasurementRecord
from app.models.device import Device
from app.models.alert import AlertRecord
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas import DataResponse


router = APIRouter()


# ===========================================
# Dashboard Overview
# ===========================================

@router.get(
    "/overview",
    response_model=DataResponse,
    summary="Get dashboard overview",
    description="Get overview statistics for a tenant's dashboard"
)
async def get_dashboard_overview(
    tenant_id: str,
    db: AsyncSession = Depends(get_db)
) -> DataResponse:
    """
    获取 Dashboard 概览数据
    
    返回：
    - today_measurements: 今日测量人次
    - today_alerts: 今日告警数
    - abnormal_ratio: 异常情绪占比 %
    - active_devices: 在线设备数
    - total_devices: 总设备数
    - avg_health_score: 今日平均健康评分
    - stress_distribution: 压力分布
    - constitution_distribution: 体质分布
    - hourly_measurements: 每小时测量人次（今日）
    - recent_alerts: 最近5条告警
    """
    try:
        tenant_uuid = UUID(tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tenant ID format")
    
    # 验证租户存在
    tenant_result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_uuid)
    )
    if not tenant_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    # 计算时间范围
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # 获取今日检测记录
    today_measurements_result = await db.execute(
        select(func.count()).select_from(MeasurementRecord)
        .join(Device)
        .where(
            and_(
                Device.tenant_id == tenant_uuid,
                MeasurementRecord.created_at >= today_start
            )
        )
    )
    today_measurements = today_measurements_result.scalar() or 0
    
    # 获取今日告警
    today_alerts_result = await db.execute(
        select(func.count()).select_from(AlertRecord)
        .where(
            and_(
                AlertRecord.tenant_id == tenant_uuid,
                AlertRecord.created_at >= today_start
            )
        )
    )
    today_alerts = today_alerts_result.scalar() or 0
    
    # 获取设备统计
    devices_result = await db.execute(
        select(Device).where(Device.tenant_id == tenant_uuid)
    )
    devices = devices_result.scalars().all()
    total_devices = len(devices)
    active_devices = sum(1 for d in devices if d.status == "online")
    
    # 获取今日检测记录的详细数据
    today_records_result = await db.execute(
        select(MeasurementRecord)
        .join(Device)
        .where(
            and_(
                Device.tenant_id == tenant_uuid,
                MeasurementRecord.created_at >= today_start,
                MeasurementRecord.derived_metrics.isnot(None)
            )
        )
    )
    today_records = today_records_result.scalars().all()
    
    # 计算平均健康评分
    health_scores = [
        r.health_score for r in today_records 
        if r.health_score is not None
    ]
    avg_health_score = round(sum(health_scores) / len(health_scores)) if health_scores else None
    
    # 计算压力分布
    stress_distribution = {"low": 0, "moderate": 0, "high": 0, "extreme": 0}
    for record in today_records:
        if record.derived_metrics:
            stress_level = record.derived_metrics.get("stress_level", "low")
            if stress_level in stress_distribution:
                stress_distribution[stress_level] += 1
    
    # 计算异常比例（高压力+极高压力）
    total_with_stress = sum(stress_distribution.values())
    abnormal_count = stress_distribution["high"] + stress_distribution["extreme"]
    abnormal_ratio = round(abnormal_count / total_with_stress * 100, 1) if total_with_stress > 0 else 0
    
    # 计算体质分布
    constitution_distribution = {}
    for record in today_records:
        if record.derived_metrics:
            constitution = record.derived_metrics.get("tcm_primary_constitution")
            if constitution:
                constitution_distribution[constitution] = constitution_distribution.get(constitution, 0) + 1
    
    # 获取每小时测量人次
    hourly_measurements = []
    for hour in range(24):
        hour_start = today_start + timedelta(hours=hour)
        hour_end = hour_start + timedelta(hours=1)
        
        if hour_end > datetime.utcnow():
            break
        
        count_result = await db.execute(
            select(func.count()).select_from(MeasurementRecord)
            .join(Device)
            .where(
                and_(
                    Device.tenant_id == tenant_uuid,
                    MeasurementRecord.created_at >= hour_start,
                    MeasurementRecord.created_at < hour_end
                )
            )
        )
        count = count_result.scalar() or 0
        
        if count > 0:
            hourly_measurements.append({
                "hour": hour_start.strftime("%H:00"),
                "count": count
            })
    
    # 获取最近告警
    recent_alerts_result = await db.execute(
        select(AlertRecord)
        .where(AlertRecord.tenant_id == tenant_uuid)
        .order_by(desc(AlertRecord.created_at))
        .limit(5)
    )
    recent_alerts = recent_alerts_result.scalars().all()
    
    recent_alerts_data = [
        {
            "id": str(a.id),
            "time": a.created_at.strftime("%Y-%m-%d %H:%M:%S") if a.created_at else None,
            "device_id": str(a.device_id),
            "type": a.alert_type,
            "message": a.message,
            "status": a.status
        }
        for a in recent_alerts
    ]
    
    return DataResponse(
        code=200,
        msg="success",
        data={
            "today_measurements": today_measurements,
            "today_alerts": today_alerts,
            "abnormal_ratio": abnormal_ratio,
            "active_devices": active_devices,
            "total_devices": total_devices,
            "avg_health_score": avg_health_score,
            "stress_distribution": stress_distribution,
            "constitution_distribution": constitution_distribution,
            "hourly_measurements": hourly_measurements,
            "recent_alerts": recent_alerts_data
        }
    )


# ===========================================
# Trends API
# ===========================================

@router.get(
    "/trends",
    response_model=DataResponse,
    summary="Get trend data",
    description="Get trend statistics for the past N days"
)
async def get_dashboard_trends(
    tenant_id: str,
    days: int = Query(default=7, ge=1, le=30, description="Number of days to look back"),
    db: AsyncSession = Depends(get_db)
) -> DataResponse:
    """
    获取趋势数据
    
    返回最近N天的：
    - 每日测量人次
    - 平均压力
    - 平均健康评分
    - 告警数量
    """
    try:
        tenant_uuid = UUID(tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tenant ID format")
    
    start_date = datetime.utcnow() - timedelta(days=days)
    
    trends = []
    
    for i in range(days):
        day_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - i - 1)
        day_end = day_start + timedelta(days=1)
        
        # 获取当天检测记录
        records_result = await db.execute(
            select(MeasurementRecord)
            .join(Device)
            .where(
                and_(
                    Device.tenant_id == tenant_uuid,
                    MeasurementRecord.created_at >= day_start,
                    MeasurementRecord.created_at < day_end,
                    MeasurementRecord.derived_metrics.isnot(None)
                )
            )
        )
        records = records_result.scalars().all()
        
        # 计算统计
        count = len(records)
        
        stress_values = [
            r.derived_metrics.get("stress_index", 0) 
            for r in records if r.derived_metrics
        ]
        avg_stress = round(sum(stress_values) / len(stress_values), 1) if stress_values else None
        
        health_values = [
            r.health_score for r in records if r.health_score is not None
        ]
        avg_health = round(sum(health_values) / len(health_values)) if health_values else None
        
        # 告警数
        alerts_result = await db.execute(
            select(func.count()).select_from(AlertRecord)
            .where(
                and_(
                    AlertRecord.tenant_id == tenant_uuid,
                    AlertRecord.created_at >= day_start,
                    AlertRecord.created_at < day_end
                )
            )
        )
        alert_count = alerts_result.scalar() or 0
        
        trends.append({
            "date": day_start.strftime("%Y-%m-%d"),
            "measurement_count": count,
            "avg_stress_index": avg_stress,
            "avg_health_score": avg_health,
            "alert_count": alert_count
        })
    
    return DataResponse(
        code=200,
        msg="success",
        data={
            "tenant_id": tenant_id,
            "days": days,
            "trends": trends
        }
    )


# ===========================================
# Real-time Stats
# ===========================================

@router.get(
    "/realtime",
    response_model=DataResponse,
    summary="Get real-time statistics",
    description="Get current active sessions and device status"
)
async def get_realtime_stats(
    tenant_id: str,
    db: AsyncSession = Depends(get_db)
) -> DataResponse:
    """
    获取实时统计数据
    
    返回：
    - 当前在线设备
    - 正在测量的用户数
    - 最近10分钟的检测数
    """
    try:
        tenant_uuid = UUID(tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tenant ID format")
    
    # 获取设备状态
    devices_result = await db.execute(
        select(Device).where(Device.tenant_id == tenant_uuid)
    )
    devices = devices_result.scalars().all()
    
    online_devices = [d for d in devices if d.status == "online"]
    in_use_devices = [d for d in devices if d.status == "in_use"]
    
    # 获取最近10分钟的检测记录
    ten_min_ago = datetime.utcnow() - timedelta(minutes=10)
    
    recent_records_result = await db.execute(
        select(func.count()).select_from(MeasurementRecord)
        .join(Device)
        .where(
            and_(
                Device.tenant_id == tenant_uuid,
                MeasurementRecord.created_at >= ten_min_ago
            )
        )
    )
    recent_count = recent_records_result.scalar() or 0
    
    # 获取正在测量的会话（状态为 measuring 的记录）
    active_sessions_result = await db.execute(
        select(func.count()).select_from(MeasurementRecord)
        .join(Device)
        .where(
            and_(
                Device.tenant_id == tenant_uuid,
                MeasurementRecord.status == "measuring"
            )
        )
    )
    active_sessions = active_sessions_result.scalar() or 0
    
    return DataResponse(
        code=200,
        msg="success",
        data={
            "online_devices": len(online_devices),
            "in_use_devices": len(in_use_devices),
            "total_devices": len(devices),
            "active_sessions": active_sessions,
            "recent_measurements_10min": recent_count,
            "device_list": [
                {
                    "id": str(d.id),
                    "device_code": d.device_code,
                    "status": d.status,
                    "last_active": d.last_active.strftime("%Y-%m-%d %H:%M:%S") if d.last_active else None
                }
                for d in devices[:10]  # 最多返回10个设备
            ]
        }
    )
