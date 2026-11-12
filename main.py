import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from api.router import router
from services.ingestion_service import IngestionService
from services.generation_service import GenerationService
from src.embedding.embedding import EmbeddingModel
from core.read_yaml import read_yaml
from database.database import Base, engine
from api.auth import router as auth_router
from services.maintaince_service import maintance_service
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = Path("frontend")
UPLOAD_DIR = ""


@asynccontextmanager
async def lifespan(app: FastAPI):

    logger.info("Initializing Insight-AI...")
    cleanup_task = asyncio.create_task(maintance_service, UPLOAD_DIR)

    try:

        embedding_model = EmbeddingModel()
        config = read_yaml()

        app.state.ingestion_service = IngestionService(
            config=config,
            embedding_model=embedding_model
        )
        app.state.generation_service = GenerationService(config=config)

        logger.info("Insight-AI initialized successfully.")
        yield

    except Exception:
        logger.exception("Insight-AI initialization failed.")
        raise

    finally:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
        logger.info("Shutting down Insight-AI.")


app = FastAPI(
    title="Insight-AI API",
    description="AI-powered knowledge assistant",
    version="1.0.0",
    lifespan=lifespan
)
app.include_router(auth_router)
app.include_router(router)

BASE_DIR = Path(__file__).resolve().parents[1]

app.mount(
    "/static",
    StaticFiles(directory=str(FRONTEND_DIR / "static")),
    name="static"
)


@app.get("/", include_in_schema=False)
async def serve_frontend():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "application": "Insight-AI"
    }
