import uuid
from datetime import datetime
from core.firebase_config import get_firestore_client, get_storage_bucket
from google.cloud import firestore

GREEN_IMAGES_COLLECTION = "green_images"
MAX_GREEN_IMAGES = 10000

def handle_storage(image_bytes: bytes, risk_level: str, camera_id: str, location: str):
    """
    Saves image based on risk_level and handles the FIFO queue logic on Firestore
    to avoid exponential DB growth.
    """
    bucket = get_storage_bucket()
    db = get_firestore_client()
    
    timestamp = datetime.utcnow()
    file_id = str(uuid.uuid4())
    
    # Define folder structure based on risk
    folder = "history/red" if risk_level == "RED" else "history/yellow" if risk_level == "YELLOW" else "temporary/green"
    file_path = f"{folder}/{camera_id}_{timestamp.strftime('%Y%m%d%H%M%S')}_{file_id}.jpg"
    
    # Upload to Cloud Storage
    blob = bucket.blob(file_path)
    blob.upload_from_string(image_bytes, content_type="image/jpeg")
    
    # Define document payload
    doc_payload = {
        "camera_id": camera_id,
        "location": location,
        "timestamp": timestamp,
        "storage_path": file_path,
        "risk_level": risk_level
    }
    
    if risk_level == "GREEN":
        # Add to green images queue
        doc_ref = db.collection(GREEN_IMAGES_COLLECTION).document(file_id)
        doc_ref.set(doc_payload)
        
        # Enforce FIFO logic (lazy evaluation to avoid locking, deleting oldest if over MAX_GREEN_IMAGES)
        _enforce_fifo(db, bucket)
    else:
        # Save to permanent history (alerts collection)
        db.collection("alerts").document(file_id).set(doc_payload)
        
    return {
        "status": "stored",
        "file_id": file_id,
        "storage_path": file_path
    }

def _enforce_fifo(db, bucket):
    """
    Checks the number of green images and deletes the oldest if exceeding limit.
    Warning: Doing this on every insert might be computationally expensive. 
    In production, use a scheduled Cloud Function instead.
    """
    try:
        # Fetch up to 1 over the limit, ordered by timestamp ascending (oldest first)
        # Using a count aggregation query is faster since Firebase introduced it.
        count_query = db.collection(GREEN_IMAGES_COLLECTION).count()
        count_result = count_query.get()
        total_count = count_result[0][0].value
        
        if total_count > MAX_GREEN_IMAGES:
            excess = total_count - MAX_GREEN_IMAGES
            
            # Fetch the oldest N documents to delete
            oldest_docs = db.collection(GREEN_IMAGES_COLLECTION).order_by("timestamp", direction=firestore.Query.ASCENDING).limit(excess).stream()
            
            for doc in oldest_docs:
                doc_data = doc.to_dict()
                storage_path = doc_data.get("storage_path")
                
                # Delete from Cloud Storage
                if storage_path:
                    blob = bucket.blob(storage_path)
                    if blob.exists():
                        blob.delete()
                
                # Delete from Firestore
                db.collection(GREEN_IMAGES_COLLECTION).document(doc.id).delete()
    except Exception as e:
        print(f"Failed to enforce FIFO logic: {str(e)}")
