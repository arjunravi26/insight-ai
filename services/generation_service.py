import time
import logging

from src.generation.models import CreateModels, Provider
from src.generation.generate import Generate
from src.retrieval.retrive import Retriever
from src.retrieval.reranker import CrossEncoderReranker

from observability.metrics import (
    CHAT_REQUESTS,
    CHAT_TOTAL_LATENCY,
    CHAT_REQUESTS_IN_PROGRESS,
    CHAT_STAGE_LATENCY,
    RETRIEVED_CHUNKS,
    RERANK_INPUT_CHUNKS,
    RERANK_OUTPUT_CHUNKS,
    LLM_CALLS,
    record_error,
)

logger = logging.getLogger(__name__)


class GenerationService:

    def __init__(self, config):
        self.model_factory = CreateModels()
        self.retriever = Retriever(config=config)
        self.reranker = CrossEncoderReranker(config=config)
        self.rag_generator = Generate(self.model_factory)

    def generate_response(
        self,
        provider: Provider,
        query: str,
        document_id: str,
        user_id: int
    ) -> tuple:

        # Provider enum -> string for Prometheus labels
        provider_name = getattr(
            provider,
            "value",
            str(provider)
        )

        # Replace with the actual selected model name once
        # your model factory exposes it.
        model_name = "configured"

        total_start = time.perf_counter()
        outcome = "failure"

        CHAT_REQUESTS_IN_PROGRESS.inc()

        try:

            # =========================================
            # 1. RETRIEVAL
            # =========================================

            with CHAT_STAGE_LATENCY.labels(
                stage="retrieval"
            ).time():

                retrieved_chunks = self.retriever.search_chunks(
                    query=query,
                    document_id=document_id,
                    user_id=user_id
                )

            RETRIEVED_CHUNKS.observe(
                len(retrieved_chunks)
            )

            logger.info(
                "Retrieved %s chunks",
                len(retrieved_chunks)
            )

            # =========================================
            # 2. RERANKING
            # =========================================

            RERANK_INPUT_CHUNKS.observe(
                len(retrieved_chunks)
            )

            with CHAT_STAGE_LATENCY.labels(
                stage="reranking"
            ).time():

                reranked_chunks = self.reranker.rerank(
                    documents=retrieved_chunks,
                    query=query
                )

            RERANK_OUTPUT_CHUNKS.observe(
                len(reranked_chunks)
            )

            logger.info(
                "Reranked %s chunks",
                len(reranked_chunks)
            )

            # =========================================
            # 3. LLM GENERATION
            # =========================================

            try:

                with CHAT_STAGE_LATENCY.labels(
                    stage="llm_generation"
                ).time():

                    answer, follow_ups = self.rag_generator.generate(
                        query=query,
                        retrieved_chunks=reranked_chunks,
                        provider=provider
                    )

                LLM_CALLS.labels(
                    provider=provider_name,
                    model=model_name,
                    outcome="success"
                ).inc()

            except Exception:

                LLM_CALLS.labels(
                    provider=provider_name,
                    model=model_name,
                    outcome="failure"
                ).inc()

                raise

            outcome = "success"

            return answer, follow_ups

        except Exception as exc:

            record_error("generation", exc)

            logger.exception(
                "Failed to generate response"
            )

            raise

        finally:

            total_duration = (
                time.perf_counter() - total_start
            )

            CHAT_TOTAL_LATENCY.labels(
                provider=provider_name,
                model=model_name
            ).observe(total_duration)

            CHAT_REQUESTS.labels(
                outcome=outcome,
                provider=provider_name,
                model=model_name
            ).inc()

            CHAT_REQUESTS_IN_PROGRESS.dec()