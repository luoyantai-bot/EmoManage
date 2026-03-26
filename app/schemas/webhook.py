# ===========================================
# Webhook Data Schemas
# ===========================================
"""
Webhook data validation models

Contains:
- RealtimeDataWebhook: Real-time data push from manufacturer
- ReportDataWebhook: Sleep report push from manufacturer
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ===========================================
# Real-time Data Webhook Schema
# ===========================================

class RealtimeDataWebhook(BaseModel):
    """
    Real-time data webhook payload
    
    Received from manufacturer when device pushes real-time data
    """
    mqtt_id: Optional[str] = Field(
        default=None,
        alias="mqttId",
        description="MQTT message ID"
    )
    device_code: str = Field(
        ...,
        alias="deviceCode",
        description="Device code (SN number)"
    )
    heart_rate: Optional[str] = Field(
        default=None,
        alias="heartRate",
        description="Heart rate (bpm)"
    )
    breathing: Optional[str] = Field(
        default=None,
        description="Breathing rate (breaths/min)"
    )
    signal: Optional[str] = Field(
        default=None,
        description="Signal strength"
    )
    sos_type: Optional[str] = Field(
        default=None,
        alias="sosType",
        description="SOS type: 5=SOS, 6=unplugged, 7=cut, 8=wet, 9=life abnormal"
    )
    bed_status: Optional[str] = Field(
        default=None,
        alias="bedStatus",
        description="Bed status: 1=in bed, 0=out of bed"
    )
    sleep_status: Optional[str] = Field(
        default=None,
        alias="sleepStatus",
        description="Sleep status: 0=off pillow, 1=normal, 2=snoring, 3=turning, 4=apnea"
    )
    create_time: Optional[str] = Field(
        default=None,
        alias="createTime",
        description="Manufacturer timestamp string"
    )
    timestamp: Optional[str] = Field(
        default=None,
        description="Unix timestamp"
    )
    sign: Optional[str] = Field(
        default=None,
        description="MD5 signature"
    )

    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "example": {
                "mqttId": None,
                "deviceCode": "TA0096400014",
                "heartRate": "78",
                "breathing": "30",
                "signal": "44",
                "sosType": "5",
                "bedStatus": "1",
                "sleepStatus": "1",
                "createTime": "2025-05-17 17:00:32",
                "timestamp": "1750759933",
                "sign": "f2d689b19f9339a25425f9e4316701ea"
            }
        }
    }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Redis storage"""
        return {
            "device_code": self.device_code,
            "heart_rate": self.heart_rate,
            "breathing": self.breathing,
            "signal": self.signal,
            "sos_type": self.sos_type,
            "bed_status": self.bed_status,
            "sleep_status": self.sleep_status,
            "create_time": self.create_time,
            "timestamp": self.timestamp,
            "received_at": datetime.utcnow().isoformat()
        }

    def get_heart_rate_int(self) -> Optional[int]:
        """Get heart rate as integer"""
        try:
            return int(self.heart_rate) if self.heart_rate else None
        except ValueError:
            return None

    def get_breathing_int(self) -> Optional[int]:
        """Get breathing rate as integer"""
        try:
            return int(self.breathing) if self.breathing else None
        except ValueError:
            return None

    def is_alert(self) -> bool:
        """Check if this data contains an alert"""
        return self.sos_type in ["5", "6", "7", "8", "9"]


# ===========================================
# Sleep Report Webhook Schema
# ===========================================

class ReportCycleData(BaseModel):
    """Sleep cycle data"""
    start_time: Optional[str] = Field(default=None, alias="startTime")
    end_time: Optional[str] = Field(default=None, alias="endTime")
    sleep_type: Optional[str] = Field(default=None, alias="sleepType")

    model_config = {"populate_by_name": True}


class ReportLeaveBedData(BaseModel):
    """Leave bed event data"""
    start_time: Optional[str] = Field(default=None, alias="startTime")
    end_time: Optional[str] = Field(default=None, alias="endTime")
    duration: Optional[str] = Field(default=None)

    model_config = {"populate_by_name": True}


