# Insight-AI — Stage 1 Production Hardening Plan

**Stage:** 1 — Production hardening of the core RAG system  
**Goal:** Make the existing PDF RAG chatbot reliable, secure, measurable, testable, and capable of operating under controlled load.  
**Status:** Pending / In progress — update only after implementation and acceptance tests pass.  
**Working rule:** Complete one task at a time. Attach implementation notes, tests, and evidence before marking a task complete.

---

## Stage 1 scope

### Included

- Fix current integration and correctness bugs.
- Retrieval improvement with cross-encoder reranking.
- RAG evaluation using RAGAS.
- Input validation, prompt-injection protections, and output validation.
- Task-aware model routing for chat and other supported LLM tasks.
- Rate limiting and resource concurrency limits.
- Queue backpressure, retry policy, and dead-letter handling.
- Partial vector-store cleanup and ingestion idempotency.
- Structured monitoring, logs, and metrics.
- Unit, integration, regression, RAG quality, and Locust load testing.
- Minimal backup/restore and CI quality gates required for a credible release.

### Explicitly deferred

Do not add these in Stage 1 unless a core requirement forces the decision:

- Long-term chat memory and conversation summarization.
- Document summarization and hierarchical summaries.
- Semantic answer caching and broad caching infrastructure.
- Agents, tool calling, autonomous workflows, and multi-agent patterns.
- Complex distributed deployments or Kubernetes.

These can be considered after the core system has reliable quality and performance baselines.

---

# Phase 0 — Stabilize the existing application

**Priority:** P0  
**Purpose:** Remove integration defects before adding capabilities.

## TASK-01: End-to-end correctness and integration fixes

**Status:** In progress — fixes reported by developer; verify against the current working tree.

- [ ] Make the application start from a clean environment.
- [ ] Align `main.py`, `GenerationService`, `Retriever`, and `EmbeddingModel` constructor contracts.
- [ ] Ensure ingestion and retrieval share the intended embedding model instance within one process.
- [ ] Fix upload route registration and request/response contracts.
- [ ] Ensure the document is flushed before creating its job and that the job stores the correct `documents.id` foreign key.
- [ ] Pass `user_id` through ingestion and store it in vector metadata.
- [ ] Pass authenticated `user_id` into every retrieval query.
- [ ] Fix prompt-input contract between prompt preparation, RAG generation, and `chain.invoke()`.
- [ ] Ensure `GenerationService`, API response schemas, and frontend agree on answer, follow-ups, and sources.
- [ ] Preserve intended `HTTPException` status codes instead of converting them to generic 500 responses.
- [ ] Align provider names/types and configuration keys across API, model factory, and frontend.
- [ ] Align document/job status names and all foreign-key identifiers.
- [ ] Align SQLite timestamp handling and remove working-directory-dependent paths.
- [ ] Ensure document listing returns all authorized statuses, not only READY.

**Acceptance criteria:**

- [ ] Fresh database migration succeeds.
- [ ] User can register and log in.
- [ ] Authenticated user can upload a valid PDF and receives HTTP 202.
- [ ] Job references the correct document record.
- [ ] Worker completes ingestion and document becomes READY.
- [ ] User can ask a question and receives a structured answer and validated sources.
- [ ] A second user cannot access the first user's document or vectors.
- [ ] Frontend accurately displays QUEUED/PROCESSING/READY/FAILED states.

---

# Phase 1 — Establish quality and observability baselines

**Priority:** P0  
**Purpose:** Make the system measurable before optimizing it. Capture the current baseline before adding reranking, model routing, or caching.

## TASK-02: Structured logging and request/job correlation

**Status:** Pending

- [ ] Use structured logging with consistent fields.
- [ ] Add `request_id`, `user_id` (non-sensitive internal identifier), `document_id`, and `job_id` where applicable.
- [ ] Log document/job lifecycle transitions.
- [ ] Log ingestion stage start/end/failure: validation, extraction, chunking, embedding, vector upsert.
- [ ] Log retrieval, reranking, model invocation, and output-validation durations.
- [ ] Record exception class and retry classification.
- [ ] Never log passwords, JWTs, API keys, full prompts, or raw document content by default.

