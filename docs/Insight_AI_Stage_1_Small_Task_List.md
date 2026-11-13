# Insight-AI — Stage 1: Focused Engineering Task List

**Goal:** Make the existing PDF RAG application reliable, measurable, safer, and testable under controlled load without expanding into a large platform rewrite.

**Working rule:** Complete one task at a time. A task is complete only when its acceptance checks pass and the evidence is recorded.

## Stage 0 — Verify the current core

- [ ] Run the application from a clean environment and a fresh database migration.
- [ ] Verify the complete flow: register/login → upload (202) → queued job → ingestion → READY → chat response with real sources.
- [ ] Verify authorization and tenant isolation for documents, jobs, and vector retrieval.
- [ ] Turn every previously fixed critical bug into a regression test.

**Done when:** The core flow works end to end and a second user cannot access the first user's data.

## Task 1 — Monitoring and metrics baseline

- [ ] Add structured logs with `request_id`, `job_id`, `document_id`, and lifecycle events. Do not log secrets, full prompts, or document contents.
- [ ] Record API request/error counts and p50/p95 latency.
- [ ] Record queue depth, oldest pending-job age, queue wait, job duration, retries, and DLQ count.
- [ ] Record embedding, vector query/upsert, reranking, and LLM latency/errors; record token usage where available.
- [ ] Capture CPU and RAM during representative workloads.

**Done when:** A slow or failed request can be traced to the API, queue, embedding, vector store, reranker, or LLM provider, and a baseline report exists.

## Task 2 — Queue reliability, backpressure, DLQ, and vector cleanup

- [ ] Set bounded queue capacity and per-user/global ingestion concurrency limits; reject overload predictably (`429`/`503` with retry guidance).
- [ ] Add idempotent job creation so client retries do not create duplicate ingestion jobs.
- [ ] Classify retryable vs permanent failures; use bounded exponential backoff with jitter and a maximum attempt count.
- [ ] Move exhausted jobs to a DLQ with inspect/replay capability.
- [ ] Validate lease expiry and lock-token ownership so stale workers cannot update reclaimed jobs.
- [ ] Use deterministic vector IDs and an `ingestion_version`; expose only the active, fully completed version to retrieval.
- [ ] Make cleanup of failed/old versions idempotent and retryable.

**Done when:** The queue cannot grow without bounds; transient failures recover; exhausted jobs are inspectable; partial or stale vectors are never returned as valid document content.

## Task 3 — RAG evaluation and cross-encoder reranking

- [ ] Build a small, versioned golden dataset from representative PDFs: answerable, unanswerable, exact-fact, multi-page, and multi-hop questions.
- [ ] Record reference answers and expected supporting pages/chunks where practical.
- [ ] Run a RAGAS baseline before changing retrieval.
- [ ] Evaluate faithfulness, answer relevance, context precision, and context recall; manually review citation correctness on the golden set.
- [ ] Retrieve a larger candidate set, rerank with a cross-encoder, and pass only the best chunks to generation.
- [ ] Compare reranked results with the baseline for quality, latency, and memory; keep a configuration switch to disable reranking.

**Done when:** Evaluation is repeatable and the cross-encoder demonstrates a measured quality improvement that justifies its latency/resource cost. Do not keep it enabled solely because it has been integrated.

## Task 4 — Input/output validation and guardrails

- [ ] Validate request schemas, query length, allowed model names, document ownership, upload size, and PDF structure/page limits.
- [ ] Treat PDF text and retrieved chunks as untrusted input; add prompt-injection regression cases.
- [ ] Require a structured model response (answer, follow-ups, source IDs) and validate it before returning it to the frontend.
- [ ] Check every cited source ID against the actual retrieved chunks; resolve filename/page metadata on the server.
- [ ] Define safe behavior for malformed output, no relevant context, and unsupported questions.

**Done when:** Invalid requests and malformed model responses fail safely, and every displayed citation resolves to a real retrieved chunk. Guardrails do not replace authentication or authorization checks.

## Task 5 — Task-aware model router

