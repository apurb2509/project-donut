import os
import firebase_admin
from firebase_admin import credentials, firestore, storage
from dotenv import load_dotenv

load_dotenv()

def initialize_firebase():
    if not firebase_admin._apps:
        # Load the service account details from the environment variable path
        cred_path = os.getenv('FIREBASE_CREDENTIALS_PATH')
        
        if cred_path and os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
            # You will need to provide your default storage bucket name in the .env
            bucket_name = os.getenv('FIREBASE_STORAGE_BUCKET')
            firebase_admin.initialize_app(cred, {
                'storageBucket': bucket_name
            })
            print("Firebase initialized successfully using credentials file.")
        else:
            # Fallback to Application Default Credentials if running in GCP directly
            firebase_admin.initialize_app()
            print("Firebase initialized using Application Default Credentials.")

def get_firestore_client():
    return firestore.client()

def get_storage_bucket():
    return storage.bucket()