class ReportDataWebhook(BaseModel):
    """
    Sleep report webhook payload
    
    Received from manufacturer when a sleep report is generated
    Contains comprehensive sleep analysis data
    """
    # Basic info
    report_id: Optional[str] = Field(
        default=None,
        alias="reportId",
        description="Report ID from manufacturer"
    )
    device_code: str = Field(
        ...,
        alias="deviceCode",
        description="Device code (SN number)"
    )
    
    # Time info
    start_time: Optional[str] = Field(
        default=None,
        alias="startTime",
        description="Sleep start time"
    )
    end_time: Optional[str] = Field(
        default=None,
        alias="endTime",
        description="Sleep end time"
    )
    total_times: Optional[str] = Field(
        default=None,
        description="Total sleep duration (minutes)"
    )
    
    # Heart rate statistics
    heart_avg: Optional[str] = Field(
        default=None,
        alias="heartAvg",
        description="Average heart rate"
    )
    heart_max: Optional[str] = Field(
        default=None,
        alias="heartMax",
        description="Maximum heart rate"
    )
    heart_min: Optional[str] = Field(
        default=None,
        alias="heartMin",
        description="Minimum heart rate"
    )
    
    # Breathing statistics
    breath_avg: Optional[str] = Field(
        default=None,
        alias="breathAvg",
        description="Average breathing rate"
    )
    breath_max: Optional[str] = Field(
        default=None,
        alias="breathMax",
        description="Maximum breathing rate"
    )
    breath_min: Optional[str] = Field(
        default=None,
        alias="breathMin",
        description="Minimum breathing rate"
    )
    
    # Sleep quality
    score: Optional[str] = Field(
        default=None,
        description="Sleep quality score (0-100)"
    )
    leave_bed_num: Optional[str] = Field(
        default=None,
        alias="leaveBedNum",
        description="Number of times leaving bed"
    )
    body_move_num: Optional[str] = Field(
        default=None,
        alias="bodyMoveNum",
        description="Number of body movements"
    )
    snore_num: Optional[str] = Field(
        default=None,
        alias="snoreNum",
        description="Number of snoring events"
    )
    apnea_num: Optional[str] = Field(
        default=None,
        alias="apneaNum",
        description="Number of apnea events"
    )
    
    # Detailed data
    cycle_data: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        alias="cycleData",
        description="Sleep cycle data"
    )
    leave_bed_data: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        alias="leaveBedData",
        description="Leave bed event data"
    )
    
    # Additional fields
    deep_sleep_time: Optional[str] = Field(
        default=None,
        alias="deepSleepTime",
        description="Deep sleep duration"
    )
    light_sleep_time: Optional[str] = Field(
        default=None,
        alias="lightSleepTime",
        description="Light sleep duration"
    )
    rem_sleep_time: Optional[str] = Field(
        default=None,
        alias="remSleepTime",
        description="REM sleep duration"
    )
    awake_time: Optional[str] = Field(
        default=None,
        alias="awakeTime",
        description="Awake duration"
    )
    
    # Signature
    timestamp: Optional[str] = Field(
        default=None,
        description="Unix timestamp"
    )
    sign: Optional[str] = Field(
        default=None,
        description="MD5 signature"
    )

    model_config = {
        "populate_by_name": True,
        "extra": "allow",  # Allow extra fields from manufacturer
    }

    def to_raw_data_summary(self) -> Dict[str, Any]:
        """Convert to raw_data_summary format for MeasurementRecord"""
        return {
            "report_id": self.report_id,
            "device_code": self.device_code,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "total_times": self.total_times,
            "heart_rate": {
                "avg": self.heart_avg,
                "max": self.heart_max,
                "min": self.heart_min,
            },
            "breathing": {
                "avg": self.breath_avg,
                "max": self.breath_max,
                "min": self.breath_min,
            },
            "sleep_quality": {
                "score": self.score,
                "leave_bed_num": self.leave_bed_num,
                "body_move_num": self.body_move_num,
                "snore_num": self.snore_num,
                "apnea_num": self.apnea_num,
            },
            "sleep_stages": {
                "deep_sleep_time": self.deep_sleep_time,
                "light_sleep_time": self.light_sleep_time,
                "rem_sleep_time": self.rem_sleep_time,
                "awake_time": self.awake_time,
            },
            "cycle_data": self.cycle_data,
            "leave_bed_data": self.leave_bed_data,
            "received_at": datetime.utcnow().isoformat(),
        }

    def get_total_times_int(self) -> Optional[int]:
        """Get total times as integer"""
        try:
            return int(self.total_times) if self.total_times else None
        except ValueError:
            return None

    def get_score_int(self) -> Optional[int]:
        """Get score as integer"""
        try:
            return int(self.score) if self.score else None
        except ValueError:
            return None


# ===========================================
# Webhook Response Schema
# ===========================================

class WebhookResponse(BaseModel):
    """Standard webhook response"""
    code: int = Field(default=200, description="Response code")
    msg: str = Field(default="OK", description="Response message")
