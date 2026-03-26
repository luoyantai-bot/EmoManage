# ===========================================
# Activities API Endpoints
# ===========================================
"""
Activity Management API

管理健康活动的发布、用户匹配和推送。
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlalchemy import select, and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.activity import Activity
from app.models.activity_push_record import ActivityPushRecord
from app.models.tenant import Tenant
from app.schemas import BaseResponse, DataResponse
from app.services.activity_service import activity_service

from pydantic import BaseModel, Field
from typing import List


router = APIRouter()


# ===========================================
# Pydantic Schemas
# ===========================================

class ActivityCreate(BaseModel):
    """创建活动请求"""
    tenant_id: str = Field(..., description="租户ID")
    title: str = Field(..., min_length=1, max_length=200, description="活动标题")
    description: Optional[str] = Field(default=None, description="活动描述")
    activity_type: str = Field(default="other", description="活动类型")
    start_time: str = Field(..., description="开始时间 (ISO格式)")
    end_time: str = Field(..., description="结束时间 (ISO格式)")
    location: Optional[str] = Field(default=None, max_length=200, description="活动地点")
    max_participants: Optional[int] = Field(default=None, ge=1, description="最大参与人数")
    target_tags: List[str] = Field(default_factory=list, description="目标用户标签")


class ActivityUpdate(BaseModel):
    """更新活动请求"""
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    activity_type: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    location: Optional[str] = None
    max_participants: Optional[int] = Field(default=None, ge=1)
    target_tags: Optional[List[str]] = None
    status: Optional[str] = None


# ===========================================
# List Activities
# ===========================================

@router.get(
    "",
    response_model=DataResponse,
    summary="List activities",
    description="Get paginated list of activities for a tenant"
)
async def list_activities(
    tenant_id: str,
    status: Optional[str] = Query(default=None, description="Filter by status"),
    activity_type: Optional[str] = Query(default=None, description="Filter by type"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
) -> DataResponse:
    """获取活动列表"""
    try:
        tenant_uuid = UUID(tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tenant ID format")
    
    # 构建查询
    query = select(Activity).where(Activity.tenant_id == tenant_uuid)
    
    if status:
        query = query.where(Activity.status == status)
    if activity_type:
        query = query.where(Activity.activity_type == activity_type)
    
    # 计数
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # 分页
    query = query.order_by(desc(Activity.created_at))
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    activities = result.scalars().all()
    
    return DataResponse(
        code=200,
        msg="success",
        data={
            "total": total,
            "page": page,
            "page_size": page_size,
            "activities": [
                {
                    "id": str(a.id),
                    "title": a.title,
                    "activity_type": a.activity_type,
                    "type_label": a.type_label if hasattr(a, 'type_label') else a.activity_type,
                    "start_time": a.start_time.isoformat() if a.start_time else None,
                    "end_time": a.end_time.isoformat() if a.end_time else None,
                    "location": a.location,
                    "status": a.status,
                    "current_participants": a.current_participants,
                    "max_participants": a.max_participants,
                    "target_tags": a.target_tags,
                    "created_at": a.created_at.isoformat() if a.created_at else None
                }
                for a in activities
            ]
        }
    )


# ===========================================
# Create Activity
# ===========================================

@router.post(
    "",
    response_model=DataResponse,
    summary="Create activity",
    description="Create a new health activity"
)
async def create_activity(
    data: ActivityCreate,
    db: AsyncSession = Depends(get_db)
) -> DataResponse:
    """创建活动"""
    try:
        tenant_uuid = UUID(data.tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tenant ID format")
    
    # 验证租户存在
    tenant_result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_uuid)
    )
    if not tenant_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    # 解析时间
    try:
        start_time = datetime.fromisoformat(data.start_time.replace("Z", "+00:00"))
        end_time = datetime.fromisoformat(data.end_time.replace("Z", "+00:00"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid time format: {e}")
    
    if end_time <= start_time:
        raise HTTPException(status_code=400, detail="End time must be after start time")
    
    # 验证活动类型
    valid_types = ["singing_bowl", "meditation", "yoga", "tcm_workshop", "other"]
    if data.activity_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid activity type. Valid types: {valid_types}")
    
    # 创建活动
    activity = Activity(
        tenant_id=tenant_uuid,
        title=data.title,
        description=data.description,
        activity_type=data.activity_type,
        start_time=start_time,
        end_time=end_time,
        location=data.location,
        max_participants=data.max_participants,
        target_tags=data.target_tags,
        status="draft"
    )
    
    db.add(activity)
    await db.commit()
    await db.refresh(activity)
    
    logger.info(f"Created activity: {activity.id} - {activity.title}")
    
    return DataResponse(
        code=200,
        msg="Activity created successfully",
        data={
            "id": str(activity.id),
            "title": activity.title,
            "status": activity.status
        }
    )


# ===========================================
# Get Activity Detail
# ===========================================

@router.get(
    "/{activity_id}",
    response_model=DataResponse,
    summary="Get activity detail",
    description="Get detailed information of an activity"
)
async def get_activity(
    activity_id: str,
    db: AsyncSession = Depends(get_db)
) -> DataResponse:
    """获取活动详情"""
    try:
        activity_uuid = UUID(activity_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid activity ID format")
    
    result = await db.execute(
        select(Activity)
        .options(selectinload(Activity.push_records))
        .where(Activity.id == activity_uuid)
    )
    activity = result.scalar_one_or_none()
    
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    
    return DataResponse(
        code=200,
        msg="success",
        data={
            "id": str(activity.id),
            "tenant_id": str(activity.tenant_id),
            "title": activity.title,
            "description": activity.description,
            "activity_type": activity.activity_type,
            "type_label": activity.type_label if hasattr(activity, 'type_label') else activity.activity_type,
            "start_time": activity.start_time.isoformat() if activity.start_time else None,
            "end_time": activity.end_time.isoformat() if activity.end_time else None,
            "location": activity.location,
            "max_participants": activity.max_participants,
            "current_participants": activity.current_participants,
            "target_tags": activity.target_tags,
            "status": activity.status,
            "push_record_count": len(activity.push_records) if activity.push_records else 0,
            "created_at": activity.created_at.isoformat() if activity.created_at else None,
            "updated_at": activity.updated_at.isoformat() if activity.updated_at else None
        }
    )


# ===========================================
# Update Activity
# ===========================================

@router.put(
    "/{activity_id}",
    response_model=DataResponse,
    summary="Update activity",
    description="Update an existing activity"
)
async def update_activity(
    activity_id: str,
    data: ActivityUpdate,
    db: AsyncSession = Depends(get_db)
) -> DataResponse:
    """更新活动"""
    try:
        activity_uuid = UUID(activity_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid activity ID format")
    
    result = await db.execute(
        select(Activity).where(Activity.id == activity_uuid)
    )
    activity = result.scalar_one_or_none()
    
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    
    # 更新字段
    update_data = data.model_dump(exclude_unset=True)
    
    if "title" in update_data:
        activity.title = update_data["title"]
    if "description" in update_data:
        activity.description = update_data["description"]
    if "activity_type" in update_data:
        activity.activity_type = update_data["activity_type"]
    if "start_time" in update_data:
        try:
            activity.start_time = datetime.fromisoformat(update_data["start_time"].replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_time format")
    if "end_time" in update_data:
        try:
            activity.end_time = datetime.fromisoformat(update_data["end_time"].replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_time format")
    if "location" in update_data:
        activity.location = update_data["location"]
    if "max_participants" in update_data:
        activity.max_participants = update_data["max_participants"]
    if "target_tags" in update_data:
        activity.target_tags = update_data["target_tags"]
    if "status" in update_data:
        valid_statuses = ["draft", "published", "ongoing", "completed", "cancelled"]
        if update_data["status"] not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Invalid status. Valid: {valid_statuses}")
        activity.status = update_data["status"]
    
    await db.commit()
    await db.refresh(activity)
    
    logger.info(f"Updated activity: {activity.id}")
    
    return DataResponse(
        code=200,
        msg="Activity updated successfully",
        data={"id": str(activity.id)}
    )


# ===========================================
# Delete Activity
# ===========================================

@router.delete(
    "/{activity_id}",
    response_model=BaseResponse,
    summary="Delete activity",
    description="Delete an activity"
)
async def delete_activity(
    activity_id: str,
    db: AsyncSession = Depends(get_db)
) -> BaseResponse:
    """删除活动"""
    try:
        activity_uuid = UUID(activity_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid activity ID format")
    
    result = await db.execute(
        select(Activity).where(Activity.id == activity_uuid)
    )
    activity = result.scalar_one_or_none()
    
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    
    await db.delete(activity)
    await db.commit()
    
    logger.info(f"Deleted activity: {activity_id}")
    
    return BaseResponse(code=200, msg="Activity deleted successfully")


# ===========================================
# Match Users for Activity
# ===========================================

@router.post(
    "/{activity_id}/match-users",
    response_model=DataResponse,
    summary="Match target users",
    description="Find users matching the activity's target tags"
)
async def match_users(
    activity_id: str,
    db: AsyncSession = Depends(get_db)
) -> DataResponse:
    """为目标活动匹配用户"""
    try:
        activity_uuid = UUID(activity_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid activity ID format")
    
    # 匹配用户
    matched_users = await activity_service.match_users_for_activity(activity_uuid, db)
    
    return DataResponse(
        code=200,
        msg="success",
        data={
            "activity_id": activity_id,
            "matched_count": len(matched_users),
            "users": matched_users
        }
    )


# ===========================================
# Create Push Records
# ===========================================

@router.post(
    "/{activity_id}/push",
    response_model=DataResponse,
    summary="Create push records",
    description="Create push records for matched users"
)
async def create_push_records(
    activity_id: str,
    db: AsyncSession = Depends(get_db)
) -> DataResponse:
    """创建推送记录"""
    try:
        activity_uuid = UUID(activity_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid activity ID format")
    
    # 创建推送记录
    records = await activity_service.create_push_records(activity_uuid, db)
    
    return DataResponse(
        code=200,
        msg=f"Created {len(records)} push records",
        data={
            "activity_id": activity_id,
            "push_count": len(records)
        }
    )


# ===========================================
# Get Push Records
# ===========================================

@router.get(
    "/{activity_id}/push-records",
    response_model=DataResponse,
    summary="Get push records",
    description="Get push records for an activity"
)
async def get_push_records(
    activity_id: str,
    status: Optional[str] = Query(default=None, description="Filter by status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
) -> DataResponse:
    """获取推送记录"""
    try:
        activity_uuid = UUID(activity_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid activity ID format")
    
    records, total = await activity_service.get_push_records(
        activity_uuid, db, page, page_size, status
    )
    
    return DataResponse(
        code=200,
        msg="success",
        data={
            "activity_id": activity_id,
            "total": total,
            "page": page,
            "page_size": page_size,
            "records": [
                {
                    "id": str(r.id),
                    "user_id": str(r.user_id),
                    "push_reason": r.push_reason,
                    "matched_tags": r.matched_tags,
                    "push_status": r.push_status,
                    "read_at": r.read_at.isoformat() if r.read_at else None,
                    "created_at": r.created_at.isoformat() if r.created_at else None
                }
                for r in records
            ]
        }
    )


# ===========================================
# Export Push List
# ===========================================

@router.get(
    "/{activity_id}/export",
    summary="Export push list as CSV",
    description="Export push records as CSV file for Excel"
)
async def export_push_list(
    activity_id: str,
    db: AsyncSession = Depends(get_db)
) -> StreamingResponse:
    """导出推送列表为CSV"""
    try:
        activity_uuid = UUID(activity_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid activity ID format")
    
    # 生成CSV
    csv_data = await activity_service.export_push_list(activity_uuid, db)
    
    # 获取活动信息
    result = await db.execute(
        select(Activity).where(Activity.id == activity_uuid)
    )
    activity = result.scalar_one_or_none()
    
    filename = f"push_list_{activity.title if activity else activity_id}_{datetime.now().strftime('%Y%m%d')}.csv"
    
    return StreamingResponse(
        iter([csv_data]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}"
        }
    )


# ===========================================
# Get Available Tags
# ===========================================

@router.get(
    "/available-tags",
    response_model=DataResponse,
    summary="Get available tags",
    description="Get list of available user tags for activity targeting"
)
async def get_available_tags() -> DataResponse:
    """获取可用标签列表"""
    return DataResponse(
        code=200,
        msg="success",
        data=activity_service.get_available_tags()
    )
