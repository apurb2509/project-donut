import requests
import base64
import json
import time

BASE_URL = "http://localhost:5000"
API_PREFIX = "/api/v1/risk-detection"

def test_health():
    print("Testing Health Check...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Health check failed: {str(e)}")
        return False

def test_ingestion():
    print("\nTesting Frame Ingestion...")
    
    # Small 1x1 pixel red dot base64
    sample_image_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    
    payload = {
        "camera_id": "TEST-CAM-001",
        "location": "Test Laboratory",
        "image_base64": sample_image_base64
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}{API_PREFIX}/ingest-frame",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2)}")
        
        if response.status_code == 200:
            print("✅ Ingestion Logic Verified.")
            print(f"Detected Risk: {result.get('analysis', {}).get('risk_level')}")
            print(f"Storage Path: {result.get('storage_info', {}).get('storage_path')}")
        else:
            print(f"❌ Ingestion Failed: {result.get('error')}")
            
        return response.status_code == 200
    except Exception as e:
        print(f"Ingestion test failed: {str(e)}")
        return False

if __name__ == "__main__":
    print("=== HERO-IE API Test Script ===")
    print("Note: Ensure the backend server is running (python app.py)")
    
    # Try health check
    if not test_health():
        print("Backend server might be offline. Please start it with 'python app.py'")
    else:
        # Try ingestion
        test_ingestion()
