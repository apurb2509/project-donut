import base64
from google.cloud import vision

# Red flag labels typically indicating high risk/certain damage
RED_FLAG_LABELS = {
    "fire", "flame", "smoke", "gun", "weapon", "explosion", 
    "blood", "assault", "violence", "knife", "collapse", "earthquake"
}

# Yellow flag labels indicating potential risk or anomalies
YELLOW_FLAG_LABELS = {
    "crowd", "overcrowding", "riot", "gathering", "protest", 
    "running", "panic", "spill", "hazard", "suspicious"
}

def analyze_image(image_bytes: bytes) -> dict:
    """
    Analyzes an image using Google Cloud Vision API and returns the risk classifications.
    Returns a dict with 'risk_level' and 'detected_labels'.
    """
    client = vision.ImageAnnotatorClient()
    image = vision.Image(content=image_bytes)
    
    # Perform label detection
    response = client.label_detection(image=image)
    
    if response.error.message:
        raise Exception(f"{response.error.message}")
        
    labels = [label.description.lower() for label in response.label_annotations]
    
    # Check flags
    risk_level = "GREEN"
    matched_red = [label for label in labels if any(red_word in label for red_word in RED_FLAG_LABELS)]
    matched_yellow = [label for label in labels if any(yellow_word in label for yellow_word in YELLOW_FLAG_LABELS)]
    
    if matched_red:
        risk_level = "RED"
    elif matched_yellow:
        risk_level = "YELLOW"
        
    return {
        "risk_level": risk_level,
        "labels": labels,
        "matched_red": matched_red,
        "matched_yellow": matched_yellow
    }
