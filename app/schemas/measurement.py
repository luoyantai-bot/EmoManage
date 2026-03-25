# ===========================================
# 检测记录相关 Pydantic Schemas
# ===========================================
"""
检测记录数据校验模型

包含:
- MeasurementCreate: 创建记录时的输入
- MeasurementUpdate: 更新记录时的输入
- MeasurementResponse: 记录信息响应
- MeasurementListResponse: 记录列表响应
- RawDataSummary: 原始数据摘要模型
- DerivedMetrics: 衍生指标模型
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas import TimestampMixin, UUIDMixin, PageData, ListResponse
from app.schemas.user import UserSimple
from app.schemas.device import DeviceSimple


# ===========================================
# 记录状态枚举
# ===========================================

RECORD_STATUSES = ["measuring", "processing", "completed", "failed"]
RECORD_STATUS_LABELS = {
    "measuring": "检测中",
    "processing": "处理中",
    "completed": "已完成",
    "failed": "失败",
}


# ===========================================
# 原始数据摘要 Schema
# ===========================================

class RawDataSummary(BaseModel):
    """
    原始数据摘要模型
    
    存储从厂家API获取的基础数据统计
    """
    # 心率数据
    heart_rate_avg: Optional[float] = Field(default=None, description="平均心率(bpm)")
    heart_rate_max: Optional[float] = Field(default=None, description="最大心率(bpm)")
    heart_rate_min: Optional[float] = Field(default=None, description="最小心率(bpm)")
    
    # 呼吸数据
    breathing_avg: Optional[float] = Field(default=None, description="平均呼吸频率(次/分钟)")
    breathing_max: Optional[float] = Field(default=None, description="最大呼吸频率(次/分钟)")
    breathing_min: Optional[float] = Field(default=None, description="最小呼吸频率(次/分钟)")
    
    # 睡眠数据
    sleep_duration: Optional[int] = Field(default=None, description="睡眠时长(分钟)")
    deep_sleep_duration: Optional[int] = Field(default=None, description="深睡时长(分钟)")
    light_sleep_duration: Optional[int] = Field(default=None, description="浅睡时长(分钟)")
    
    # 在床状态统计
    in_bed_count: Optional[int] = Field(default=None, description="在床次数")
    out_bed_count: Optional[int] = Field(default=None, description="离床次数")
    
    # 异常事件
    sos_events: Optional[int] = Field(default=None, description="SOS事件次数")
    apnea_events: Optional[int] = Field(default=None, description="呼吸暂停事件次数")


# ===========================================
# 衍生指标 Schema
# ===========================================

class DerivedMetrics(BaseModel):
    """
    衍生指标模型
    
    由算法计算的高级健康指标
    """
    # 心率变异性
    hrv: Optional[float] = Field(
        default=None,
        ge=0,
        le=200,
        description="心率变异性(ms)，越高表示心脏适应能力越强"
    )
    hrv_level: Optional[str] = Field(
        default=None,
        description="HRV等级: excellent/good/normal/poor"
    )
    
    # 压力评估
    stress_index: Optional[int] = Field(
        default=None,
        ge=0,
        le=100,
        description="压力指数(0-100)，数值越大压力越大"
    )
    stress_level: Optional[str] = Field(
        default=None,
        description="压力等级: low/medium/high"
    )
    
    # 放松评估
    relaxation_index: Optional[int] = Field(
        default=None,
        ge=0,
        le=100,
        description="放松指数(0-100)，数值越大越放松"
    )
    relaxation_level: Optional[str] = Field(
        default=None,
        description="放松等级: high/medium/low"
    )
    
    # 睡眠质量
    sleep_quality: Optional[int] = Field(
        default=None,
        ge=0,
        le=100,
        description="睡眠质量评分(0-100)"
    )
    sleep_efficiency: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
        description="睡眠效率(%)"
    )
    
    # 情绪评估
    emotional_state: Optional[str] = Field(
        default=None,
        description="情绪状态: relaxed/neutral/anxious/stressed"
    )
    
    # 疲劳程度
    fatigue_level: Optional[str] = Field(
        default=None,
        description="疲劳程度: low/medium/high"
    )
    
    # 能量水平
    energy_level: Optional[int] = Field(
        default=None,
        ge=0,
        le=100,
        description="能量水平(0-100)"
    )


# ===========================================
# 创建 Schema
# ===========================================

class MeasurementCreate(BaseModel):
    """
    创建检测记录时的输入模型
    
    必填字段:
        - user_id: 用户ID
        - device_id: 设备ID
        - start_time: 检测开始时间
    
    可选字段:
        - end_time: 检测结束时间
        - status: 记录状态，默认为检测中
        - raw_data_summary: 原始数据摘要
        - derived_metrics: 衍生指标
        - ai_analysis: AI分析报告
        - health_score: 健康评分
    """
    user_id: UUID = Field(..., description="用户ID")
    device_id: UUID = Field(..., description="设备ID")
    start_time: datetime = Field(..., description="检测开始时间")
    end_time: Optional[datetime] = Field(default=None, description="检测结束时间")
    status: str = Field(
        default="measuring",
        description="记录状态: measuring/processing/completed/failed"
    )
    raw_data_summary: Optional[RawDataSummary] = Field(
        default=None,
        description="原始数据摘要"
    )
    derived_metrics: Optional[DerivedMetrics] = Field(
        default=None,
        description="衍生指标"
    )
    ai_analysis: Optional[str] = Field(
        default=None,
        description="AI分析报告(Markdown格式)"
    )
    health_score: Optional[int] = Field(
        default=None,
        ge=0,
        le=100,
        description="健康评分(0-100)"
    )

    @field_validator('status')
    @classmethod
    def validate_status(cls, v: str) -> str:
        """验证记录状态"""
        if v not in RECORD_STATUSES:
            raise ValueError(f"无效的记录状态: {v}，有效值为: {RECORD_STATUSES}")
        return v


# ===========================================
# 更新 Schema
# ===========================================

class MeasurementUpdate(BaseModel):
    """
    更新检测记录时的输入模型
    
    所有字段都是可选的，只更新传入的字段
    """
    end_time: Optional[datetime] = Field(default=None, description="检测结束时间")
    status: Optional[str] = Field(default=None, description="记录状态")
    raw_data_summary: Optional[Dict[str, Any]] = Field(
        default=None,
        description="原始数据摘要"
    )
    derived_metrics: Optional[Dict[str, Any]] = Field(
        default=None,
        description="衍生指标"
    )
    ai_analysis: Optional[str] = Field(default=None, description="AI分析报告")
    health_score: Optional[int] = Field(
        default=None,
        ge=0,
        le=100,
        description="健康评分"
    )

    @field_validator('status')
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        """验证记录状态"""
        if v is not None and v not in RECORD_STATUSES:
            raise ValueError(f"无效的记录状态: {v}，有效值为: {RECORD_STATUSES}")
        return v


# ===========================================
# 响应 Schema
# ===========================================

class MeasurementResponse(UUIDMixin, TimestampMixin):
    """
    检测记录响应模型
    
    包含记录的所有信息和关联的用户、设备信息
    """
    user_id: UUID = Field(description="用户ID")
    device_id: UUID = Field(description="设备ID")
    start_time: datetime = Field(description="检测开始时间")
    end_time: Optional[datetime] = Field(default=None, description="检测结束时间")
    duration_minutes: Optional[int] = Field(default=None, description="检测时长(分钟)")
    status: str = Field(description="记录状态")
    status_label: str = Field(description="记录状态中文标签")
    raw_data_summary: Optional[Dict[str, Any]] = Field(
        default=None,
        description="原始数据摘要"
    )
    derived_metrics: Optional[Dict[str, Any]] = Field(
        default=None,
        description="衍生指标"
    )
    ai_analysis: Optional[str] = Field(default=None, description="AI分析报告")
    health_score: Optional[int] = Field(default=None, description="健康评分")
    user: Optional[UserSimple] = Field(default=None, description="用户信息")
    device: Optional[DeviceSimple] = Field(default=None, description="设备信息")

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm_with_label(cls, obj):
        """从ORM模型创建响应，自动添加状态标签"""
        data = {
            'id': obj.id,
            'user_id': obj.user_id,
            'device_id': obj.device_id,
            'start_time': obj.start_time,
            'end_time': obj.end_time,
            'duration_minutes': obj.duration_minutes,
            'status': obj.status,
            'status_label': RECORD_STATUS_LABELS.get(obj.status, obj.status),
            'raw_data_summary': obj.raw_data_summary,
            'derived_metrics': obj.derived_metrics,
            'ai_analysis': obj.ai_analysis,
            'health_score': obj.health_score,
            'created_at': obj.created_at,
            'updated_at': obj.updated_at,
        }
        # 添加用户信息（如果已加载）
        if hasattr(obj, 'user') and obj.user:
            data['user'] = UserSimple.model_validate(obj.user)
        # 添加设备信息（如果已加载）
        if hasattr(obj, 'device') and obj.device:
            data['device'] = DeviceSimple.model_validate(obj.device)
        return cls(**data)



# ===========================================
# 列表响应 Schema
# ===========================================

class MeasurementListResponse(ListResponse[MeasurementResponse]):
    """
    检测记录分页列表响应
    
    包含分页信息和记录列表
    """
    pass


class MeasurementQueryParams(BaseModel):
    """
    检测记录查询参数
    
    用于过滤记录列表
    """
    user_id: Optional[UUID] = Field(default=None, description="按用户ID过滤")
    device_id: Optional[UUID] = Field(default=None, description="按设备ID过滤")
    status: Optional[str] = Field(default=None, description="按记录状态过滤")
    start_time_from: Optional[datetime] = Field(default=None, description="开始时间起")
    start_time_to: Optional[datetime] = Field(default=None, description="开始时间止")
