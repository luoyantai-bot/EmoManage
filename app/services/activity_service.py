# ===========================================
# Activity Service
# ===========================================
"""
Activity Management and Smart Push Service

管理活动发布和智能推送，根据用户健康标签匹配目标用户。
"""

import csv
import io
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from loguru import logger
from sqlalchemy import select, and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.activity import Activity
from app.models.activity_push_record import ActivityPushRecord
from app.models.user import User
from app.models.measurement import MeasurementRecord
from app.database import get_db_context


# ===========================================
# 用户标签规则定义
# ===========================================

TAG_RULES = {
    # 压力相关标签
    "high_stress": {
        "label": "高压力",
        "rule": lambda m: m.get("stress_index", 0) > 70,
        "description": "压力指数>70%"
    },
    "extreme_stress": {
        "label": "极高压力",
        "rule": lambda m: m.get("stress_index", 0) > 85,
        "description": "压力指数>85%"
    },
    
    # 焦虑相关标签
    "anxiety": {
        "label": "焦虑倾向",
        "rule": lambda m: m.get("anxiety_index", 0) > 60,
        "description": "焦虑指数>60%"
    },
    "high_anxiety": {
        "label": "高焦虑",
        "rule": lambda m: m.get("anxiety_index", 0) > 80,
        "description": "焦虑指数>80%"
    },
    
    # HRV相关标签
    "low_hrv": {
        "label": "低心率变异性",
        "rule": lambda m: m.get("hrv_score", 100) < 35,
        "description": "HRV<35ms"
    },
    
    # 疲劳相关标签
    "fatigue": {
        "label": "疲劳",
        "rule": lambda m: m.get("fatigue_index", 0) > 60,
        "description": "疲劳指数>60%"
    },
    "high_fatigue": {
        "label": "高疲劳",
        "rule": lambda m: m.get("fatigue_index", 0) > 80,
        "description": "疲劳指数>80%"
    },
    
    # 中医体质标签
    "yin_deficiency": {
        "label": "阴虚质",
        "rule": lambda m: m.get("tcm_primary_constitution") == "阴虚质",
        "description": "主要体质为阴虚质"
    },
    "yang_deficiency": {
        "label": "阳虚质",
        "rule": lambda m: m.get("tcm_primary_constitution") == "阳虚质",
        "description": "主要体质为阳虚质"
    },
    "qi_deficiency": {
        "label": "气虚质",
        "rule": lambda m: m.get("tcm_primary_constitution") == "气虚质",
        "description": "主要体质为气虚质"
    },
    "qi_stagnation": {
        "label": "气郁质",
        "rule": lambda m: m.get("tcm_primary_constitution") == "气郁质",
        "description": "主要体质为气郁质"
    },
    "blood_stasis": {
        "label": "血瘀质",
        "rule": lambda m: m.get("tcm_primary_constitution") == "血瘀质",
        "description": "主要体质为血瘀质"
    },
    "phlegm_dampness": {
        "label": "痰湿质",
        "rule": lambda m: m.get("tcm_primary_constitution") == "痰湿质",
        "description": "主要体质为痰湿质"
    },
    "damp_heat": {
        "label": "湿热质",
        "rule": lambda m: m.get("tcm_primary_constitution") == "湿热质",
        "description": "主要体质为湿热质"
    },
    "balanced": {
        "label": "平和质",
        "rule": lambda m: m.get("tcm_primary_constitution") == "平和质",
        "description": "主要体质为平和质"
    },
    
    # 姿态相关标签
    "poor_posture": {
        "label": "姿态不佳",
        "rule": lambda m: m.get("posture_stability", 100) < 50,
        "description": "坐姿稳定性<50%"
    },
    
    # 自主神经相关标签
    "sympathetic_dominant": {
        "label": "交感神经主导",
        "rule": lambda m: m.get("autonomic_balance", 1.5) > 2.5,
        "description": "自主神经平衡>2.5，表示紧张状态"
    },
    "parasympathetic_dominant": {
        "label": "副交感神经主导",
        "rule": lambda m: m.get("autonomic_balance", 1.5) < 1.0,
        "description": "自主神经平衡<1.0，表示过度放松"
    },
    
    # 综合评估标签
    "health_attention": {
        "label": "健康需关注",
        "rule": lambda m: m.get("overall_health_score", 100) < 60,
        "description": "综合健康评分<60分"
    },
    "health_warning": {
        "label": "健康预警",
        "rule": lambda m: m.get("overall_health_score", 100) < 40,
        "description": "综合健康评分<40分"
    },
}