**Acceptance criteria:** A request or job can be traced across API, worker, retrieval, and generation logs without exposing secrets or document contents.

## TASK-03: Metrics collection

**Status:** Pending

- [ ] API request count, status codes, and error rate by endpoint.
- [ ] API latency: p50, p95, and p99.
- [ ] Upload size, page count, chunk count, and ingestion duration by stage.
- [ ] Queue depth, oldest pending-job age, queue wait time, job duration, retries, lease expirations, and DLQ size.
- [ ] Embedding latency, batch size, throughput, and failures.
- [ ] Pinecone query/upsert/delete latency and failures.
- [ ] Retrieval latency, candidate count, reranking latency, and final context count.
- [ ] LLM latency, token usage, provider errors, timeout count, and estimated cost.
- [ ] Cache hit rate when a cache is later introduced; do not build a cache solely to collect this metric.
- [ ] Process CPU, RAM, disk usage, and worker utilization.

**Acceptance criteria:** A developer can identify whether latency or failures originate in the API, queue, embedding model, vector store, reranker, or LLM provider.

## TASK-04: Define service-level objectives and performance baseline

**Status:** Pending

- [ ] Define target API availability and error rate for the initial deployment.
- [ ] Define target chat latency and ingestion completion objectives for representative document sizes.
- [ ] Separate upload acceptance latency from asynchronous ingestion completion time.
- [ ] Record a baseline before cross-encoder and model-router changes.
- [ ] Define resource ceilings for the development machine and target deployment.

**Acceptance criteria:** Performance improvements are compared with a recorded baseline, not subjective impressions. Targets are explicit and are not presented as measured results until load tests support them.

---

# Phase 2 — Ingestion reliability, queue protection, and vector consistency

**Priority:** P0  
**Purpose:** Ensure accepted ingestion work is bounded, retryable, and recoverable without leaving incomplete searchable data.

## TASK-05: Queue backpressure and admission control

**Status:** Pending

- [ ] Define maximum global pending-job count.
- [ ] Define maximum pending jobs per user.
- [ ] Define maximum concurrent ingestion jobs.
- [ ] Define maximum concurrent embedding operations and embedding batch size.
- [ ] Enforce file size, page count, chunk count, and processing-time limits.
- [ ] Define behavior when capacity is exhausted: reject or defer before accepting the job.
- [ ] Return a clear 429 or 503 response and `Retry-After` where appropriate.
- [ ] Ensure queue capacity checks and job creation cannot race into uncontrolled over-admission.
- [ ] Record queue depth, wait time, rejection count, and capacity utilization.

**Acceptance criteria:** The system cannot accept unlimited ingestion work; overload behavior is predictable and observable.

## TASK-06: Retry classification and dead-letter queue

**Status:** Pending

- [ ] Classify failures as retryable or permanent.
- [ ] Retry transient provider/network/database failures where safe.
- [ ] Do not retry invalid, corrupt, encrypted/unsupported PDFs unless the error is known to be transient.
- [ ] Implement exponential backoff with jitter and configurable maximum attempts.
- [ ] Preserve the final error category and useful diagnostic details.
- [ ] Mark exhausted jobs as DEAD/FAILED (choose one canonical terminal status and use it consistently).
- [ ] Add an admin-only way to inspect dead jobs.
- [ ] Add an explicit, audited replay operation that creates a safe new attempt or requeues an eligible job.
- [ ] Ensure document state remains consistent with terminal job state.

**Acceptance criteria:** Transient failures retry safely; permanent failures stop retrying; exhausted jobs remain visible and can be investigated or deliberately replayed.

## TASK-07: Idempotency for upload and job creation

**Status:** Pending — must be completed with queue/DLQ work.

- [ ] Enforce a unique idempotency scope, such as `(user_id, idempotency_key)`.
- [ ] Store a request fingerprint so the same key cannot be reused for a different upload payload.
- [ ] Return the existing document/job for a legitimate retry.
- [ ] Handle concurrent duplicate requests with database constraints and transaction-safe logic.
- [ ] Define key retention/expiration behavior.

