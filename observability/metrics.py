from prometheus_client import Counter, Histogram, Gauge


HTTP_REQUESTS = Counter(
    "insight_http_requests",
    "Total HTTP requests",
    ["method", "route", "status_code"]
)

HTTP_REQUEST_LATENCY = Histogram(
    "insight_http_request_duration_seconds",
    "Total HTTP request duration",
    ["method", "route"],
    buckets=(
        0.01, 0.05, 0.1, 0.25, 0.5,
        1, 2, 5, 10, 30, 60
    )
)

HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "insight_http_requests_in_progress",
    "Currently active HTTP requests",
    ["method"]
)



CHAT_REQUESTS = Counter(
    "insight_chat_requests",
    "Total chat requests",
    ["outcome", "provider", "model"]
)

CHAT_TOTAL_LATENCY = Histogram(
    "insight_chat_duration_seconds",
    "Complete chat service execution time",
    ["provider", "model"],
    buckets=(
        0.1, 0.25, 0.5, 1, 2, 3,
        5, 10, 20, 30, 60, 120
    )
)

CHAT_REQUESTS_IN_PROGRESS = Gauge(
    "insight_chat_requests_in_progress",
    "Currently processing chat requests"
)

CHAT_STAGE_LATENCY = Histogram(
    "insight_chat_stage_latency_seconds",
    "Latency of individual chat pipeline components",
    ["stage"],
    buckets=(
        0.001, 0.005, 0.01, 0.025,
        0.05, 0.1, 0.25, 0.5,
        1, 2, 5, 10, 30, 60
    )
)

RETRIEVED_CHUNKS = Histogram(
    "insight_retrieved_chunks",
    "Number of chunks returned by the retriever",
    buckets=(0, 1, 3, 5, 10, 20, 30, 50, 100)
)

RERANK_INPUT_CHUNKS = Histogram(
    "insight_rerank_input_chunks",
    "Number of candidates given to the reranker",
    buckets=(0, 1, 5, 10, 20, 30, 50, 100)
)

RERANK_OUTPUT_CHUNKS = Histogram(
    "insight_rerank_output_chunks",
    "Number of chunks retained after reranking",
    buckets=(0, 1, 3, 5, 10, 20, 30, 50)
)



LLM_CALLS = Counter(
    "insight_llm_calls",
    "Total LLM calls",
    ["provider", "model", "outcome"]
)

LLM_TOKENS = Counter(
    "insight_llm_tokens",
    "LLM tokens processed",
    ["provider", "model", "kind"]
)



EMBEDDING_TOKENS = Counter(
    "insight_embedding_tokens",
    "Tokens sent to the embedding model",
    ["operation"]
)



INGESTION_STAGE_LATENCY = Histogram(
    "insight_ingestion_stage_duration_seconds",
    "Duration of ingestion pipeline components",
    ["stage"],
    buckets=(
        0.01, 0.05, 0.1, 0.5, 1,
        2, 5, 10, 30, 60, 120, 300, 600
    )
)

INGESTION_ATTEMPT_LATENCY = Histogram(
    "insight_ingestion_attempt_duration_seconds",
    "Duration of one ingestion attempt",
    ["outcome"],
    buckets=(
        1, 2, 5, 10, 30, 60, 120, 300, 600
    )
)

INGESTION_JOB_LATENCY = Histogram(
    "insight_ingestion_job_duration_seconds",
    "End-to-end duration from job creation to terminal state",
    ["outcome"],
    buckets=(
        1, 5, 10, 30, 60, 120, 300, 600, 1200
    )
)

INGESTION_ATTEMPTS = Counter(
    "insight_ingestion_attempts",
    "Total ingestion attempts",
    ["outcome"]
)

INGESTION_JOBS = Counter(
    "insight_ingestion_jobs",
    "Terminal ingestion job outcomes",
    ["outcome"]
)

INGESTION_IN_PROGRESS = Gauge(
    "insight_ingestion_in_progress",
    "Currently running ingestion attempts"
)

INGESTION_QUEUE_WAIT = Histogram(
    "insight_ingestion_queue_wait_seconds",
    "Time spent waiting before a worker claims a job",
    buckets=(0.1, 1, 5, 10, 30, 60, 120, 300, 600)
)

INGESTION_QUEUE_DEPTH = Gauge(
    "insight_ingestion_queue_depth",
    "Number of jobs in each queue state",
    ["status"]
)

INGESTION_OLDEST_PENDING_AGE = Gauge(
    "insight_ingestion_oldest_pending_age_seconds",
    "Age of the oldest pending ingestion job"
)

INGESTION_PAGES = Histogram(
    "insight_ingestion_pages_per_document",
    "Number of pages per ingested document",
    buckets=(1, 5, 10, 25, 50, 100, 250, 500)
)

INGESTION_CHUNKS_PER_DOCUMENT = Histogram(
    "insight_ingestion_chunks_per_document",
    "Number of chunks created per document",
    buckets=(1, 5, 10, 25, 50, 100, 250, 500, 1000)
)

