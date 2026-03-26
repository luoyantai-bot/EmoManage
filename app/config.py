# ===========================================
# 应用配置管理
# ===========================================
"""
使用 Pydantic Settings 管理环境变量配置

配置优先级:
1. 环境变量
2. .env 文件
3. 默认值
"""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    应用配置类
    
    所有配置项都从环境变量或.env文件中读取
    """
    
    # ===========================================
    # 应用基础配置
    # ===========================================
    APP_NAME: str = "Emotion Cushion System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # ===========================================
    # 数据库配置
    # ===========================================
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/emotion_cushion"
    
    # ===========================================
    # Redis配置
    # ===========================================
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # ===========================================
    # 点点甜睡云服务配置
    # ===========================================
    CUSHION_CLOUD_USERNAME: str = ""
    CUSHION_CLOUD_PASSWORD: str = ""
    CUSHION_CLOUD_WEBHOOK_SECRET: str = ""
    
    # ===========================================
    # AI大模型配置
    # ===========================================
    SILICONFLOW_API_KEY: str = ""
    SILICONFLOW_MODEL: str = "Qwen/Qwen2.5-72B-Instruct"
    
    # ===========================================
    # JWT配置
    # ===========================================
    JWT_SECRET_KEY: str = "your-super-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24小时
    
    # ===========================================
    # CORS配置
    # ===========================================
    CORS_ORIGINS: str = "*"  # 开发阶段允许所有来源
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    @property
    def cors_origins_list(self) -> list:
        """获取CORS允许的来源列表"""
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]


@lru_cache()
def get_settings() -> Settings:
    """
    获取配置实例(缓存)
    
    使用 lru_cache 确保配置只加载一次
    
    Returns:
        Settings实例
    """
    return Settings()


# 全局配置实例
settings = get_settings()