**Acceptance criteria:** Retrying an upload after a timeout does not create duplicate document/job records or trigger duplicate ingestion unintentionally.

## TASK-08: Partial vector-store cleanup and versioned ingestion

**Status:** Pending

- [ ] Assign an ingestion version to each document ingestion attempt/version.
- [ ] Use deterministic vector IDs scoped by document/version/chunk.
- [ ] Store `user_id`, `document_id`, `ingestion_version`, chunk index, filename, and page metadata.
- [ ] Keep a version in STAGING/PROCESSING until all required upserts are confirmed.
- [ ] Make retrieval filter only the active/READY ingestion version.
- [ ] On failure, enqueue cleanup of vectors belonging to the failed version.
- [ ] When a new version is activated, retire/delete vectors from the previous version safely.
- [ ] Handle fewer chunks on re-ingestion so stale trailing chunks do not remain searchable.
- [ ] Persist cleanup failures and retry them independently.
- [ ] Make cleanup idempotent.

**Acceptance criteria:** Partial or failed vector writes are never exposed as a READY document; stale vectors are detectable and cleanup can be retried.

## TASK-09: Worker lease and crash-recovery validation

**Status:** Pending — lease implementation exists; verify and harden.

- [ ] Test atomic claim with two concurrent workers.
- [ ] Test lease renewal during long ingestion.
- [ ] Test reclaiming an expired RUNNING job.
- [ ] Test that an old lock token cannot mark success/failure or renew a reclaimed job.
- [ ] Bound heartbeat retry behavior during database outages.
- [ ] Define graceful shutdown timeout and behavior for in-flight ingestion.
- [ ] Reconcile RUNNING jobs, temporary files, and incomplete document states at startup/periodically.

**Acceptance criteria:** Crashes and restarts do not silently lose accepted jobs; stale workers cannot update a job after ownership has changed.

---

# Phase 3 — RAG quality and retrieval improvement

**Priority:** P0  
**Purpose:** Make retrieval measurable and improve ranking only when evaluation shows a benefit.

## TASK-10: RAG evaluation dataset and RAGAS baseline

**Status:** Pending

- [ ] Build a representative dataset from several document types and question types.
- [ ] Include answerable, unanswerable, multi-page, exact-fact, comparative, and multi-hop questions.
- [ ] Record reference answers and expected supporting source chunks/pages where practical.
- [ ] Establish the current retrieval and generation baseline before adding reranking.
- [ ] Evaluate context precision and context recall.
- [ ] Evaluate faithfulness and answer relevancy.
- [ ] Track failures by question type and document type.
- [ ] Version the dataset, prompts, embedding model, retrieval settings, and model configuration.
- [ ] Keep a small deterministic regression set for every code change; use RAGAS as a broader evaluation suite, not the sole correctness test.

**Acceptance criteria:** The team can compare retrieval and answer quality before/after changes using a repeatable, versioned evaluation set.

## TASK-11: Cross-encoder reranking

**Status:** Pending

- [ ] Select a cross-encoder compatible with the deployment's CPU/RAM/GPU budget.
- [ ] Retrieve a larger candidate set from Pinecone (initially benchmark sensible values such as 20–50; do not assume these are optimal).
- [ ] Rerank candidates using query-document relevance scores.
- [ ] Select a smaller final context set for generation.
- [ ] Preserve original source IDs, page numbers, and chunk metadata through reranking.
- [ ] Add a configuration flag to enable/disable reranking.
- [ ] Benchmark retrieval quality and added latency/memory.
- [ ] Compare against the no-reranker baseline on the same evaluation dataset.

**Acceptance criteria:** Reranking improves measured retrieval quality enough to justify its latency and resource cost. It must be possible to disable it without code changes.

## TASK-12: Citation validation and grounded response contract

**Status:** Pending — verify existing implementation.

