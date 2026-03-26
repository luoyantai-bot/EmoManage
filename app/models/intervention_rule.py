# ===========================================
# 干预规则模型
# ===========================================
"""
InterventionRule - 干预规则表

商家可以配置自动干预规则，当用户指标满足条件时自动触发干预动作。
例如：压力指数>80时，自动启动香薰机播放舒缓音乐。
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional, Dict, Any
from uuid import uuid4

from sqlalchemy import DateTime, String, Integer, Boolean, Text, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.models import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.tenant import Tenant


class InterventionRule(Base, TimestampMixin):
    """
    干预规则表
    
    B端商家可配置的自动干预规则，支持多条件组合和多动作执行。
    
    属性:
        id: UUID主键
        tenant_id: 租户ID
        name: 规则名称
        description: 规则描述
        is_active: 是否启用
        priority: 优先级（1最高）
        condition_config: 条件配置JSON
        action_config: 动作配置JSON
    """
    __tablename__ = "intervention_rules"
    __table_args__ = {"comment": "干预规则表"}
    
    # 主键
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="规则ID"
    )
    
    # 外键关联
    tenant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="租户ID"
    )
    
    # 规则基本信息
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="规则名称（如'高压力自动减压'）"
    )
    
    description: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="规则描述"
    )
    
    # 规则状态
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="是否启用"
    )
    
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=10,
        comment="优先级（1最高）"
    )
    
    # 条件配置
    condition_config: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment="""
        条件配置JSON
        示例:
        {
            "logic": "AND",
            "conditions": [
                {"metric": "stress_index", "operator": ">", "value": 80},
                {"metric": "anxiety_index", "operator": ">", "value": 70}
            ]
        }
        """
    )
    
    # 动作配置
    action_config: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment="""
        动作配置JSON
        示例:
        {
            "actions": [
                {"device_type": "aroma", "action": "start", "params": {"scent": "lavender", "intensity": 60}},
                {"device_type": "light", "action": "dim", "params": {"brightness": 30, "color": "warm"}},
                {"device_type": "speaker", "action": "play", "params": {"playlist": "meditation", "volume": 40}}
            ]
        }
        """
    )
    
    # 关联关系
    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="intervention_rules"
    )
    
    def __repr__(self) -> str:
        return f"<InterventionRule(id={self.id}, name='{self.name}', is_active={self.is_active})>"
    
    def get_condition_summary(self) -> str:
        """获取条件摘要文本"""
        conditions = self.condition_config.get("conditions", [])
        logic = self.condition_config.get("logic", "AND")
        
        if not conditions:
            return "无条件"
        
        parts = []
        metric_names = {
            "stress_index": "压力指数",
            "anxiety_index": "焦虑指数",
            "hrv_score": "HRV",
            "autonomic_balance": "自主神经平衡",
            "fatigue_index": "疲劳指数",
            "overall_health_score": "健康评分",
            "avg_heart_rate": "心率",
            "posture_stability": "坐姿稳定性"
        }
        
        for c in conditions:
            metric = metric_names.get(c.get("metric"), c.get("metric"))
            op = c.get("operator")
            value = c.get("value")
            parts.append(f"{metric}{op}{value}")
        
        return f" {logic} ".join(parts)
    
    def get_action_summary(self) -> str:
        """获取动作摘要文本"""
        actions = self.action_config.get("actions", [])
        
        if not actions:
            return "无动作"
        
        device_names = {
            "aroma": "香薰机",
            "light": "灯光",
            "speaker": "音箱",
            "humidifier": "加湿器"
        }
        
        action_names = {
            "start": "启动",
            "stop": "停止",
            "dim": "调暗",
            "brighten": "调亮",
            "color_change": "变色",
            "play": "播放",
            "off": "关闭"
        }
        
        parts = []
        for a in actions:
            device = device_names.get(a.get("device_type"), a.get("device_type"))
            action = action_names.get(a.get("action"), a.get("action"))
            parts.append(f"{device}{action}")
        
        return "、".join(parts)
