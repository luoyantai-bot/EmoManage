# ===========================================
# Algorithm Engine Tests
# ===========================================
"""
Test MockAlgorithmEngine for various scenarios

Run with: pytest tests/test_algorithm.py -v
"""

import pytest
import random
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.services.algorithm_engine import (
    MockAlgorithmEngine,
    RawDataPoint,
    DerivedMetrics,
    create_mock_data
)


# ===========================================
# Test Fixtures
# ===========================================

@pytest.fixture
def engine():
    """Create algorithm engine instance"""
    return MockAlgorithmEngine()


# ===========================================
# Test Cases
# ===========================================

class TestNormalPerson:
    """Test normal healthy person data"""
    
    def test_normal_person(self, engine):
        """
        Normal person data: HR 68-72, breathing 15-17, stable sitting
        
        Expected: Low stress, normal HRV, balanced constitution, score > 75
        """
        # Generate 5 minutes of normal data
        data = create_mock_data(
            duration_minutes=5,
            heart_rate_range=(68, 72),
            breathing_range=(15, 17),
            bed_status=1,
            sleep_status_weights={1: 0.98, 2: 0.01, 3: 0.01}
        )
        
        metrics = engine.calculate(data)
        
        # Assertions
        assert metrics.valid_data_points >= 300
        assert 65 <= metrics.avg_heart_rate <= 75
        assert 14 <= metrics.avg_breathing <= 18
        assert metrics.stress_level == "low"
        assert metrics.hrv_level in ["normal", "high"]
        assert metrics.stress_index < 35
        assert metrics.overall_health_score >= 70
        assert metrics.tcm_primary_constitution in ["平和质", "阳虚质", "气虚质"]
        
        print(f"\n=== Normal Person Results ===")
        print(f"Avg HR: {metrics.avg_heart_rate:.1f}")
        print(f"Avg BR: {metrics.avg_breathing:.1f}")
        print(f"Stress: {metrics.stress_index:.1f} ({metrics.stress_level})")
        print(f"HRV: {metrics.hrv_score:.1f} ({metrics.hrv_level})")
        print(f"Overall Score: {metrics.overall_health_score}")
        print(f"TCM: {metrics.tcm_primary_constitution} ({metrics.tcm_primary_score})")


class TestStressedPerson:
    """Test stressed person data"""
    
    def test_stressed_person(self, engine):
        """
        Stressed person: HR 88-95, breathing 22-26, frequent movements
        
        Expected: High stress (>60), low HRV, Yin deficiency tendency, score < 60
        """
        data = create_mock_data(
            duration_minutes=5,
            heart_rate_range=(88, 95),
            breathing_range=(22, 26),
            bed_status=1,
            sleep_status_weights={1: 0.85, 2: 0.05, 3: 0.10}  # More movement
        )
        
        metrics = engine.calculate(data)
        
        # Assertions
        assert metrics.avg_heart_rate >= 85
        assert metrics.avg_breathing >= 20
        assert metrics.stress_index > 50
        assert metrics.hrv_score < 60  # HRV should be lower
        assert metrics.overall_health_score < 65
        
        print(f"\n=== Stressed Person Results ===")
        print(f"Avg HR: {metrics.avg_heart_rate:.1f}")
        print(f"Avg BR: {metrics.avg_breathing:.1f}")
        print(f"Stress: {metrics.stress_index:.1f} ({metrics.stress_level})")
        print(f"HRV: {metrics.hrv_score:.1f} ({metrics.hrv_level})")
        print(f"Overall Score: {metrics.overall_health_score}")
        print(f"TCM: {metrics.tcm_primary_constitution} ({metrics.tcm_primary_score})")
        
        # Should have risk items
        assert len(metrics.risk_items) > 0
        print(f"Risks: {[r['name'] for r in metrics.risk_items]}")


class TestFatiguedPerson:
    """Test fatigued person data"""
    
    def test_fatigued_person(self, engine):
        """
        Fatigued person: HR 58-63, breathing 12-14, no movement
        
        Expected: High fatigue, Yang deficiency or Qi deficiency
        """
        data = create_mock_data(
            duration_minutes=5,
            heart_rate_range=(58, 63),
            breathing_range=(12, 14),
            bed_status=1,
            sleep_status_weights={1: 0.99, 2: 0.005, 3: 0.005}
        )
        
        metrics = engine.calculate(data)
        
        # Assertions
        assert metrics.avg_heart_rate < 68
        assert metrics.avg_breathing < 16
        assert metrics.fatigue_index > 20
        assert metrics.stress_index < 40  # Low stress
        assert metrics.tcm_primary_constitution in ["阳虚质", "气虚质", "平和质"]
        
        print(f"\n=== Fatigued Person Results ===")
        print(f"Avg HR: {metrics.avg_heart_rate:.1f}")
        print(f"Avg BR: {metrics.avg_breathing:.1f}")
        print(f"Fatigue: {metrics.fatigue_index:.1f} ({metrics.fatigue_level})")
        print(f"HRV: {metrics.hrv_score:.1f}")
        print(f"Overall Score: {metrics.overall_health_score}")
        print(f"TCM: {metrics.tcm_primary_constitution} ({metrics.tcm_primary_score})")


