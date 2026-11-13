# Insight-AI frontend rewrite — backend contract

This frontend is written for the FastAPI contracts in the uploaded project, with one required backend adjustment for asynchronous document status tracking.

## Endpoints used

### `POST /api/auth/register`
Request JSON:

```json
{"username":"arjun","email":"arjun@example.com","password":"password123"}
```

Expected: HTTP 201 and a user object. The frontend does not automatically sign the user in after registration.

### `POST /api/auth/login`
Request content type: `application/x-www-form-urlencoded`

Fields: `username`, `password`.

Expected response:

```json
{"access_token":"...","token_type":"bearer"}
```

### `GET /api/auth/me`
Authorization: `Bearer <access_token>`

Expected user fields include `id`, `username`, `email`, and `is_active`.

### `POST /api/documents`
Authorization: `Bearer <access_token>`
Request: multipart form data with field `file` containing the PDF.

Expected HTTP 202 response:

```json
{
  "document_id":"public-document-uuid",
  "job_id":"ingestion-job-uuid",
  "filename":"report.pdf",
  "document_status":"PROCESSING",
  "job_status":"PENDING",
  "message":"Document uploaded. Ingestion has been queued.",
  "created_at":"2026-11-12T12:00:00"
}
```

The frontend intentionally does not display `READY` based on the upload response. It waits for the documents endpoint to report the final state.

### `GET /api/documents`
Authorization: `Bearer <access_token>`

Expected response is an array of the current user's documents, including all statuses:

```json
[
  {"document_id":"public-document-uuid","filename":"report.pdf","status":"PROCESSING"},
  {"document_id":"another-document-uuid","filename":"notes.pdf","status":"READY"}
]
```

**Required backend adjustment:** the current uploaded `DocumentRepository.get_user_documents()` filters to `Document.status == "READY"`. Remove that filter so the frontend can observe `PROCESSING` and `FAILED` states as well. Keep the `user_id` filter and return only the authenticated user's documents. The router can continue returning `document_id`, `filename`, and `status`.

The frontend polls `GET /api/documents` every three seconds while at least one document is `QUEUED`, `PENDING`, `PROCESSING`, or `RUNNING`. It stops polling when no such document remains.

### `POST /api/chat`
Authorization: `Bearer <access_token>`
Request JSON:

```json
{
  "document_id":"public-document-uuid",
  "query":"Summarize the main argument.",
  "model":"Groq"
}
```

Allowed model values: `Gemini`, `Mistral`, `Groq`.

Expected response:

```json
{
  "answer":"The document argues that...",
  "follow_ups":["What evidence supports this?","What are the limitations?"]
}
```

The backend must ensure `answer` is a string and `follow_ups` is a list of strings. The current frontend renders content using `textContent`, not `innerHTML`.

## Important backend checks

1. The upload endpoint must be the function registered at `POST /api/documents`, not the low-level file-saving helper.
2. The upload route must return HTTP 202 and the response fields shown above.
3. The job record's `document_record_id` must reference `Document.id` (the integer database primary key), not `Document.document_id` (the public UUID).
4. `GET /api/documents` must include documents in non-terminal and failed states, not only READY documents.
5. `POST /api/chat` must validate document ownership and readiness, pass the authenticated `user_id` into retrieval, and return the `ChatResponse` schema.
6. `POST /api/auth/register` must persist `hashed_password`; the frontend expects the standard user response from the backend.

## Install

Replace these files in your project:

- `frontend/index.html`
- `frontend/static/auth.js`
- `frontend/static/app.js`
- `frontend/static/style.css`

Keep serving `/static` from `frontend/static` and `/` from `frontend/index.html`.

## Browser token note

This implementation retains the project's current `sessionStorage` Bearer-token approach. It is suitable as an initial integration, but JavaScript can read the token; an XSS vulnerability can therefore expose it. For a hardened browser deployment, consider an HttpOnly, Secure, SameSite cookie design with CSRF protection and a corresponding backend authentication change.

## Minimal backend alignment patch

Your uploaded snapshot's `DocumentRepository.get_user_documents()` filters to READY documents. For the frontend polling workflow, change it to return all statuses:

```python
def get_user_documents(self, user_id: int):
    return (
        self.db.query(Document)
        .filter(Document.user_id == user_id)
        .order_by(Document.created_at.desc())
        .all()
    )
```

Keep the router response user-scoped:

```python
@router.get("/documents")
def get_user_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repository = DocumentRepository(db)
    documents = repository.get_user_documents(current_user.id)
    return [
        {
            "document_id": item.document_id,
            "filename": item.filename,
            "status": item.status,
            "created_at": item.created_at,
        }
        for item in documents
    ]
```

The chat request model currently allows `Gemini`, `Mistral`, and `Groq`. In the uploaded snapshot, `src/generation/models.py` annotates `Provider` as `Literal["Gemini", "Mistral", "Together"]` even though its implementation has a Groq branch. Align that type alias with the actual supported providers:

```python
Provider = Literal["Gemini", "Mistral", "Groq"]
```
