# Insight-AI — System Design Note

**Purpose:** Build a reliable, secure PDF-based RAG assistant that allows authenticated users to upload documents, ask questions about selected documents, and receive answers with verifiable sources.

## 1. High-level architecture

```text
                         ┌─────────────────────┐
                         │    Web Frontend     │
                         │ Upload / Chat / Docs│
                         └──────────┬──────────┘
                                    │ HTTPS
                                    ▼
                 ┌──────────────────────────────────┐
                 │          FastAPI Backend         │
                 │                                  │
                 │ Authentication (JWT)             │
                 │ Authorization / Ownership        │
                 │ Rate Limiting / Request Validation│
                 │ Resource Limits / Guardrails      │
                 └──────────────┬───────────────────┘
                                │
                  ┌─────────────┴──────────────┐
                  │                            │
                  ▼                            ▼
       ┌────────────────────┐       ┌────────────────────┐
       │  Document Upload   │       │    Chat Endpoint   │
       │  + Job Creation    │       │  + Query Validation│
       └──────────┬─────────┘       └──────────┬─────────┘
                  │                            │
                  ▼                            ▼
       ┌────────────────────┐       ┌────────────────────┐
       │  File Storage      │       │  Cache Layer       │
       │  Temp → Final      │       │  Exact / Semantic  │
       └──────────┬─────────┘       └──────────┬─────────┘
                  │                            │
                  ▼                            ▼
       ┌────────────────────┐       ┌────────────────────┐
       │ Durable Job Queue  │       │ Retrieval Service  │
       │ Backpressure       │       │ Tenant + Doc Filter│
       └──────────┬─────────┘       └──────────┬─────────┘
                  │                            │
                  ▼                            ▼
       ┌────────────────────┐       ┌────────────────────┐
       │ Ingestion Workers  │       │  Cross-Encoder     │
       │                    │       │  (Optional)        │
       │ PDF Validation     │       └──────────┬─────────┘
       │ Extraction         │                  │
       │ Chunking            │                  ▼
       │ Embedding           │       ┌────────────────────┐
       └──────────┬─────────┘       │ Context Assembly   │
                  │                 └──────────┬─────────┘
                  ▼                            │
       ┌────────────────────┐                  ▼
       │ Pinecone Vector DB │       ┌────────────────────┐
       │ Tenant/Doc Metadata│       │     LLM Provider   │
       └──────────┬─────────┘       └──────────┬─────────┘
                  │                            │
                  ▼                            ▼
       ┌────────────────────┐       ┌────────────────────┐
       │ Verify & Update DB │       │ Citation Validation│
       │ Document = READY   │       │ Guardrails         │
       └────────────────────┘       └──────────┬─────────┘
                                               │
                                               ▼
                                      ┌────────────────────┐
                                      │ Answer + Sources   │
                                      └────────────────────┘

                 ┌──────────────────────────────────┐
                 │        SQLite Database           │
                 │ Users / Documents / Jobs         │
                 │ Idempotency / Status / Metadata  │
                 └──────────────────────────────────┘

                 ┌──────────────────────────────────┐
                 │ Observability & Reliability      │
                 │ Logs / Metrics / Alerts          │
                 │ Retries / DLQ / Reconciliation  │
                 └──────────────────────────────────┘
```

## 2. Core components

### A. Authentication, authorization and data isolation

- Implement user registration and login with password hashing and JWT-based authentication.
- Every document belongs to a specific user.
- Every document operation must verify ownership on the backend.
- Store `user_id` and `document_id` in document records and Pinecone metadata.
- Every vector search must filter by both the authenticated user's identity and the requested document.
- Never trust a `document_id` supplied by the frontend without checking database ownership.

**Important:** JWT proves identity; database ownership checks enforce authorization.

### B. Database and file storage

Use SQLite initially for this single-instance learning project.

The database is the source of truth for users, documents and processing jobs. Pinecone stores searchable vectors; it should not be the only place where document ownership or processing status is maintained.

Suggested tables:

| Table | Responsibility |
|---|---|
| `users` | User accounts and authentication data |
| `documents` | Owner, filename, storage path, status, size, version |
| `jobs` | Ingestion/generation job state, attempts and errors |
| `idempotency_keys` | Prevent duplicate operations |
| `audit_logs` | Important user and system actions |

