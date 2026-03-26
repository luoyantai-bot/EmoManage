# ===========================================
# Webhook Test Script
# ===========================================
"""
Test script for webhook endpoints

Run: python tests/test_webhook.py
"""

import asyncio
import httpx
import json
from datetime import datetime


BASE_URL = "http://127.0.0.1:8000"


async def test_realtime_data_webhook():
    """Test the realtime data webhook endpoint"""
    
    # Valid payload according to RealtimeDataWebhook schema
    payload = {
        "mqttId": "test123",
        "deviceCode": "TA0096400014",  # Required field (use alias name)
        "heartRate": "78",
        "breathing": "16",
        "signal": "44",
        "sosType": None,
        "bedStatus": "1",
        "sleepStatus": "1",
        "createTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "timestamp": str(int(datetime.now().timestamp())),
        "sign": "test_sign_placeholder"
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test 1: Using test endpoint (no signature verification)
        print("=" * 50)
        print("Test 1: Test endpoint (no signature verification)")
        print("=" * 50)
        print(f"URL: {BASE_URL}/api/v1/webhook/test/realtime-data")
        print(f"Payload: {json.dumps(payload, indent=2)}")
        
        try:
            response = await client.post(
                f"{BASE_URL}/api/v1/webhook/test/realtime-data",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
        except Exception as e:
            print(f"Error: {e}")
        
        # Test 2: Using production endpoint (with signature verification)
        print("\n" + "=" * 50)
        print("Test 2: Production endpoint (with signature verification)")
        print("=" * 50)
        print(f"URL: {BASE_URL}/api/v1/webhook/realtime-data")
        
        try:
            response = await client.post(
                f"{BASE_URL}/api/v1/webhook/realtime-data",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
        except Exception as e:
            print(f"Error: {e}")
        
        # Test 3: Invalid payload (missing required field)
        print("\n" + "=" * 50)
        print("Test 3: Invalid payload (missing deviceCode)")
        print("=" * 50)
        
        invalid_payload = {
            "heartRate": "78",
            "breathing": "16"
        }
        
        try:
            response = await client.post(
                f"{BASE_URL}/api/v1/webhook/test/realtime-data",
                json=invalid_payload,
                headers={"Content-Type": "application/json"}
            )
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
        except Exception as e:
            print(f"Error: {e}")
        
        # Test 4: Using snake_case field names (will fail)
        print("\n" + "=" * 50)
        print("Test 4: Using snake_case field names (should fail)")
        print("=" * 50)
        
        snake_case_payload = {
            "device_code": "TA0096400014",  # Wrong! Should be deviceCode
            "heart_rate": "78",  # Wrong! Should be heartRate
            "breathing": "16"
        }
        
        try:
            response = await client.post(
                f"{BASE_URL}/api/v1/webhook/test/realtime-data",
                json=snake_case_payload,
                headers={"Content-Type": "application/json"}
            )
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
        except Exception as e:
            print(f"Error: {e}")


async def test_report_webhook():
    """Test the report webhook endpoint"""
    
    payload = {
        "reportId": "RPT001",
        "deviceCode": "TA0096400014",
        "startTime": "2025-05-17 22:00:00",
        "endTime": "2025-05-18 06:00:00",
        "totalTimes": "480",
        "heartAvg": "65",
        "heartMax": "85",
        "heartMin": "55",
        "breathAvg": "14",
        "breathMax": "18",
        "breathMin": "10",
        "score": "85",
        "leaveBedNum": "2",
        "bodyMoveNum": "15",
        "snoreNum": "5",
        "apneaNum": "0",
        "deepSleepTime": "120",
        "lightSleepTime": "200",
        "remSleepTime": "80",
        "awakeTime": "10",
        "timestamp": str(int(datetime.now().timestamp())),
        "sign": "test_sign"
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("\n" + "=" * 50)
        print("Test: Report Webhook")
        print("=" * 50)
        print(f"URL: {BASE_URL}/api/v1/webhook/report")
        print(f"Payload: {json.dumps(payload, indent=2)}")
        
        try:
            response = await client.post(
                f"{BASE_URL}/api/v1/webhook/report",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
        except Exception as e:
            print(f"Error: {e}")


async def check_server_health():
    """Check if the server is running"""
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            response = await client.get(f"{BASE_URL}/docs")
            if response.status_code == 200:
                print("Server is running. API docs available at: {BASE_URL}/docs")
                return True
        except Exception as e:
            print(f"Server is not running or not accessible: {e}")
            return False


async def main():
    print("=" * 60)
    print("Webhook Test Script")
    print("=" * 60)
    
    # Check server health first
    server_running = await check_server_health()
    
    if not server_running:
        print("\nPlease start the server first:")
        print("  cd backend && python -m uvicorn app.main:app --reload")
        return
    
    print("\nStarting webhook tests...\n")
    
    # Test realtime data webhook
    await test_realtime_data_webhook()
    
    # Test report webhook
    await test_report_webhook()
    
    print("\n" + "=" * 60)
    print("Tests completed!")
    print("=" * 60)
    print("\nNote: 401 errors are expected for production endpoints without valid signature")
    print("Use /api/v1/webhook/test/realtime-data for testing without signature")


if __name__ == "__main__":
    asyncio.run(main())
