# ===========================================
# Intervention Rules API Endpoints
# ===========================================
"""
Intervention Rules Management API

管理干预规则的 CRUD 操作和规则测试。
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from sqlalchemy import select, and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.intervention_rule import InterventionRule
from app.models.intervention_log import InterventionLog
from app.models.tenant import Tenant
from app.schemas import BaseResponse, DataResponse
from app.services.intervention_engine import intervention_engine

from pydantic import BaseModel, Field
from typing import List, Dict, Any


router = APIRouter()


# ===========================================
# Pydantic Schemas
# ===========================================

class ConditionItem(BaseModel):
    """单个条件"""
    metric: str = Field(..., description="指标键名")
    operator: str = Field(..., description="运算符: >, <, >=, <=, ==, !=")
    value: float = Field(..., description="目标值")


class ConditionConfig(BaseModel):
    """条件配置"""
    logic: str = Field(default="AND", description="逻辑: AND 或 OR")
    conditions: List[ConditionItem] = Field(default_factory=list, description="条件列表")


class ActionItem(BaseModel):
    """单个动作"""
    device_type: str = Field(..., description="设备类型: aroma/light/speaker/humidifier")
    action: str = Field(..., description="动作: start/stop/play/dim 等")
    params: Dict[str, Any] = Field(default_factory=dict, description="动作参数")


class ActionConfig(BaseModel):
    """动作配置"""
    actions: List[ActionItem] = Field(default_factory=list, description="动作列表")
    webhook_url: Optional[str] = Field(default=None, description="Webhook通知地址")


class RuleCreate(BaseModel):
    """创建规则请求"""
    tenant_id: str = Field(..., description="租户ID")
    name: str = Field(..., min_length=1, max_length=100, description="规则名称")
    description: Optional[str] = Field(default=None, max_length=500, description="规则描述")
    is_active: bool = Field(default=True, description="是否启用")
    priority: int = Field(default=10, ge=1, le=100, description="优先级")
    condition_config: ConditionConfig = Field(..., description="条件配置")
    action_config: ActionConfig = Field(..., description="动作配置")


class RuleUpdate(BaseModel):
    """更新规则请求"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    is_active: Optional[bool] = Field(default=None)
    priority: Optional[int] = Field(default=None, ge=1, le=100)
    condition_config: Optional[ConditionConfig] = None
    action_config: Optional[ActionConfig] = None


class RuleTestRequest(BaseModel):
    """测试规则请求"""
    condition_config: ConditionConfig = Field(..., description="条件配置")
    test_metrics: Dict[str, Any] = Field(..., description="测试指标")


# ===========================================
# List Rules
# ===========================================

