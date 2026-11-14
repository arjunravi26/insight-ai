import time
import logging

from src.ingestion.chunking import Chunking
from src.ingestion.ingestion import PineconeVectorStore
from src.ingestion.read_data import ExtractData

from observability.metrics import (
    INGESTION_STAGE_LATENCY,
    INGESTION_ATTEMPT_LATENCY,
    INGESTION_ATTEMPTS,
    INGESTION_IN_PROGRESS,
    INGESTION_PAGES,
    INGESTION_CHUNKS_PER_DOCUMENT,
    INGESTION_CHUNKS,
    VECTOR_OPERATIONS,
    record_error,
)

logger = logging.getLogger(__name__)


class IngestionService:

    def __init__(self, config, embedding_model):

        self.extractor = ExtractData()

        self.chunker = Chunking(config)

        self.vector_store = PineconeVectorStore(
            embedding_model=embedding_model,
            config=config,
            create_if_missing=True
        )

    def ingest_pdf(
        self,
        pdf_path: str,
        document_id: str,
        user_id: int,
        filename: str
    ):

        start_time = time.perf_counter()

        outcome = "failure"

        INGESTION_IN_PROGRESS.inc()

        try:

            # =========================================
            # 1. PDF EXTRACTION
            # =========================================

            with INGESTION_STAGE_LATENCY.labels(
                stage="pdf_extraction"
            ).time():

                extracted_documents = self.extractor.extract(
                    pdf_path=pdf_path,
                    document_id=document_id,
                    filename=filename
                )

            # Use this as a page count only if your extractor
            # returns one Document object per PDF page.
            INGESTION_PAGES.observe(
                len(extracted_documents)
            )

            # =========================================
            # 2. CHUNKING
            # =========================================

            with INGESTION_STAGE_LATENCY.labels(
                stage="chunking"
            ).time():

                chunked_documents = self.chunker.split_documents(
                    extracted_documents
                )

            chunk_count = len(chunked_documents)

            INGESTION_CHUNKS_PER_DOCUMENT.observe(
                chunk_count
            )

            INGESTION_CHUNKS.labels(
                operation="created"
            ).inc(chunk_count)

            # =========================================
            # 3. VECTOR UPSERT
            # =========================================

            try:

                with INGESTION_STAGE_LATENCY.labels(
                    stage="vector_upsert"
                ).time():

                    result = self.vector_store.upsert_chunks(
                        chunks=chunked_documents,
                        user_id=user_id,
                        document_id=document_id,
                        filename=filename
                    )

                VECTOR_OPERATIONS.labels(
                    operation="upsert",
                    outcome="success"
                ).inc()

                INGESTION_CHUNKS.labels(
                    operation="upserted"
                ).inc(chunk_count)

            except Exception:

                VECTOR_OPERATIONS.labels(
                    operation="upsert",
                    outcome="failure"
                ).inc()

                raise

            outcome = "success"

            logger.info(
                "Ingestion completed. Document ID: %s, Chunks: %s",
                document_id,
                chunk_count
            )

            return result

        except Exception as exc:

            record_error("ingestion", exc)

            logger.exception(
                "Ingestion failed. Document ID: %s",
                document_id
            )

            raise

        finally:

            duration = time.perf_counter() - start_time

            INGESTION_ATTEMPT_LATENCY.labels(
                outcome=outcome
            ).observe(duration)

            INGESTION_ATTEMPTS.labels(
                outcome=outcome
            ).inc()

            INGESTION_IN_PROGRESS.dec()