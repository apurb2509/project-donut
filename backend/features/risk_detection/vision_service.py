import os
import random
from core.firebase_config import get_vision_client
from google.cloud import vision

# Red flag labels typically indicating high risk/certain damage
RED_FLAG_LABELS = {
    "fire", "flame", "smoke", "gun", "weapon", "explosion", 
    "blood", "assault", "violence", "knife", "collapse", "earthquake",
    "emergency", "accident", "crash"
}

# Yellow flag labels indicating potential risk or anomalies
YELLOW_FLAG_LABELS = {
    "crowd", "overcrowding", "riot", "gathering", "protest", 
    "running", "panic", "spill", "hazard", "suspicious",
    "abandoned", "trespass", "loitering"
}

def analyze_image(image_bytes: bytes) -> dict:
    """
    Analyzes an image using Google Cloud Vision API and returns the risk classifications.
    If MOCK_VISION=true is set in .env, returns a simulated response to bypass billing errors.
    """
    # Check for Mock Mode
    if os.getenv("MOCK_VISION", "false").lower() == "true":
        print("[MOCK MODE] Simulating Vision AI analysis...")
        # Simulate different risk levels for testing
        # 80% Green, 15% Yellow, 5% Red
        choice = random.random()
        if choice < 0.05:
            risk_level = "RED"
            matched_red = ["fire", "smoke"]
            matched_yellow = []
            labels = ["fire", "smoke", "emergency", "danger"]
        elif choice < 0.20:
            risk_level = "YELLOW"
            matched_red = []
            matched_yellow = ["crowd", "suspicious"]
            labels = ["crowd", "gathering", "suspicious", "people"]
        else:
            risk_level = "GREEN"
            matched_red = []
            matched_yellow = []
            labels = ["room", "interior", "floor", "wall"]
            
        return {
            "risk_level": risk_level,
            "labels": labels,
            "matched_red": matched_red,
            "matched_yellow": matched_yellow,
            "raw_analysis": [{"description": l, "score": 0.9} for l in labels],
            "is_mock": True
        }

    client = get_vision_client()
    image = vision.Image(content=image_bytes)
    
    # Perform label detection
    try:
        response = client.label_detection(image=image)
        
        if response.error.message:
            raise Exception(f"Vision API Error: {response.error.message}")
            
        # Extract labels and scores
        labels_with_scores = [
            {"description": label.description.lower(), "score": label.score} 
            for label in response.label_annotations
        ]
        
        labels = [l["description"] for l in labels_with_scores]
        
        # Check flags with a confidence threshold (e.g., > 0.6)
        THRESHOLD = 0.6
        
        matched_red = [
            l["description"] for l in labels_with_scores 
            if l["score"] > THRESHOLD and any(red_word in l["description"] for red_word in RED_FLAG_LABELS)
        ]
        
        matched_yellow = [
            l["description"] for l in labels_with_scores 
            if l["score"] > THRESHOLD and any(yellow_word in l["description"] for yellow_word in YELLOW_FLAG_LABELS)
        ]
        
        # Tier logic
        risk_level = "GREEN"
        if matched_red:
            risk_level = "RED"
        elif matched_yellow:
            risk_level = "YELLOW"
            
        return {
            "risk_level": risk_level,
            "labels": labels,
            "matched_red": matched_red,
            "matched_yellow": matched_yellow,
            "raw_analysis": labels_with_scores,
            "is_mock": False
        }
    except Exception as e:
        if "billing to be enabled" in str(e):
            print("WARNING: Billing is disabled for Vision API. Please enable it in Google Cloud Console.")
            print("HINT: Set MOCK_VISION=true in .env to continue testing without API calls.")
        raise e
