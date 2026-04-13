import os
from dotenv import load_dotenv
from core.firebase_config import initialize_firebase, get_firestore_client

load_dotenv()
initialize_firebase()

try:
    print("Testing Firestore client...")
    db = get_firestore_client()
    print("Listing collections (lightweight)...")
    collections = list(db.collections())
    print(f"Success! Found {len(collections)} collections.")
    for col in collections:
        print(f" - {col.id}")
except Exception as e:
    print(f"\nERROR ACCESSING FIRESTORE: {e}")
    print("\nTroubleshooting tips:")
    print("1. Ensure Firestore is enabled in the Firebase Console (Native Mode).")
    print("2. Ensure the Service Account in your JSON has 'Cloud Datastore User' or 'Editor' role.")
    print("3. Check if your project has a database created.")
