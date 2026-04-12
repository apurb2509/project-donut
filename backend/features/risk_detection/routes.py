import base64
from flask import Blueprint, request, jsonify
from .vision_service import analyze_image
from .storage_service import handle_storage
from features.deadman_switch.service import trigger_deadman_switch

risk_bp = Blueprint('risk_detection', __name__)

@risk_bp.route('/ingest-frame', methods=['POST'])
def ingest_frame():
    """
    Ingests a CCTV frame, analyzes it with Cloud Vision, and stores it according to the FIFO/permanent logic.
    Expected JSON Payload:
    {
        "camera_id": "CAM-01-LOBBY",
        "location": "Main Lobby",
        "image_base64": "base64_encoded_string_of_image_bytes"
    }
    """
    data = request.get_json()
    
    if not data or 'image_base64' not in data or 'camera_id' not in data:
        return jsonify({"error": "Missing required fields (image_base64, camera_id)"}), 400
        
    try:
        # 1. Decode Image
        image_bytes = base64.b64decode(data['image_base64'])
        
        # 2. Analyze Image
        analysis_result = analyze_image(image_bytes)
        risk_level = analysis_result['risk_level']
        
        # 3. Handle Storage Logic (FIFO for Green, Permanent for Yellow/Red)
        storage_result = handle_storage(
            image_bytes=image_bytes, 
            risk_level=risk_level, 
            camera_id=data['camera_id'], 
            location=data.get('location', 'Unknown')
        )

        deadman_switch_result = None
        if risk_level in {"YELLOW", "RED"}:
            deadman_switch_result = trigger_deadman_switch({
                "source": "risk_detection_ingest",
                "camera_id": data["camera_id"],
                "location": data.get("location", "Unknown"),
                "risk_level": risk_level,
                "labels": analysis_result.get("labels", []),
                "matched_red": analysis_result.get("matched_red", []),
                "matched_yellow": analysis_result.get("matched_yellow", []),
                "analysis": analysis_result,
                "storage_info": storage_result,
            })
        
        return jsonify({
            "message": "Frame processed successfully",
            "analysis": analysis_result,
            "storage_info": storage_result,
            "dead_man_switch": deadman_switch_result or {
                "armed": False,
                "status": "not_required_for_green",
            }
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
