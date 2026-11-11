INSIGHT-AI AUTHENTICATION FRONTEND INTEGRATION

Included files:
- index.html                  Replacement frontend HTML.
- static/auth.css             Additional styles for login/register and user session.
- static/auth.js              Registration, login, JWT session handling, /me validation and logout.
- static/app.js               Your existing app.js updated to:
                                1. attach JWT to upload and chat requests via authenticatedFetch()
                                2. keep cached document lists separated by user ID
                                3. restore that user's document UI state after authentication.

Integration:
1. Replace your frontend index.html with this index.html.
2. Keep your existing static/style.css unchanged.
3. Copy static/auth.css and static/auth.js into your existing static/ directory.
4. Replace your existing static/app.js with the included static/app.js.
5. Ensure FastAPI serves the frontend assets at /static/ and serves index.html at /.
6. Ensure the backend exposes POST /api/auth/register, POST /api/auth/login and GET /api/auth/me.
7. Add Depends(get_current_user) to protected backend endpoints such as POST /api/documents and POST /api/chat.
8. For document operations, also check that the requested document belongs to current_user.id. Apply user_id and document_id filters to Pinecone retrieval.

Login sends application/x-www-form-urlencoded fields named username and password because the backend uses OAuth2PasswordRequestForm.
Registration sends JSON fields username, email and password.

Token storage:
The sample stores the access token in sessionStorage for this initial implementation. It is accessible to JavaScript and is not the final production browser-security design. For production, consider HttpOnly Secure cookies and CSRF protection.

Document metadata:
The existing frontend stores document display metadata in localStorage. This update scopes that cache by authenticated user ID, but it does not replace a backend GET /api/documents endpoint. The backend database must remain the source of truth.

Logout:
Logout removes the token from this browser tab. The backend implementation currently has no server-side token revocation, so a copied token remains valid until its expiry.
