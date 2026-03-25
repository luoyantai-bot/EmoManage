# ===========================================
# 租户相关 Pydantic Schemas
# ===========================================
"""
租户数据校验模型

包含:
- TenantCreate: 创建租户时的输入
- TenantUpdate: 更新租户时的输入
- TenantResponse: 租户信息响应
- TenantListResponse: 租户列表响应
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas import TimestampMixin, UUIDMixin, PageData, ListResponse


# ===========================================
# 商家类型枚举
# ===========================================

TENANT_TYPES = ["chinese_medicine", "hotel", "wellness_center"]
TENANT_TYPE_LABELS = {
    "chinese_medicine": "中医馆",
    "hotel": "酒店",
    "wellness_center": "养生中心",
}


# ===========================================
# 创建 Schema
# ===========================================

class TenantCreate(BaseModel):
    """
    创建租户时的输入模型
    
    必填字段:
        - name: 商家名称
    
    可选字段:
        - type: 商家类型，默认为养生中心
        - contact_phone: 联系电话
        - address: 商家地址
    """
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="商家名称",
        examples=["仁和养生中心"]
    )
    type: str = Field(
        default="wellness_center",
        description="商家类型: chinese_medicine/hotel/wellness_center",
        examples=["wellness_center"]
    )
    contact_phone: Optional[str] = Field(
        default=None,
        max_length=20,
        description="联系电话",
        examples=["13800138000"]
    )
    address: Optional[str] = Field(
        default=None,
        max_length=500,
        description="商家地址",
        examples=["北京市朝阳区xxx路xxx号"]
    )

    @field_validator('type')
    @classmethod
    def validate_type(cls, v: str) -> str:
        """验证商家类型"""
        if v not in TENANT_TYPES:
            raise ValueError(f"无效的商家类型: {v}，有效值为: {TENANT_TYPES}")
        return v


# ===========================================
# 更新 Schema
# ===========================================

class TenantUpdate(BaseModel):
    """
    更新租户时的输入模型
    
    所有字段都是可选的，只更新传入的字段
    """
    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="商家名称"
    )
    type: Optional[str] = Field(
        default=None,
        description="商家类型: chinese_medicine/hotel/wellness_center"
    )
    contact_phone: Optional[str] = Field(
        default=None,
        max_length=20,
        description="联系电话"
    )
    address: Optional[str] = Field(
        default=None,
        max_length=500,
        description="商家地址"
    )

    @field_validator('type')
    @classmethod
    def validate_type(cls, v: Optional[str]) -> Optional[str]:
        """验证商家类型"""
        if v is not None and v not in TENANT_TYPES:
            raise ValueError(f"无效的商家类型: {v}，有效值为: {TENANT_TYPES}")
        return v


# ===========================================
# 响应 Schema
# ===========================================

class TenantResponse(UUIDMixin, TimestampMixin):
    """
    租户信息响应模型
    
    包含租户的所有信息和时间戳
    """
    name: str = Field(description="商家名称")
    type: str = Field(description="商家类型")
    type_label: str = Field(description="商家类型中文标签")
    contact_phone: Optional[str] = Field(default=None, description="联系电话")
    address: Optional[str] = Field(default=None, description="商家地址")

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm_with_label(cls, obj):
        """从ORM模型创建响应，自动添加类型标签"""
        data = {
            'id': obj.id,
            'name': obj.name,
            'type': obj.type,
            'type_label': TENANT_TYPE_LABELS.get(obj.type, obj.type),
            'contact_phone': obj.contact_phone,
            'address': obj.address,
            'created_at': obj.created_at,
            'updated_at': obj.updated_at,
        }
        return cls(**data)


class TenantSimple(UUIDMixin, BaseModel):
    """
    租户简要信息模型
    
    用于在其他模型的响应中嵌套显示租户信息
    """
    name: str = Field(description="商家名称")
    type: str = Field(description="商家类型")

    model_config = ConfigDict(from_attributes=True)


# ===========================================
# 列表响应 Schema
# ===========================================

class TenantListResponse(ListResponse[TenantResponse]):
    """
    租户分页列表响应
    
    包含分页信息和租户列表
    """
    pass
