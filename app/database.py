# ===========================================
# 数据库连接配置
# ===========================================
"""
异步数据库连接和会话管理

使用 SQLAlchemy 2.0 异步模式
- AsyncEngine: 异步数据库引擎
- AsyncSession: 异步会话
- async_sessionmaker: 异步会话工厂
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.config import settings
from app.models import Base


# ===========================================
# 数据库引擎配置
# ===========================================

def create_engine() -> AsyncEngine:
    """
    创建异步数据库引擎
    
    配置说明:
    - echo: 是否打印SQL语句(开发环境建议开启)
    - pool_pre_ping: 每次连接前检查连接是否有效
    - pool_size: 连接池大小(异步模式下建议使用NullPool)
    
    Returns:
        AsyncEngine实例
    """
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        # 异步模式下使用NullPool，每次请求创建新连接
        # 这样可以避免连接池的一些问题，特别是在Serverless环境下
        poolclass=NullPool,
    )
    
    logger.info(f"数据库引擎创建成功: {settings.DATABASE_URL.split('@')[-1]}")
    return engine


# 全局引擎实例
engine: AsyncEngine = create_engine()

# 会话工厂
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ===========================================
# 依赖注入
# ===========================================

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话(FastAPI依赖注入)
    
    使用示例:
        @router.get("/")
        async def list_items(db: AsyncSession = Depends(get_db)):
            ...
    
    Yields:
        AsyncSession实例
    """
    async with async_session_factory() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"数据库会话错误: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()


# ===========================================
# 上下文管理器
# ===========================================

@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """
    数据库会话上下文管理器
    
    在非FastAPI环境中使用，如后台任务、定时任务等
    
    使用示例:
        async with get_db_context() as db:
            result = await db.execute(select(User))
            users = result.scalars().all()
    
    Yields:
        AsyncSession实例
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            logger.error(f"数据库会话错误: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()


# ===========================================
# 数据库初始化
# ===========================================

async def init_db():
    """
    初始化数据库
    
    创建所有表结构(仅用于开发测试，生产环境使用Alembic迁移)
    """
    async with engine.begin() as conn:
        # 创建所有表
        await conn.run_sync(Base.metadata.create_all)
        logger.info("数据库表结构初始化完成")


async def close_db():
    """
    关闭数据库连接
    
    应用关闭时调用
    """
    await engine.dispose()
    logger.info("数据库连接已关闭")


# ===========================================
# 测试连接
# ===========================================

async def test_connection() -> bool:
    """
    测试数据库连接
    
    Returns:
        连接是否成功
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("数据库连接测试成功")
        return True
    except Exception as e:
        logger.error(f"数据库连接测试失败: {e}")
        return False
