# ===========================================
# 用户相关 Pydantic Schemas
# ===========================================
"""
用户数据校验模型

包含:
- UserCreate: 创建用户时的输入
- UserUpdate: 更新用户时的输入
- UserResponse: 用户信息响应
- UserListResponse: 用户列表响应
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas import TimestampMixin, UUIDMixin, PageData, ListResponse
from app.schemas.tenant import TenantSimple


# ===========================================
# 性别枚举
# ===========================================

GENDERS = ["male", "female", "other"]
GENDER_LABELS = {
    "male": "男",
    "female": "女",
    "other": "其他",
}


# ===========================================
# 创建 Schema
# ===========================================

class UserCreate(BaseModel):
    """
    创建用户时的输入模型
    
    必填字段:
        - tenant_id: 所属租户ID
        - name: 用户姓名
        - gender: 性别
    
    可选字段:
        - age: 年龄
        - height: 身高(cm)
        - weight: 体重(kg)
        - phone: 联系电话
    """
    tenant_id: UUID = Field(
        ...,
        description="所属租户ID"
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="用户姓名",
        examples=["张三"]
    )
    gender: str = Field(
        ...,
        description="性别: male/female/other",
        examples=["male"]
    )
    age: Optional[int] = Field(
        default=None,
        ge=0,
        le=200,
        description="年龄",
        examples=[30]
    )
    height: Optional[float] = Field(
        default=None,
        gt=0,
        le=300,
        description="身高(cm)",
        examples=[175.0]
    )
    weight: Optional[float] = Field(
        default=None,
        gt=0,
        le=500,
        description="体重(kg)",
        examples=[70.0]
    )
    phone: Optional[str] = Field(
        default=None,
        max_length=20,
        description="联系电话",
        examples=["13800138000"]
    )

    @field_validator('gender')
    @classmethod
    def validate_gender(cls, v: str) -> str:
        """验证性别"""
        if v not in GENDERS:
            raise ValueError(f"无效的性别: {v}，有效值为: {GENDERS}")
        return v


# ===========================================
# 更新 Schema
# ===========================================

class UserUpdate(BaseModel):
    """
    更新用户时的输入模型
    
    所有字段都是可选的，只更新传入的字段
    """
    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=50,
        description="用户姓名"
    )
    gender: Optional[str] = Field(
        default=None,
        description="性别: male/female/other"
    )
    age: Optional[int] = Field(
        default=None,
        ge=0,
        le=200,
        description="年龄"
    )
    height: Optional[float] = Field(
        default=None,
        gt=0,
        le=300,
        description="身高(cm)"
    )
    weight: Optional[float] = Field(
        default=None,
        gt=0,
        le=500,
        description="体重(kg)"
    )
    phone: Optional[str] = Field(
        default=None,
        max_length=20,
        description="联系电话"
    )

    @field_validator('gender')
    @classmethod
    def validate_gender(cls, v: Optional[str]) -> Optional[str]:
        """验证性别"""
        if v is not None and v not in GENDERS:
            raise ValueError(f"无效的性别: {v}，有效值为: {GENDERS}")
        return v


# ===========================================
# 响应 Schema
# ===========================================

class UserResponse(UUIDMixin, TimestampMixin):
    """
    用户信息响应模型
    
    包含用户的所有信息，包括自动计算的BMI和时间戳
    """
    tenant_id: UUID = Field(description="所属租户ID")
    name: str = Field(description="用户姓名")
    gender: str = Field(description="性别")
    gender_label: str = Field(description="性别中文标签")
    age: Optional[int] = Field(default=None, description="年龄")
    height: Optional[float] = Field(default=None, description="身高(cm)")
    weight: Optional[float] = Field(default=None, description="体重(kg)")
    bmi: Optional[float] = Field(default=None, description="身体质量指数(自动计算)")
    phone: Optional[str] = Field(default=None, description="联系电话")
    tenant: Optional[TenantSimple] = Field(default=None, description="所属租户信息")

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm_with_label(cls, obj):
        """从ORM模型创建响应，自动添加性别标签"""
        data = {
            'id': obj.id,
            'tenant_id': obj.tenant_id,
            'name': obj.name,
            'gender': obj.gender,
            'gender_label': GENDER_LABELS.get(obj.gender, obj.gender),
            'age': obj.age,
            'height': obj.height,
            'weight': obj.weight,
            'bmi': obj.bmi,
            'phone': obj.phone,
            'created_at': obj.created_at,
            'updated_at': obj.updated_at,
        }
        # 添加租户信息（如果已加载）
        if hasattr(obj, 'tenant') and obj.tenant:
            data['tenant'] = TenantSimple.model_validate(obj.tenant)
        return cls(**data)



class UserSimple(UUIDMixin, BaseModel):
    """
    用户简要信息模型
    
    用于在其他模型的响应中嵌套显示用户信息
    """
    name: str = Field(description="用户姓名")
    gender: str = Field(description="性别")

    model_config = ConfigDict(from_attributes=True)


# ===========================================
# 列表响应 Schema
# ===========================================

class UserListResponse(ListResponse[UserResponse]):
    """
    用户分页列表响应
    
    包含分页信息和用户列表
    """
    pass


class UserQueryParams(BaseModel):
    """
    用户查询参数
    
    用于过滤用户列表
    """
    tenant_id: Optional[UUID] = Field(default=None, description="按租户ID过滤")
    name: Optional[str] = Field(default=None, description="按姓名模糊搜索")
    gender: Optional[str] = Field(default=None, description="按性别过滤")
