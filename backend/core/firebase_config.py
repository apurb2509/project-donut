import os
import firebase_admin
from firebase_admin import credentials, firestore, storage
from google.cloud import vision
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class FirebaseServices:
    _instance = None
    
    def __init__(self):
        self.db = None
        self.bucket = None
        self.vision_client = None
        self._initialize()

    def _initialize(self):
        cred_path = os.getenv('FIREBASE_CREDENTIALS_PATH', 'firebase-credentials.json')
        bucket_name = os.getenv('FIREBASE_STORAGE_BUCKET')
        
        # Absolute path for credentials to ensure reliability
        if not os.path.isabs(cred_path):
            backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            cred_path = os.path.join(backend_dir, cred_path)

        if os.path.exists(cred_path):
            # Set environment variable for Google Cloud SDKs (Vision API)
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = cred_path
            
            cred = credentials.Certificate(cred_path)
            if not firebase_admin._apps:
                firebase_admin.initialize_app(cred, {
                    'storageBucket': bucket_name
                })
            print(f"Firebase initialized successfully using: {cred_path}")
        else:
            if not firebase_admin._apps:
                firebase_admin.initialize_app()
            print("Firebase initialized using Application Default Credentials.")

        self.db = firestore.client()
        self.bucket = storage.bucket()
        self.vision_client = vision.ImageAnnotatorClient()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

def get_firestore_client():
    return FirebaseServices.get_instance().db

def get_storage_bucket():
    return FirebaseServices.get_instance().bucket

def get_vision_client():
    return FirebaseServices.get_instance().vision_client

def initialize_firebase():
    """Compatibility function to trigger initialization"""
    FirebaseServices.get_instance()