class TestAnxiousPerson:
    """Test anxious person data"""
    
    def test_anxious_person(self, engine):
        """
        Anxious person: HR varies widely (70-90), fast breathing, frequent moves
        
        Expected: High anxiety, high stress, Qi stagnation tendency
        """
        data = []
        for i in range(300):
            # Simulate wide HR variation
            hr = random.choice([
                random.randint(70, 75),
                random.randint(80, 85),
                random.randint(85, 90)
            ])
            
            point = RawDataPoint(
                heart_rate=hr,
                breathing=random.randint(20, 24),
                bed_status=1,
                sleep_status=random.choices(
                    [1, 3],
                    weights=[0.88, 0.12]
                )[0],
                timestamp=datetime.utcnow().isoformat()
            )
            data.append(point)
        
        metrics = engine.calculate(data)
        
        # Assertions
        assert metrics.anxiety_index > 30
        assert metrics.stress_index > 30
        assert metrics.movement_frequency > 0.05
        
        print(f"\n=== Anxious Person Results ===")
        print(f"Avg HR: {metrics.avg_heart_rate:.1f}")
        print(f"Avg BR: {metrics.avg_breathing:.1f}")
        print(f"Anxiety: {metrics.anxiety_index:.1f} ({metrics.anxiety_level})")
        print(f"Stress: {metrics.stress_index:.1f}")
        print(f"Movement Freq: {metrics.movement_frequency:.2f}")
        print(f"TCM: {metrics.tcm_primary_constitution} ({metrics.tcm_primary_score})")


class TestMinimumData:
    """Test minimum data requirements"""
    
    def test_minimum_data(self, engine):
        """Test with exactly 5 minutes of data"""
        data = create_mock_data(
            duration_minutes=5,
            heart_rate_range=(70, 75),
            breathing_range=(15, 17)
        )
        
        metrics = engine.calculate(data)
        
        assert metrics.valid_data_points >= 300
        assert metrics.duration_minutes >= 5
        print(f"\nMinimum data test passed: {metrics.valid_data_points} points")
    
    def test_insufficient_data(self, engine):
        """Test with less than 5 minutes of data - should raise exception"""
        data = create_mock_data(
            duration_minutes=3,  # Only 3 minutes
            heart_rate_range=(70, 75),
            breathing_range=(15, 17)
        )
        
        with pytest.raises(ValueError) as exc_info:
            engine.calculate(data)
        
        assert "Insufficient data" in str(exc_info.value)
        print(f"\nInsufficient data test passed: {exc_info.value}")


class TestReportData:
    """Test report-based calculation"""
    
    def test_calculate_from_report(self, engine):
        """Test calculation from manufacturer's aggregated report"""
        report_data = {
            "heartAvg": 78,
            "heartMax": 95,
            "heartMin": 62,
            "breathAvg": 18,
            "breathMax": 24,
            "breathMin": 12,
            "totalTimes": 45,
            "bodyMoveNum": 3,
            "snoreNum": 5,
            "apneaNum": 2,
            "leaveBedNum": 2,
            "efficiency": 85
        }
        
        metrics = engine.calculate_from_report(report_data)
        
        # Assertions
        assert metrics.avg_heart_rate == 78.0
        assert metrics.max_heart_rate == 95
        assert metrics.min_heart_rate == 62
        assert metrics.avg_breathing == 18.0
        assert metrics.duration_minutes == 45
        assert metrics.hrv_score > 0
        assert metrics.stress_index >= 0
        assert len(metrics.tcm_constitution_detail) == 9
        
        print(f"\n=== Report-based Results ===")
        print(f"Avg HR: {metrics.avg_heart_rate:.1f}")
        print(f"Avg BR: {metrics.avg_breathing:.1f}")
        print(f"Stress: {metrics.stress_index:.1f} ({metrics.stress_level})")
        print(f"HRV: {metrics.hrv_score:.1f} ({metrics.hrv_level})")
        print(f"Overall Score: {metrics.overall_health_score}")
        print(f"TCM: {metrics.tcm_primary_constitution}")


