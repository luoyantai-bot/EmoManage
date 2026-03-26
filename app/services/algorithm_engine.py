# ===========================================
# Mock Algorithm Engine
# ===========================================
"""
Mock Algorithm Engine - Convert raw sensor data into derived health metrics

This engine calculates advanced health indicators from raw heart rate, 
breathing, and sleep status data collected by the smart cushion.

Main indicators:
- HRV (Heart Rate Variability)
- Stress Index
- Autonomic Balance
- Anxiety Index
- Fatigue Index
- TCM Constitution Analysis
- Overall Health Score
"""

import math
import random
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple


# ===========================================
# Data Classes
# ===========================================

@dataclass
class RawDataPoint:
    """Single raw data point from device"""
    heart_rate: int       # Heart rate (bpm)
    breathing: int        # Breathing rate (breaths/min)
    bed_status: int       # 1=in bed/sitting, 0=left
    sleep_status: int     # 0:left, 1=normal, 2=snoring, 3=turning, 4=apnea
    timestamp: str        # Timestamp string
    signal: Optional[int] = None  # Signal strength
    sos_type: Optional[str] = None  # SOS type if any


@dataclass
class DerivedMetrics:
    """Calculated derived health metrics"""
    # Basic aggregations
    avg_heart_rate: float = 0.0
    max_heart_rate: int = 0
    min_heart_rate: int = 0
    avg_breathing: float = 0.0
    max_breathing: int = 0
    min_breathing: int = 0
    valid_data_points: int = 0
    duration_minutes: int = 0
    
    # HRV indicators
    hrv_score: float = 0.0
    hrv_level: str = "normal"
    
    # Stress indicators
    stress_index: float = 0.0
    stress_level: str = "low"
    
    # Autonomic nervous system
    autonomic_balance: float = 1.5
    autonomic_state: str = "balanced"
    
    # Anxiety indicators
    anxiety_index: float = 0.0
    anxiety_level: str = "low"
    
    # Fatigue indicators
    fatigue_index: float = 0.0
    fatigue_level: str = "low"
    
    # Movement/posture analysis
    movement_frequency: float = 0.0
    posture_stability: float = 100.0
    
    # TCM constitution analysis
    tcm_primary_constitution: str = "平和质"
    tcm_primary_score: int = 50
    tcm_secondary_constitution: str = "气虚质"
    tcm_secondary_score: int = 40
    tcm_constitution_detail: Dict = field(default_factory=dict)
    
    # Overall score
    overall_health_score: int = 75
    risk_items: List[Dict] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to JSON-serializable dictionary"""
        return asdict(self)


# ===========================================
# Algorithm Engine
# ===========================================

class MockAlgorithmEngine:
    """
    Mock Algorithm Engine
    
    Converts raw physiological data into derived health metrics.
    Uses simulated algorithms that produce reasonable outputs based on
    input variations while maintaining medical plausibility.
    
    Note: These are simulated algorithms, not medical-grade calculations.
    """
    
    # TCM Nine Constitutions
    TCM_CONSTITUTIONS = [
        "平和质",   # Normal/Balanced
        "气虚质",   # Qi Deficiency
        "阳虚质",   # Yang Deficiency
        "阴虚质",   # Yin Deficiency
        "痰湿质",   # Phlegm-Dampness
        "湿热质",   # Damp-Heat
        "血瘀质",   # Blood Stasis
        "气郁质",   # Qi Stagnation
        "特禀质",   # Special/Allergic
    ]
    
    # Minimum required data points (5 minutes at 1 point/second)
    MIN_DATA_POINTS = 300
    
    def calculate(self, raw_data: List[RawDataPoint]) -> DerivedMetrics:
        """
        Main entry point: Calculate derived metrics from raw data
        
        Args:
            raw_data: List of raw data points (at least 5 minutes of valid data)
        
        Returns:
            DerivedMetrics with all calculated indicators
        
        Raises:
            ValueError: If insufficient valid data
        """
        # Filter valid data (heart_rate > 0 and bed_status = 1)
        valid_data = [
            d for d in raw_data 
            if d.heart_rate > 0 and d.bed_status == 1
        ]
        
        if len(valid_data) < self.MIN_DATA_POINTS:
            raise ValueError(
                f"Insufficient data: need at least {self.MIN_DATA_POINTS} valid points, "
                f"got {len(valid_data)}"
            )
        
        # Calculate basic statistics
        basic_stats = self._calculate_basic_stats(valid_data)
        
        # Extract heart rates for advanced calculations
        heart_rates = [d.heart_rate for d in valid_data]
        breathings = [d.breathing for d in valid_data if d.breathing > 0]
        
        # Calculate movement metrics
        movement_freq, posture_stability = self._calculate_movement(valid_data)
        
        # Calculate HRV
        hrv_score, hrv_level = self._calculate_hrv(
            heart_rates, basic_stats['avg_heart_rate'], movement_freq
        )
        
        # Calculate stress index
        stress_index, stress_level = self._calculate_stress(
            basic_stats['avg_heart_rate'],
            basic_stats['avg_breathing'],
            movement_freq,
            hrv_score
        )
        
        # Calculate autonomic balance
        autonomic_balance, autonomic_state = self._calculate_autonomic_balance(
            basic_stats['avg_heart_rate'], hrv_score, stress_index
        )
        
        # Calculate anxiety index
        anxiety_index, anxiety_level = self._calculate_anxiety(
            stress_index, hrv_score, movement_freq
        )
        
        # Calculate fatigue index
        fatigue_index, fatigue_level = self._calculate_fatigue(
            basic_stats['avg_heart_rate'],
            basic_stats['avg_breathing'],
            hrv_score,
            basic_stats['duration_minutes']
        )
        
        # Calculate TCM constitution
        tcm_result = self._calculate_tcm_constitution(
            basic_stats['avg_heart_rate'],
            basic_stats['avg_breathing'],
            stress_index,
            autonomic_balance,
            movement_freq,
            hrv_score
        )
        
        # Calculate overall health score
        overall_score = self._calculate_overall_score(
            stress_index, hrv_score, anxiety_index, 
            fatigue_index, posture_stability
        )
        
        # Build metrics object
        metrics = DerivedMetrics(
            # Basic stats
            avg_heart_rate=basic_stats['avg_heart_rate'],
            max_heart_rate=basic_stats['max_heart_rate'],
            min_heart_rate=basic_stats['min_heart_rate'],
            avg_breathing=basic_stats['avg_breathing'],
            max_breathing=basic_stats['max_breathing'],
            min_breathing=basic_stats['min_breathing'],
            valid_data_points=len(valid_data),
            duration_minutes=basic_stats['duration_minutes'],
            
            # Advanced metrics
            hrv_score=round(hrv_score, 1),
            hrv_level=hrv_level,
            stress_index=round(stress_index, 1),
            stress_level=stress_level,
            autonomic_balance=round(autonomic_balance, 2),
            autonomic_state=autonomic_state,
            anxiety_index=round(anxiety_index, 1),
            anxiety_level=anxiety_level,
            fatigue_index=round(fatigue_index, 1),
            fatigue_level=fatigue_level,
            movement_frequency=round(movement_freq, 2),
            posture_stability=round(posture_stability, 1),
            
            # TCM constitution
            tcm_primary_constitution=tcm_result['primary']['name'],
            tcm_primary_score=tcm_result['primary']['score'],
            tcm_secondary_constitution=tcm_result['secondary']['name'],
            tcm_secondary_score=tcm_result['secondary']['score'],
            tcm_constitution_detail=tcm_result['all_scores'],
            
            # Overall
            overall_health_score=overall_score,
            risk_items=[]
        )
        
        # Identify risks
        metrics.risk_items = self._identify_risks(metrics.to_dict())
        
        return metrics
    
    def calculate_from_report(self, report_data: dict) -> DerivedMetrics:
        """
        Calculate derived metrics from manufacturer's aggregated report data
        
        Since we don't have per-second data, we use aggregated values
        with reasonable randomization to simulate derived metrics.
        
        Args:
            report_data: Dictionary with heartAvg, heartMax, heartMin, 
                        breathAvg, breathMax, breathMin, totalTimes, etc.
        
        Returns:
            DerivedMetrics with calculated indicators
        """
        # Extract basic values from report
        avg_hr = float(report_data.get('heartAvg', 72))
        max_hr = int(report_data.get('heartMax', avg_hr + 10))
        min_hr = int(report_data.get('heartMin', avg_hr - 10))
        avg_br = float(report_data.get('breathAvg', 16))
        max_br = int(report_data.get('breathMax', avg_br + 4))
        min_br = int(report_data.get('breathMin', avg_br - 4))
        duration = int(report_data.get('totalTimes', 30))
        
        # Movement data from report
        body_move_num = int(report_data.get('bodyMoveNum', 0))
        snore_num = int(report_data.get('snoreNum', 0))
        apnea_num = int(report_data.get('apneaNum', 0))
        
        # Calculate simulated movement frequency
        movement_freq = (body_move_num + snore_num * 0.3) / max(duration, 1) * 60
        
        # Simulate HRV based on heart rate and randomness
        # Higher heart rate variability suggests lower HRV
        hr_variability = max_hr - min_hr
        base_hrv = 50 + hr_variability * 2
        
        # Add stress-based adjustment
        if avg_hr > 85:
            base_hrv -= 15
        elif avg_hr < 65:
            base_hrv += 10
        
        # Add reasonable random variation
        hrv_score = base_hrv + random.uniform(-8, 8)
        hrv_score = max(20, min(100, hrv_score))
        hrv_level = self._get_hrv_level(hrv_score)
        
        # Calculate stress index
        stress_index, stress_level = self._calculate_stress(
            avg_hr, avg_br, movement_freq, hrv_score
        )
        
        # Calculate autonomic balance
        autonomic_balance, autonomic_state = self._calculate_autonomic_balance(
            avg_hr, hrv_score, stress_index
        )
        
        # Calculate anxiety
        anxiety_index, anxiety_level = self._calculate_anxiety(
            stress_index, hrv_score, movement_freq
        )
        
        # Calculate fatigue
        fatigue_index, fatigue_level = self._calculate_fatigue(
            avg_hr, avg_br, hrv_score, duration
        )
        
        # Adjust fatigue based on apnea events
        if apnea_num > 5:
            fatigue_index = min(100, fatigue_index + apnea_num * 2)
        
        # Calculate posture stability
        posture_stability = 100 - (body_move_num * 2) - (snore_num * 0.5)
        posture_stability = max(30, min(100, posture_stability))
        
        # Calculate TCM constitution
        tcm_result = self._calculate_tcm_constitution(
            avg_hr, avg_br, stress_index, autonomic_balance, 
            movement_freq, hrv_score
        )
        
        # Adjust for apnea tendency
        if apnea_num > 3:
            tcm_result['all_scores']['气虚质'] = min(100, 
                tcm_result['all_scores'].get('气虚质', 40) + apnea_num * 3)
        
        # Calculate overall score
        overall_score = self._calculate_overall_score(
            stress_index, hrv_score, anxiety_index, 
            fatigue_index, posture_stability
        )
        
        # Build metrics
        metrics = DerivedMetrics(
            avg_heart_rate=round(avg_hr, 1),
            max_heart_rate=max_hr,
            min_heart_rate=min_hr,
            avg_breathing=round(avg_br, 1),
            max_breathing=max_br,
            min_breathing=min_br,
            valid_data_points=duration * 60,  # Estimate
            duration_minutes=duration,
            hrv_score=round(hrv_score, 1),
            hrv_level=hrv_level,
            stress_index=round(stress_index, 1),
            stress_level=stress_level,
            autonomic_balance=round(autonomic_balance, 2),
            autonomic_state=autonomic_state,
            anxiety_index=round(anxiety_index, 1),
            anxiety_level=anxiety_level,
            fatigue_index=round(fatigue_index, 1),
            fatigue_level=fatigue_level,
            movement_frequency=round(movement_freq, 2),
            posture_stability=round(posture_stability, 1),
            tcm_primary_constitution=tcm_result['primary']['name'],
            tcm_primary_score=tcm_result['primary']['score'],
            tcm_secondary_constitution=tcm_result['secondary']['name'],
            tcm_secondary_score=tcm_result['secondary']['score'],
            tcm_constitution_detail=tcm_result['all_scores'],
            overall_health_score=overall_score,
            risk_items=[]
        )
        
        metrics.risk_items = self._identify_risks(metrics.to_dict())
        
        return metrics
    
    # ===========================================
    # Private Calculation Methods
    # ===========================================
    
    def _calculate_basic_stats(self, data: List[RawDataPoint]) -> dict:
        """Calculate basic statistics from valid data"""
        heart_rates = [d.heart_rate for d in data]
        breathings = [d.breathing for d in data if d.breathing > 0]
        
        avg_hr = sum(heart_rates) / len(heart_rates) if heart_rates else 0
        max_hr = max(heart_rates) if heart_rates else 0
        min_hr = min(heart_rates) if heart_rates else 0
        
        avg_br = sum(breathings) / len(breathings) if breathings else 0
        max_br = max(breathings) if breathings else 0
        min_br = min(breathings) if breathings else 0
        
        duration_minutes = len(data) // 60  # Assuming 1 point per second
        
        return {
            'avg_heart_rate': avg_hr,
            'max_heart_rate': max_hr,
            'min_heart_rate': min_hr,
            'avg_breathing': avg_br,
            'max_breathing': max_br,
            'min_breathing': min_br,
            'duration_minutes': duration_minutes
        }
    
    def _calculate_hrv(
        self, 
        heart_rates: List[int], 
        avg_hr: float,
        movement_freq: float
    ) -> Tuple[float, str]:
        """
        Calculate simulated HRV (Heart Rate Variability)
        
        HRV represents the variation in time between heartbeats.
        Higher HRV generally indicates better health.
        Normal range: 40-80ms
        
        Logic:
        - Base value: 50ms
        - Heart rate variability contributes to HRV
        - High heart rate + high movement reduces HRV
        - Low heart rate + stability increases HRV
        """
        if len(heart_rates) < 10:
            return 50.0, "normal"
        
        # Calculate standard deviation of heart rates
        hr_variance = sum((hr - avg_hr) ** 2 for hr in heart_rates) / len(heart_rates)
        hr_std = math.sqrt(hr_variance)
        
        # Base HRV from variability (scaled)
        base_hrv = 50 + hr_std * 1.5
        
        # Adjust for average heart rate
        if avg_hr > 85:
            # High heart rate suggests stress, lower HRV
            base_hrv -= 15 + movement_freq * 2
        elif avg_hr < 65:
            # Low heart rate, potentially higher HRV
            base_hrv += 8
        elif 60 <= avg_hr <= 75:
            # Normal range, slight boost
            base_hrv += 5
        
        # Adjust for movement frequency
        if movement_freq > 0.5:
            base_hrv -= movement_freq * 3
        
        # Add reasonable random fluctuation
        random_factor = random.uniform(-5, 5)
        hrv_score = base_hrv + random_factor
        
        # Clamp to reasonable range
        hrv_score = max(15, min(120, hrv_score))
        
        # Determine level
        level = self._get_hrv_level(hrv_score)
        
        return hrv_score, level
    
    def _get_hrv_level(self, hrv: float) -> str:
        """Get HRV level category"""
        if hrv < 40:
            return "low"
        elif hrv > 80:
            return "high"
        else:
            return "normal"
    
    def _calculate_stress(
        self, 
        avg_hr: float, 
        avg_br: float,
        movement_freq: float, 
        hrv: float
    ) -> Tuple[float, str]:
        """
        Calculate stress index
        
        Formula: 
        stress = hr_contribution * 0.3 + br_contribution * 0.2 
               + move_contribution * 0.2 + hrv_contribution * 0.3
        
        Mappings:
        - Heart rate: 60bpm=0%, 100bpm=100%
        - Breathing: 12/min=0%, 24/min=100%
        - Movement: mapped to 0-100%
        - HRV inverse: 80=0%, 20=100%
        """
        # Heart rate contribution (60-100 bpm mapped to 0-100%)
        hr_contribution = max(0, min(100, (avg_hr - 60) / 40 * 100))
        
        # Breathing contribution (12-24 /min mapped to 0-100%)
        br_contribution = max(0, min(100, (avg_br - 12) / 12 * 100))
        
        # Movement contribution
        move_contribution = min(100, movement_freq * 50)
        
        # HRV inverse contribution (high HRV = low stress)
        hrv_contribution = max(0, min(100, (80 - hrv) / 60 * 100))
        
        # Weighted sum
        stress_index = (
            hr_contribution * 0.3 +
            br_contribution * 0.2 +
            move_contribution * 0.2 +
            hrv_contribution * 0.3
        )
        
        # Add small random variation
        stress_index += random.uniform(-3, 3)
        stress_index = max(0, min(100, stress_index))
        
        # Determine level
        if stress_index >= 70:
            level = "extreme"
        elif stress_index >= 50:
            level = "high"
        elif stress_index >= 30:
            level = "moderate"
        else:
            level = "low"
        
        return stress_index, level
    
    def _calculate_autonomic_balance(
        self, 
        avg_hr: float, 
        hrv: float,
        stress: float
    ) -> Tuple[float, str]:
        """
        Calculate autonomic nervous system balance
        
        Scale: 0-5, normal = 1.5
        - >2.5: Sympathetic dominant (stressed, alert)
        - <1.0: Parasympathetic dominant (relaxed, calm)
        - 1.0-2.5: Balanced
        """
        # Base balance
        balance = 1.5
        
        # High heart rate shifts toward sympathetic
        if avg_hr > 80:
            balance += (avg_hr - 80) / 20
        elif avg_hr < 65:
            balance -= (65 - avg_hr) / 15
        
        # High stress shifts toward sympathetic
        if stress > 50:
            balance += (stress - 50) / 50
        elif stress < 20:
            balance -= (20 - stress) / 20
        
        # Low HRV shifts toward sympathetic
        if hrv < 40:
            balance += (40 - hrv) / 30
        
        # Clamp and add small variation
        balance = max(0.3, min(4.5, balance))
        balance += random.uniform(-0.1, 0.1)
        
        # Determine state
        if balance > 2.5:
            state = "sympathetic"
        elif balance < 1.0:
            state = "parasympathetic"
        else:
            state = "balanced"
        
        return balance, state
    
    def _calculate_anxiety(
        self, 
        stress: float, 
        hrv: float,
        movement_freq: float
    ) -> Tuple[float, str]:
        """
        Calculate anxiety index
        
        Based on stress, HRV, and movement patterns
        """
        # Base anxiety from stress
        anxiety = stress * 0.6
        
        # Low HRV increases anxiety
        if hrv < 40:
            anxiety += (40 - hrv) / 2
        
        # High movement frequency increases anxiety
        anxiety += movement_freq * 10
        
        # Add variation
        anxiety += random.uniform(-5, 5)
        anxiety = max(0, min(100, anxiety))
        
        # Determine level
        if anxiety >= 70:
            level = "high"
        elif anxiety >= 40:
            level = "moderate"
        else:
            level = "low"
        
        return anxiety, level
    
    def _calculate_fatigue(
        self, 
        avg_hr: float, 
        avg_br: float,
        hrv: float, 
        duration: int
    ) -> Tuple[float, str]:
        """
        Calculate fatigue index
        
        Low heart rate + shallow breathing + low HRV + long duration
        suggests fatigue
        """
        fatigue = 0.0
        
        # Low heart rate indicates fatigue
        if avg_hr < 65:
            fatigue += (65 - avg_hr) * 1.5
        elif avg_hr > 80:
            fatigue -= 5  # Alert, not fatigued
        
        # Shallow breathing
        if avg_br < 14:
            fatigue += (14 - avg_br) * 3
        
        # Low HRV indicates accumulated fatigue
        if hrv < 40:
            fatigue += (40 - hrv) / 2
        
        # Long duration increases fatigue
        if duration > 30:
            fatigue += (duration - 30) * 0.5
        
        # Add variation
        fatigue += random.uniform(-5, 5)
        fatigue = max(0, min(100, fatigue))
        
        # Determine level
        if fatigue >= 70:
            level = "high"
        elif fatigue >= 40:
            level = "moderate"
        else:
            level = "low"
        
        return fatigue, level
    
    def _calculate_movement(
        self, 
        data: List[RawDataPoint]
    ) -> Tuple[float, float]:
        """
        Calculate movement frequency and posture stability
        
        sleepStatus values:
        - 3: Turning/major movement
        - 2: Snoring (minor movement)
        
        Returns (movement_frequency, posture_stability)
        """
        if not data:
            return 0.0, 100.0
        
        duration_minutes = len(data) / 60
        
        # Count movements
        major_moves = sum(1 for d in data if d.sleep_status == 3)
        minor_moves = sum(1 for d in data if d.sleep_status == 2)
        
        # Movement frequency (per minute)
        movement_freq = (major_moves + minor_moves * 0.3) / max(duration_minutes, 0.1)
        
        # Posture stability (inverse of movement)
        # Start at 100%, decrease with movements
        stability = 100 - (major_moves * 3 + minor_moves * 0.5)
        stability = max(30, min(100, stability + random.uniform(-2, 2)))
        
        return movement_freq, stability
    
    def _calculate_tcm_constitution(
        self, 
        avg_hr: float, 
        avg_br: float,
        stress: float, 
        autonomic: float,
        movement_freq: float, 
        hrv: float
    ) -> dict:
        """
        Calculate TCM (Traditional Chinese Medicine) constitution analysis
        
        Rules:
        1. Shallow fast breathing + high stress + high HR → 阴虚质
        2. Low HR + slow breathing + low stress → 阳虚质  
        3. High movement + unstable → 气郁质
        4. Low HRV + high stress + sympathetic → 血瘀质
        5. Normal HR + normal BR + low stress → 平和质
        6. High HR + fast BR + active → 湿热质
        7. Low HR + slow BR + low HRV → 气虚质
        8. Low movement + stable but high HR → 痰湿质
        9. High variability → 特禀质
        """
        # Initialize scores for all 9 constitutions
        scores = {constitution: 30 for constitution in self.TCM_CONSTITUTIONS}
        
        # Rule 1: 阴虚质 (Yin Deficiency)
        if avg_br > 20 and stress > 60 and avg_hr > 80:
            scores["阴虚质"] += 40
        elif avg_br > 18 or stress > 50:
            scores["阴虚质"] += 20
        
        # Rule 2: 阳虚质 (Yang Deficiency)
        if avg_hr < 65 and avg_br < 14 and stress < 30:
            scores["阳虚质"] += 45
        elif avg_hr < 68 or stress < 35:
            scores["阳虚质"] += 15
        
        # Rule 3: 气郁质 (Qi Stagnation)
        if movement_freq > 0.5 and stress > 40:
            scores["气郁质"] += 35
        elif movement_freq > 0.3:
            scores["气郁质"] += 15
        
        # Rule 4: 血瘀质 (Blood Stasis)
        if hrv < 35 and stress > 50 and autonomic > 2.5:
            scores["血瘀质"] += 40
        elif hrv < 45 or autonomic > 2.0:
            scores["血瘀质"] += 15
        
        # Rule 5: 平和质 (Balanced/Normal)
        if 65 <= avg_hr <= 75 and 14 <= avg_br <= 18 and stress < 30:
            scores["平和质"] += 50
        elif 62 <= avg_hr <= 78 and stress < 40:
            scores["平和质"] += 20
        
        # Rule 6: 湿热质 (Damp-Heat)
        if avg_hr > 78 and avg_br > 18 and movement_freq > 0.3:
            scores["湿热质"] += 35
        elif avg_hr > 75:
            scores["湿热质"] += 15
        
        # Rule 7: 气虚质 (Qi Deficiency)
        if avg_hr < 65 and avg_br < 15 and hrv < 45:
            scores["气虚质"] += 40
        elif avg_hr < 68 and hrv < 50:
            scores["气虚质"] += 15
        
        # Rule 8: 痰湿质 (Phlegm-Dampness)
        if movement_freq < 0.1 and avg_hr > 75 and stress < 50:
            scores["痰湿质"] += 35
        elif movement_freq < 0.2:
            scores["痰湿质"] += 10
        
        # Rule 9: 特禀质 (Special/Allergic)
        # High heart rate variability might indicate sensitivity
        hr_range_bonus = random.randint(0, 15)  # Add some randomness
        scores["特禀质"] += hr_range_bonus
        
        # Add random variation to all scores
        for constitution in scores:
            scores[constitution] = min(100, max(20, 
                scores[constitution] + random.randint(-5, 5)))
        
        # Sort by score
        sorted_constitutions = sorted(
            scores.items(), 
            key=lambda x: x[1], 
            reverse=True
        )
        
        return {
            'primary': {
                'name': sorted_constitutions[0][0],
                'score': sorted_constitutions[0][1]
            },
            'secondary': {
                'name': sorted_constitutions[1][0],
                'score': sorted_constitutions[1][1]
            },
            'all_scores': scores
        }
    
    def _calculate_overall_score(
        self, 
        stress: float, 
        hrv: float,
        anxiety: float, 
        fatigue: float,
        posture_stability: float
    ) -> int:
        """
        Calculate overall health score (0-100)
        
        Formula: 100 - (stress_deduction + hrv_deduction + 
                       anxiety_deduction + fatigue_deduction + posture_deduction)
        
        Weights: stress 30%, HRV 25%, anxiety 20%, fatigue 15%, posture 10%
        """
        # Stress deduction (30% weight)
        stress_deduction = (stress / 100) * 30
        
        # HRV deduction (25% weight) - inverse
        if hrv >= 70:
            hrv_deduction = 0
        elif hrv >= 50:
            hrv_deduction = (70 - hrv) / 20 * 12.5
        else:
            hrv_deduction = 12.5 + (50 - hrv) / 30 * 12.5
        
        # Anxiety deduction (20% weight)
        anxiety_deduction = (anxiety / 100) * 20
        
        # Fatigue deduction (15% weight)
        fatigue_deduction = (fatigue / 100) * 15
        
        # Posture deduction (10% weight) - inverse
        posture_deduction = (100 - posture_stability) / 100 * 10
        
        # Calculate total
        total_deduction = (
            stress_deduction + hrv_deduction + 
            anxiety_deduction + fatigue_deduction + posture_deduction
        )
        
        score = int(100 - total_deduction)
        score = max(20, min(100, score + random.randint(-3, 3)))
        
        return score
    
    def _identify_risks(self, metrics: dict) -> List[dict]:
        """
        Identify health risk items
        
        Returns list of risk items with level, name, and description
        """
        risks = []
        
        # High stress risk
        stress = metrics.get('stress_index', 0)
        if stress >= 80:
            risks.append({
                "level": "high",
                "name": "压力过载",
                "desc": "当前压力水平过高，建议进行放松休息"
            })
        elif stress >= 60:
            risks.append({
                "level": "medium",
                "name": "压力偏高",
                "desc": "压力水平偏高，建议适当放松"
            })
        
        # Low HRV risk
        hrv = metrics.get('hrv_score', 50)
        if hrv < 30:
            risks.append({
                "level": "high",
                "name": "心率变异性异常偏低",
                "desc": "HRV过低可能表示心血管调节能力下降"
            })
        elif hrv < 40:
            risks.append({
                "level": "medium",
                "name": "心率变异性偏低",
                "desc": "HRV偏低，建议增加运动改善心血管功能"
            })
        
        # High anxiety risk
        anxiety = metrics.get('anxiety_index', 0)
        if anxiety >= 70:
            risks.append({
                "level": "medium",
                "name": "焦虑倾向明显",
                "desc": "检测到较高焦虑水平，建议进行心理调适"
            })
        elif anxiety >= 50:
            risks.append({
                "level": "low",
                "name": "轻度焦虑倾向",
                "desc": "存在一定焦虑情绪，注意调节"
            })
        
        # High heart rate risk
        avg_hr = metrics.get('avg_heart_rate', 72)
        if avg_hr >= 90:
            risks.append({
                "level": "medium",
                "name": "静息心率偏高",
                "desc": f"平均心率{avg_hr:.0f}bpm偏高，建议关注心血管健康"
            })
        elif avg_hr >= 85:
            risks.append({
                "level": "low",
                "name": "心率略高",
                "desc": f"平均心率{avg_hr:.0f}bpm略高于正常范围"
            })
        
        # Fast breathing risk
        avg_br = metrics.get('avg_breathing', 16)
        if avg_br >= 22:
            risks.append({
                "level": "low",
                "name": "呼吸频率偏快",
                "desc": f"平均呼吸{avg_br:.0f}次/分，建议练习深呼吸"
            })
        
        # Posture stability risk
        posture = metrics.get('posture_stability', 100)
        if posture < 50:
            risks.append({
                "level": "low",
                "name": "坐姿不稳定",
                "desc": "检测到频繁身体移动，建议调整坐姿"
            })
        
        # High fatigue risk
        fatigue = metrics.get('fatigue_index', 0)
        if fatigue >= 70:
            risks.append({
                "level": "medium",
                "name": "疲劳程度较高",
                "desc": "检测到明显的疲劳状态，建议适当休息"
            })
        
        return risks


# ===========================================
# Convenience Functions
# ===========================================

def create_mock_data(
    duration_minutes: int = 5,
    heart_rate_range: Tuple[int, int] = (68, 72),
    breathing_range: Tuple[int, int] = (15, 17),
    bed_status: int = 1,
    sleep_status_weights: Optional[Dict[int, float]] = None
) -> List[RawDataPoint]:
    """
    Create mock data for testing
    
    Args:
        duration_minutes: Duration in minutes
        heart_rate_range: (min, max) heart rate
        breathing_range: (min, max) breathing rate
        bed_status: Bed status (default 1 = in bed)
        sleep_status_weights: Optional weights for sleep status
    
    Returns:
        List of RawDataPoint objects
    """
    data = []
    total_points = duration_minutes * 60
    
    # Default sleep status weights (normal dominant)
    if sleep_status_weights is None:
        sleep_status_weights = {1: 0.95, 2: 0.02, 3: 0.02, 4: 0.01}
    
    for i in range(total_points):
        # Generate random sleep status based on weights
        rand = random.random()
        cumulative = 0
        sleep_status = 1
        for status, weight in sleep_status_weights.items():
            cumulative += weight
            if rand < cumulative:
                sleep_status = status
                break
        
        point = RawDataPoint(
            heart_rate=random.randint(*heart_rate_range),
            breathing=random.randint(*breathing_range),
            bed_status=bed_status,
            sleep_status=sleep_status,
            timestamp=datetime.utcnow().isoformat()
        )
        data.append(point)
    
    return data
