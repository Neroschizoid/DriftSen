from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
from api.routes import router
from core.model_loader import load_model
from core.kafka_producer import get_producer
from utils.logger import logger

@asynccontextmanager
async def lifespan(app: FastAPI):
    load_model()
    kafka_enabled = os.getenv("KAFKA_ENABLED", "false").lower() == "true"
    kafka_url = os.getenv("KAFKA_URL", "")
    producer = get_producer()
    logger.info(
        "Inference startup | kafka_enabled=%s | kafka_url=%s | producer_connected=%s",
        kafka_enabled,
        kafka_url or "<unset>",
        bool(producer),
    )
    yield

app = FastAPI(title="DriftSentinel Inference Service", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
