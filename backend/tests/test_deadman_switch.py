import requests
import time
import json

BASE_URL = "http://localhost:5000/api/v1/deadman-switch"

def test_deadman_switch_flow():
    print("--- Starting Dead-man's Switch Flow Test ---")
    
    # 1. Trigger an incident
    trigger_payload = {
        "camera_id": "TEST-CAM-999",
        "location": "Test Laboratory Delta",
        "risk_level": "RED",
        "alarm_window_seconds": 5
    }
    
    print("\n1. Triggering incident...")
    resp = requests.post(f"{BASE_URL}/trigger", json=trigger_payload)
    if resp.status_code != 201:
        print(f"FAILED: Trigger status {resp.status_code}")
        print(resp.text)
        return
    
    data = resp.json()
    incident_id = data['incident']['incident_id']
    print(f"SUCCESS: Incident {incident_id} triggered.")
    
    # 2. Check active incidents
    print("\n2. Checking active incidents...")
    resp = requests.get(f"{BASE_URL}/incidents/active")
    active_ids = [inc['incident_id'] for inc in resp.json()['incidents']]
    if incident_id in active_ids:
        print(f"SUCCESS: Incident found in active list.")
    else:
        print(f"FAILED: Incident not found in active list.")
        return

    # 3. Acknowledge the incident
    print("\n3. Acknowledging incident...")
    ack_payload = {"acknowledged_by": "Test Operator 01", "notes": "All clear, false alarm."}
    resp = requests.post(f"{BASE_URL}/incidents/{incident_id}/acknowledge", json=ack_payload)
    if resp.status_code == 200:
        print(f"SUCCESS: Incident acknowledged.")
    else:
        print(f"FAILED: Acknowledge status {resp.status_code}")
        return

    # 4. Verify status is ACKNOWLEDGED
    print("\n4. Verifying status...")
    resp = requests.get(f"{BASE_URL}/incidents/{incident_id}")
    status = resp.json()['incident']['status']
    print(f"Current Status: {status}")
    if status == "ACKNOWLEDGED":
        print("SUCCESS: Status verified as ACKNOWLEDGED.")
    else:
        print(f"FAILED: Expected ACKNOWLEDGED but got {status}")

    # 5. Test Escalation (Timeout)
    print("\n5. Testing Escalation (Timeout)...")
    trigger_payload['alarm_window_seconds'] = 3
    resp = requests.post(f"{BASE_URL}/trigger", json=trigger_payload)
    incident_id = resp.json()['incident']['incident_id']
    print(f"Incident {incident_id} triggered with 3s window. Waiting 5s...")
    
    time.sleep(5)
    
    resp = requests.get(f"{BASE_URL}/incidents/{incident_id}")
    status = resp.json()['incident']['status']
    print(f"Current Status: {status}")
    if status == "ESCALATED":
        print("SUCCESS: Status verified as ESCALATED.")
        print("Outreach Data:", json.dumps(resp.json()['incident']['outreach'], indent=2))
    else:
        print(f"FAILED: Expected ESCALATED but got {status}")

if __name__ == "__main__":
    try:
        requests.get("http://localhost:5000/health")
        test_deadman_switch_flow()
    except requests.exceptions.ConnectionError:
        print("ERROR: Backend server not running at http://localhost:5000")