INGESTION_CHUNKS = Counter(
    "insight_ingestion_chunks",
    "Chunk operations",
    ["operation"]
)



VECTOR_OPERATIONS = Counter(
    "insight_vector_operations",
    "Pinecone vector operations",
    ["operation", "outcome"]
)


ERRORS = Counter(
    "insight_errors",
    "Application errors",
    ["component", "error_type"]
)

VALIDATION_FAILURES = Counter(
    "insight_validation_failures",
    "Input and output validation failures",
    ["component", "reason"]
)

RATE_LIMIT_REJECTIONS = Counter(
    "insight_rate_limit_rejections",
    "Requests rejected by rate limiting",
    ["route"]
)

RETRIES = Counter(
    "insight_retries",
    "Number of retried operations",
    ["component"]
)
MAINTENANCE_RUNS = Counter(
    "insight_maintenance_runs",
    "Periodic maintenance execution outcomes",
    ["outcome"]
)

MAINTENANCE_DURATION = Histogram(
    "insight_maintenance_duration_seconds",
    "Duration of maintenance operations",
    buckets=(0.1, 1, 5, 10, 30, 60, 120)
)

FILES_CLEANED = Counter(
    "insight_files_cleaned",
    "Number of files deleted by maintenance"
)



def record_error(component: str, exc: Exception):
    ERRORS.labels(
        component=component,
        error_type=type(exc).__name__
    ).inc()


def record_llm_usage(
    response,
    provider: str,
    model: str
):
    """
    Extract token usage from common LangChain/provider
    response structures.

    Call this while the original AIMessage/response object
    is still available.
    """

    def get_value(obj, key):
        if isinstance(obj, dict):
            return obj.get(key)

        return getattr(obj, key, None)

    metadata = get_value(response, "response_metadata")

    sources = [
        get_value(response, "usage_metadata"),
        get_value(metadata, "token_usage"),
        get_value(metadata, "usage"),
        get_value(response, "usage"),
        metadata,
    ]

    def find_integer(keys):
        for source in sources:
            for key in keys:
                value = get_value(source, key)

                if value is not None:
                    try:
                        return max(int(value), 0)
                    except (TypeError, ValueError):
                        continue

        return None

    input_tokens = find_integer([
        "input_tokens",
        "prompt_tokens",
        "prompt_token_count"
    ])

    output_tokens = find_integer([
        "output_tokens",
        "completion_tokens",
        "candidates_token_count"
    ])

    if input_tokens is not None:
        LLM_TOKENS.labels(
            provider=provider,
            model=model,
            kind="input"
        ).inc(input_tokens)

    if output_tokens is not None:
        LLM_TOKENS.labels(
            provider=provider,
            model=model,
            kind="output"
        ).inc(output_tokens)


def record_embedding_tokens(
    tokenizer,
    texts,
    operation: str,
    max_length: int | None = None
):
    """
    Count tokens using the embedding model's tokenizer.

    operation: query or documents
    """

    if isinstance(texts, str):
        texts = [texts]

    if not texts:
        return

    encoded = tokenizer(
        list(texts),
        add_special_tokens=True,
        padding=False,
        truncation=max_length is not None,
        **(
            {"max_length": max_length}
            if max_length is not None
            else {}
        )
    )

    token_count = sum(
        len(ids) for ids in encoded["input_ids"]
    )

    EMBEDDING_TOKENS.labels(
        operation=operation
    ).inc(token_count)


def update_queue_metrics(
    pending: int,
    running: int,
    oldest_pending_age_seconds: float
):
    INGESTION_QUEUE_DEPTH.labels(
        status="pending"
    ).set(pending)

    INGESTION_QUEUE_DEPTH.labels(
        status="running"
    ).set(running)

    INGESTION_OLDEST_PENDING_AGE.set(
        max(oldest_pending_age_seconds, 0)
    )


def record_job_claim(created_at):
    """
    Call once when a worker claims an ingestion job.
    Database timestamps are assumed to represent UTC.
    """

    from datetime import datetime, timezone

    if created_at is None:
        return

    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    wait_seconds = (
        datetime.now(timezone.utc) - created_at
    ).total_seconds()

    INGESTION_QUEUE_WAIT.observe(
        max(wait_seconds, 0)
    )


def record_terminal_job(outcome: str, created_at):
    """
    Call ONLY after the job has reached a terminal state
    and that transition has been committed.

    outcome: ready / failed / dead_letter
    """

    import time
    from datetime import datetime, timezone

    INGESTION_JOBS.labels(
        outcome=outcome
    ).inc()

    if created_at is None:
        return

    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    elapsed = (
        datetime.now(timezone.utc) - created_at
    ).total_seconds()

    INGESTION_JOB_LATENCY.labels(
        outcome=outcome
    ).observe(max(elapsed, 0))