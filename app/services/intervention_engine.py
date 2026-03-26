# ===========================================
# Intervention Engine Service
# ===========================================
"""
Intervention Rule Engine - 自动触发干预动作

根据用户健康指标自动触发预设的干预动作。
支持多条件组合、优先级排序、动作执行日志记录。
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
from uuid import UUID
import json

from loguru import logger
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.intervention_rule import InterventionRule
from app.models.intervention_log import InterventionLog
from app.models.measurement import MeasurementRecord
from app.database import get_db_context


# ===========================================
# 可用指标定义
# ===========================================

AVAILABLE_METRICS = [
    {"key": "stress_index", "label": "压力敏感度", "unit": "%", "range": "0-100", 
     "description": "压力敏感度越高表示用户当前压力越大"},
    {"key": "anxiety_index", "label": "焦虑指数", "unit": "", "range": "0-100",
     "description": "焦虑指数越高表示用户当前焦虑程度越高"},
    {"key": "hrv_score", "label": "HRV心率变异性", "unit": "ms", "range": "0-100",
     "description": "HRV越高表示心脏自主神经调节能力越好"},
    {"key": "autonomic_balance", "label": "自主神经平衡", "unit": "", "range": "0-5",
     "description": "平衡值越低表示副交感主导(放松)，越高表示交感主导(紧张)"},
    {"key": "fatigue_index", "label": "疲劳指数", "unit": "", "range": "0-100",
     "description": "疲劳指数越高表示用户当前疲劳程度越高"},
    {"key": "overall_health_score", "label": "综合健康评分", "unit": "分", "range": "0-100",
     "description": "综合各项指标计算的健康评分"},
    {"key": "avg_heart_rate", "label": "平均心率", "unit": "bpm", "range": "40-200",
     "description": "检测期间的平均心率"},
    {"key": "posture_stability", "label": "坐姿稳定性", "unit": "%", "range": "0-100",
     "description": "坐姿稳定性越高表示用户坐姿越稳定"},
]


# ===========================================
# 可用动作定义
# ===========================================

AVAILABLE_ACTIONS = [
    {
        "device_type": "aroma", 
        "label": "香薰机", 
        "actions": ["start", "stop"],
        "params": [
            {"key": "scent", "type": "select", "options": ["lavender", "peppermint", "eucalyptus", "chamomile"],
             "label": "香味"},
            {"key": "intensity", "type": "number", "min": 0, "max": 100, "label": "浓度"}
        ]
    },
    {
        "device_type": "light", 
        "label": "智能灯光", 
        "actions": ["dim", "brighten", "color_change", "off"],
        "params": [
            {"key": "brightness", "type": "number", "min": 0, "max": 100, "label": "亮度"},
            {"key": "color", "type": "select", "options": ["warm", "cool", "blue", "green"], "label": "颜色"}
        ]
    },
    {
        "device_type": "speaker", 
        "label": "音箱", 
        "actions": ["play", "stop"],
        "params": [
            {"key": "playlist", "type": "select", 
             "options": ["meditation", "nature", "white_noise", "classical"], "label": "播放列表"},
            {"key": "volume", "type": "number", "min": 0, "max": 100, "label": "音量"}
        ]
    },
    {
        "device_type": "humidifier", 
        "label": "加湿器", 
        "actions": ["start", "stop"],
        "params": [
            {"key": "humidity", "type": "number", "min": 30, "max": 80, "label": "目标湿度%"}
        ]
    },
]


# ===========================================
# 干预规则引擎
# ===========================================

class InterventionEngine:
    """
    干预规则引擎
    
    根据用户指标自动触发干预动作。支持：
    - 多条件组合（AND/OR逻辑）
    - 规则优先级排序
    - 动作执行日志记录
    - Webhook通知（预留接口）
    """
    
    def __init__(self):
        self.metrics = {m["key"]: m for m in AVAILABLE_METRICS}
    
    async def evaluate(
        self,
        measurement_id: UUID,
        tenant_id: UUID,
        derived_metrics: dict,
        device_code: str,
        user_id: Optional[UUID] = None
    ) -> List[InterventionLog]:
        """
        评估所有活跃规则，对匹配的规则执行干预动作
        
        流程：
        1. 查询该商家的所有 is_active=True 的规则，按 priority 排序
        2. 对每条规则，检查 condition_config 中的条件是否满足
        3. 满足的规则，生成 InterventionLog 记录
        4. 如果配置了 Webhook URL，调用 Webhook 通知（第一期仅记录日志）
        5. 返回所有触发的日志列表
        
        Args:
            measurement_id: 检测记录ID
            tenant_id: 租户ID
            derived_metrics: 衍生指标字典
            device_code: 设备编码
            user_id: 用户ID（可选）
        
        Returns:
            触发的干预日志列表
        """
        triggered_logs = []
        
        async with get_db_context() as db:
            # 查询活跃规则
            result = await db.execute(
                select(InterventionRule)
                .where(
                    and_(
                        InterventionRule.tenant_id == tenant_id,
                        InterventionRule.is_active == True
                    )
                )
                .order_by(InterventionRule.priority.asc())
            )
            rules = result.scalars().all()
            
            if not rules:
                logger.debug(f"No active intervention rules for tenant {tenant_id}")
                return []
            
            logger.info(f"Found {len(rules)} active rules to evaluate")
            
            for rule in rules:
                try:
                    # 评估条件
                    if self._evaluate_conditions(rule.condition_config, derived_metrics):
                        logger.info(f"Rule '{rule.name}' matched! Creating intervention log")
                        
                        # 创建日志记录
                        log = InterventionLog(
                            rule_id=rule.id,
                            measurement_id=measurement_id,
                            user_id=user_id,
                            tenant_id=tenant_id,
                            device_code=device_code,
                            trigger_metrics=derived_metrics,
                            actions_executed=rule.action_config.get("actions", []),
                            status="triggered"
                        )
                        
                        # 尝试执行动作（目前仅记录日志）
                        try:
                            await self._execute_actions(rule.action_config, log)
                            log.status = "executed"
                        except Exception as e:
                            log.status = "failed"
                            log.error_message = str(e)
                            logger.error(f"Failed to execute actions for rule {rule.id}: {e}")
                        
                        db.add(log)
                        triggered_logs.append(log)
                        
                except Exception as e:
                    logger.error(f"Error evaluating rule {rule.id}: {e}")
                    continue
            
            if triggered_logs:
                await db.commit()
                logger.info(f"Triggered {len(triggered_logs)} intervention rules")
        
        return triggered_logs
    
    def _evaluate_conditions(
        self,
        conditions_config: dict,
        metrics: dict
    ) -> bool:
        """
        评估条件是否满足
        
        支持 AND/OR 逻辑
        支持运算符: >, <, >=, <=, ==, !=
        
        Args:
            conditions_config: 条件配置
                {
                    "logic": "AND",  // "AND" 或 "OR"
                    "conditions": [
                        {"metric": "stress_index", "operator": ">", "value": 80}
                    ]
                }
            metrics: 用户指标字典
        
        Returns:
            条件是否满足
        """
        logic = conditions_config.get("logic", "AND").upper()
        conditions = conditions_config.get("conditions", [])
        
        if not conditions:
            return False
        
        results = []
        for condition in conditions:
            metric_key = condition.get("metric")
            operator = condition.get("operator")
            value = condition.get("value")
            
            if not metric_key or not operator or value is None:
                logger.warning(f"Invalid condition format: {condition}")
                continue
            
            result = self._evaluate_single_condition(metric_key, operator, value, metrics)
            results.append(result)
        
        if not results:
            return False
        
        if logic == "AND":
            return all(results)
        else:  # OR
            return any(results)
    
    def _evaluate_single_condition(
        self,
        metric_key: str,
        operator: str,
        value: float,
        metrics: dict
    ) -> bool:
        """
        评估单个条件
        
        Args:
            metric_key: 指标键名
            operator: 运算符 (>, <, >=, <=, ==, !=)
            value: 目标值
            metrics: 用户指标字典
        
        Returns:
            条件是否满足
        """
        actual_value = metrics.get(metric_key)
        
        if actual_value is None:
            logger.debug(f"Metric '{metric_key}' not found in metrics")
            return False
        
        try:
            actual_value = float(actual_value)
            value = float(value)
        except (TypeError, ValueError) as e:
            logger.warning(f"Failed to convert values to float: {e}")
            return False
        
        # 执行比较
        if operator == ">":
            return actual_value > value
        elif operator == "<":
            return actual_value < value
        elif operator == ">=":
            return actual_value >= value
        elif operator == "<=":
            return actual_value <= value
        elif operator == "==":
            return actual_value == value
        elif operator == "!=":
            return actual_value != value
        else:
            logger.warning(f"Unknown operator: {operator}")
            return False
    
    async def _execute_actions(
        self,
        action_config: dict,
        log: InterventionLog
    ) -> None:
        """
        执行干预动作
        
        第一期实现：仅记录日志，不实际调用硬件
        预留 Webhook 接口供后续扩展
        
        Args:
            action_config: 动作配置
            log: 日志记录
        """
        actions = action_config.get("actions", [])
        webhook_url = action_config.get("webhook_url")
        
        if webhook_url:
            # TODO: 实现Webhook调用
            logger.info(f"Webhook URL configured: {webhook_url}")
            log.webhook_response = {
                "webhook_url": webhook_url,
                "status": "pending",
                "message": "Webhook call not implemented yet"
            }
        
        logger.info(f"Actions configured: {json.dumps(actions, ensure_ascii=False)}")
    
    async def test_rule(
        self,
        condition_config: dict,
        test_metrics: dict
    ) -> dict:
        """
        测试规则条件（用于前端预览）
        
        Args:
            condition_config: 条件配置
            test_metrics: 测试指标
        
        Returns:
            测试结果，包含匹配状态和详细信息
        """
        result = self._evaluate_conditions(condition_config, test_metrics)
        
        # 生成详细评估信息
        conditions = condition_config.get("conditions", [])
        details = []
        
        for condition in conditions:
            metric_key = condition.get("metric")
            operator = condition.get("operator")
            value = condition.get("value")
            actual = test_metrics.get(metric_key)
            
            metric_info = self.metrics.get(metric_key, {})
            
            details.append({
                "metric": metric_key,
                "metric_label": metric_info.get("label", metric_key),
                "operator": operator,
                "target_value": value,
                "actual_value": actual,
                "matched": self._evaluate_single_condition(
                    metric_key, operator or ">", value or 0, test_metrics
                ) if actual is not None else False
            })
        
        return {
            "matched": result,
            "logic": condition_config.get("logic", "AND"),
            "details": details
        }
    
    def get_available_metrics(self) -> List[dict]:
        """返回可用指标列表（供前端下拉选择）"""
        return AVAILABLE_METRICS
    
    def get_available_actions(self) -> List[dict]:
        """返回可用动作列表（供前端下拉选择）"""
        return AVAILABLE_ACTIONS


# ===========================================
# 全局实例
# ===========================================

intervention_engine = InterventionEngine()