Suggested document states:

`UPLOADING → PROCESSING → READY`

Failure or deletion states:

`FAILED`, `DELETE_PENDING`, `DELETED`

Store files using a temporary file followed by an atomic rename after upload and validation. Keep original PDFs so documents can be reprocessed if the embedding model or chunking strategy changes.

SQLite is suitable for the initial single-instance version. Plan to migrate to PostgreSQL when concurrent writes, multiple API instances or multiple workers become important.

### C. Document ingestion and durable job queue

The upload endpoint should:

1. Authenticate the user and validate the request.
2. Enforce file size, file type and page-count limits.
3. Create the document and job records.
4. Save the PDF safely.
5. Submit the ingestion job to a bounded, durable queue.
6. Return `202 Accepted` with a `document_id` and `job_id`.

The worker performs:

`PDF Validation → Extraction → Cleaning → Chunking → Embedding → Pinecone Upsert → Verification → READY`

The client can poll a job-status endpoint such as:

`GET /api/jobs/{job_id}`

Use a durable queue rather than relying on an in-memory queue for production work. For the initial version, a database-backed job table and worker polling can be sufficient. Later, introduce Redis with RQ, Celery or another durable job-processing system.

### D. Partial failures, retries and idempotency

Pinecone writes and SQLite transactions cannot be committed as one atomic operation. Design for partial failure.

- Generate deterministic vector IDs using the document version and chunk index.
- Make repeated ingestion attempts safe to execute.
- If an ingestion fails after partial Pinecone writes, attempt compensating deletion for that document version.
- If cleanup also fails, mark the document `DELETE_PENDING` or `FAILED` and schedule reconciliation.
- Use exponential backoff with jitter for transient failures.
- Do not retry invalid PDFs or other permanent validation failures.
- After a configured maximum number of attempts, move the job to a Dead Letter Queue (DLQ).

Use an idempotency key for upload/job creation so a client retry does not unintentionally create duplicate documents or jobs.

### E. Chat and generation workflow

The chat path should:

1. Authenticate the user.
2. Validate the query and document ownership.
3. Apply input guardrails.
4. Check the appropriate cache.
5. Retrieve chunks using user and document filters.
6. Optionally rerank retrieved chunks.
7. Assemble context and call the selected LLM.
8. Validate citations and output.
9. Return the answer and source metadata.

For normal interactive chat, use a regular response or streaming. Use `202 Accepted` and job polling for generation that is genuinely long-running or needs to run asynchronously. Do not create a job for every short chat request without a measured need.

### F. Sources and citation validation

The LLM should return references to retrieved chunk IDs, not invent page numbers or filenames.

The backend must validate every cited chunk ID against the retrieved context and map it to trusted metadata such as:

- Original filename
- Page number
- Chunk ID
- Optional text snippet

Only validated references should be returned as sources. The LLM generates the answer; the backend verifies the source references.

### G. Resource management and backpressure

Do not accept unlimited uploads or unlimited concurrent processing.

Introduce:
- Maximum PDF size, page count and chunk count.
- Maximum concurrent ingestion workers.
- Bounded queue capacity.
- Per-user upload and request quotas.
- Limits on generation concurrency and input tokens.
- Clear overload responses, such as `429` or `503` with `Retry-After`.

Use asynchronous I/O where it helps, but do not make everything asynchronous simply for appearance. `aiofiles` can help with asynchronous file operations, but it does not make PDF parsing or embedding computation non-blocking. Use bounded thread/process workers for synchronous or CPU-heavy operations and measure resource usage before increasing concurrency.

### H. Cache and retrieval optimization

Introduce caching in stages:

1. Cache embeddings using a key based on chunk content hash and embedding model version.
2. Cache query embeddings where useful.
3. Add exact-answer caching for repeated requests.
4. Consider semantic answer caching only after establishing safe cache boundaries.

Cache keys must include the user/tenant scope, relevant document versions, model and prompt versions, and retrieval configuration. Never allow one user's cached answer to leak to another user.

A cross-encoder reranker is an optional retrieval improvement. First retrieve a larger candidate set, then rerank it and pass only the best results to the LLM. Add it after retrieval evaluation shows a meaningful ranking problem, since it adds latency and compute cost.

## 3. Security and guardrails

