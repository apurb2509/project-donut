import os
import firebase_admin
from firebase_admin import credentials, storage
from google.cloud import vision
from dotenv import load_dotenv

def test_connections():
    load_dotenv()
    print("--- Connection Test ---")

    # 1. Firebase Storage Check
    cred_path = os.getenv('FIREBASE_CREDENTIALS_PATH')
    bucket_name = "donut-e5a15.appspot.com"
    
    print(f"Checking Firebase Storage with bucket: {bucket_name}...")
    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred, {'storageBucket': bucket_name})
        
        bucket = storage.bucket()
        # Try to list blobs (limited to 1 to just check access)
        blobs = list(bucket.list_blobs(max_results=1))
        print("✅ Firebase Storage: Connected and accessible!")
    except Exception as e:
        print(f"❌ Firebase Storage Error: {e}")

    # 2. Google Cloud Vision API Check
    print("\nChecking Google Cloud Vision API...")
    try:
        # Vision API uses the same credentials if you set the environment variable
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = cred_path
        client = vision.ImageAnnotatorClient()
        print("✅ Google Cloud Vision: Client initialized successfully!")
        print("   (Note: Vision API is ready for requests.)")
    except Exception as e:
        print(f"❌ Google Cloud Vision Error: {e}")

if __name__ == "__main__":
    test_connections()
