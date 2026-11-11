# Insight-AI — Engineering Task Tracker

**Project:** Insight-AI — Production-ready PDF RAG assistant
**Status:** Not started
**Approach:** Complete one phase at a time. Review and test each major component before moving forward.

## Phase 1 — Database and access control

### TASK-01: Design and implement the database
**Priority:** P0
**Status:** Not started

- [ ] Create SQLite database connection and configuration.
- [ ] Create `users` table.
- [ ] Create `documents` table for document metadata.
- [ ] Create `jobs` table for ingestion and generation jobs.
- [ ] Create `idempotency_keys` table.
- [ ] Add foreign keys, indexes and timestamps.
- [ ] Implement database migrations.
- [ ] Create database service/repository layer.

**Acceptance criteria:**
- User, document and job records persist across application restarts.
- Document ownership can be traced to a user.
- Job status can be queried and updated.
- Database operations are tested.

### TASK-02: User authentication using JWT
**Priority:** P0
**Status:** Not started

- [ ] Implement user registration.
- [ ] Hash passwords securely.
- [ ] Implement login and JWT access tokens.
- [ ] Implement token validation.
- [ ] Implement logout/token revocation strategy.
- [ ] Protect private API endpoints.

**Acceptance criteria:**
- Users can register and log in.
- Invalid or expired tokens are rejected.
- Passwords are never stored in plaintext.
- Unauthenticated users cannot access protected endpoints.

### TASK-03: Authorization and data ownership
**Priority:** P0
**Status:** Not started

- [ ] Associate every document with a `user_id`.
- [ ] Validate ownership before document access.
- [ ] Add `user_id` and `document_id` to Pinecone metadata.
- [ ] Apply ownership filters to every vector search.
- [ ] Prevent cross-user access through guessed document IDs.
- [ ] Validate ownership for deletion and job-status endpoints.

**Acceptance criteria:**
- User A cannot access User B's PDF, vectors, metadata or jobs.
- Every document retrieval is scoped to the authenticated user.

### TASK-04: API rate limiting
**Priority:** P1
**Status:** Not started

- [ ] Add rate limiting to authentication endpoints.
- [ ] Add per-user upload limits.
- [ ] Add per-user chat request limits.
- [ ] Configure limits for expensive operations.
- [ ] Return appropriate `429 Too Many Requests` responses.
- [ ] Test concurrent requests and limit enforcement.

**Acceptance criteria:**
- Excessive requests are rejected predictably.
- Limits are configurable rather than hardcoded throughout the application.

## Phase 2 — Ingestion pipeline and resource management

### TASK-05: Safe asynchronous file handling
**Priority:** P1
**Status:** Not started

- [ ] Implement asynchronous file writing where appropriate.
- [ ] Stream uploaded files in bounded-size chunks.
- [ ] Enforce file size and PDF validation limits.
- [ ] Write uploads to temporary files.
- [ ] Atomically move validated files to final storage.
- [ ] Clean incomplete temporary files.

**Acceptance criteria:**
- Large uploads do not require loading the entire file into memory.
- Incomplete uploads do not appear as valid documents.
- File operations do not unnecessarily block the event loop.

### TASK-06: Document lifecycle management
**Priority:** P0
**Status:** Not started

- [ ] Define document states: `UPLOADING`, `PROCESSING`, `READY`, `FAILED`, `DELETE_PENDING`, `DELETED`.
- [ ] Implement valid state transitions.
- [ ] Persist state changes in SQLite.
- [ ] Add document status API.
- [ ] Handle failures at each ingestion stage.
- [ ] Prevent retrieval from documents that are not `READY`.

**Acceptance criteria:**
- Document status accurately reflects processing progress.
- Failed documents are not treated as searchable documents.
- Invalid state transitions are rejected.

### TASK-07: Separate ingestion job queue
**Priority:** P0
**Status:** Not started

- [ ] Separate ingestion execution from the upload endpoint.
- [ ] Implement a durable ingestion job queue.
- [ ] Create ingestion worker(s).
- [ ] Persist jobs before processing begins.
- [ ] Track queued, running, completed and failed states.
- [ ] Add configurable worker concurrency.

**Acceptance criteria:**
- Upload endpoint does not perform the entire ingestion pipeline synchronously.
- Accepted jobs survive an API process restart.
- Worker concurrency is configurable.

