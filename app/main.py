# ===========================================
# FastAPI 应用入口
# ===========================================
"""
情绪管理与智能坐垫干预系统 - 主应用

主要功能:
- FastAPI应用配置
- CORS中间件
- 路由注册
- 异常处理
- 启动/关闭事件
"""

import sys
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from app.api.router import api_router
from app.config import settings
from app.database import close_db, init_db, test_connection
from app.schemas import BaseResponse


# ===========================================
# 日志配置
# ===========================================

def setup_logging():
    """配置Loguru日志"""
    # 移除默认处理器
    logger.remove()
    
    # 添加控制台处理器
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="DEBUG" if settings.DEBUG else "INFO",
        colorize=True,
    )
    
    # 添加文件处理器(生产环境)
    if not settings.DEBUG:
        logger.add(
            "logs/app_{time:YYYY-MM-DD}.log",
            rotation="00:00",
            retention="30 days",
            level="INFO",
            encoding="utf-8",
        )


# ===========================================
# 应用生命周期
# ===========================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理
    
    启动时:
    - 配置日志
    - 测试数据库连接
    - 打印路由信息
    
    关闭时:
    - 关闭数据库连接
    """
    # 启动
    setup_logging()
    logger.info(f"🚀 启动 {settings.APP_NAME} v{settings.APP_VERSION}")
    
    # 测试数据库连接
    if await test_connection():
        logger.info("✅ 数据库连接成功")
    else:
        logger.warning("⚠️ 数据库连接失败，请检查配置")
    
    # 开发模式下初始化数据库表(生产环境应使用Alembic)
    if settings.DEBUG:
        try:
            await init_db()
        except Exception as e:
            logger.warning(f"数据库表初始化警告: {e}")
    
    # 打印注册的路由
    logger.info("📋 注册的路由:")
    for route in app.routes:
        if hasattr(route, "methods") and hasattr(route, "path"):
            methods = ", ".join(route.methods)
            logger.info(f"  {methods:10} {route.path}")
    
    yield
    
    # 关闭
    await close_db()
    logger.info("👋 应用已关闭")


# ===========================================
# 创建FastAPI应用
# ===========================================

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
## 情绪管理与智能坐垫干预系统 API

智能坐垫硬件采集用户心率、呼吸等生理数据，通过本系统进行处理和分析。

### 主要功能
- 多租户SaaS架构
- 智能坐垫数据采集与处理
- HRV、压力指数等高级指标计算
- AI大模型生成健康报告

### 商家类型
- 中医馆 (chinese_medicine)
- 酒店 (hotel)
- 养生中心 (wellness_center)
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


# ===========================================
# CORS中间件
# ===========================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===========================================
# 异常处理
# ===========================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    全局异常处理器
    
    捕获所有未处理的异常，返回统一格式的错误响应
    """
    logger.error(f"未处理的异常: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=jsonable_encoder({
            "code": 500,
            "msg": "服务器内部错误" if not settings.DEBUG else str(exc),
            "data": None
        })
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """
    ValueError异常处理器
    
    处理数据验证错误
    """
    logger.warning(f"数据验证错误: {exc}")
    
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=jsonable_encoder({
            "code": 400,
            "msg": str(exc),
            "data": None
        })
    )


# ===========================================
# 健康检查端点
# ===========================================

@app.get("/health", tags=["健康检查"], summary="健康检查")
async def health_check() -> Dict[str, Any]:
    """
    健康检查端点
    
    用于监控系统、负载均衡等场景
    
    Returns:
        健康状态信息
    """
    return {
        "code": 200,
        "msg": "healthy",
        "data": {
            "app_name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "status": "running"
        }
    }


@app.get("/", tags=["根路径"], summary="API信息")
async def root() -> Dict[str, Any]:
    """
    根路径
    
    返回API基本信息和文档链接
    
    Returns:
        API信息
    """
    return {
        "code": 200,
        "msg": "success",
        "data": {
            "app_name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": "/docs",
            "redoc": "/redoc",
            "openapi": "/openapi.json"
        }
    }


# ===========================================
# 注册路由
# ===========================================

app.include_router(api_router, prefix="/api/v1")


# ===========================================
# 开发服务器入口
# ===========================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info",
    )