- Rate limiting on authentication, upload and chat endpoints.
- Input validation and upload/parser validation.
- Prompt-injection checks during ingestion and cautious handling of retrieved document content at generation time.
- Input and output guardrails for inappropriate or unsupported requests.
- Strict tenant and document isolation in retrieval and caching.
- Secure secret management; never log API keys or sensitive document contents.
- HTTPS, appropriate CORS/CSRF protection and secure token handling.
- Audit important actions such as uploads, deletions and authentication events.

Prompt-injection detection is not a guarantee that a document is safe. Treat PDF content as untrusted data, not as instructions that can override the system prompt.

## 4. Retention and deletion policy

For the initial product, propose a **90-day inactivity retention period** for uploaded PDFs, clearly disclosed to users and configurable as product requirements evolve. Allow users to delete documents immediately.

Deletion must cover all related data:

- Original PDF
- SQLite document metadata
- Pinecone vectors
- Cached embeddings and answers
- Associated jobs and temporary artifacts

Use a `DELETE_PENDING` state and retry cleanup until all stores confirm deletion. Keep temporary or abandoned upload files for no longer than 24 hours before cleanup. Retention duration is a product/privacy decision, not a universal technical standard.

## 5. Observability and evaluation

Track structured logs and metrics with `request_id`, `job_id`, `user_id` and `document_id`.

Important metrics include:
- Upload size, page count and ingestion failures.
- Extraction, chunking and embedding latency.
- Queue depth, queue wait time and job failure/retry counts.
- Pinecone upsert and retrieval latency.
- Retrieval scores and reranking latency.
- LLM latency, token usage, errors and cost.
- Chat latency, cache hit rate and API error rate.
- CPU, RAM and worker utilization.

Use RAGAS as one component of evaluation. Maintain a small representative test set with expected answers and supporting sources. Evaluate retrieval quality and answer faithfulness separately, and manually inspect failures. Automated scores alone should not determine production quality.

A reconciliation task should periodically detect stale jobs, orphaned files, inconsistent document states and vectors belonging to failed or deleted document versions.

## 6. Reliability patterns

| Pattern | Purpose |
|---|---|
| Retry with backoff | Recover from transient failures |
| Idempotency | Make safe retries possible |
| Dead Letter Queue | Isolate jobs that repeatedly fail |
| Circuit breaker | Stop repeatedly calling an unhealthy dependency |
| Backpressure | Prevent resource exhaustion |
| Reconciliation worker | Repair inconsistencies across storage systems |
| Health/readiness checks | Report whether the API can serve traffic |

## 7. Implementation roadmap

**Phase 1 — Reliable single-instance foundation**
- SQLite schema and backend document listing.
- JWT authentication and document ownership.
- Safe upload, atomic file writes and validation.
- Document/job status lifecycle.
- Pinecone metadata filters and partial-write cleanup.
- Source-backed citations.
- Basic limits, logging and unit/integration tests.

**Phase 2 — Asynchronous processing and reliability**
- Durable ingestion job queue and `202 Accepted`.
- Bounded workers and backpressure.
- Retry, idempotency and DLQ.
- Generation jobs where latency requires them.
- Deletion and retention workflow.
- Rate limiting and circuit breakers.

**Phase 3 — Retrieval quality and performance**
- Embedding/query/answer caching.
- Cross-encoder reranking.
- RAGAS evaluation and regression dataset.
- Detailed metrics, dashboards and alerts.
- Load testing and resource tuning.

**Phase 4 — Scale**
- PostgreSQL.
- Redis-backed queue and cache.
- Object storage for PDFs.
- Separate API and worker deployments.
- Horizontal scaling, distributed tracing and automated recovery.

## 8. Definition of done

The system should be considered ready for its next stage when:

- A user cannot access another user's documents or vectors.
- A failed or repeated upload does not create duplicate or orphaned data.
- Partial Pinecone writes can be detected and cleaned up.
- Queue overload is controlled instead of exhausting system resources.
- Deleted documents are eventually removed from every storage layer.
- Returned citations can be verified against retrieved chunks.
- Worker/API restarts do not silently lose accepted jobs.
- Evaluation and load tests provide measurable quality and performance baselines.

**Design principle:** Start with a dependable single-instance system. Keep clear boundaries between API, services, workers, database, file storage and vector storage. Introduce distributed infrastructure only when real workload or reliability requirements justify it.