- [ ] Define a small model registry/config for the tasks currently supported (initially chat).
- [ ] Store provider/model, context/output limits, timeout, and relevant generation settings in configuration.
- [ ] Route deterministically by task/configuration; do not ask another LLM to choose the model.
- [ ] Add bounded provider concurrency, timeouts, and fallback only for appropriate transient provider failures.
- [ ] Record selected provider/model, latency, token usage, and errors.

**Done when:** Model selection is configurable, observable, and covered by provider-failure tests.

## Task 6 — Rate limiting and resource protection

- [ ] Add IP-based limits for registration/login and per-user limits for upload/chat.
- [ ] Apply stricter limits to expensive chat/model operations.
- [ ] Bound concurrent LLM, embedding, and reranking work as well as request rate.
- [ ] Return predictable `429` responses and `Retry-After` where appropriate.
- [ ] Ensure the chosen limiter works across all API processes before running multiple workers.

**Done when:** Burst traffic cannot exhaust model/provider capacity or create unbounded work, and legitimate users receive predictable overload responses.

## Task 7 — Minimal chat memory

- [ ] Persist conversations and messages, each conversation owned by one user.
- [ ] Load only a bounded recent-message window into the prompt, together with the current document/RAG context.
- [ ] Keep conversation history separate from retrieved document evidence and validate ownership on every read/write.
- [ ] Provide a way to start a new conversation and delete/clear its history.

**Done when:** Follow-up questions can use recent turns in the same conversation, but one user's history cannot leak to another conversation or user.

**Scope boundary:** This means conversation history, not global personal memory, automatic long-term fact extraction, or rolling summaries. Defer those until there is a demonstrated need.

## Task 8 — Regression, RAG quality, failure, and Locust testing

- [ ] Add pytest unit and API/worker integration tests; use test DBs and mocked external providers for deterministic tests.
- [ ] Keep regression tests for auth, tenant isolation, upload/job lifecycle, retry/DLQ, vector cleanup, chat response schema, and citations.
- [ ] Run the golden RAG evaluation after changes to chunking, embeddings, retrieval, reranking, prompts, or models.
- [ ] Inject key failures: worker crash, Pinecone timeout/partial upsert, provider timeout/429, and DB unavailability.
- [ ] Create Locust scenarios for login, upload, status polling, and chat; ramp load gradually and record p50/p95/p99, errors, queue wait, CPU, and RAM.
- [ ] Run tests and lint/format checks in CI.
- [ ] Before using real user data, perform one database backup-and-restore drill.

**Done when:** Regression and failure tests pass, the RAG evaluation is recorded, and Locust establishes a measured safe operating envelope.

---

## Recommended implementation order

1. Stage 0 — Verify core correctness and tenant isolation.
2. Task 1 — Add monitoring and capture the baseline.
3. Task 2 — Make ingestion/queue/vector writes recoverable and bounded.
4. Task 3 — Build the RAGAS baseline, then add and compare the cross-encoder.
5. Tasks 4–6 — Add guardrails, deterministic model routing, and rate/resource limits.
6. Task 7 — Add minimal conversation-scoped memory.
7. Task 8 — Run regression, failure, quality, and Locust tests; close release gaps.

## Stage 1 release checklist

- [ ] Core upload-to-chat flow and tenant-isolation tests pass.
- [ ] Queue capacity, retries, DLQ, idempotency, lease recovery, and partial-vector cleanup are tested.
- [ ] RAGAS baseline and cross-encoder comparison are recorded; citations are validated.
- [ ] Input/output validation and prompt-injection regression cases pass.
- [ ] Model routing, provider timeouts, rate limits, and concurrency limits are tested.
- [ ] Conversation history is user-scoped and bounded.
- [ ] Logs/metrics and Locust results identify the system's supported operating envelope.
- [ ] CI checks and a basic backup/restore drill pass.

## Explicitly out of scope for this stage

Agents and tool calling, document summarization, global personal memory, automatic conversation summaries, semantic answer caching, multi-query/agentic retrieval, Kubernetes, and distributed infrastructure redesign.
