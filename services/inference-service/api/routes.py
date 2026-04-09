from fastapi import APIRouter, BackgroundTasks
from schemas.request_schema import InferenceRequest
from core.model_loader import predict
from core.kafka_producer import produce_inference_event
import uuid
import json
import os
from datetime import datetime

router = APIRouter()

@router.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

LOG_FILE = os.path.join(os.path.dirname(__file__), "../../../logs/inference.log")

def write_log_entry(req_id: str, features: dict, pred: int, conf: float):
    # Ensure logs directory exists
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    timestamp = datetime.utcnow().isoformat()
    log_entry = {
        "timestamp": timestamp,
        "request_id": req_id,
        "features": features,
        "prediction": pred,
        "confidence": conf
    }
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(log_entry) + "\n")
    
    # Also push to Kafka
    produce_inference_event("inference-events", req_id, features, pred, conf, timestamp)

@router.post("/predict")
def make_prediction(request: InferenceRequest, background_tasks: BackgroundTasks):
    req_id = str(uuid.uuid4())
    pred, conf = predict(request.features)
    
    background_tasks.add_task(write_log_entry, req_id, request.features, pred, conf)
    
    return {
        "request_id": req_id,
        "prediction": pred,
        "confidence": conf
    }
