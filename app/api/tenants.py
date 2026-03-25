# ===========================================
# 租户管理 API 路由
# ===========================================
"""
租户相关的 CRUD 接口

接口列表:
- POST / - 创建租户
- GET / - 获取租户列表(分页)
- GET /{tenant_id} - 获取租户详情
- PUT /{tenant_id} - 更新租户
- DELETE /{tenant_id} - 删除租户
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.tenant import Tenant
from app.schemas import DataResponse
from app.schemas.tenant import (
    TenantCreate,
    TenantUpdate,
    TenantResponse,
    TenantListResponse,
    PageData,
)


router = APIRouter()


@router.post("/", response_model=DataResponse[TenantResponse], summary="创建租户")
async def create_tenant(
    tenant_in: TenantCreate,
    db: AsyncSession = Depends(get_db)
) -> DataResponse[TenantResponse]:
    """
    创建新租户
    
    - **name**: 商家名称(必填)
    - **type**: 商家类型(chinese_medicine/hotel/wellness_center)
    - **contact_phone**: 联系电话
    - **address**: 商家地址
    """
    # 创建租户对象
    tenant = Tenant(
        name=tenant_in.name,
        type=tenant_in.type,
        contact_phone=tenant_in.contact_phone,
        address=tenant_in.address,
    )
    
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    
    return DataResponse(
        code=200,
        msg="创建成功",
        data=TenantResponse.from_orm_with_label(tenant)
    )


@router.get("/", response_model=TenantListResponse, summary="获取租户列表")
async def list_tenants(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=10, ge=1, le=100, description="每页记录数"),
    name: Optional[str] = Query(default=None, description="商家名称(模糊搜索)"),
    type: Optional[str] = Query(default=None, description="商家类型"),
    db: AsyncSession = Depends(get_db)
) -> TenantListResponse:
    """
    获取租户分页列表
    
    - **page**: 页码，从1开始
    - **page_size**: 每页记录数，默认10，最大100
    - **name**: 按商家名称模糊搜索
    - **type**: 按商家类型过滤
    """
    # 构建查询
    query = select(Tenant)
    count_query = select(func.count(Tenant.id))
    
    # 应用过滤条件
    if name:
        query = query.where(Tenant.name.ilike(f"%{name}%"))
        count_query = count_query.where(Tenant.name.ilike(f"%{name}%"))
    
    if type:
        query = query.where(Tenant.type == type)
        count_query = count_query.where(Tenant.type == type)
    
    # 获取总数
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # 分页
    offset = (page - 1) * page_size
    query = query.order_by(Tenant.created_at.desc()).offset(offset).limit(page_size)
    
    # 执行查询
    result = await db.execute(query)
    tenants = result.scalars().all()
    
    # 构建响应
    items = [TenantResponse.from_orm_with_label(t) for t in tenants]
    
    return TenantListResponse(
        code=200,
        msg="success",
        data=PageData(
            total=total,
            page=page,
            page_size=page_size,
            items=items
        )
    )


@router.get("/{tenant_id}", response_model=DataResponse[TenantResponse], summary="获取租户详情")
async def get_tenant(
    tenant_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> DataResponse[TenantResponse]:
    """
    根据ID获取租户详情
    
    - **tenant_id**: 租户ID
    """
    # 查询租户
    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    tenant = result.scalar_one_or_none()
    
    if not tenant:
        raise HTTPException(status_code=404, detail="租户不存在")
    
    return DataResponse(
        code=200,
        msg="success",
        data=TenantResponse.from_orm_with_label(tenant)
    )


@router.put("/{tenant_id}", response_model=DataResponse[TenantResponse], summary="更新租户")
async def update_tenant(
    tenant_id: UUID,
    tenant_in: TenantUpdate,
    db: AsyncSession = Depends(get_db)
) -> DataResponse[TenantResponse]:
    """
    更新租户信息
    
    - **tenant_id**: 租户ID
    - 请求体中只包含需要更新的字段
    """
    # 查询租户
    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    tenant = result.scalar_one_or_none()
    
    if not tenant:
        raise HTTPException(status_code=404, detail="租户不存在")
    
    # 更新字段
    update_data = tenant_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(tenant, field, value)
    
    await db.commit()
    await db.refresh(tenant)
    
    return DataResponse(
        code=200,
        msg="更新成功",
        data=TenantResponse.from_orm_with_label(tenant)
    )


@router.delete("/{tenant_id}", response_model=DataResponse, summary="删除租户")
async def delete_tenant(
    tenant_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> DataResponse:
    """
    删除租户
    
    - **tenant_id**: 租户ID
    
    注意：删除租户会级联删除其下的所有用户和设备
    """
    # 查询租户
    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    tenant = result.scalar_one_or_none()
    
    if not tenant:
        raise HTTPException(status_code=404, detail="租户不存在")
    
    # 删除租户
    await db.delete(tenant)
    await db.commit()
    
    return DataResponse(
        code=200,
        msg="删除成功",
        data=None
    )
