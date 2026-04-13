import os
import threading
import uuid
import datetime
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from google.cloud import firestore

from core.firebase_config import get_firestore_client
from .outreach_service import dispatch_outreach

INCIDENTS_COLLECTION = "deadman_switch_incidents"
DEFAULT_ALARM_WINDOW_SECONDS = int(os.getenv("DEADMAN_SWITCH_ALARM_WINDOW_SECONDS", "15"))
MONITOR_INTERVAL_SECONDS = int(os.getenv("DEADMAN_SWITCH_MONITOR_INTERVAL_SECONDS", "5"))

_MONITOR_THREAD_STARTED = False
_MONITOR_LOCK = threading.Lock()
_TIMERS: Dict[str, threading.Timer] = {}
_MONITOR_DISABLED = False

# Mock Storage for logic verification without Firestore
_MOCK_STORAGE: Dict[str, Dict[str, Any]] = {}

def is_mock_mode() -> bool:
    return os.getenv("MOCK_FIRESTORE", "false").lower() == "true"

def trigger_deadman_switch(payload: Dict[str, Any]) -> Dict[str, Any]:
    incident_id = str(uuid.uuid4())
    created_at = datetime.utcnow()
    alarm_window_seconds = int(payload.get("alarm_window_seconds") or DEFAULT_ALARM_WINDOW_SECONDS)
    alarm_expires_at = created_at + timedelta(seconds=alarm_window_seconds)

    incident = {
        "incident_id": incident_id,
        "source": payload.get("source", "risk_detection"),
        "camera_id": payload.get("camera_id"),
        "location": payload.get("location", "Unknown"),
        "risk_level": payload.get("risk_level", "UNKNOWN"),
        "labels": payload.get("labels", []),
        "matched_red": payload.get("matched_red", []),
        "matched_yellow": payload.get("matched_yellow", []),
        "storage_info": payload.get("storage_info", {}),
        "analysis": payload.get("analysis", {}),
        "status": "ACK_PENDING",
        "alarm_state": "ACTIVE",
        "alarm_window_seconds": alarm_window_seconds,
        "alarm_started_at": created_at,
        "alarm_expires_at": alarm_expires_at,
        "acknowledged_at": None,
        "acknowledged_by": None,
        "escalated_at": None,
        "escalation_reason": None,
        "outreach": {
            "venue_alarm": "active",
            "email": "pending",
            "sms": "pending",
            "call": "pending",
        },
        "created_at": created_at,
        "updated_at": created_at,
        "is_mock": is_mock_mode()
    }

    if is_mock_mode():
        print(f"[MOCK MODE] Triggering incident {incident_id}")
        _MOCK_STORAGE[incident_id] = incident
    else:
        db = get_firestore_client()
        db.collection(INCIDENTS_COLLECTION).document(incident_id).set(incident)

    _schedule_escalation(incident_id, alarm_window_seconds)

    return _serialize_incident(incident)


def acknowledge_deadman_switch(incident_id: str, acknowledged_by: Optional[str] = None, notes: Optional[str] = None) -> Dict[str, Any]:
    if is_mock_mode():
        if incident_id not in _MOCK_STORAGE:
            raise ValueError("Incident not found (Mock)")
        incident = _MOCK_STORAGE[incident_id]
    else:
        db = get_firestore_client()
        incident_ref = db.collection(INCIDENTS_COLLECTION).document(incident_id)
        snapshot = incident_ref.get()
        if not snapshot.exists:
            raise ValueError("Incident not found")
        incident = snapshot.to_dict()

    if incident.get("status") == "ACKNOWLEDGED":
        return _serialize_incident(incident)

    _cancel_escalation_timer(incident_id)

    updated_at = datetime.utcnow()
    update_data = {
        "status": "ACKNOWLEDGED",
        "alarm_state": "DISMISSED",
        "acknowledged_at": updated_at,
        "acknowledged_by": acknowledged_by,
        "moderator_notes": notes,
        "updated_at": updated_at,
    }

    if is_mock_mode():
        print(f"[MOCK MODE] Acknowledging incident {incident_id}")
        _MOCK_STORAGE[incident_id].update(update_data)
        incident = _MOCK_STORAGE[incident_id]
    else:
        db.collection(INCIDENTS_COLLECTION).document(incident_id).update(update_data)
        incident.update(update_data)

    return _serialize_incident(incident)


def get_incident(incident_id: str) -> Dict[str, Any]:
    if is_mock_mode():
        if incident_id not in _MOCK_STORAGE:
            raise ValueError("Incident not found (Mock)")
        incident = _MOCK_STORAGE[incident_id]
        _reconcile_incident_if_needed(incident_id, incident)
        return _serialize_incident(_MOCK_STORAGE[incident_id])
    
    db = get_firestore_client()
    snapshot = db.collection(INCIDENTS_COLLECTION).document(incident_id).get()

    if not snapshot.exists:
        raise ValueError("Incident not found")

    incident = snapshot.to_dict()
    _reconcile_incident_if_needed(incident_id, incident)
    latest_snapshot = db.collection(INCIDENTS_COLLECTION).document(incident_id).get()
    return _serialize_incident(latest_snapshot.to_dict())


