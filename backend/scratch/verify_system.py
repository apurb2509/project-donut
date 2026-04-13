import sys
import os

# Add backend to path to allow imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from core.firebase_config import get_vision_client, get_firestore_client, get_storage_bucket
    from features.risk_detection.vision_service import analyze_image
    
    print("Checking Initialization...")
    vision_client = get_vision_client()
    db = get_firestore_client()
    bucket = get_storage_bucket()
    print("All clients initialized (Centralized).")
    
except Exception as e:
    print(f"Initialization Failed: {str(e)}")
    print("Hint: Check if FIREBASE_CREDENTIALS_PATH in .env is correct and the file exists.")