- [ ] Give each retrieved chunk a server-generated source identifier.
- [ ] Ask the model to cite only supplied identifiers.
- [ ] Parse model output using a validated structured schema.
- [ ] Reject or remove citations that do not map to retrieved chunks.
- [ ] Resolve citation filename/page/chunk metadata on the server, never from model-generated metadata.
- [ ] Define behavior for no retrieved context and insufficient evidence.
- [ ] Return structured sources in the API response.
- [ ] Test malformed JSON, missing fields, duplicate IDs, and invented citations.

**Acceptance criteria:** Every displayed citation maps to an actual retrieved chunk; unsupported answers are handled explicitly.

---

# Phase 4 — Input/output safety and model routing

**Priority:** P0/P1  
**Purpose:** Apply consistent validation and select models based on task requirements, reliability, latency, and cost.

## TASK-13: Input validation and document safety

**Status:** Pending

- [ ] Validate request schemas, lengths, allowed model/task values, and document ownership.
- [ ] Enforce upload byte, page, chunk, and processing limits.
- [ ] Validate PDFs with a parser; extension and `%PDF-` signature checks alone are insufficient.
- [ ] Handle malformed, encrypted, unsupported, and decompression/resource-abusive documents safely.
- [ ] Treat PDF text and retrieved chunks as untrusted data.
- [ ] Add prompt-injection test documents containing instructions to reveal secrets, override system instructions, or request unauthorized actions.
- [ ] Ensure retrieved document instructions cannot change system policy or grant tool permissions.

**Acceptance criteria:** Invalid inputs are rejected predictably; document text is never treated as trusted system instructions.

## TASK-14: LLM output validation and response guardrails

**Status:** Pending

- [ ] Define Pydantic response schemas for answer, follow-ups, and citations.
- [ ] Validate provider output before returning it to the frontend.
- [ ] Enforce maximum answer/follow-up lengths and item counts.
- [ ] Validate citation identifiers against retrieved sources.
- [ ] Define safe behavior for malformed, empty, or non-JSON output.
- [ ] Avoid trusting the model to decide user authorization or document ownership.
- [ ] Add regression cases for prompt injection, unsupported claims, malformed responses, and refusal/insufficient-context behavior.

**Acceptance criteria:** Invalid model output cannot break the API response contract or create trusted, fabricated source metadata.

## TASK-15: Task-aware model router

**Status:** Pending

- [ ] Define explicit task types, initially at least `chat` and any already-supported auxiliary task.
- [ ] Define model profiles with provider, model name, context limit, output limit, temperature, timeout, and cost metadata.
- [ ] Route by explicit task/configuration rather than asking an LLM to choose every model.
- [ ] Support separate model choices for chat and future summarization without implementing summarization in this stage.
- [ ] Add provider-specific timeout and retry policies.
- [ ] Add fallback only for appropriate transient provider failures.
- [ ] Do not fallback on validation, authorization, or unsupported-input errors.
- [ ] Record selected provider/model, latency, tokens, and estimated cost.
- [ ] Keep provider secrets in environment/secret configuration, never source code.

**Acceptance criteria:** Model selection is configurable and observable; a provider failure follows a tested policy without silently changing task behavior.

---

# Phase 5 — Rate limiting and capacity protection

**Priority:** P1  
**Purpose:** Protect the API, model providers, vector store, and local resources from accidental or abusive overload.

## TASK-16: API rate limiting

**Status:** Pending

- [ ] Apply IP-based limits to registration and login.
- [ ] Apply per-user limits to chat and upload endpoints.
- [ ] Use stricter limits for expensive model operations.
- [ ] Return HTTP 429 with `Retry-After` when appropriate.
- [ ] Make limits configurable by endpoint and user tier.
- [ ] Avoid leaking account existence through authentication throttling responses.
- [ ] Choose a shared rate-limit store before running multiple API processes; do not rely on process-local counters for multi-process production.
- [ ] Test bursts and sustained request rates.

**Acceptance criteria:** Limits are enforced consistently and do not depend on which API process receives the request.

## TASK-17: Concurrency and provider/resource limits

**Status:** Pending

- [ ] Bound simultaneous embedding operations.
- [ ] Bound simultaneous LLM requests per provider/model.
- [ ] Bound concurrent reranking operations.
- [ ] Define per-user and global ingestion concurrency limits.
- [ ] Handle provider 429 responses with bounded backoff.
- [ ] Prevent unbounded thread-pool submission.
- [ ] Measure saturation and queue wait time.