def list_active_incidents() -> List[Dict[str, Any]]:
    if is_mock_mode():
        incidents = []
        for iid, inc in _MOCK_STORAGE.items():
            if inc.get("status") in ["ACK_PENDING", "ESCALATED"]:
                _reconcile_incident_if_needed(iid, inc)
                incidents.append(_serialize_incident(_MOCK_STORAGE[iid]))
        return sorted(incidents, key=lambda x: x["created_at"], reverse=True)

    db = get_firestore_client()
    snapshots = (
        db.collection(INCIDENTS_COLLECTION)
        .where("status", "in", ["ACK_PENDING", "ESCALATED"])
        .order_by("created_at", direction=firestore.Query.DESCENDING)
        .stream()
    )

    incidents = []
    for snapshot in snapshots:
        incident = snapshot.to_dict()
        _reconcile_incident_if_needed(snapshot.id, incident)
        refreshed = db.collection(INCIDENTS_COLLECTION).document(snapshot.id).get()
        incidents.append(_serialize_incident(refreshed.to_dict()))

    return incidents


def process_due_incidents() -> int:
    if is_mock_mode():
        now = datetime.utcnow()
        processed = 0
        ids_to_escalate = []
        for iid, inc in _MOCK_STORAGE.items():
            if inc.get("status") == "ACK_PENDING":
                expires_at = inc.get("alarm_expires_at")
                if expires_at and expires_at <= now:
                    ids_to_escalate.append(iid)
        
        for iid in ids_to_escalate:
            if escalate_incident(iid):
                processed += 1
        return processed

    db = get_firestore_client()
    now = datetime.utcnow()
    query = (
        db.collection(INCIDENTS_COLLECTION)
        .where("status", "==", "ACK_PENDING")
        .where("alarm_expires_at", "<=", now)
    )

    processed = 0
    for snapshot in query.stream():
        if escalate_incident(snapshot.id):
            processed += 1
    return processed


def escalate_incident(incident_id: str) -> Optional[Dict[str, Any]]:
    if is_mock_mode():
        if incident_id not in _MOCK_STORAGE:
            return None
        incident = _MOCK_STORAGE[incident_id]
    else:
        db = get_firestore_client()
        incident_ref = db.collection(INCIDENTS_COLLECTION).document(incident_id)
        snapshot = incident_ref.get()
        if not snapshot.exists:
            return None
        incident = snapshot.to_dict()

    if incident.get("status") != "ACK_PENDING":
        return _serialize_incident(incident)

    now = datetime.utcnow()
    if incident.get("alarm_expires_at") and incident["alarm_expires_at"] > now:
        return _serialize_incident(incident)

    print(f"[DEADMAN SWITCH] Escalating incident {incident_id}...")
    outreach_result = dispatch_outreach(incident)
    
    update_data = {
        "status": "ESCALATED",
        "alarm_state": "EXPIRED",
        "escalated_at": now,
        "escalation_reason": "moderator_timeout",
        "outreach": {
            "venue_alarm": "sent",
            "email": outreach_result["outbox"][1]["status"],
            "sms": outreach_result["outbox"][2]["status"],
            "call": outreach_result["outbox"][3]["status"],
        },
        "updated_at": now,
    }

    if is_mock_mode():
        _MOCK_STORAGE[incident_id].update(update_data)
        updated_incident = _MOCK_STORAGE[incident_id]
    else:
        incident_ref.update(update_data)
        incident.update(update_data)
        updated_incident = incident

    return _serialize_incident(updated_incident)


def start_deadman_switch_monitor() -> None:
    global _MONITOR_THREAD_STARTED
    global _MONITOR_DISABLED

    if _MONITOR_THREAD_STARTED or _MONITOR_DISABLED:
        return

    with _MONITOR_LOCK:
        if _MONITOR_THREAD_STARTED or _MONITOR_DISABLED:
            return

        # Skip firestore check in mock mode
        if not is_mock_mode() and not _can_access_firestore():
            _MONITOR_DISABLED = True
            print("Dead-man switch monitor disabled: Firestore is unavailable. Configure Firebase credentials to enable it.")
            return

        if is_mock_mode():
            print("Dead-man switch monitor started in MOCK MODE (In-memory storage).")
        else:
            print("Dead-man switch monitor started.")

        monitor_thread = threading.Thread(target=_monitor_loop, daemon=True)
        monitor_thread.start()
        _MONITOR_THREAD_STARTED = True


def _monitor_loop() -> None:
    while True:
        try:
            process_due_incidents()
        except Exception as exc:
            print(f"Dead-man switch monitor error: {exc}")
        finally:
            threading.Event().wait(MONITOR_INTERVAL_SECONDS)


def _can_access_firestore() -> bool:
    try:
        db = get_firestore_client()
        # Trigger one lightweight call to validate auth/config at startup.
        next(db.collections(), None)
        return True
    except Exception:
        return False


def _schedule_escalation(incident_id: str, alarm_window_seconds: int) -> None:
    _cancel_escalation_timer(incident_id)

    timer = threading.Timer(alarm_window_seconds, lambda: escalate_incident(incident_id))
    timer.daemon = True
    timer.start()
    _TIMERS[incident_id] = timer


def _cancel_escalation_timer(incident_id: str) -> None:
    timer = _TIMERS.pop(incident_id, None)
    if timer:
        timer.cancel()


def _reconcile_incident_if_needed(incident_id: str, incident: Dict[str, Any]) -> None:
    if not incident:
        return

    if incident.get("status") != "ACK_PENDING":
        return

    expires_at = incident.get("alarm_expires_at")
    # Handle both iso string (if already serialized in some flows) and datetime objects
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00')).replace(tzinfo=None)
        
    if expires_at and expires_at <= datetime.utcnow():
        escalate_incident(incident_id)


def _serialize_incident(incident: Dict[str, Any]) -> Dict[str, Any]:
    return _serialize(incident)


def _serialize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat() + "Z"
    return value
