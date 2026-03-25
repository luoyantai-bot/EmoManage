# ===========================================
# 检测记录管理 API 路由
# ===========================================
"""
检测记录相关的 CRUD 接口

接口列表:
- POST / - 创建检测记录
- GET / - 获取记录列表(分页，支持按用户和设备过滤)
- GET /{record_id} - 获取记录详情
- PUT /{record_id} - 更新记录
- DELETE /{record_id} - 删除记录
- POST /{record_id}/analyze - 触发AI分析
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.measurement import MeasurementRecord
from app.models.user import User
from app.models.device import Device
from app.schemas import DataResponse
from app.schemas.measurement import (
    MeasurementCreate,
    MeasurementUpdate,
    MeasurementResponse,
    MeasurementListResponse,
    PageData,
)


router = APIRouter()


@router.post("/", response_model=DataResponse[MeasurementResponse], summary="创建检测记录")
async def create_measurement(
    measurement_in: MeasurementCreate,
    db: AsyncSession = Depends(get_db)
) -> DataResponse[MeasurementResponse]:
    """
    创建新检测记录
    
    - **user_id**: 用户ID(必填)
    - **device_id**: 设备ID(必填)
    - **start_time**: 检测开始时间(必填)
    - **end_time**: 检测结束时间
    - **status**: 记录状态(measuring/processing/completed/failed)
    - **raw_data_summary**: 原始数据摘要
    - **derived_metrics**: 衍生指标
    - **ai_analysis**: AI分析报告
    - **health_score**: 健康评分(0-100)
    """
    # 验证用户存在
    user_result = await db.execute(
        select(User).where(User.id == measurement_in.user_id)
    )
    if not user_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="指定的用户不存在")
    
    # 验证设备存在
    device_result = await db.execute(
        select(Device).where(Device.id == measurement_in.device_id)
    )
    if not device_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="指定的设备不存在")
    
    # 创建检测记录对象
    measurement = MeasurementRecord(
        user_id=measurement_in.user_id,
        device_id=measurement_in.device_id,
        start_time=measurement_in.start_time,
        end_time=measurement_in.end_time,
        status=measurement_in.status,
        raw_data_summary=measurement_in.raw_data_summary.model_dump() if measurement_in.raw_data_summary else None,
        derived_metrics=measurement_in.derived_metrics.model_dump() if measurement_in.derived_metrics else None,
        ai_analysis=measurement_in.ai_analysis,
        health_score=measurement_in.health_score,
    )
    
    db.add(measurement)
    await db.commit()
    await db.refresh(measurement)
    
    # 重新加载以获取关联信息
    result = await db.execute(
        select(MeasurementRecord)
        .options(
            selectinload(MeasurementRecord.user),
            selectinload(MeasurementRecord.device)
        )
        .where(MeasurementRecord.id == measurement.id)
    )
    measurement = result.scalar_one()
    
    return DataResponse(
        code=200,
        msg="创建成功",
        data=MeasurementResponse.from_orm_with_label(measurement)
    )


@router.get("/", response_model=MeasurementListResponse, summary="获取检测记录列表")
async def list_measurements(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=10, ge=1, le=100, description="每页记录数"),
    user_id: Optional[UUID] = Query(default=None, description="用户ID过滤"),
    device_id: Optional[UUID] = Query(default=None, description="设备ID过滤"),
    status: Optional[str] = Query(default=None, description="记录状态过滤"),
    start_time_from: Optional[datetime] = Query(default=None, description="开始时间起"),
    start_time_to: Optional[datetime] = Query(default=None, description="开始时间止"),
    db: AsyncSession = Depends(get_db)
) -> MeasurementListResponse:
    """
    获取检测记录分页列表
    
    - **page**: 页码，从1开始
    - **page_size**: 每页记录数，默认10，最大100
    - **user_id**: 按用户ID过滤
    - **device_id**: 按设备ID过滤
    - **status**: 按记录状态过滤
    - **start_time_from**: 开始时间范围起点
    - **start_time_to**: 开始时间范围终点
    """
    # 构建查询
    query = select(MeasurementRecord).options(
        selectinload(MeasurementRecord.user),
        selectinload(MeasurementRecord.device)
    )
    count_query = select(func.count(MeasurementRecord.id))
    
    # 构建过滤条件
    filters = []
    
    if user_id:
        filters.append(MeasurementRecord.user_id == user_id)
    
    if device_id:
        filters.append(MeasurementRecord.device_id == device_id)
    
    if status:
        filters.append(MeasurementRecord.status == status)
    
    if start_time_from:
        filters.append(MeasurementRecord.start_time >= start_time_from)
    
    if start_time_to:
        filters.append(MeasurementRecord.start_time <= start_time_to)
    
    # 应用过滤条件
    if filters:
        query = query.where(and_(*filters))
        count_query = count_query.where(and_(*filters))
    
    # 获取总数
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # 分页
    offset = (page - 1) * page_size
    query = query.order_by(MeasurementRecord.start_time.desc()).offset(offset).limit(page_size)
    
    # 执行查询
    result = await db.execute(query)
    measurements = result.scalars().all()
    
    # 构建响应
    items = [MeasurementResponse.from_orm_with_label(m) for m in measurements]
    
    return MeasurementListResponse(
        code=200,
        msg="success",
        data=PageData(
            total=total,
            page=page,
            page_size=page_size,
            items=items
        )
    )


@router.get("/{record_id}", response_model=DataResponse[MeasurementResponse], summary="获取检测记录详情")
async def get_measurement(
    record_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> DataResponse[MeasurementResponse]:
    """
    根据ID获取检测记录详情
    
    - **record_id**: 记录ID
    """
    # 查询记录（包含关联信息）
    result = await db.execute(
        select(MeasurementRecord)
        .options(
            selectinload(MeasurementRecord.user),
            selectinload(MeasurementRecord.device)
        )
        .where(MeasurementRecord.id == record_id)
    )
    measurement = result.scalar_one_or_none()
    
    if not measurement:
        raise HTTPException(status_code=404, detail="检测记录不存在")
    
    return DataResponse(
        code=200,
        msg="success",
        data=MeasurementResponse.from_orm_with_label(measurement)
    )


@router.put("/{record_id}", response_model=DataResponse[MeasurementResponse], summary="更新检测记录")
async def update_measurement(
    record_id: UUID,
    measurement_in: MeasurementUpdate,
    db: AsyncSession = Depends(get_db)
) -> DataResponse[MeasurementResponse]:
    """
    更新检测记录
    
    - **record_id**: 记录ID
    - 请求体中只包含需要更新的字段
    """
    # 查询记录
    result = await db.execute(
        select(MeasurementRecord)
        .options(
            selectinload(MeasurementRecord.user),
            selectinload(MeasurementRecord.device)
        )
        .where(MeasurementRecord.id == record_id)
    )
    measurement = result.scalar_one_or_none()
    
    if not measurement:
        raise HTTPException(status_code=404, detail="检测记录不存在")
    
    # 更新字段
    update_data = measurement_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(measurement, field, value)
    
    await db.commit()
    await db.refresh(measurement)
    
    return DataResponse(
        code=200,
        msg="更新成功",
        data=MeasurementResponse.from_orm_with_label(measurement)
    )


@router.delete("/{record_id}", response_model=DataResponse, summary="删除检测记录")
async def delete_measurement(
    record_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> DataResponse:
    """
    删除检测记录
    
    - **record_id**: 记录ID
    """
    # 查询记录
    result = await db.execute(
        select(MeasurementRecord).where(MeasurementRecord.id == record_id)
    )
    measurement = result.scalar_one_or_none()
    
    if not measurement:
        raise HTTPException(status_code=404, detail="检测记录不存在")
    
    # 删除记录
    await db.delete(measurement)
    await db.commit()
    
    return DataResponse(
        code=200,
        msg="删除成功",
        data=None
    )


@router.post("/{record_id}/analyze", response_model=DataResponse[MeasurementResponse], summary="触发AI分析")
async def trigger_ai_analysis(
    record_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> DataResponse[MeasurementResponse]:
    """
    触发AI分析生成健康报告
    
    - **record_id**: 记录ID
    
    此接口会调用AI大模型分析检测数据并生成健康报告
    """
    # 查询记录
    result = await db.execute(
        select(MeasurementRecord)
        .options(
            selectinload(MeasurementRecord.user),
            selectinload(MeasurementRecord.device)
        )
        .where(MeasurementRecord.id == record_id)
    )
    measurement = result.scalar_one_or_none()
    
    if not measurement:
        raise HTTPException(status_code=404, detail="检测记录不存在")
    
    # 更新状态为处理中
    measurement.status = "processing"
    await db.commit()
    
    # TODO: 调用AI服务生成分析报告
    # from app.services.ai_service import AIAnalysisService
    # ai_service = AIAnalysisService()
    # analysis = await ai_service.analyze_measurement(measurement)
    # measurement.ai_analysis = analysis
    # measurement.status = "completed"
    # await db.commit()
    
    return DataResponse(
        code=200,
        msg="分析已触发",
        data=MeasurementResponse.from_orm_with_label(measurement)
    )