### TASK-08: Queue backpressure and resource limits
**Priority:** P0
**Status:** Not started

- [ ] Set maximum queue capacity.
- [ ] Limit concurrent ingestion jobs.
- [ ] Define maximum file size, pages and chunks.
- [ ] Limit embedding and generation concurrency.
- [ ] Reject or defer work when capacity is exhausted.
- [ ] Return clear overload responses.
- [ ] Measure queue depth and waiting time.

**Acceptance criteria:**
- The system cannot accept unlimited work.
- Resource limits are enforced before the system becomes unstable.
- Overloaded requests receive a predictable response.

### TASK-09: Partial embedding cleanup
**Priority:** P0
**Status:** Not started

- [ ] Generate stable vector IDs using document/version/chunk identifiers.
- [ ] Track the document version being ingested.
- [ ] Handle partial Pinecone upsert failures.
- [ ] Delete vectors belonging to a failed document version.
- [ ] Persist cleanup failures for later reconciliation.
- [ ] Prevent failed or incomplete document versions from being retrieved.

**Acceptance criteria:**
- Partial writes can be identified.
- Failed ingestion does not leave searchable orphaned vectors.
- Cleanup can be retried safely.

## Phase 3 — Job reliability and crash recovery

### TASK-10: Retry, idempotency and Dead Letter Queue
**Priority:** P0
**Status:** Not started

- [ ] Implement idempotency keys for upload/job creation.
- [ ] Prevent duplicate job creation during client retries.
- [ ] Implement exponential backoff with jitter.
- [ ] Define retryable and non-retryable errors.
- [ ] Configure maximum attempts.
- [ ] Move exhausted jobs into a DLQ.
- [ ] Implement a way to inspect and replay eligible DLQ jobs.

**Acceptance criteria:**
- Retried requests do not create duplicate ingestion operations.
- Transient failures are retried safely.
- Permanently failed jobs are visible and recoverable where appropriate.

### TASK-11: Basic crash recovery
**Priority:** P0
**Status:** Not started

- [ ] Persist job state before execution.
- [ ] Track worker start time and last heartbeat.
- [ ] Implement worker job leases or timeout detection.
- [ ] Detect jobs left in `RUNNING` after a crash.
- [ ] Requeue eligible expired jobs.
- [ ] Reconcile temporary files and incomplete document states.

**Acceptance criteria:**
- API or worker restarts do not silently lose accepted jobs.
- Stale jobs can be identified and safely recovered.
- Duplicate execution does not corrupt document/vector data.

### TASK-12: Advanced crash handling and recovery
**Priority:** P2
**Status:** Not started

- [ ] Add periodic reconciliation across SQLite, file storage and Pinecone.
- [ ] Handle worker termination during every ingestion stage.
- [ ] Handle database and vector-store connectivity failures.
- [ ] Implement orphaned file/vector detection.
- [ ] Add recovery procedures for partially completed deletion.
- [ ] Test restart and failure scenarios systematically.

**Acceptance criteria:**
- Cross-system inconsistencies are detectable.
- Recovery operations are idempotent.
- The system can recover without manual database editing in normal failure scenarios.

## Phase 4 — Answer quality and retrieval

### TASK-13: Answer sources and citation validation
**Priority:** P0
**Status:** Not started

- [ ] Preserve filename, page number and chunk ID during ingestion.
- [ ] Include source metadata in retrieved context.
- [ ] Ask the LLM to reference retrieved chunk IDs.
- [ ] Validate cited chunk IDs against retrieved results.
- [ ] Map valid citations to filename and page number.
- [ ] Return structured sources with the answer.
- [ ] Handle answers with insufficient supporting context.

**Acceptance criteria:**
- Every returned source maps to an actual retrieved chunk.
- The backend does not trust invented filenames or page numbers from the LLM.
- Users can identify where an answer came from.

### TASK-14: RAG evaluation using RAGAS
**Priority:** P1
**Status:** Not started

- [ ] Create a representative evaluation dataset.
- [ ] Define expected answers and supporting sources.
- [ ] Establish baseline retrieval and answer quality.
- [ ] Evaluate context precision and recall.
- [ ] Evaluate faithfulness and answer relevance.
- [ ] Track evaluation results across changes.
- [ ] Add regression evaluations for important questions.

**Acceptance criteria:**
- RAG quality is measured rather than judged only by manual inspection.
- Changes to chunking, retrieval or prompts can be compared against a baseline.

