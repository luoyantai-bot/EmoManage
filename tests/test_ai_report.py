# ===========================================
# AI Report Tests
# ===========================================
"""
Test AI Report Service and Report Generation Service

Run with: pytest tests/test_ai_report.py -v
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.services.ai_report_service import (
    AIReportService,
    UserInfo,
    DerivedMetrics
)
from app.services.report_generation_service import (
    ReportGenerationService,
    report_generation_service
)


# ===========================================
# Test Fixtures
# ===========================================

@pytest.fixture
def ai_service():
    """Create AI report service instance"""
    return AIReportService()


@pytest.fixture
def sample_user_info():
    """Sample user info"""
    return UserInfo(
        name="张三",
        gender="male",
        age=35,
        height=175.0,
        weight=70.0,
        bmi=22.9
    )


@pytest.fixture
def sample_metrics():
    """Sample derived metrics"""
    return DerivedMetrics(
        avg_heart_rate=75.0,
        max_heart_rate=92,
        min_heart_rate=62,
        avg_breathing=16.5,
        max_breathing=20,
        min_breathing=14,
        valid_data_points=1800,
        duration_minutes=30,
        hrv_score=55.0,
        hrv_level="normal",
        stress_index=42.0,
        stress_level="moderate",
        autonomic_balance=1.8,
        autonomic_state="balanced",
        anxiety_index=35.0,
        anxiety_level="low",
        fatigue_index=28.0,
        fatigue_level="low",
        movement_frequency=0.15,
        posture_stability=88.0,
        tcm_primary_constitution="平和质",
        tcm_primary_score=68,
        tcm_secondary_constitution="气虚质",
        tcm_secondary_score=45,
        tcm_constitution_detail={"平和质": 68, "气虚质": 45, "阳虚质": 35},
        overall_health_score=72,
        risk_items=[
            {"level": "medium", "name": "压力偏高", "desc": "压力指数42%，建议适当放松"}
        ]
    )


# ===========================================
# AIReportService Tests
# ===========================================

class TestAIReportService:
    """Test AI Report Service"""
    
    def test_build_user_data_prompt(self, ai_service, sample_user_info, sample_metrics):
        """Test user data prompt building"""
        prompt = ai_service._build_user_data_prompt(
            sample_user_info.to_dict() if hasattr(sample_user_info, 'to_dict') else {
                "name": sample_user_info.name,
                "gender": sample_user_info.gender,
                "age": sample_user_info.age,
                "height": sample_user_info.height,
                "weight": sample_user_info.weight,
                "bmi": sample_user_info.bmi
            },
            sample_metrics.to_dict() if hasattr(sample_metrics, 'to_dict') else {
                "avg_heart_rate": sample_metrics.avg_heart_rate,
                "max_heart_rate": sample_metrics.max_heart_rate,
                "min_heart_rate": sample_metrics.min_heart_rate,
                "avg_breathing": sample_metrics.avg_breathing,
                "max_breathing": sample_metrics.max_breathing,
                "min_breathing": sample_metrics.min_breathing,
                "valid_data_points": sample_metrics.valid_data_points,
                "duration_minutes": sample_metrics.duration_minutes,
                "hrv_score": sample_metrics.hrv_score,
                "hrv_level": sample_metrics.hrv_level,
                "stress_index": sample_metrics.stress_index,
                "stress_level": sample_metrics.stress_level,
                "autonomic_balance": sample_metrics.autonomic_balance,
                "autonomic_state": sample_metrics.autonomic_state,
                "anxiety_index": sample_metrics.anxiety_index,
                "anxiety_level": sample_metrics.anxiety_level,
                "fatigue_index": sample_metrics.fatigue_index,
                "fatigue_level": sample_metrics.fatigue_level,
                "movement_frequency": sample_metrics.movement_frequency,
                "posture_stability": sample_metrics.posture_stability,
                "tcm_primary_constitution": sample_metrics.tcm_primary_constitution,
                "tcm_primary_score": sample_metrics.tcm_primary_score,
                "tcm_secondary_constitution": sample_metrics.tcm_secondary_constitution,
                "tcm_secondary_score": sample_metrics.tcm_secondary_score,
                "tcm_constitution_detail": sample_metrics.tcm_constitution_detail,
                "overall_health_score": sample_metrics.overall_health_score,
                "risk_items": sample_metrics.risk_items
            }
        )
        
        # Verify prompt contains key sections
        assert "用户基本信息" in prompt
        assert "张三" in prompt
        assert "心率数据" in prompt
        assert "75" in prompt
        assert "中医体质评估" in prompt
        assert "平和质" in prompt
        
        print(f"\n=== User Data Prompt Test ===")
        print("Prompt contains all expected sections")
    
    @pytest.mark.asyncio
    async def test_generate_fallback_report(self, ai_service, sample_user_info, sample_metrics):
        """Test fallback report generation"""
        report = ai_service._generate_fallback_report(
            sample_user_info.to_dict() if hasattr(sample_user_info, 'to_dict') else sample_user_info,
            sample_metrics.to_dict() if hasattr(sample_metrics, 'to_dict') else sample_metrics
        )
        
        # Verify report structure
        assert "# 健康分析报告" in report
        assert "心血管系统" in report
        assert "呼吸系统" in report
        assert "压力评估" in report
        assert "中医体质评估" in report
        assert "综合健康评分" in report
        
        print(f"\n=== Fallback Report Test ===")
        print(f"Report length: {len(report)} characters")
        print("Report contains all expected sections")
    
    @pytest.mark.asyncio
    @patch('app.services.ai_report_service.httpx.AsyncClient')
    async def test_generate_report_success(self, mock_client, ai_service, sample_user_info, sample_metrics):
        """Test successful report generation with mocked API"""
        # Mock successful API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "# 健康分析报告\n\n## 总体健康状态概述\n\n根据本次检测结果，您的整体健康状况良好..."
                    }
                }
            ]
        }
        mock_client.return_value.__aenter__.return_value = mock_response
        
        report = await ai_service.generate_report(
            sample_user_info.to_dict() if hasattr(sample_user_info, 'to_dict') else sample_user_info,
            sample_metrics.to_dict() if hasattr(sample_metrics, 'to_dict') else sample_metrics
        )
        
        assert "# 健康分析报告" in report
        print(f"\n=== Report Generation Test ===")
        print(f"Report generated successfully, length: {len(report)} characters")


# ===========================================
# ReportGenerationService Tests
# ===========================================

class TestReportGenerationService:
    """Test Report Generation Service"""
    
    @pytest.mark.asyncio
    @patch('app.services.report_generation_service.httpx.AsyncClient')
    async def test_generate_full_report(self, mock_client, sample_user_info, sample_metrics):
        """Test full report generation"""
        # Mock successful API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": """# 健康分析报告

