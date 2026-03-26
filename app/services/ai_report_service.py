# ===========================================
# AI Report Service - SiliconFlow API Integration
# ===========================================
"""
AI Report Service - Generate personalized health analysis reports using AI

Integrates with SiliconFlow API (Qwen model) to generate comprehensive
health reports based on physiological metrics collected from smart cushion.

Features:
- Personalized health analysis
- TCM constitution interpretation
- Risk assessment
- Actionable recommendations
- Fallback report generation when AI unavailable
"""

import asyncio
import json
import httpx
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass

from loguru import logger

from app.config import settings


# ===========================================
# Data Classes
# ===========================================

@dataclass
class UserInfo:
    """User information for report generation"""
    name: str = "未知"
    gender: str = "未知"  # "male" or "female"
    age: int = 0
    height: float = 0.0  # cm
    weight: float = 0.0  # kg
    bmi: float = 0.0


@dataclass
class DerivedMetrics:
    """Derived health metrics from algorithm engine"""
    avg_heart_rate: float = 72.0
    max_heart_rate: int = 80
    min_heart_rate: int = 65
    avg_breathing: float = 16.0
    max_breathing: int = 20
    min_breathing: int = 14
    valid_data_points: int = 0
    duration_minutes: int = 0
    
    hrv_score: float = 50.0
    hrv_level: str = "normal"
    
    stress_index: float = 30.0
    stress_level: str = "low"
    
    autonomic_balance: float = 1.5
    autonomic_state: str = "balanced"
    
    anxiety_index: float = 25.0
    anxiety_level: str = "low"
    
    fatigue_index: float = 20.0
    fatigue_level: str = "low"
    
    movement_frequency: float = 0.1
    posture_stability: float = 90.0
    
    tcm_primary_constitution: str = "平和质"
    tcm_primary_score: int = 60
    tcm_secondary_constitution: str = "气虚质"
    tcm_secondary_score: int = 45
    tcm_constitution_detail: Dict = None
    
    overall_health_score: int = 75
    risk_items: List[Dict] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'avg_heart_rate': self.avg_heart_rate,
            'max_heart_rate': self.max_heart_rate,
            'min_heart_rate': self.min_heart_rate,
            'avg_breathing': self.avg_breathing,
            'max_breathing': self.max_breathing,
            'min_breathing': self.min_breathing,
            'valid_data_points': self.valid_data_points,
            'duration_minutes': self.duration_minutes,
            'hrv_score': self.hrv_score,
            'hrv_level': self.hrv_level,
            'stress_index': self.stress_index,
            'stress_level': self.stress_level,
            'autonomic_balance': self.autonomic_balance,
            'autonomic_state': self.autonomic_state,
            'anxiety_index': self.anxiety_index,
            'anxiety_level': self.anxiety_level,
            'fatigue_index': self.fatigue_index,
            'fatigue_level': self.fatigue_level,
            'movement_frequency': self.movement_frequency,
            'posture_stability': self.posture_stability,
            'tcm_primary_constitution': self.tcm_primary_constitution,
            'tcm_primary_score': self.tcm_primary_score,
            'tcm_secondary_constitution': self.tcm_secondary_constitution,
            'tcm_secondary_score': self.tcm_secondary_score,
            'tcm_constitution_detail': self.tcm_constitution_detail or {},
            'overall_health_score': self.overall_health_score,
            'risk_items': self.risk_items or []
        }


# ===========================================
# AI Report Service
# ===========================================

