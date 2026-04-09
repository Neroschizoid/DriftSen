from fastapi import FastAPI
from contextlib import asynccontextmanager
from api.routes import router
from core.model_loader import load_model
from core.kafka_producer import get_producer

@asynccontextmanager
async def lifespan(app: FastAPI):
    load_model()
    get_producer()
    yield

app = FastAPI(title="DriftSentinel Inference Service", lifespan=lifespan)

app.include_router(router, prefix="/api/v1")

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