### TASK-15: Cross-encoder reranking
**Priority:** P2
**Status:** Not started

- [ ] Select a suitable cross-encoder model.
- [ ] Retrieve a candidate set from Pinecone.
- [ ] Rerank retrieved chunks using the cross-encoder.
- [ ] Select the final context for generation.
- [ ] Measure ranking quality and latency.
- [ ] Compare results against the baseline retriever.

**Acceptance criteria:**
- Reranking demonstrably improves retrieval quality.
- Additional latency and resource consumption are measured.
- The feature can be disabled through configuration.

## Phase 5 — Performance and observability

### TASK-16: Logging and observability
**Priority:** P0
**Status:** Not started

- [ ] Configure structured application logging.
- [ ] Add request IDs and job IDs.
- [ ] Log document and job lifecycle events.
- [ ] Track ingestion stage latency.
- [ ] Track retrieval and generation latency.
- [ ] Track failures, retries and queue wait time.
- [ ] Avoid logging secrets or sensitive document contents.

**Acceptance criteria:**
- A failed request/job can be traced across its processing stages.
- Logs contain enough context to diagnose common failures.

### TASK-17: Metrics and monitoring
**Priority:** P1
**Status:** Not started

- [ ] Track API request count and error rate.
- [ ] Track queue depth and worker utilization.
- [ ] Track CPU and memory usage.
- [ ] Track Pinecone latency and failures.
- [ ] Track embedding and LLM latency.
- [ ] Track token usage and cache hit rate.
- [ ] Configure basic alerts for abnormal failures and resource usage.

**Acceptance criteria:**
- Important reliability and performance indicators can be inspected over time.
- Resource saturation and growing queue backlogs are visible.

### TASK-18: Caching
**Priority:** P2
**Status:** Not started

- [ ] Identify repeated expensive operations.
- [ ] Implement embedding cache using content hash and model version.
- [ ] Implement query embedding cache where useful.
- [ ] Evaluate exact-answer caching.
- [ ] Evaluate semantic-answer caching.
- [ ] Scope caches by user, document/version and model configuration.
- [ ] Define invalidation for re-ingestion and deletion.

**Acceptance criteria:**
- Repeated operations can avoid unnecessary computation.
- Cached results cannot leak across users or document versions.
- Cache invalidation works when source documents change or are deleted.

## Phase 6 — Data governance and optimization

### TASK-19: Deletion and retention workflow
**Priority:** P1
**Status:** Not started

- [ ] Define and document retention rules.
- [ ] Implement document deletion endpoint.
- [ ] Mark documents `DELETE_PENDING`.
- [ ] Delete original PDFs.
- [ ] Delete associated Pinecone vectors.
- [ ] Invalidate related caches.
- [ ] Remove or expire related temporary job artifacts.
- [ ] Retry incomplete deletion operations.
- [ ] Implement scheduled cleanup of abandoned temporary files.

**Acceptance criteria:**
- Users can request document deletion.
- Related data is eventually removed from every storage layer.
- Failed deletion remains visible until resolved.

### TASK-20: Load testing and resource tuning
**Priority:** P1
**Status:** Not started

- [ ] Create representative upload and chat workloads.
- [ ] Test with increasing concurrent users.
- [ ] Measure p50 and p95 response latency.
- [ ] Measure ingestion throughput and queue wait time.
- [ ] Measure CPU, RAM and worker utilization.
- [ ] Identify bottlenecks.
- [ ] Tune worker count, queue limits and concurrency.
- [ ] Record performance baselines and test results.

**Acceptance criteria:**
- The system has measured operating limits.
- Concurrency settings are based on test results.
- Performance regressions can be identified.

---

## Progress tracker

| Phase | Tasks | Completion |
|---|---:|---|
| 1. Database and access control | 4 | 0/4 |
| 2. Ingestion and resource management | 5 | 0/5 |
| 3. Reliability and crash recovery | 3 | 0/3 |
| 4. Answer quality and retrieval | 3 | 0/3 |
| 5. Performance and observability | 3 | 0/3 |
| 6. Data governance and optimization | 2 | 0/2 |
| **Total** | **20** | **0/20** |

**Working agreement:** Complete a task, share the implementation/code and test results, and review it before marking it complete. Update the task status only after the acceptance criteria are satisfied.