class AIReportService:
    """
    SiliconFlow AI API Integration for Health Report Generation
    
    Uses Qwen model to generate personalized health analysis reports
    based on physiological metrics from smart cushion.
    """
    
    # SiliconFlow API configuration
    API_URL = "https://api.siliconflow.cn/v1/chat/completions"
    
    # Default model
    DEFAULT_MODEL = "Qwen/Qwen2.5-72B-Instruct"
    
    # System prompt for health report generation
    SYSTEM_PROMPT = """你是一位融合了中医体质学与现代心理生理学的主治医师。
请根据以下智能坐垫采集到的用户生理指标JSON，生成一份严谨、有同理心的健康综合分析与建议。

必须严格按照以下四个模块结构返回（使用Markdown格式）：

### 📊 总体健康状态概述
[用2-3段话分析用户整体情况，包括综合评分解读、当前状态总结，与正常值的对比]

### 🔍 各板块详细分析

#### 心血管系统
[结合心率数据和HRV分析心脏自主调节能力，说明当前心率是否正常、HRV水平意味着什么]

#### 呼吸系统
[分析呼吸频率和节律，是否有呼吸过快/过慢的情况]

#### 情绪与神经系统
[结合自主神经平衡值分析情绪状态、压力指数和焦虑指数的含义，是交感神经还是副交感神经主导]

#### 中医体质评估
[解读主要体质类型的特征和成因，次要体质的影响，给出体质调理方向]

#### 姿态与行为分析
[分析坐姿稳定性和动作频率，是否有坐立不安、抖腿等行为]

### ⚠️ 风险指标预警
[按重度/中度/轻度分别列出风险项，每项说明指标值、正常范围、潜在影响]

用表格形式展示：
| 风险等级 | 指标名称 | 当前值 | 正常范围 | 建议 |
|---------|---------|--------|---------|------|

### 💡 个性化健康建议

#### 🔹 短期调整（1-3个月）
[列出3-5条具体可执行的建议，包括呼吸练习、运动方式、作息调整等]

#### 🔸 长期干预（6-12个月）
[列出2-3条长期健康管理建议]

#### 🍵 饮食与作息建议
[根据中医体质给出具体的饮食推荐和禁忌、作息时间建议]

请确保：
1. 语气温和专业，有同理心
2. 每个建议都要具体可执行，不要泛泛而谈
3. 中医建议要与现代医学建议相结合
4. 如果有严重异常指标，要建议用户及时就医"""
    
    def __init__(self):
        """Initialize AI Report Service"""
        self.api_key = settings.SILICONFLOW_API_KEY
        self.model = settings.SILICONFLOW_MODEL or self.DEFAULT_MODEL
        self.timeout = 30.0  # 30 seconds timeout
        self.max_retries = 2
        
        if not self.api_key:
            logger.warning("SILICONFLOW_API_KEY not configured, AI reports will use fallback mode")
    
    async def generate_report(
        self,
        user_info: Dict,
        derived_metrics: Dict
    ) -> str:
        """
        Generate health report using SiliconFlow AI
        
        Args:
            user_info: {"name": "张三", "gender": "male", "age": 35, "height": 175, "weight": 70, "bmi": 22.9}
            derived_metrics: DerivedMetrics.to_dict() 的输出
            
        Returns:
            Markdown format report text
        """
        # Check if API key is configured
        if not self.api_key:
            logger.warning("AI API key not configured, Using fallback report")
            return self._generate_fallback_report(user_info, derived_metrics)
        
        try:
            # Build user data prompt
            user_data_prompt = self._build_user_data_prompt(user_info, derived_metrics)
            
            # Construct messages
            messages = [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_data_prompt}
            ]
            
            # Call SiliconFlow API
            response = await self._call_siliconflow_api(messages)
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to generate AI report: {e}")
            return self._generate_fallback_report(user_info, derived_metrics)
    
    async def _call_siliconflow_api(self, messages: List[Dict]) -> str:
        """
        Call SiliconFlow API
        
        Args:
            messages: Chat messages array
            
        Returns:
            AI generated content
            
        Raises:
            httpx.HTTPError: API call failed
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 4000,
            "top_p": 0.9
 # Focus on health report
        }
        
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        self.API_URL,
                        headers=headers,
                        json=payload
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                        
                        if content:
                            logger.info("AI report generated successfully")
                            return content
                        else:
                            raise ValueError("Empty response from AI API")
                    else:
                        error_detail = response.text
                        logger.error(f"AI API error: {response.status_code} - {error_detail}")
                        
                        if response.status_code == 429:
                            # Rate limit - wait longer
                            await asyncio.sleep(2 ** attempt)
                            continue
                        
                        raise httpx.HTTPStatusError(
                            f"AI API returned {response.status_code}: {error_detail}"
                        )
                        
            except httpx.TimeoutException:
                last_error = "API timeout"
                logger.warning(f"AI API timeout (attempt {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1)
                    continue
                raise
                
            except httpx.HTTPError as e:
                last_error = str(e)
                logger.warning(f"AI API HTTP error (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1)
                    continue
                raise
        
        # All retries exhausted
        raise httpx.HTTPError(f"AI API failed after {self.max_retries} retries: {last_error}")
    
    def _generate_fallback_report(
        self,
        user_info: Dict,
        metrics: Dict
    ) -> str:
        """
        Generate fallback report when AI API is unavailable
        Uses pre-defined templates based on metric levels
        """
        name = user_info.get('name', '用户')
        gender = '男' if user_info.get('gender') == 'male' else '女'
        age = user_info.get('age', 0)
        bmi = user_info.get('bmi', 0)
        
        # Get metrics
        avg_hr = metrics.get('avg_heart_rate', 72)
        hrv_score = metrics.get('hrv_score', 50)
        stress_index = metrics.get('stress_index', 30)
        anxiety_index = metrics.get('anxiety_index', 25)
        fatigue_index = metrics.get('fatigue_index', 20)
        health_score = metrics.get('overall_health_score', 75)
        tcm_primary = metrics.get('tcm_primary_constitution', '平和质')
        
        # Determine status
        if health_score >= 80:
            status = "良好"
        elif health_score >= 60:
            status = "一般"
        else:
            status = "需关注"
        
        # Build fallback report
        report = f"""### 📊 总体健康状态概述

{name}您好！根据智能坐垫的检测数据，您的综合健康评分为 **{health_score}分**，满分100分），整体状态：**{status}**。