# 所有可用标签（供前端选择）
AVAILABLE_TAGS = [
    {"key": k, "label": v["label"], "description": v["description"]}
    for k, v in TAG_RULES.items()
]


class ActivityService:
    """
    活动管理与智能推送服务
    
    功能：
    1. 根据用户健康数据自动计算标签
    2. 为活动匹配合适的目标用户
    3. 批量创建推送记录
    4. 导出推送列表
    """
    
    async def get_user_tags(self, user_id: UUID, db: AsyncSession) -> List[str]:
        """
        根据用户最近一次检测数据，计算用户标签
        
        Args:
            user_id: 用户ID
            db: 数据库会话
        
        Returns:
            用户标签列表
        """
        # 获取用户最近一次检测记录
        result = await db.execute(
            select(MeasurementRecord)
            .where(MeasurementRecord.user_id == user_id)
            .where(MeasurementRecord.status == "completed")
            .where(MeasurementRecord.derived_metrics.isnot(None))
            .order_by(desc(MeasurementRecord.created_at))
            .limit(1)
        )
        record = result.scalar_one_or_none()
        
        if not record or not record.derived_metrics:
            return []
        
        # 计算标签
        tags = []
        metrics = record.derived_metrics
        
        for tag_key, tag_info in TAG_RULES.items():
            try:
                if tag_info["rule"](metrics):
                    tags.append(tag_key)
            except Exception as e:
                logger.warning(f"Error evaluating tag {tag_key}: {e}")
                continue
        
        return tags
    
    async def get_user_metrics(self, user_id: UUID, db: AsyncSession) -> Optional[dict]:
        """
        获取用户最近的健康指标
        
        Args:
            user_id: 用户ID
            db: 数据库会话
        
        Returns:
            指标字典或None
        """
        result = await db.execute(
            select(MeasurementRecord)
            .where(MeasurementRecord.user_id == user_id)
            .where(MeasurementRecord.status == "completed")
            .where(MeasurementRecord.derived_metrics.isnot(None))
            .order_by(desc(MeasurementRecord.created_at))
            .limit(1)
        )
        record = result.scalar_one_or_none()
        
        return record.derived_metrics if record else None
    
    async def match_users_for_activity(
        self,
        activity_id: UUID,
        db: AsyncSession
    ) -> List[Dict]:
        """
        为指定活动匹配目标用户
        
        流程：
        1. 读取活动的 target_tags
        2. 查询该商家下所有用户的最近一次检测的 derived_metrics
        3. 对每个用户计算标签，与活动标签取交集
        4. 返回匹配的用户列表，包含匹配原因
        
        Args:
            activity_id: 活动ID
            db: 数据库会话
        
        Returns:
            匹配用户列表 [{"user": User, "matched_tags": [], "match_reason": str}]
        """
        # 获取活动信息
        result = await db.execute(
            select(Activity).where(Activity.id == activity_id)
        )
        activity = result.scalar_one_or_none()
        
        if not activity:
            raise ValueError(f"Activity not found: {activity_id}")
        
        target_tags = activity.target_tags or []
        
        if not target_tags:
            return []
        
        # 获取该商家下所有有检测记录的用户
        result = await db.execute(
            select(User)
            .options(selectinload(User.tenant))
            .where(User.tenant_id == activity.tenant_id)
        )
        users = result.scalars().all()
        
        matched_users = []
        
        for user in users:
            # 获取用户最近指标
            metrics = await self.get_user_metrics(user.id, db)
            
            if not metrics:
                continue
            
            # 计算用户标签
            user_tags = []
            for tag_key in target_tags:
                tag_info = TAG_RULES.get(tag_key)
                if tag_info:
                    try:
                        if tag_info["rule"](metrics):
                            user_tags.append(tag_key)
                    except Exception:
                        continue
            
            # 如果有匹配的标签
            if user_tags:
                # 生成匹配原因
                tag_labels = [
                    TAG_RULES.get(t, {}).get("label", t)
                    for t in user_tags
                ]
                match_reason = f"用户匹配标签：{', '.join(tag_labels)}"
                
                matched_users.append({
                    "user": {
                        "id": str(user.id),
                        "name": user.name,
                        "gender": user.gender,
                        "age": user.age,
                        "phone": user.phone
                    },
                    "matched_tags": user_tags,
                    "match_reason": match_reason,
                    "metrics_summary": {
                        "stress_index": metrics.get("stress_index"),
                        "anxiety_index": metrics.get("anxiety_index"),
                        "health_score": metrics.get("overall_health_score"),
                        "tcm_constitution": metrics.get("tcm_primary_constitution")
                    }
                })
        
        return matched_users
    
    async def create_push_records(
        self,
        activity_id: UUID,
        db: AsyncSession
    ) -> List[ActivityPushRecord]:
        """
        批量创建推送记录
        
        Args:
            activity_id: 活动ID
            db: 数据库会话
        
        Returns:
            创建的推送记录列表
        """
        # 匹配用户
        matched_users = await self.match_users_for_activity(activity_id, db)
        
        if not matched_users:
            return []
        
        records = []
        
        for match in matched_users:
            record = ActivityPushRecord(
                activity_id=activity_id,
                user_id=UUID(match["user"]["id"]),
                push_reason=match["match_reason"],
                matched_tags=match["matched_tags"],
                push_status="pending"
            )
            db.add(record)
            records.append(record)
        
        await db.commit()
        
        logger.info(f"Created {len(records)} push records for activity {activity_id}")
        
        return records
    
    async def export_push_list(
        self,
        activity_id: UUID,
        db: AsyncSession
    ) -> bytes:
        """
        导出推送列表为CSV文件
        
        Args:
            activity_id: 活动ID
            db: 数据库会话
        
        Returns:
            CSV文件字节数据
        """
        # 获取推送记录
        result = await db.execute(
            select(ActivityPushRecord)
            .options(
                selectinload(ActivityPushRecord.user),
                selectinload(ActivityPushRecord.activity)
            )
            .where(ActivityPushRecord.activity_id == activity_id)
            .order_by(ActivityPushRecord.created_at)
        )
        records = result.scalars().all()
        
        # 创建CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # 写入表头
        writer.writerow([
            "序号",
            "用户姓名",
            "性别",
            "年龄",
            "电话",
            "匹配标签",
            "推送原因",
            "推送状态",
            "创建时间"
        ])
        
        # 写入数据
        for i, record in enumerate(records, 1):
            user = record.user
            tag_labels = [
                TAG_RULES.get(t, {}).get("label", t)
                for t in (record.matched_tags or [])
            ]
            
            writer.writerow([
                i,
                user.name if user else "",
                "男" if user and user.gender == "male" else "女" if user and user.gender == "female" else "其他",
                user.age if user else "",
                user.phone if user else "",
                ", ".join(tag_labels),
                record.push_reason,
                {"pending": "待推送", "sent": "已发送", "read": "已阅读"}.get(record.push_status, record.push_status),
                record.created_at.strftime("%Y-%m-%d %H:%M:%S") if record.created_at else ""
            ])
        
        return output.getvalue().encode("utf-8-sig")  # BOM for Excel compatibility
    
    async def get_push_records(
        self,
        activity_id: UUID,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None
    ) -> Tuple[List[ActivityPushRecord], int]:
        """
        获取活动的推送记录（分页）
        
        Args:
            activity_id: 活动ID
            db: 数据库会话
            page: 页码
            page_size: 每页数量
            status: 状态过滤
        
        Returns:
            (记录列表, 总数)
        """
        query = select(ActivityPushRecord).where(
            ActivityPushRecord.activity_id == activity_id
        )
        
        if status:
            query = query.where(ActivityPushRecord.push_status == status)
        
        # 计数
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        # 分页
        query = query.order_by(desc(ActivityPushRecord.created_at))
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await db.execute(query)
        records = result.scalars().all()
        
        return list(records), total
    
    @staticmethod
    def get_available_tags() -> List[Dict]:
        """获取所有可用标签（供前端选择）"""
        return AVAILABLE_TAGS


# ===========================================
# 全局实例
# ===========================================

activity_service = ActivityService()
