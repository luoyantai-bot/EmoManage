# ===========================================
# 设备相关 Pydantic Schemas
# ===========================================
"""
设备数据校验模型

包含:
- DeviceCreate: 创建设备时的输入
- DeviceUpdate: 更新设备时的输入
- DeviceResponse: 设备信息响应
- DeviceListResponse: 设备列表响应
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas import TimestampMixin, UUIDMixin, PageData, ListResponse
from app.schemas.tenant import TenantSimple


# ===========================================
# 设备状态枚举
# ===========================================

DEVICE_STATUSES = ["online", "offline", "in_use"]
DEVICE_STATUS_LABELS = {
    "online": "在线",
    "offline": "离线",
    "in_use": "使用中",
}


# ===========================================
# 创建 Schema
# ===========================================

class DeviceCreate(BaseModel):
    """
    创建设备时的输入模型
    
    必填字段:
        - device_code: 设备编码(SN号)
        - tenant_id: 所属租户ID
    
    可选字段:
        - status: 设备状态，默认为离线
        - device_type: 设备型号
        - ble_mac: 蓝牙MAC地址
        - wifi_mac: WiFi MAC地址
        - firmware_version: 固件版本
        - hardware_version: 硬件版本
        - cloud_device_id: 厂家云平台设备ID
    """
    device_code: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="设备编码(SN号)，如TA0096400014",
        examples=["TA0096400014"]
    )
    tenant_id: UUID = Field(
        ...,
        description="所属租户ID"
    )
    status: str = Field(
        default="offline",
        description="设备状态: online/offline/in_use",
        examples=["offline"]
    )
    device_type: Optional[str] = Field(
        default=None,
        max_length=100,
        description="设备型号",
        examples=["智能坐垫V1"]
    )
    ble_mac: Optional[str] = Field(
        default=None,
        max_length=20,
        description="蓝牙MAC地址"
    )
    wifi_mac: Optional[str] = Field(
        default=None,
        max_length=20,
        description="WiFi MAC地址"
    )
    firmware_version: Optional[str] = Field(
        default=None,
        max_length=20,
        description="固件版本"
    )
    hardware_version: Optional[str] = Field(
        default=None,
        max_length=20,
        description="硬件版本"
    )
    cloud_device_id: Optional[int] = Field(
        default=None,
        description="厂家云平台设备ID"
    )

    @field_validator('status')
    @classmethod
    def validate_status(cls, v: str) -> str:
        """验证设备状态"""
        if v not in DEVICE_STATUSES:
            raise ValueError(f"无效的设备状态: {v}，有效值为: {DEVICE_STATUSES}")
        return v


# ===========================================
# 更新 Schema
# ===========================================

class DeviceUpdate(BaseModel):
    """
    更新设备时的输入模型
    
    所有字段都是可选的，只更新传入的字段
    """
    status: Optional[str] = Field(
        default=None,
        description="设备状态: online/offline/in_use"
    )
    device_type: Optional[str] = Field(
        default=None,
        max_length=100,
        description="设备型号"
    )
    ble_mac: Optional[str] = Field(
        default=None,
        max_length=20,
        description="蓝牙MAC地址"
    )
    wifi_mac: Optional[str] = Field(
        default=None,
        max_length=20,
        description="WiFi MAC地址"
    )
    firmware_version: Optional[str] = Field(
        default=None,
        max_length=20,
        description="固件版本"
    )
    hardware_version: Optional[str] = Field(
        default=None,
        max_length=20,
        description="硬件版本"
    )
    cloud_device_id: Optional[int] = Field(
        default=None,
        description="厂家云平台设备ID"
    )
    last_online_at: Optional[datetime] = Field(
        default=None,
        description="最后在线时间"
    )

    @field_validator('status')
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        """验证设备状态"""
        if v is not None and v not in DEVICE_STATUSES:
            raise ValueError(f"无效的设备状态: {v}，有效值为: {DEVICE_STATUSES}")
        return v


# ===========================================
# 响应 Schema
# ===========================================

class DeviceResponse(UUIDMixin, TimestampMixin):
    """
    设备信息响应模型
    
    包含设备的所有信息和时间戳
    """
    device_code: str = Field(description="设备编码(SN号)")
    tenant_id: UUID = Field(description="所属租户ID")
    status: str = Field(description="设备状态")
    status_label: str = Field(description="设备状态中文标签")
    device_type: Optional[str] = Field(default=None, description="设备型号")
    ble_mac: Optional[str] = Field(default=None, description="蓝牙MAC地址")
    wifi_mac: Optional[str] = Field(default=None, description="WiFi MAC地址")
    firmware_version: Optional[str] = Field(default=None, description="固件版本")
    hardware_version: Optional[str] = Field(default=None, description="硬件版本")
    cloud_device_id: Optional[int] = Field(default=None, description="厂家云平台设备ID")
    last_online_at: Optional[datetime] = Field(default=None, description="最后在线时间")
    tenant: Optional[TenantSimple] = Field(default=None, description="所属租户信息")

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm_with_label(cls, obj):
        """从ORM模型创建响应，自动添加状态标签"""
        data = {
            'id': obj.id,
            'device_code': obj.device_code,
            'tenant_id': obj.tenant_id,
            'status': obj.status,
            'status_label': DEVICE_STATUS_LABELS.get(obj.status, obj.status),
            'device_type': obj.device_type,
            'ble_mac': obj.ble_mac,
            'wifi_mac': obj.wifi_mac,
            'firmware_version': obj.firmware_version,
            'hardware_version': obj.hardware_version,
            'cloud_device_id': obj.cloud_device_id,
            'last_online_at': obj.last_online_at,
            'created_at': obj.created_at,
            'updated_at': obj.updated_at,
        }
        # 添加租户信息（如果已加载）
        if hasattr(obj, 'tenant') and obj.tenant:
            data['tenant'] = TenantSimple.model_validate(obj.tenant)
        return cls(**data)



class DeviceSimple(UUIDMixin, BaseModel):
    """
    设备简要信息模型
    
    用于在其他模型的响应中嵌套显示设备信息
    """
    device_code: str = Field(description="设备编码")
    status: str = Field(description="设备状态")

    model_config = ConfigDict(from_attributes=True)


# ===========================================
# 列表响应 Schema
# ===========================================

class DeviceListResponse(ListResponse[DeviceResponse]):
    """
    设备分页列表响应
    
    包含分页信息和设备列表
    """
    pass


class DeviceQueryParams(BaseModel):
    """
    设备查询参数
    
    用于过滤设备列表
    """
    tenant_id: Optional[UUID] = Field(default=None, description="按租户ID过滤")
    status: Optional[str] = Field(default=None, description="按设备状态过滤")
    device_code: Optional[str] = Field(default=None, description="按设备编码模糊搜索")