**Acceptance criteria:** The system degrades predictably under load rather than exhausting RAM, threads, provider quotas, or database connections.

---

# Phase 6 — Regression, quality, failure, and load testing

**Priority:** P0  
**Purpose:** Prove the system works and quantify its operating envelope.

## TASK-18: Automated test foundation and CI quality gates

**Status:** Pending — important addition to the original list.

- [ ] Add pytest and a defined test directory/fixtures.
- [ ] Unit-test repositories and service state transitions.
- [ ] Integration-test API contracts and database transactions.
- [ ] Use fake/mock LLM and Pinecone adapters for deterministic tests.
- [ ] Add tests for authorization and tenant isolation.
- [ ] Add tests for idempotency, duplicate requests, and concurrent job claims.
- [ ] Add migration-from-empty-database tests.
- [ ] Add linting, formatting, and type-checking commands.
- [ ] Run tests and checks in CI for each change.

**Acceptance criteria:** A clean checkout can install dependencies, migrate an empty test database, and run automated checks consistently.

## TASK-19: Regression testing

**Status:** Pending

- [ ] Test registration, login, authentication expiry, and authorization.
- [ ] Test upload validation, HTTP 202 contract, and document listing.
- [ ] Test job lifecycle and frontend polling.
- [ ] Test successful ingestion and each failure stage.
- [ ] Test chat response schema and frontend rendering.
- [ ] Test user/document/vector isolation.
- [ ] Test deletion/cleanup if deletion functionality is included in the current release.
- [ ] Run the fixed regression set after changes to prompts, chunking, embedding models, retrieval, reranking, or model routing.

**Acceptance criteria:** Previously fixed behavior remains correct after every relevant change.

## TASK-20: Failure-injection and recovery testing

**Status:** Pending

- [ ] Simulate worker crash after claim.
- [ ] Simulate crash during extraction, embedding, and Pinecone upsert.
- [ ] Simulate crash after successful upsert but before database success update.
- [ ] Simulate Pinecone timeout/partial failure.
- [ ] Simulate database lock/temporary unavailability.
- [ ] Simulate provider timeout, rate limit, and server error.
- [ ] Verify lease recovery, retry, DLQ, and vector cleanup.
- [ ] Verify no document becomes READY before its active vector version is complete.

**Acceptance criteria:** Each expected failure has a defined, tested recovery or terminal-failure behavior.

## TASK-21: RAG quality testing

**Status:** Pending

- [ ] Run RAGAS baseline and post-change evaluations.
- [ ] Compare no-reranker vs cross-encoder configurations.
- [ ] Test answer faithfulness, relevance, context precision, and context recall.
- [ ] Manually review important failure cases and citation correctness.
- [ ] Track evaluation results by version and model configuration.
- [ ] Define minimum release thresholds based on measured baseline and use case; do not invent thresholds without evidence.

**Acceptance criteria:** The chosen RAG configuration has measurable quality and no unexplained regression on the agreed evaluation set.

## TASK-22: Locust load and capacity testing

**Status:** Pending

- [ ] Create Locust scenarios for authentication, document upload, status polling, and chat.
- [ ] Test realistic document sizes and question distributions.
- [ ] Ramp users gradually rather than starting at maximum concurrency.
- [ ] Measure p50/p95/p99 latency, throughput, errors, queue wait, ingestion duration, CPU, RAM, and provider throttling.
- [ ] Test steady-state and burst traffic.
- [ ] Test overload behavior and recovery after load drops.
- [ ] Record worker/concurrency settings and the environment used.
- [ ] Identify a supported operating envelope and document it.

**Acceptance criteria:** Performance limits are measured and documented; queue and resource protection work under load; no unacceptable tenant leak or data corruption occurs.

---

# Phase 7 — Minimum operational readiness

**Priority:** P1  
**Purpose:** Make the system recoverable and reproducible outside the developer's laptop.

## TASK-23: Database backup and restore drill

