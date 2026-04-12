import json
import os
from datetime import datetime
from typing import Any, Dict, List

from firebase_admin import messaging

from core.firebase_config import get_firestore_client

OUTBOX_COLLECTION = "deadman_switch_outbox"


def _parse_recipients(value):
    if not value:
        return []

    value = value.strip()
    if not value:
        return []

    if value.startswith("["):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            pass

    return [item.strip() for item in value.split(",") if item.strip()]


def build_default_outreach_plan(incident: Dict[str, Any]) -> Dict[str, Any]:
    venue_contacts = _parse_recipients(os.getenv("DEADMAN_SWITCH_VENUE_CONTACTS"))
    emergency_contacts = _parse_recipients(os.getenv("DEADMAN_SWITCH_EMERGENCY_CONTACTS"))

    return {
        "venue_alarm": True,
        "channels": ["venue_alarm", "email", "sms", "call"],
        "recipients": {
            "venue_contacts": venue_contacts,
            "emergency_contacts": emergency_contacts,
        },
        "target_groups": [
            "nearby police stations",
            "hospitals",
            "fire stations",
            "rescue teams",
            "ngos",
        ],
        "source": {
            "camera_id": incident.get("camera_id"),
            "location": incident.get("location"),
            "risk_level": incident.get("risk_level"),
        },
    }


def dispatch_outreach(incident: Dict[str, Any]) -> Dict[str, Any]:
    db = get_firestore_client()
    plan = build_default_outreach_plan(incident)
    outbox_entries = []

    outbox_entries.append(
        _store_outbox_entry(
            db=db,
            incident=incident,
            channel="venue_alarm",
            target="venue-wide alert",
            message=_build_alarm_message(incident),
            status="sent",
            provider="firebase_firestore",
        )
    )

    outbox_entries.extend(
        [
            _dispatch_email_alert(db, incident, plan),
            _dispatch_sms_alert(db, incident, plan),
            _dispatch_call_alert(db, incident, plan),
        ]
    )

    _send_firebase_topic_alert(incident)

    return {
        "plan": plan,
        "outbox": outbox_entries,
    }


def _build_alarm_message(incident: Dict[str, Any]) -> str:
    return (
        f"Dead-man's switch alarm triggered for {incident.get('location', 'Unknown location')} "
        f"({incident.get('camera_id', 'Unknown camera')}) due to {incident.get('risk_level', 'UNKNOWN')} risk."
    )


def _store_outbox_entry(
    db,
    incident: Dict[str, Any],
    channel: str,
    target: str,
    message: str,
    status: str,
    provider: str,
) -> Dict[str, Any]:
    outbox_id = f"{incident['incident_id']}-{channel}-{int(datetime.utcnow().timestamp() * 1000)}"
    payload = {
        "outbox_id": outbox_id,
        "incident_id": incident["incident_id"],
        "channel": channel,
        "target": target,
        "message": message,
        "status": status,
        "provider": provider,
        "created_at": datetime.utcnow(),
    }
    db.collection(OUTBOX_COLLECTION).document(outbox_id).set(payload)
    return _serialize(payload)


def _dispatch_email_alert(db, incident: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    recipients = plan["recipients"].get("emergency_contacts") or _parse_recipients(
        os.getenv("DEADMAN_SWITCH_EMAIL_RECIPIENTS")
    )
    subject = f"[ALERT] {incident.get('risk_level', 'UNKNOWN')} incident at {incident.get('location', 'Unknown location')}"
    message = _build_alarm_message(incident)

    if recipients and _send_email_via_google_workspace(recipients, subject, message):
        status = "sent"
    else:
        status = "queued"

    return _store_outbox_entry(
        db=db,
        incident=incident,
        channel="email",
        target=", ".join(recipients) if recipients else "unconfigured",
        message=message,
        status=status,
        provider="google_workspace_gmail_api" if recipients else "firestore_queue",
    )


def _dispatch_sms_alert(db, incident: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    recipients = plan["recipients"].get("emergency_contacts") or _parse_recipients(
        os.getenv("DEADMAN_SWITCH_SMS_RECIPIENTS")
    )
    message = _build_alarm_message(incident)
    status = "queued" if recipients else "unconfigured"

    return _store_outbox_entry(
        db=db,
        incident=incident,
        channel="sms",
        target=", ".join(recipients) if recipients else "unconfigured",
        message=message,
        status=status,
        provider="firestore_queue",
    )


def _dispatch_call_alert(db, incident: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    recipients = plan["recipients"].get("emergency_contacts") or _parse_recipients(
        os.getenv("DEADMAN_SWITCH_CALL_RECIPIENTS")
    )
    message = _build_alarm_message(incident)
    status = "queued" if recipients else "unconfigured"

    return _store_outbox_entry(
        db=db,
        incident=incident,
        channel="call",
        target=", ".join(recipients) if recipients else "unconfigured",
        message=message,
        status=status,
        provider="firestore_queue",
    )


def _send_email_via_google_workspace(recipients: List[str], subject: str, body: str) -> bool:
    service_account_file = os.getenv("GOOGLE_WORKSPACE_SERVICE_ACCOUNT_FILE")
    impersonate_user = os.getenv("GOOGLE_WORKSPACE_IMPERSONATE_USER")

    if not service_account_file or not impersonate_user:
        return False

    try:
        from email.message import EmailMessage

        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        credentials = service_account.Credentials.from_service_account_file(
            service_account_file,
            scopes=["https://www.googleapis.com/auth/gmail.send"],
        ).with_subject(impersonate_user)

        gmail_service = build("gmail", "v1", credentials=credentials, cache_discovery=False)

        email_message = EmailMessage()
        email_message["To"] = ", ".join(recipients)
        email_message["From"] = impersonate_user
        email_message["Subject"] = subject
        email_message.set_content(body)

        encoded_message = {
            "raw": _to_base64url(email_message.as_bytes()),
        }

        gmail_service.users().messages().send(userId="me", body=encoded_message).execute()
        return True
    except Exception as exc:
        print(f"Failed to send Gmail alert: {exc}")
        return False


def _send_firebase_topic_alert(incident: Dict[str, Any]) -> None:
    topic = os.getenv("DEADMAN_SWITCH_FCM_TOPIC", "venue-wide-alerts")
    message = messaging.Message(
        topic=topic,
        notification=messaging.Notification(
            title=f"{incident.get('risk_level', 'UNKNOWN')} risk detected",
            body=_build_alarm_message(incident),
        ),
        data={
            "incident_id": incident["incident_id"],
            "camera_id": incident.get("camera_id", ""),
            "location": incident.get("location", ""),
            "risk_level": incident.get("risk_level", "UNKNOWN"),
        },
    )

    try:
        messaging.send(message)
    except Exception as exc:
        print(f"Failed to send Firebase topic alert: {exc}")


def _to_base64url(payload: bytes) -> str:
    import base64

    return base64.urlsafe_b64encode(payload).decode("utf-8")


def _serialize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat() + "Z"
    return value
