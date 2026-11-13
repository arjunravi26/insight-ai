import asyncio
import logging

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.router import router
from api.auth import router as auth_router

from services.ingestion_service import IngestionService
from services.generation_service import GenerationService
from services.ingestion_job_service import IngestionJobService
from services.maintaince_service import maintance_service

from workers.ingestion_worker import worker

from src.embedding.embedding import EmbeddingModel
from core.read_yaml import read_yaml
from database.database import SessionLocal


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
print(type(BASE_DIR))

FRONTEND_DIR = BASE_DIR / "frontend"
UPLOAD_DIR = BASE_DIR / "data" / "uploads"


@asynccontextmanager
async def lifespan(app: FastAPI):

    logger.info("Initializing Insight-AI...")

    # Initialize these before entering try/finally.
    # Startup can fail before the tasks are created.
    worker_task = None
    maintenance_task = None
    stop_event = asyncio.Event()

    try:

        # 1. Prepare directories.
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

        # 2. Load configuration.
        config = read_yaml()

        # 3. Initialize embedding model only once.
        embedding_model = EmbeddingModel()

        # 4. Initialize application services.
        ingestion_service = IngestionService(
            config=config,
            embedding_model=embedding_model
        )

        generation_service = GenerationService(
            config=config
        )

        # 5. Initialize job service.
        job_service = IngestionJobService(
            session_factory=SessionLocal,
            lease_seconds=300
        )

        # 6. Store application-level resources.
        app.state.embedding_model = embedding_model
        app.state.ingestion_service = ingestion_service
        app.state.generation_service = generation_service
        app.state.job_service = job_service

        # 7. Start maintenance task.
        maintenance_task = asyncio.create_task(
            maintance_service(UPLOAD_DIR),
            name="upload-maintenance"
        )

        # 8. Start ingestion worker.
        worker_task = asyncio.create_task(
            worker(
                ingestion_service=ingestion_service,
                job_service=job_service,
                stop_event=stop_event
            ),
            name="ingestion-worker"
        )

        app.state.worker_task = worker_task
        app.state.stop_event = stop_event

        logger.info("Insight-AI initialized successfully.")

        yield

    except Exception:
        logger.exception("Insight-AI lifecycle error.")
        raise

    finally:

        logger.info("Shutting down Insight-AI...")

        # 1. Tell worker not to claim new jobs.
        stop_event.set()

        # 2. Wait for the worker to finish its current job.
        if worker_task is not None:

            try:
                await worker_task

            except asyncio.CancelledError:
                logger.info("Ingestion worker was cancelled.")

            except Exception:
                logger.exception(
                    "Ingestion worker failed during shutdown."
                )

        # 3. Stop periodic maintenance.
        if maintenance_task is not None:

            maintenance_task.cancel()

            await asyncio.gather(
                maintenance_task,
                return_exceptions=True
            )

        logger.info("Insight-AI shutdown complete.")


# Create the FastAPI application only once.
app = FastAPI(
    title="Insight-AI API",
    description="AI-powered knowledge assistant",
    version="1.0.0",
    lifespan=lifespan
)


# Register routers.
app.include_router(auth_router)
app.include_router(router)


# Serve frontend static files.
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