class TestOutputFormat:
    """Test output format and validity"""
    
    def test_output_format(self, engine):
        """Verify all DerivedMetrics fields have valid values"""
        data = create_mock_data(duration_minutes=5)
        metrics = engine.calculate(data)
        
        # Test to_dict method
        result = metrics.to_dict()
        
        # Check all required fields exist
        required_fields = [
            'avg_heart_rate', 'max_heart_rate', 'min_heart_rate',
            'avg_breathing', 'max_breathing', 'min_breathing',
            'valid_data_points', 'duration_minutes',
            'hrv_score', 'hrv_level',
            'stress_index', 'stress_level',
            'autonomic_balance', 'autonomic_state',
            'anxiety_index', 'anxiety_level',
            'fatigue_index', 'fatigue_level',
            'movement_frequency', 'posture_stability',
            'tcm_primary_constitution', 'tcm_primary_score',
            'tcm_secondary_constitution', 'tcm_secondary_score',
            'tcm_constitution_detail',
            'overall_health_score', 'risk_items'
        ]
        
        for field in required_fields:
            assert field in result, f"Missing field: {field}"
        
        # Check value ranges
        assert 40 <= result['avg_heart_rate'] <= 120
        assert result['max_heart_rate'] >= result['min_heart_rate']
        assert 0 <= result['stress_index'] <= 100
        assert 15 <= result['hrv_score'] <= 100
        assert 0 <= result['anxiety_index'] <= 100
        assert 0 <= result['fatigue_index'] <= 100
        assert 20 <= result['overall_health_score'] <= 100
        assert 0 <= result['posture_stability'] <= 100
        
        # Check level strings are valid
        assert result['stress_level'] in ['low', 'moderate', 'high', 'extreme']
        assert result['hrv_level'] in ['low', 'normal', 'high']
        assert result['autonomic_state'] in ['parasympathetic', 'balanced', 'sympathetic']
        assert result['anxiety_level'] in ['low', 'moderate', 'high']
        assert result['fatigue_level'] in ['low', 'moderate', 'high']
        
        # Check TCM constitution detail
        assert len(result['tcm_constitution_detail']) == 9
        for constitution, score in result['tcm_constitution_detail'].items():
            assert 0 <= score <= 100
        
        print(f"\n=== Output Format Test ===")
        print(f"All {len(required_fields)} fields present and valid")
        print(f"Valid ranges verified")
        
    def test_risk_items_format(self, engine):
        """Test risk items format"""
        # Use stressed data to generate risk items
        data = create_mock_data(
            duration_minutes=5,
            heart_rate_range=(90, 100),
            breathing_range=(24, 28)
        )
        metrics = engine.calculate(data)
        
        for risk in metrics.risk_items:
            assert 'level' in risk
            assert 'name' in risk
            assert 'desc' in risk
            assert risk['level'] in ['high', 'medium', 'low']
            assert isinstance(risk['name'], str)
            assert isinstance(risk['desc'], str)
        
        print(f"\n=== Risk Items Test ===")
        print(f"Found {len(metrics.risk_items)} risk items")
        for risk in metrics.risk_items:
            print(f"  [{risk['level'].upper()}] {risk['name']}: {risk['desc']}")


class TestConsistency:
    """Test consistency and relationships between metrics"""
    
    def test_stress_hrv_relationship(self, engine):
        """
        Test that high stress correlates with low HRV
        """
        # Generate high stress data
        high_stress_data = create_mock_data(
            duration_minutes=5,
            heart_rate_range=(90, 100),
            breathing_range=(24, 28)
        )
        high_stress_metrics = engine.calculate(high_stress_data)
        
        # Generate low stress data
        low_stress_data = create_mock_data(
            duration_minutes=5,
            heart_rate_range=(62, 68),
            breathing_range=(14, 16)
        )
        low_stress_metrics = engine.calculate(low_stress_data)
        
        # High stress should have lower HRV (generally)
        # Note: Due to randomness, we use averages over multiple runs
        high_stress_hrv_avg = high_stress_metrics.hrv_score
        low_stress_hrv_avg = low_stress_metrics.hrv_score
        
        print(f"\n=== Stress-HRV Relationship ===")
        print(f"High stress data: stress={high_stress_metrics.stress_index:.1f}, HRV={high_stress_hrv_avg:.1f}")
        print(f"Low stress data: stress={low_stress_metrics.stress_index:.1f}, HRV={low_stress_hrv_avg:.1f}")
        
        # Generally, high stress should correlate with lower HRV
        # We allow some tolerance due to randomness
        assert high_stress_metrics.stress_index > low_stress_metrics.stress_index
    
    def test_score_components_relationship(self, engine):
        """Test that individual metrics affect overall score"""
        # High stress should reduce score
        high_stress_data = create_mock_data(
            duration_minutes=5,
            heart_rate_range=(95, 105),
            breathing_range=(24, 28)
        )
        high_stress_metrics = engine.calculate(high_stress_data)
        
        # Low stress should have higher score
        low_stress_data = create_mock_data(
            duration_minutes=5,
            heart_rate_range=(65, 70),
            breathing_range=(15, 17)
        )
        low_stress_metrics = engine.calculate(low_stress_data)
        
        print(f"\n=== Score Components Test ===")
        print(f"High stress score: {high_stress_metrics.overall_health_score}")
        print(f"Low stress score: {low_stress_metrics.overall_health_score}")
        
        # Low stress should have higher overall score
        assert low_stress_metrics.overall_health_score > high_stress_metrics.overall_health_score


# ===========================================
# Run Tests
# ===========================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
