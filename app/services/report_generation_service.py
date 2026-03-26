# ===========================================
# Report Generation Service
# ===========================================
"""
Report Generation Service - Orchestrates the complete report generation workflow

Integrates:
- AIReportService for AI-powered health analysis
- MockAlgorithmEngine for derived metrics calculation
- Database for data persistence

Workflow:
1. Webhook receives report → trigger report generation
2. User ends measurement -> trigger report generation
3. Manual regeneration via API endpoint
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db_context
from app.models.measurement import MeasurementRecord
from app.models.user import User
from app.models.device import Device
from app.services.ai_report_service import AIReportService, UserInfo, DerivedMetrics


from app.services.algorithm_engine import MockAlgorithmEngine


class ReportGenerationService:
    """
    Complete report generation workflow orchestestrator
    
    This service coordinates:
    1. Data retrieval from database
    2. Derived metrics calculation (if not already present)
    3. AI report generation via AIReportService
    4. Database updates
    5. Optional: Intervention rules check
    """
    
    def __init__(self):
        """Initialize service"""
        self.ai_report_service = AIReportService()
        self.algorithm_engine = MockAlgorithmEngine()
    
    async def generate_full_report(
        self, 
        measurement_id: UUID,
        db: AsyncSession
    ) -> MeasurementRecord:
        """
        Complete report generation workflow
        
        Args:
            measurement_id: UUID of the db: Database session (optional, for testing)
        
        Returns:
            Updated MeasurementRecord with AI analysis
        
        Raises:
            ValueError: If measurement record not found
        """
        # Get measurement record with related data
        result = await db.execute(
            select(MeasurementRecord)
            .options(
                selectinload(MeasurementRecord.user),
                selectinload(MeasurementRecord.device)
            )
            .where(MeasurementRecord.id == measurement_id)
        )
        record = result.scalar_one_or_none()
        
        if not record:
            logger.error(f"Measurement record not found: {measurement_id}")
            raise ValueError(f"Measurement record not found: {measurement_id}")
        
        # Get user info
        user_info = {}
        if record.user:
            user_info = {
                "name": record.user.name or "未知用户",
                "gender": record.user.gender or "unknown",
                "age": record.user.age or 0,
                "height": record.user.height or 0,
                "weight": record.user.weight or 0,
                "bmi": record.user.bmi
            }
        
        # Check if derived metrics exist
        if record.derived_metrics:
            # Use existing derived metrics
            metrics_dict = record.derived_metrics
            metrics = self._dict_to_metrics(metrics_dict)
        elif record.raw_data_summary:
            # Calculate derived metrics from raw data
            logger.info(f"Calculating derived metrics for measurement {measurement_id}")
            raw_report_data = record.raw_data_summary
            
            # Extract heart rate data
            heart_rate_data = raw_report_data.get('heart_rate', {})
            avg_hr = float(heart_rate_data.get('avg', 72))
            max_hr = int(heart_rate_data.get('max', 80))
            min_hr = int(heart_rate_data.get('min', 65))
            
            # Extract breathing data
            breathing_data = raw_report_data.get('breathing', {})
            avg_br = float(breathing_data.get('avg', 16)) if breathing_data else 16
            max_br = int(breathing_data.get('max', 20)) if breathing_data else 20
            min_br = int(breathing_data.get('min', 14)) if breathing_data else 14
            
            # Get duration
            duration = raw_report_data.get('total_times', 30)
            if isinstance(duration, str):
                duration = int(duration)
            
            # Get sleep quality data
            sleep_quality = raw_report_data.get('sleep_quality', {})
            score = sleep_quality.get('score', 75)
            body_move = int(sleep_quality.get('body_move_num', 0))
            snore_num = int(sleep_quality.get('snore_num', 0))
            apnea_num = int(sleep_quality.get('apnea_num', 0))
            
            # Use algorithm engine to calculate derived metrics
            try:
                algo_metrics = self.algorithm_engine.calculate_from_report({
                    'heartAvg': avg_hr,
                    'heartMax': max_hr,
                    'heartMin': min_hr,
                    'breathAvg': avg_br,
                    'breathMax': max_br,
                    'breathMin': min_br,
                    'totalTimes': duration,
                    'bodyMoveNum': body_move,
                    'snoreNum': snore_num,
                    'apneaNum': apnea_num,
                })
                
                metrics = algo_metrics.to_dict()
                record.derived_metrics = metrics
                
                # Update health score
                record.health_score = metrics.get('overall_health_score', 75)
                
                logger.info(f"Calculated derived metrics for measurement {measurement_id}: "
                           f"score={record.health_score}")
                
            except Exception as e:
                logger.error(f"Failed to calculate derived metrics: {e}")
                # Continue with empty metrics
        
        else:
            # Use existing derived metrics
            metrics = record.derived_metrics
        
        # Generate AI report
        try:
            ai_analysis = await self.ai_report_service.generate_report(user_info, metrics)
            
            record.ai_analysis = ai_analysis
            record.status = "completed"
            
            logger.info(f"Generated AI report for measurement {measurement_id}")
            
        except Exception as e:
            logger.error(f"Failed to generate AI report: {e}")
            record.status = "error"
            record.error_message = str(e)
        
        # Save changes
        await db.commit()
        await db.refresh(record)
        
        return record
    
    async def regenerate_ai_analysis(
        self, 
        measurement_id: UUID,
        db: AsyncSession = None
    ) -> MeasurementRecord:
        """
        Regenerate AI analysis for a measurement record
        
        This allows users to refresh their reports when they feel
        the initial analysis was not accurate or sufficient.
        
        Args:
            measurement_id: UUID
            db: Database session (optional, for testing)
        
        Returns:
            Updated MeasurementRecord with new AI analysis
        
        Raises:
            ValueError: If measurement record not found
        """
        async with get_db_context() as db:
            result = await db.execute(
                select(MeasurementRecord)
                .options(
                    selectinload(MeasurementRecord.user),
                    selectinload(MeasurementRecord.device)
                )
                .where(MeasurementRecord.id == measurement_id)
            )
            record = result.scalar_one_or_none()
            
            if not record:
                raise ValueError(f"Measurement record not found: {measurement_id}")
            
            if not record.derived_metrics:
                raise ValueError("No derived metrics available for AI analysis")
            
            # Get user info
            user_info = {}
            if record.user:
                user_info = {
                    "name": record.user.name or "未知用户",
                    "gender": record.user.gender or "unknown",
                    "age": record.user.age or 0,
                    "height": record.user.height or 0,
                    "weight": record.user.weight or 0,
                    "bmi": record.user.bmi
                }
            
            # Generate new AI report
            ai_analysis = await self.ai_report_service.generate_report(user_info, record.derived_metrics)
            
            record.ai_analysis = ai_analysis
            record.status = "completed"
            record.updated_at = datetime.utcnow()
            
            await db.commit()
            await db.refresh(record)
            
            logger.info(f"Regenerated AI analysis for measurement {measurement_id}")
            
            return record
    
    def _dict_to_metrics(self, metrics_dict: dict) -> DerivedMetrics:
        """Convert dictionary to DerivedMetrics dataclass"""
        return DerivedMetrics(
            avg_heart_rate=metrics_dict.get('avg_heart_rate', 0.0),
            max_heart_rate=metrics_dict.get('max_heart_rate', 0),
            min_heart_rate=metrics_dict.get('min_heart_rate', 0),
            avg_breathing=metrics_dict.get('avg_breathing', 0.0),
            max_breathing=metrics_dict.get('max_breathing', 0),
            min_breathing=metrics_dict.get('min_breathing', 0),
            valid_data_points=metrics_dict.get('valid_data_points', 0),
            duration_minutes=metrics_dict.get('duration_minutes', 0),
            hrv_score=metrics_dict.get('hrv_score', 50.0),
            hrv_level=metrics_dict.get('hrv_level', 'normal'),
            stress_index=metrics_dict.get('stress_index', 30.0),
            stress_level=metrics_dict.get('stress_level', 'low'),
            autonomic_balance=metrics_dict.get('autonomic_balance', 1.5),
            autonomic_state=metrics_dict.get('autonomic_state', 'balanced'),
            anxiety_index=metrics_dict.get('anxiety_index', 25.0),
            anxiety_level=metrics_dict.get('anxiety_level', 'low'),
            fatigue_index=metrics_dict.get('fatigue_index', 20.0),
            fatigue_level=metrics_dict.get('fatigue_level', 'low'),
            movement_frequency=metrics_dict.get('movement_frequency', 0.1),
            posture_stability=metrics_dict.get('posture_stability', 90.0),
            tcm_primary_constitution=metrics_dict.get('tcm_primary_constitution', '平和质'),
            tcm_primary_score=metrics_dict.get('tcm_primary_score', 60),
            tcm_secondary_constitution=metrics_dict.get('tcm_secondary_constitution', '气虚质'),
            tcm_secondary_score=metrics_dict.get('tcm_secondary_score', 45),
            tcm_constitution_detail=metrics_dict.get('tcm_constitution_detail', {}),
            overall_health_score=metrics_dict.get('overall_health_score', 75),
            risk_items=metrics_dict.get('risk_items', [])
        )


# ===========================================
# Global Service Instance
# ===========================================

report_generation_service = ReportGenerationService()
