# ===========================================
# 用户管理 API 路由
# ===========================================
"""
用户相关的 CRUD 接口

接口列表:
- POST / - 创建用户
- GET / - 获取用户列表(分页，支持按租户过滤)
- GET /{user_id} - 获取用户详情
- PUT /{user_id} - 更新用户
- DELETE /{user_id} - 删除用户
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import User
from app.models.tenant import Tenant
from app.schemas import DataResponse
from app.schemas.user import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserListResponse,
    PageData,
)


router = APIRouter()


@router.post("/", response_model=DataResponse[UserResponse], summary="创建用户")
async def create_user(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db)
) -> DataResponse[UserResponse]:
    """
    创建新用户
    
    - **tenant_id**: 所属租户ID(必填)
    - **name**: 用户姓名(必填)
    - **gender**: 性别(male/female/other，必填)
    - **age**: 年龄
    - **height**: 身高(cm)
    - **weight**: 体重(kg)
    - **phone**: 联系电话
    
    注意：BMI会在保存时自动计算
    """
    # 验证租户存在
    tenant_result = await db.execute(
        select(Tenant).where(Tenant.id == user_in.tenant_id)
    )
    if not tenant_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="指定的租户不存在")
    
    # 创建用户对象
    user = User(
        tenant_id=user_in.tenant_id,
        name=user_in.name,
        gender=user_in.gender,
        age=user_in.age,
        height=user_in.height,
        weight=user_in.weight,
        phone=user_in.phone,
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    # 重新加载以获取关联的租户信息
    result = await db.execute(
        select(User)
        .options(selectinload(User.tenant))
        .where(User.id == user.id)
    )
    user = result.scalar_one()
    
    return DataResponse(
        code=200,
        msg="创建成功",
        data=UserResponse.from_orm_with_label(user)
    )


@router.get("/", response_model=UserListResponse, summary="获取用户列表")
async def list_users(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=10, ge=1, le=100, description="每页记录数"),
    tenant_id: Optional[UUID] = Query(default=None, description="租户ID过滤"),
    name: Optional[str] = Query(default=None, description="用户姓名(模糊搜索)"),
    gender: Optional[str] = Query(default=None, description="性别过滤"),
    db: AsyncSession = Depends(get_db)
) -> UserListResponse:
    """
    获取用户分页列表
    
    - **page**: 页码，从1开始
    - **page_size**: 每页记录数，默认10，最大100
    - **tenant_id**: 按租户ID过滤
    - **name**: 按用户姓名模糊搜索
    - **gender**: 按性别过滤
    """
    # 构建查询
    query = select(User).options(selectinload(User.tenant))
    count_query = select(func.count(User.id))
    
    # 应用过滤条件
    if tenant_id:
        query = query.where(User.tenant_id == tenant_id)
        count_query = count_query.where(User.tenant_id == tenant_id)
    
    if name:
        query = query.where(User.name.ilike(f"%{name}%"))
        count_query = count_query.where(User.name.ilike(f"%{name}%"))
    
    if gender:
        query = query.where(User.gender == gender)
        count_query = count_query.where(User.gender == gender)
    
    # 获取总数
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # 分页
    offset = (page - 1) * page_size
    query = query.order_by(User.created_at.desc()).offset(offset).limit(page_size)
    
    # 执行查询
    result = await db.execute(query)
    users = result.scalars().all()
    
    # 构建响应
    items = [UserResponse.from_orm_with_label(u) for u in users]
    
    return UserListResponse(
        code=200,
        msg="success",
        data=PageData(
            total=total,
            page=page,
            page_size=page_size,
            items=items
        )
    )


@router.get("/{user_id}", response_model=DataResponse[UserResponse], summary="获取用户详情")
async def get_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> DataResponse[UserResponse]:
    """
    根据ID获取用户详情
    
    - **user_id**: 用户ID
    """
    # 查询用户（包含租户信息）
    result = await db.execute(
        select(User)
        .options(selectinload(User.tenant))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    return DataResponse(
        code=200,
        msg="success",
        data=UserResponse.from_orm_with_label(user)
    )


@router.put("/{user_id}", response_model=DataResponse[UserResponse], summary="更新用户")
async def update_user(
    user_id: UUID,
    user_in: UserUpdate,
    db: AsyncSession = Depends(get_db)
) -> DataResponse[UserResponse]:
    """
    更新用户信息
    
    - **user_id**: 用户ID
    - 请求体中只包含需要更新的字段
    
    注意：如果更新了身高或体重，BMI会自动重新计算
    """
    # 查询用户
    result = await db.execute(
        select(User)
        .options(selectinload(User.tenant))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 更新字段
    update_data = user_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    
    await db.commit()
    await db.refresh(user)
    
    return DataResponse(
        code=200,
        msg="更新成功",
        data=UserResponse.from_orm_with_label(user)
    )


@router.delete("/{user_id}", response_model=DataResponse, summary="删除用户")
async def delete_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> DataResponse:
    """
    删除用户
    
    - **user_id**: 用户ID
    
    注意：删除用户会级联删除其所有检测记录
    """
    # 查询用户
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 删除用户
    await db.delete(user)
    await db.commit()
    
    return DataResponse(
        code=200,
        msg="删除成功",
        data=None
    )