@router.get(
    "",
    response_model=DataResponse,
    summary="List intervention rules",
    description="Get paginated list of intervention rules for a tenant"
)
async def list_rules(
    tenant_id: str,
    is_active: Optional[bool] = Query(default=None, description="Filter by active status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
) -> DataResponse:
    """获取干预规则列表"""
    try:
        tenant_uuid = UUID(tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tenant ID format")
    
    # 构建查询
    query = select(InterventionRule).where(InterventionRule.tenant_id == tenant_uuid)
    
    if is_active is not None:
        query = query.where(InterventionRule.is_active == is_active)
    
    # 计数
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # 分页
    query = query.order_by(InterventionRule.priority.asc(), InterventionRule.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    rules = result.scalars().all()
    
    return DataResponse(
        code=200,
        msg="success",
        data={
            "total": total,
            "page": page,
            "page_size": page_size,
            "rules": [
                {
                    "id": str(r.id),
                    "name": r.name,
                    "description": r.description,
                    "is_active": r.is_active,
                    "priority": r.priority,
                    "condition_summary": r.get_condition_summary() if hasattr(r, 'get_condition_summary') else "",
                    "action_summary": r.get_action_summary() if hasattr(r, 'get_action_summary') else "",
                    "created_at": r.created_at.isoformat() if r.created_at else None
                }
                for r in rules
            ]
        }
    )


# ===========================================
# Create Rule
# ===========================================

@router.post(
    "",
    response_model=DataResponse,
    summary="Create intervention rule",
    description="Create a new intervention rule"
)
async def create_rule(
    data: RuleCreate,
    db: AsyncSession = Depends(get_db)
) -> DataResponse:
    """创建干预规则"""
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
    
    # 创建规则
    rule = InterventionRule(
        tenant_id=tenant_uuid,
        name=data.name,
        description=data.description,
        is_active=data.is_active,
        priority=data.priority,
        condition_config=data.condition_config.model_dump(),
        action_config=data.action_config.model_dump()
    )
    
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    
    logger.info(f"Created intervention rule: {rule.id} - {rule.name}")
    
    return DataResponse(
        code=200,
        msg="Rule created successfully",
        data={
            "id": str(rule.id),
            "name": rule.name,
            "is_active": rule.is_active
        }
    )


# ===========================================
# Get Rule Detail
# ===========================================

@router.get(
    "/{rule_id}",
    response_model=DataResponse,
    summary="Get rule detail",
    description="Get detailed information of an intervention rule"
)
async def get_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db)
) -> DataResponse:
    """获取规则详情"""
    try:
        rule_uuid = UUID(rule_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid rule ID format")
    
    result = await db.execute(
        select(InterventionRule).where(InterventionRule.id == rule_uuid)
    )
    rule = result.scalar_one_or_none()
    
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    return DataResponse(
        code=200,
        msg="success",
        data={
            "id": str(rule.id),
            "tenant_id": str(rule.tenant_id),
            "name": rule.name,
            "description": rule.description,
            "is_active": rule.is_active,
            "priority": rule.priority,
            "condition_config": rule.condition_config,
            "action_config": rule.action_config,
            "created_at": rule.created_at.isoformat() if rule.created_at else None,
            "updated_at": rule.updated_at.isoformat() if rule.updated_at else None
        }
    )


# ===========================================
# Update Rule
# ===========================================

@router.put(
    "/{rule_id}",
    response_model=DataResponse,
    summary="Update intervention rule",
    description="Update an existing intervention rule"
)
async def update_rule(
    rule_id: str,
    data: RuleUpdate,
    db: AsyncSession = Depends(get_db)
) -> DataResponse:
    """更新干预规则"""
    try:
        rule_uuid = UUID(rule_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid rule ID format")
    
    result = await db.execute(
        select(InterventionRule).where(InterventionRule.id == rule_uuid)
    )
    rule = result.scalar_one_or_none()
    
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    # 更新字段
    update_data = data.model_dump(exclude_unset=True)
    
    if "name" in update_data:
        rule.name = update_data["name"]
    if "description" in update_data:
        rule.description = update_data["description"]
    if "is_active" in update_data:
        rule.is_active = update_data["is_active"]
    if "priority" in update_data:
        rule.priority = update_data["priority"]
    if "condition_config" in update_data:
        rule.condition_config = update_data["condition_config"].model_dump()
    if "action_config" in update_data:
        rule.action_config = update_data["action_config"].model_dump()
    
    await db.commit()
    await db.refresh(rule)
    
    logger.info(f"Updated intervention rule: {rule.id}")
    
    return DataResponse(
        code=200,
        msg="Rule updated successfully",
        data={"id": str(rule.id)}
    )


# ===========================================
# Delete Rule
# ===========================================

@router.delete(
    "/{rule_id}",
    response_model=BaseResponse,
    summary="Delete intervention rule",
    description="Delete an intervention rule"
)
async def delete_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db)
) -> BaseResponse:
    """删除干预规则"""
    try:
        rule_uuid = UUID(rule_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid rule ID format")
    
    result = await db.execute(
        select(InterventionRule).where(InterventionRule.id == rule_uuid)
    )
    rule = result.scalar_one_or_none()
    
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    await db.delete(rule)
    await db.commit()
    
    logger.info(f"Deleted intervention rule: {rule_id}")
    
    return BaseResponse(code=200, msg="Rule deleted successfully")


# ===========================================
# Test Rule
# ===========================================

@router.post(
    "/{rule_id}/test",
    response_model=DataResponse,
    summary="Test rule with metrics",
    description="Test if a rule would match given metrics"
)
async def test_rule(
    rule_id: str,
    test_metrics: Dict[str, Any] = None,
    db: AsyncSession = Depends(get_db)
) -> DataResponse:
    """测试规则是否匹配"""
    try:
        rule_uuid = UUID(rule_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid rule ID format")
    
    result = await db.execute(
        select(InterventionRule).where(InterventionRule.id == rule_uuid)
    )
    rule = result.scalar_one_or_none()
    
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    if test_metrics is None:
        test_metrics = {}
    
    # 执行测试
    test_result = await intervention_engine.test_rule(
        rule.condition_config,
        test_metrics
    )
    
    return DataResponse(
        code=200,
        msg="success",
        data=test_result
    )


# ===========================================
# Get Available Metrics
# ===========================================

@router.get(
    "/available-metrics",
    response_model=DataResponse,
    summary="Get available metrics",
    description="Get list of available metrics for rule conditions"
)
async def get_available_metrics() -> DataResponse:
    """获取可用指标列表"""
    return DataResponse(
        code=200,
        msg="success",
        data=intervention_engine.get_available_metrics()
    )


# ===========================================
# Get Available Actions
# ===========================================

@router.get(
    "/available-actions",
    response_model=DataResponse,
    summary="Get available actions",
    description="Get list of available actions for rule execution"
)
async def get_available_actions() -> DataResponse:
    """获取可用动作列表"""
    return DataResponse(
        code=200,
        msg="success",
        data=intervention_engine.get_available_actions()
    )


# ===========================================
# Intervention Logs
# ===========================================

@router.get(
    "/logs",
    response_model=DataResponse,
    summary="List intervention logs",
    description="Get paginated list of intervention execution logs"
)
async def list_intervention_logs(
    tenant_id: str,
    rule_id: Optional[str] = Query(default=None, description="Filter by rule ID"),
    status: Optional[str] = Query(default=None, description="Filter by status"),
    start_date: Optional[str] = Query(default=None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="End date (YYYY-MM-DD)"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
) -> DataResponse:
    """获取干预执行日志列表"""
    try:
        tenant_uuid = UUID(tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tenant ID format")
    
    # 构建查询
    query = select(InterventionLog).where(InterventionLog.tenant_id == tenant_uuid)
    
    if rule_id:
        try:
            rule_uuid = UUID(rule_id)
            query = query.where(InterventionLog.rule_id == rule_uuid)
        except ValueError:
            pass
    
    if status:
        query = query.where(InterventionLog.status == status)
    
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.where(InterventionLog.created_at >= start_dt)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            query = query.where(InterventionLog.created_at < end_dt)
        except ValueError:
            pass
    
    # 计数
    from datetime import timedelta
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # 分页
    query = query.order_by(desc(InterventionLog.created_at))
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    return DataResponse(
        code=200,
        msg="success",
        data={
            "total": total,
            "page": page,
            "page_size": page_size,
            "logs": [
                {
                    "id": str(log.id),
                    "rule_id": str(log.rule_id) if log.rule_id else None,
                    "device_code": log.device_code,
                    "status": log.status,
                    "trigger_metrics": log.trigger_metrics,
                    "actions_executed": log.actions_executed,
                    "error_message": log.error_message,
                    "created_at": log.created_at.isoformat() if log.created_at else None
                }
                for log in logs
            ]
        }
    )
