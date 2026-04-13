import uuid
from datetime import datetime
from core.firebase_config import get_firestore_client, get_storage_bucket
from google.cloud import firestore

GREEN_IMAGES_COLLECTION = "green_images"
MAX_GREEN_IMAGES = 10000

def handle_storage(image_bytes: bytes, risk_level: str, camera_id: str, location: str, metadata: dict = None):
    """
    Saves image based on risk_level and handles the FIFO queue logic for Green images.
    Yellow/Red flags are permanently archived for forensic audits.
    """
    bucket = get_storage_bucket()
    db = get_firestore_client()
    
    timestamp = datetime.utcnow()
    file_id = str(uuid.uuid4())
    
    # Define folder structure based on risk
    # Red/Yellow = history (permanent), Green = temporary
    folder = f"monitoring/{risk_level.lower()}"
    file_path = f"{folder}/{camera_id}/{timestamp.strftime('%Y/%m/%d')}/{file_id}.jpg"
    
    # Upload to Cloud Storage
    blob = bucket.blob(file_path)
    blob.upload_from_string(image_bytes, content_type="image/jpeg")
    
    # Define document payload
    doc_payload = {
        "file_id": file_id,
        "camera_id": camera_id,
        "location": location,
        "timestamp": timestamp,
        "storage_path": file_path,
        "risk_level": risk_level,
        "analysis_metadata": metadata or {}
    }
    
    if risk_level == "GREEN":
        # Add to green images queue
        doc_ref = db.collection(GREEN_IMAGES_COLLECTION).document(file_id)
        doc_ref.set(doc_payload)
        
        # Enforce FIFO logic
        # Note: In a high-traffic system, this should be done via a Cloud Function Trigger.
        # But for this implementation, we handle it inline for simplicity and direct control.
        _enforce_fifo(db, bucket)
    else:
        # Yellow and Red are permanently archived in the 'alerts' collection
        db.collection("alerts").document(file_id).set(doc_payload)
        
    return {
        "status": "success",
        "file_id": file_id,
        "risk_level": risk_level,
        "storage_path": file_path
    }

def _enforce_fifo(db, bucket):
    """
    Maintains a limit of MAX_GREEN_IMAGES in the green_images collection.
    Deletes the oldest documents and their corresponding storage objects.
    """
    try:
        # Count current green images
        count_agg = db.collection(GREEN_IMAGES_COLLECTION).count().get()
        total_count = count_agg[0][0].value
        
        if total_count > MAX_GREEN_IMAGES:
            # Calculate how many to delete (delete in batches of 10 if way over, or just the excess)
            excess = total_count - MAX_GREEN_IMAGES
            
            # Fetch oldest documents
            oldest_docs = db.collection(GREEN_IMAGES_COLLECTION) \
                            .order_by("timestamp", direction=firestore.Query.ASCENDING) \
                            .limit(excess) \
                            .stream()
            
            for doc in oldest_docs:
                data = doc.to_dict()
                path = data.get("storage_path")
                
                # 1. Delete from Storage
                if path:
                    blob = bucket.blob(path)
                    if blob.exists():
                        blob.delete()
                
                # 2. Delete from Firestore
                db.collection(GREEN_IMAGES_COLLECTION).document(doc.id).delete()
                
    except Exception as e:
        print(f"FIFO Optimization Error: {str(e)}")
