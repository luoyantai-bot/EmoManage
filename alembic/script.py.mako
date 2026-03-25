# ===========================================
# Alembic 迁移脚本模板
# ===========================================
"""
迁移脚本模板

使用方法:
    alembic revision -m "描述信息"  # 创建空迁移文件
    alembic revision --autogenerate -m "描述信息"  # 自动生成迁移
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    """
    升级迁移
    
    定义数据库结构变更
    """
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """
    降级迁移
    
    回滚 upgrade() 中的变更
    """
    ${downgrades if downgrades else "pass"}