本次检测时长约 {metrics.get('duration_minutes', 0)} 分钟，采集了有效数据点 {metrics.get('valid_data_points', 0)} 个。

### 🔍 各板块详细分析

#### 心血管系统
- 平均心率：{avg_hr:.0} 次/分（正常范围：60-100）
- 心率变异性(HRV)：{hrv_score:.1}ms（{'偏低' if hrv_score < 40 else '正常' if hrv_score < 80 else '良好'}）

#### 情绪与神经系统
- 压力指数：{stress_index:.0f}%（{'较低' if stress_index < 30 else '中等' if stress_index < 60 else '较高'}）
- 焦虑指数：{anxiety_index:.0f}%（{'较低' if anxiety_index < 30 else '中等' if anxiety_index < 60 else '较高'}）
- 疲劳指数：{fatigue_index:.0f}%（{'较低' if fatigue_index < 30 else '中等' if fatigue_index < 60 else '较高'}）

#### 中医体质评估
- 主要体质：{tcm_primary}
- 根据体质特征，建议进行针对性的调理

### 💡 个性化健康建议

1. 保持规律作息，保证充足睡眠
2. 适量运动，每天进行30分钟中等强度运动
3. 均衡饮食，注意营养搭配
4. 如有持续不适，请及时就医

---
*本报告由系统自动生成，仅供参考。如有健康疑虑，请咨询专业医生。*
"""
        return report
    
    def _build_user_data_prompt(
        self,
        user_info: Dict,
        metrics: Dict
    ) -> str:
        """
        Build user data part of the prompt sent to AI
        Format as readable JSON + key metric explanations
        """
        # User basic info
        name = user_info.get('name', '未知')
        gender_text = '男' if user_info.get('gender') == 'male' else '女'
        age = user_info.get('age', 0)
        bmi = user_info.get('bmi', 0)
        
        # Duration info
        duration = metrics.get('duration_minutes', 0)
        
        # Heart rate data
        avg_hr = metrics.get('avg_heart_rate', 72)
        max_hr = metrics.get('max_heart_rate', 80)
        min_hr = metrics.get('min_heart_rate', 65)
        
        # Breathing data
        avg_br = metrics.get('avg_breathing', 16)
        max_br = metrics.get('max_breathing', 20)
        min_br = metrics.get('min_breathing', 14)
        
        # Advanced metrics
        hrv_score = metrics.get('hrv_score', 50)
        hrv_level = metrics.get('hrv_level', 'normal')
        stress_index = metrics.get('stress_index', 30)
        stress_level = metrics.get('stress_level', 'low')
        autonomic_balance = metrics.get('autonomic_balance', 1.5)
        autonomic_state = metrics.get('autonomic_state', 'balanced')
        anxiety_index = metrics.get('anxiety_index', 25)
        anxiety_level = metrics.get('anxiety_level', 'low')
        fatigue_index = metrics.get('fatigue_index', 20)
        fatigue_level = metrics.get('fatigue_level', 'low')
        posture_stability = metrics.get('posture_stability', 90)
        movement_freq = metrics.get('movement_frequency', 0.1)
        
        # TCM constitution
        tcm_primary = metrics.get('tcm_primary_constitution', '平和质')
        tcm_primary_score = metrics.get('tcm_primary_score', 60)
        tcm_secondary = metrics.get('tcm_secondary_constitution', '气虚质')
        tcm_secondary_score = metrics.get('tcm_secondary_score', 45)
        
        # Overall score
        overall_score = metrics.get('overall_health_score', 75)
        
        # Risk items
        risk_items = metrics.get('risk_items', [])
        risk_json = json.dumps(risk_items, ensure_ascii=False, indent=2) if risk_items else "[]"
        
        prompt = f"""
用户基本信息：
- 姓名：{name}
- 性别：{gender_text}
- 年龄：{age}岁
- BMI：{bmi}

检测数据（智能坐垫 {duration} 分钟检测）：

心率数据：
- 平均心率：{avg_hr} 次/分
- 最高心率：{max_hr} 次/分
- 最低心率：{min_hr} 次/分

呼吸数据：
- 平均呼吸：{avg_br} 次/分

高级指标：
- HRV心率变异性：{hrv_score}ms（{hrv_level}）
- 压力敏感度：{stress_index}%（{stress_level}）
- 自主神经平衡：{autonomic_balance}（{autonomic_state}）
- 焦虑指数：{anxiety_index}%（{anxiety_level}）
- 疲劳指数：{fatigue_index}%（{fatigue_level}）
- 坐姿稳定性：{posture_stability}%

中医体质评估：
- 主要体质：{tcm_primary}（{tcm_primary_score}分）
- 次要体质：{tcm_secondary}（{tcm_secondary_score}分）

综合健康评分：{overall_score}/100

风险项：
{risk_json}
"""
        return prompt


# ===========================================
# Global Service Instance
# ===========================================

ai_report_service = AIReportService()
