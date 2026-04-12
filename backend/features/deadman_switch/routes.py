from flask import Blueprint, jsonify, request

from .service import (
    acknowledge_deadman_switch,
    get_incident,
    list_active_incidents,
    trigger_deadman_switch,
)

deadman_switch_bp = Blueprint("deadman_switch", __name__)


@deadman_switch_bp.route("/trigger", methods=["POST"])
def trigger():
    data = request.get_json(silent=True) or {}

    if not data.get("camera_id"):
        return jsonify({"error": "Missing required field: camera_id"}), 400

    incident = trigger_deadman_switch(data)
    return jsonify(
        {
            "message": "Dead-man's switch armed",
            "incident": incident,
            "frontend_contract": {
                "acknowledge_endpoint": f"/api/v1/deadman-switch/incidents/{incident['incident_id']}/acknowledge",
                "status_endpoint": f"/api/v1/deadman-switch/incidents/{incident['incident_id']}",
            },
        }
    ), 201


@deadman_switch_bp.route("/incidents/<incident_id>/acknowledge", methods=["POST"])
def acknowledge(incident_id: str):
    data = request.get_json(silent=True) or {}

    try:
        incident = acknowledge_deadman_switch(
            incident_id=incident_id,
            acknowledged_by=data.get("acknowledged_by"),
            notes=data.get("notes"),
        )
        return jsonify({"message": "Incident acknowledged", "incident": incident}), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404


@deadman_switch_bp.route("/incidents/<incident_id>", methods=["GET"])
def incident_status(incident_id: str):
    try:
        incident = get_incident(incident_id)
        return jsonify({"incident": incident}), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404


@deadman_switch_bp.route("/incidents/active", methods=["GET"])
def active_incidents():
    incidents = list_active_incidents()
    return jsonify({"incidents": incidents}), 200
