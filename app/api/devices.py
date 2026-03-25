# ===========================================
# 设备管理 API 路由
# ===========================================
"""
设备相关的 CRUD 接口

接口列表:
- POST / - 创建设备
- GET / - 获取设备列表(分页，支持按租户和状态过滤)
- GET /{device_id} - 获取设备详情
- PUT /{device_id} - 更新设备
- DELETE /{device_id} - 删除设备
- POST /{device_id}/sync - 同步设备状态(从厂家云平台)
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.device import Device
from app.models.tenant import Tenant
from app.schemas import DataResponse
from app.schemas.device import (
    DeviceCreate,
    DeviceUpdate,
    DeviceResponse,
    DeviceListResponse,
    PageData,
)


router = APIRouter()


@router.post("/", response_model=DataResponse[DeviceResponse], summary="创建设备")
async def create_device(
    device_in: DeviceCreate,
    db: AsyncSession = Depends(get_db)
) -> DataResponse[DeviceResponse]:
    """
    创建新设备
    
    - **device_code**: 设备编码/SN号(必填，唯一)
    - **tenant_id**: 所属租户ID(必填)
    - **status**: 设备状态(online/offline/in_use)
    - **device_type**: 设备型号
    - **ble_mac**: 蓝牙MAC地址
    - **wifi_mac**: WiFi MAC地址
    - **firmware_version**: 固件版本
    - **hardware_version**: 硬件版本
    - **cloud_device_id**: 厂家云平台设备ID
    """
    # 验证租户存在
    tenant_result = await db.execute(
        select(Tenant).where(Tenant.id == device_in.tenant_id)
    )
    if not tenant_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="指定的租户不存在")
    
    # 检查设备编码是否已存在
    existing_result = await db.execute(
        select(Device).where(Device.device_code == device_in.device_code)
    )
    if existing_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="设备编码已存在")
    
    # 创建设备对象
    device = Device(
        device_code=device_in.device_code,
        tenant_id=device_in.tenant_id,
        status=device_in.status,
        device_type=device_in.device_type,
        ble_mac=device_in.ble_mac,
        wifi_mac=device_in.wifi_mac,
        firmware_version=device_in.firmware_version,
        hardware_version=device_in.hardware_version,
        cloud_device_id=device_in.cloud_device_id,
    )
    
    db.add(device)
    await db.commit()
    await db.refresh(device)
    
    # 重新加载以获取关联的租户信息
    result = await db.execute(
        select(Device)
        .options(selectinload(Device.tenant))
        .where(Device.id == device.id)
    )
    device = result.scalar_one()
    
    return DataResponse(
        code=200,
        msg="创建成功",
        data=DeviceResponse.from_orm_with_label(device)
    )


@router.get("/", response_model=DeviceListResponse, summary="获取设备列表")
async def list_devices(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=10, ge=1, le=100, description="每页记录数"),
    tenant_id: Optional[UUID] = Query(default=None, description="租户ID过滤"),
    status: Optional[str] = Query(default=None, description="设备状态过滤"),
    device_code: Optional[str] = Query(default=None, description="设备编码(模糊搜索)"),
    db: AsyncSession = Depends(get_db)
) -> DeviceListResponse:
    """
    获取设备分页列表
    
    - **page**: 页码，从1开始
    - **page_size**: 每页记录数，默认10，最大100
    - **tenant_id**: 按租户ID过滤
    - **status**: 按设备状态过滤
    - **device_code**: 按设备编码模糊搜索
    """
    # 构建查询
    query = select(Device).options(selectinload(Device.tenant))
    count_query = select(func.count(Device.id))
    
    # 应用过滤条件
    if tenant_id:
        query = query.where(Device.tenant_id == tenant_id)
        count_query = count_query.where(Device.tenant_id == tenant_id)
    
    if status:
        query = query.where(Device.status == status)
        count_query = count_query.where(Device.status == status)
    
    if device_code:
        query = query.where(Device.device_code.ilike(f"%{device_code}%"))
        count_query = count_query.where(Device.device_code.ilike(f"%{device_code}%"))
    
    # 获取总数
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # 分页
    offset = (page - 1) * page_size
    query = query.order_by(Device.created_at.desc()).offset(offset).limit(page_size)
    
    # 执行查询
    result = await db.execute(query)
    devices = result.scalars().all()
    
    # 构建响应
    items = [DeviceResponse.from_orm_with_label(d) for d in devices]
    
    return DeviceListResponse(
        code=200,
        msg="success",
        data=PageData(
            total=total,
            page=page,
            page_size=page_size,
            items=items
        )
    )


@router.get("/{device_id}", response_model=DataResponse[DeviceResponse], summary="获取设备详情")
async def get_device(
    device_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> DataResponse[DeviceResponse]:
    """
    根据ID获取设备详情
    
    - **device_id**: 设备ID
    """
    # 查询设备（包含租户信息）
    result = await db.execute(
        select(Device)
        .options(selectinload(Device.tenant))
        .where(Device.id == device_id)
    )
    device = result.scalar_one_or_none()
    
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    return DataResponse(
        code=200,
        msg="success",
        data=DeviceResponse.from_orm_with_label(device)
    )


@router.put("/{device_id}", response_model=DataResponse[DeviceResponse], summary="更新设备")
async def update_device(
    device_id: UUID,
    device_in: DeviceUpdate,
    db: AsyncSession = Depends(get_db)
) -> DataResponse[DeviceResponse]:
    """
    更新设备信息
    
    - **device_id**: 设备ID
    - 请求体中只包含需要更新的字段
    """
    # 查询设备
    result = await db.execute(
        select(Device)
        .options(selectinload(Device.tenant))
        .where(Device.id == device_id)
    )
    device = result.scalar_one_or_none()
    
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    # 更新字段
    update_data = device_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(device, field, value)
    
    await db.commit()
    await db.refresh(device)
    
    return DataResponse(
        code=200,
        msg="更新成功",
        data=DeviceResponse.from_orm_with_label(device)
    )


@router.delete("/{device_id}", response_model=DataResponse, summary="删除设备")
async def delete_device(
    device_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> DataResponse:
    """
    删除设备
    
    - **device_id**: 设备ID
    
    注意：删除设备会级联删除其所有检测记录
    """
    # 查询设备
    result = await db.execute(
        select(Device).where(Device.id == device_id)
    )
    device = result.scalar_one_or_none()
    
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    # 删除设备
    await db.delete(device)
    await db.commit()
    
    return DataResponse(
        code=200,
        msg="删除成功",
        data=None
    )


@router.post("/{device_id}/sync", response_model=DataResponse[DeviceResponse], summary="同步设备状态")
async def sync_device_status(
    device_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> DataResponse[DeviceResponse]:
    """
    从厂家云平台同步设备状态
    
    - **device_id**: 设备ID
    
    此接口会调用厂家API获取最新的设备信息和状态
    """
    # 查询设备
    result = await db.execute(
        select(Device)
        .options(selectinload(Device.tenant))
        .where(Device.id == device_id)
    )
    device = result.scalar_one_or_none()
    
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    # TODO: 调用厂家API同步设备状态
    # from app.services.cushion_cloud_client import CushionCloudClient
    # client = CushionCloudClient()
    # device_info = await client.get_device_list(device.device_code)
    # 更新设备信息...
    
    return DataResponse(
        code=200,
        msg="同步成功",
        data=DeviceResponse.from_orm_with_label(device)
    )