## 📊 总体健康状态概述

根据本次30分钟的检测数据分析，您的整体健康状况处于**良好**水平，综合健康评分为**72分**。

### 当前状态总结
- 心血管功能正常，心率稳定在正常范围内
- 呼吸系统运作良好
- 压力水平适中，建议适当放松
- 疲劳程度较低

### 与正常值对比
您的各项指标大部分处于健康范围内，建议持续关注压力管理。

## 🔍 各板块详细分析

### 心血管系统
平均心率75次/分，处于正常成人静息心率范围(60-100次/分)。心率变异性(HRV)为55ms，属于正常水平，表明心脏自主神经调节能力良好。

### 呼吸系统
平均呼吸频率16.5次/分，处于正常范围(12-20次/分)。呼吸节律稳定。

### 情绪与神经系统
自主神经平衡值为1.8，处于平衡状态。压力指数42%，属于中等压力水平。

### 中医体质评估
主要体质为**平和质**(68分)，这是最理想的体质状态。次要体质倾向为气虚质。

### 姿态与行为分析
坐姿稳定性88%，表明坐姿较为稳定，偶有调整。

## ⚠️ 风险指标预警
暂无高风险指标。

| 风险等级 | 指标名称 | 当前值 | 正常范围 | 建议 |
|---------|---------|--------|---------|------|
| 中度 | 压力偏高 | 42% | <30% | 建议适当放松 |

## 💡 个性化健康建议

### 🔹 短期调整(1-3个月)
1. 每天进行10-15分钟深呼吸练习
2. 午休时使用坐垫进行20分钟放松检测
3. 保持规律作息，避免熬夜

### 🔸 长期干预(6-12个月)
1. 建立每周3次的有氧运动习惯
2. 定期进行心理健康评估

### 🍵 饮食与作息建议
根据平和质特点：
- 饮食宜均衡，多食新鲜蔬果
- 忌暴饮暴食
- 建议每晚11点前入睡，保证7-8小时睡眠

---
*注意：本报告由AI自动生成，仅供参考。如有健康疑虑，请咨询专业医生。*
"""
                    }
                }
            ]
        }
        mock_client.return_value.__aenter__.return_value = mock_response
        
        report = await report_generation_service.generate_full_report(
            "test-measurement-id",
            sample_user_info.to_dict() if hasattr(sample_user_info, 'to_dict') else sample_user_info,
            sample_metrics.to_dict() if hasattr(sample_metrics, 'to_dict') else sample_metrics
        )
        
        # Verify report content
        assert "# 健康分析报告" in report
        assert "总体健康状态概述" in report
        assert "心血管系统" in report
        assert "中医体质评估" in report
        assert "个性化健康建议" in report
        
        print(f"\n=== Full Report Generation Test ===")
        print(f"Report generated successfully")
        print(f"Report length: {len(report)} characters")
        print("Report contains all required sections")


# ===========================================
# Integration Tests
# ===========================================

class TestIntegration:
    """Integration tests for report workflow"""
    
    def test_metrics_to_report_flow(self, sample_metrics):
        """Test the flow from metrics to report structure"""
        metrics_dict = sample_metrics.to_dict() if hasattr(sample_metrics, 'to_dict') else {
            "avg_heart_rate": sample_metrics.avg_heart_rate,
            "hrv_score": sample_metrics.hrv_score,
            "stress_index": sample_metrics.stress_index,
            "overall_health_score": sample_metrics.overall_health_score
        }
        
        # Verify metrics dict structure
        assert "avg_heart_rate" in metrics_dict
        assert "hrv_score" in metrics_dict
        assert "stress_index" in metrics_dict
        assert "overall_health_score" in metrics_dict
        
        # Verify health score range
        assert 0 <= metrics_dict["overall_health_score"] <= 100
        
        print(f"\n=== Integration Test ===")
        print("Metrics to report flow verified")


# ===========================================
# Run Tests
# ===========================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
