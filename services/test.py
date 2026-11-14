import time
import logging

from observability.metrics import (
    CHAT_REQUESTS,
    CHAT_TOTAL_LATENCY,
    CHAT_REQUESTS_IN_PROGRESS,
    CHAT_STAGE_LATENCY,
    RETRIEVED_CHUNKS,
    RERANK_INPUT_CHUNKS,
    RERANK_OUTPUT_CHUNKS,
    LLM_CALLS,
    record_llm_usage,
    record_embedding_tokens,
    record_error,
)

logger = logging.getLogger(__name__)


def generate_answer(
    self,
    question: str,
    user_id: int,
    document_id: str,
    provider: str,
    model_name: str
):

    start_time = time.perf_counter()

    outcome = "failure"

    CHAT_REQUESTS_IN_PROGRESS.inc()

    try:

        # =========================================
        # 1. RETRIEVAL
        # =========================================

        # Optional: count the query tokens using the
        # same tokenizer used by your embedding model.
        record_embedding_tokens(
            tokenizer=self.embedding_model.tokenizer,
            texts=question,
            operation="query",
            max_length=self.embedding_model.max_seq_length
        )

        with CHAT_STAGE_LATENCY.labels(
            stage="retrieval"
        ).time():

            retrieved_chunks = self.retriever.search_chunks(
                query=question,
                document_id=document_id,
                user_id=user_id,
                top_k=20
            )

        RETRIEVED_CHUNKS.observe(
            len(retrieved_chunks)
        )


        # =========================================
        # 2. RERANKING
        # =========================================

        if self.reranker:

            RERANK_INPUT_CHUNKS.observe(
                len(retrieved_chunks)
            )

            with CHAT_STAGE_LATENCY.labels(
                stage="reranking"
            ).time():

                reranked_chunks = self.reranker.rerank(
                    query=question,
                    documents=retrieved_chunks,
                    top_n=5
                )

            RERANK_OUTPUT_CHUNKS.observe(
                len(reranked_chunks)
            )

        else:
            reranked_chunks = retrieved_chunks


        # =========================================
        # 3. PROMPT CONSTRUCTION
        # =========================================

        with CHAT_STAGE_LATENCY.labels(
            stage="prompt_building"
        ).time():

            prompt = self.prompt_builder.build(
                question=question,
                contexts=reranked_chunks
            )


        # =========================================
        # 4. LLM GENERATION
        # =========================================

        try:

            with CHAT_STAGE_LATENCY.labels(
                stage="llm_generation"
            ).time():

                # Keep the raw response object so that
                # we can inspect its token-usage metadata.
                llm_response = self.llm.invoke(prompt)

            LLM_CALLS.labels(
                provider=provider,
                model=model_name,
                outcome="success"
            ).inc()

            record_llm_usage(
                response=llm_response,
                provider=provider,
                model=model_name
            )

        except Exception:
            LLM_CALLS.labels(
                provider=provider,
                model=model_name,
                outcome="failure"
            ).inc()

            raise


        # =========================================
        # 5. OUTPUT EXTRACTION / VALIDATION
        # =========================================

        with CHAT_STAGE_LATENCY.labels(
            stage="output_validation"
        ).time():

            answer = llm_response.content

            # Apply your existing response validation here.
            # For example, validate citations against the
            # retrieved chunk IDs.


        outcome = "success"

        return answer


    except Exception as exc:

        record_error("generation", exc)

        logger.exception(
            "Generation failed"
        )

        raise


    finally:

        elapsed = time.perf_counter() - start_time

        CHAT_TOTAL_LATENCY.labels(
            provider=provider,
            model=model_name
        ).observe(elapsed)

        CHAT_REQUESTS.labels(
            outcome=outcome,
            provider=provider,
            model=model_name
        ).inc()

        CHAT_REQUESTS_IN_PROGRESS.dec()