**Status:** Pending — important addition.

- [ ] Define backup frequency and retention for the SQLite database at the current deployment scale.
- [ ] Use a SQLite-safe backup method; do not copy a live database file blindly when WAL mode is enabled.
- [ ] Document what is stored in SQLite versus local file storage versus Pinecone.
- [ ] Test restoring the database into a clean environment.
- [ ] Verify documents, jobs, users, and migration revision after restore.
- [ ] Document how vectors can be rebuilt/reconciled from retained source files and metadata.

**Acceptance criteria:** A restore drill succeeds and the recovery procedure is documented. A backup is not considered valid until restoration has been tested.

## TASK-24: Release and operations documentation

**Status:** Pending

- [ ] Document environment variables and secret provisioning.
- [ ] Document clean installation, migrations, startup, shutdown, and worker operation.
- [ ] Document rate limits, queue limits, and supported workload assumptions.
- [ ] Document provider fallback behavior and operational failure modes.
- [ ] Document database backup/restore and vector reconciliation.
- [ ] Document how to inspect and replay dead-letter jobs.
- [ ] Add a release checklist and rollback procedure.

**Acceptance criteria:** Another engineer can deploy, operate, diagnose, and recover the application using the documentation without relying on undocumented local state.

---

# Recommended execution order

1. **Phase 0:** Fix and verify existing correctness/integration issues.
2. **Phase 1:** Add basic logs and metrics early; record a baseline.
3. **Phase 2:** Complete backpressure, retry/DLQ, idempotency, vector cleanup, and recovery.
4. **Phase 3:** Create RAGAS baseline, implement cross-encoder, validate citations.
5. **Phase 4:** Implement input/output safety and task-aware model routing.
6. **Phase 5:** Enforce API rate limits and model/worker concurrency limits.
7. **Phase 6:** Run automated regression, failure-injection, RAG quality, and Locust tests.
8. **Phase 7:** Complete backup/restore and operational documentation.

The ordering is intentional: measure before optimizing; make ingestion safe before increasing load; establish a retrieval baseline before deciding whether reranking helps; and test the complete system before calling the stage complete.

---

# Stage 1 release gates

Do not mark Stage 1 complete until all of the following are true:

- [ ] Fresh install and migration from an empty database work.
- [ ] End-to-end upload → 202 → queued job → ingestion → READY works.
- [ ] End-to-end chat returns a validated answer and real source references.
- [ ] Cross-user document and vector access tests pass.
- [ ] Queue capacity, concurrency limits, retry, DLQ, lease recovery, and idempotency tests pass.
- [ ] Partial vector writes cannot become visible as a READY version.
- [ ] RAGAS evaluation and reranker comparison are recorded.
- [ ] Input/output validation and prompt-injection regression cases pass.
- [ ] Model routing, provider timeouts, and fallback behavior are tested.
- [ ] Structured logs and metrics allow diagnosis of API, ingestion, retrieval, and generation failures.
- [ ] Locust tests establish the supported operating envelope.
- [ ] Database backup restoration has been demonstrated.
- [ ] CI runs automated tests and code-quality checks.

---

# Deferred backlog — do not pull into Stage 1

These are valuable, but should follow the first-stage release gates:

- Persistent chat memory and conversation summaries.
- Document summarization, hierarchical map/reduce summaries, and summary refresh on re-ingestion.
- Semantic answer cache and broader multi-layer caching.
- Advanced query rewriting, multi-query retrieval, and agentic retrieval.
- Multi-modal PDF/image understanding.
- Feedback-driven retrieval tuning and personalization.
- Distributed worker deployment and Kubernetes.

---

## Working agreement

For every task:

1. Agree on the requirement and acceptance criteria.
2. Inspect the current implementation before changing it.
3. Implement the smallest suitable design.
4. Add tests for success, failure, and relevant concurrency/security cases.
5. Run the tests and record evidence.
6. Review maintainability, latency, resource impact, and security.
7. Only then mark the task complete.

**Engineering principle:** Stage 1 is complete when the system demonstrates correct and measurable behavior under expected failures and controlled load—not when every checkbox has code behind it.
