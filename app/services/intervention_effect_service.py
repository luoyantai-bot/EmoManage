# ===========================================
# Intervention Effect Service
# ===========================================
"""
Intervention Effect Evaluation Service

评估干预措施的效果，对比干预前后的指标变化。
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from loguru import logger
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.intervention_log import InterventionLog
from app.models.measurement import MeasurementRecord
from app.database import get_db_context


class InterventionEffectService:
    """
    干预效果评估服务
    
    功能：
    1. 分析用户干预前后的指标变化
    2. 生成效果对比报告
    3. 提供时间线数据供可视化
    """
    
    # 核心评估指标
    CORE_METRICS = [
        "stress_index",
        "anxiety_index",
        "hrv_score",
        "fatigue_index",
        "overall_health_score"
    ]
    
    async def evaluate_effect(
        self,
        user_id: UUID,
        rule_id: Optional[UUID] = None,
        days: int = 30
    ) -> Dict:
        """
        评估干预效果
        
        流程：
        1. 找到该用户所有的干预记录
        2. 对比干预前后3次检测的平均指标
        3. 计算变化率
        4. 返回对比数据（供前端柱状图使用）
        
        Args:
            user_id: 用户ID
            rule_id: 规则ID（可选，筛选特定规则）
            days: 统计天数
        
        Returns:
            效果评估结果
        """
        async with get_db_context() as db:
            # 查询干预记录
            query = select(InterventionLog).where(
                and_(
                    InterventionLog.user_id == user_id,
                    InterventionLog.status.in_(["triggered", "executed"]),
                    InterventionLog.created_at >= datetime.utcnow() - timedelta(days=days)
                )
            )
            
            if rule_id:
                query = query.where(InterventionLog.rule_id == rule_id)
            
            query = query.order_by(InterventionLog.created_at)
            
            result = await db.execute(query)
            intervention_logs = result.scalars().all()
            
            if not intervention_logs:
                return {
                    "has_data": False,
                    "message": "未找到干预记录",
                    "intervention_count": 0
                }
            
            # 获取所有检测记录
            measurement_result = await db.execute(
                select(MeasurementRecord)
                .where(
                    and_(
                        MeasurementRecord.user_id == user_id,
                        MeasurementRecord.status == "completed",
                        MeasurementRecord.derived_metrics.isnot(None)
                    )
                )
                .order_by(MeasurementRecord.created_at)
            )
            measurements = measurement_result.scalars().all()
            
            if len(measurements) < 2:
                return {
                    "has_data": False,
                    "message": "检测记录不足",
                    "intervention_count": len(intervention_logs)
                }
            
            # 构建时间线
            timeline = self._build_timeline(measurements, intervention_logs)
            
            # 计算干预前后对比
            before_avg, after_avg = self._calculate_before_after_averages(
                measurements, intervention_logs
            )
            
            # 计算变化率
            change_rate = {}
            for metric in self.CORE_METRICS:
                before_val = before_avg.get(metric)
                after_val = after_avg.get(metric)
                
                if before_val is not None and after_val is not None and before_val != 0:
                    change_rate[metric] = round(
                        ((after_val - before_val) / before_val) * 100, 1
                    )
                else:
                    change_rate[metric] = None
            
            # 统计摘要
            improvement_count = sum(
                1 for m, rate in change_rate.items()
                if rate is not None and (
                    m == "overall_health_score" and rate > 0 or
                    m == "hrv_score" and rate > 0 or
                    m in ["stress_index", "anxiety_index", "fatigue_index"] and rate < 0
                )
            )
            
            return {
                "has_data": True,
                "intervention_count": len(intervention_logs),
                "before_avg": before_avg,
                "after_avg": after_avg,
                "change_rate": change_rate,
                "improvement_metrics": improvement_count,
                "total_metrics": len(self.CORE_METRICS),
                "timeline": timeline,
                "summary": self._generate_summary(before_avg, after_avg, change_rate)
            }
    
    def _build_timeline(
        self,
        measurements: List[MeasurementRecord],
        intervention_logs: List[InterventionLog]
    ) -> List[Dict]:
        """
        构建时间线数据
        
        Args:
            measurements: 检测记录列表
            intervention_logs: 干预记录列表
        
        Returns:
            时间线数据
        """
        # 创建干预时间点集合
        intervention_times = set()
        for log in intervention_logs:
            if log.created_at:
                intervention_times.add(log.created_at.date())
        
        timeline = []
        
        for m in measurements:
            entry = {
                "date": m.created_at.strftime("%Y-%m-%d") if m.created_at else None,
                "stress_index": m.derived_metrics.get("stress_index") if m.derived_metrics else None,
                "anxiety_index": m.derived_metrics.get("anxiety_index") if m.derived_metrics else None,
                "hrv_score": m.derived_metrics.get("hrv_score") if m.derived_metrics else None,
                "fatigue_index": m.derived_metrics.get("fatigue_index") if m.derived_metrics else None,
                "overall_health_score": m.derived_metrics.get("overall_health_score") if m.derived_metrics else None,
                "intervention": m.created_at.date() in intervention_times if m.created_at else False
            }
            timeline.append(entry)
        
        return timeline
    
    def _calculate_before_after_averages(
        self,
        measurements: List[MeasurementRecord],
        intervention_logs: List[InterventionLog]
    ) -> Tuple[Dict, Dict]:
        """
        计算干预前后的平均指标
        
        取干预前3次和干预后3次的平均值
        
        Args:
            measurements: 检测记录
            intervention_logs: 干预记录
        
        Returns:
            (干预前平均值, 干预后平均值)
        """
        if not intervention_logs:
            # 无干预记录，取前半和后半对比
            mid = len(measurements) // 2
            before = measurements[:mid]
            after = measurements[mid:]
        else:
            # 取最近一次干预作为分界点
            latest_intervention = max(
                intervention_logs,
                key=lambda x: x.created_at
            )
            intervention_time = latest_intervention.created_at
            
            before = [m for m in measurements if m.created_at < intervention_time][-3:]
            after = [m for m in measurements if m.created_at >= intervention_time][:3]
        
        # 计算平均值
        before_avg = self._average_metrics(before)
        after_avg = self._average_metrics(after)
        
        return before_avg, after_avg
    
    def _average_metrics(
        self,
        measurements: List[MeasurementRecord]
    ) -> Dict:
        """
        计算指标平均值
        
        Args:
            measurements: 检测记录列表
        
        Returns:
            平均指标字典
        """
        if not measurements:
            return {}
        
        sums = {metric: [] for metric in self.CORE_METRICS}
        
        for m in measurements:
            if m.derived_metrics:
                for metric in self.CORE_METRICS:
                    val = m.derived_metrics.get(metric)
                    if val is not None:
                        sums[metric].append(val)
        
        averages = {}
        for metric, values in sums.items():
            if values:
                averages[metric] = round(sum(values) / len(values), 1)
            else:
                averages[metric] = None
        
        return averages
    
    def _generate_summary(
        self,
        before_avg: Dict,
        after_avg: Dict,
        change_rate: Dict
    ) -> str:
        """
        生成效果摘要文本
        
        Args:
            before_avg: 干预前平均
            after_avg: 干预后平均
            change_rate: 变化率
        
        Returns:
            摘要文本
        """
        improvements = []
        concerns = []
        
        # 压力指数下降是改善
        if change_rate.get("stress_index") is not None:
            rate = change_rate["stress_index"]
            if rate < -10:
                improvements.append(f"压力指数下降{abs(rate):.1f}%")
            elif rate > 10:
                concerns.append(f"压力指数上升{rate:.1f}%")
        
        # 焦虑指数下降是改善
        if change_rate.get("anxiety_index") is not None:
            rate = change_rate["anxiety_index"]
            if rate < -10:
                improvements.append(f"焦虑指数下降{abs(rate):.1f}%")
            elif rate > 10:
                concerns.append(f"焦虑指数上升{rate:.1f}%")
        
        # HRV上升是改善
        if change_rate.get("hrv_score") is not None:
            rate = change_rate["hrv_score"]
            if rate > 10:
                improvements.append(f"HRV提升{rate:.1f}%")
            elif rate < -10:
                concerns.append(f"HRV下降{abs(rate):.1f}%")
        
        # 健康评分上升是改善
        if change_rate.get("overall_health_score") is not None:
            rate = change_rate["overall_health_score"]
            if rate > 5:
                improvements.append(f"健康评分提升{rate:.1f}%")
            elif rate < -5:
                concerns.append(f"健康评分下降{abs(rate):.1f}%")
        
        parts = []
        if improvements:
            parts.append("改善方面：" + "、".join(improvements))
        if concerns:
            parts.append("需关注：" + "、".join(concerns))
        
        if not parts:
            return "指标相对稳定，无明显变化趋势"
        
        return "；".join(parts)
    
    async def get_rule_effect_summary(
        self,
        rule_id: UUID,
        tenant_id: UUID,
        days: int = 30
    ) -> Dict:
        """
        获取规则的整体效果摘要
        
        Args:
            rule_id: 规则ID
            tenant_id: 租户ID
            days: 统计天数
        
        Returns:
            规则效果摘要
        """
        async with get_db_context() as db:
            # 统计触发次数
            result = await db.execute(
                select(InterventionLog).where(
                    and_(
                        InterventionLog.rule_id == rule_id,
                        InterventionLog.tenant_id == tenant_id,
                        InterventionLog.created_at >= datetime.utcnow() - timedelta(days=days)
                    )
                )
            )
            logs = result.scalars().all()
            
            if not logs:
                return {
                    "trigger_count": 0,
                    "affected_users": 0,
                    "success_rate": 0
                }
            
            # 统计
            trigger_count = len(logs)
            affected_users = len(set(log.user_id for log in logs if log.user_id))
            success_count = sum(1 for log in logs if log.status == "executed")
            
            return {
                "trigger_count": trigger_count,
                "affected_users": affected_users,
                "success_rate": round(success_count / trigger_count * 100, 1) if trigger_count > 0 else 0,
                "avg_daily_triggers": round(trigger_count / days, 1)
            }


# ===========================================
# 全局实例
# ===========================================

intervention_effect_service = InterventionEffectService()
