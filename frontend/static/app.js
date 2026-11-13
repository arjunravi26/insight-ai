(() => {
  "use strict";

  const API_BASE = "/api";
  const MAX_FILE_SIZE = 20 * 1024 * 1024;

  const POLL_INTERVAL_MS = 3000;
  const MAX_POLL_INTERVAL_MS = 15000;
  const MAX_POLL_DURATION_MS = 10 * 60 * 1000;

  const PROCESSING_STATUSES = new Set([
    "QUEUED",
    "PENDING",
    "PROCESSING",
    "RUNNING"
  ]);

  const READY_STATUS = "READY";
  const FAILED_STATUS = "FAILED";
  const TIMEOUT_STATUS = "TIMEOUT";

  const $ = (id) => document.getElementById(id);
  const elements = {
    messages: $("messages"),
    welcome: $("welcome-screen"),
    chatContainer: $("chat-container"),
    followupContainer: $("followup-container"),
    followupButtons: $("followup-buttons"),
    chatForm: $("chat-form"),
    userInput: $("user-input"),
    sendButton: $("send-button"),
    modelSelect: $("model-select"),
    clearButton: $("clear-chat"),
    pdfInput: $("pdf-input"),
    uploadButton: $("upload-button"),
    documentSelect: $("document-select"),
    uploadStatus: $("upload-status"),
    activeDocumentName: $("active-document-name"),
    activeDocumentDot: $("activeDocumentDot"),
    documentCount: $("documentCount")
  };

  const state = {
    user: null,
    documents: [],
    selectedDocumentId: null,
    chatHistory: [],

    isUploading: false,
    isProcessing: false,
    isLoadingDocuments: false,

    // One timer drives polling for all documents, each with its own deadline.
    pollTimer: null,
    pollNextDelay: POLL_INTERVAL_MS,
    pollingDocuments: new Map(),

    // Keep a newly accepted document visible until GET /documents returns it.
    locallyAcceptedDocuments: new Map()
  };

  function setNotice(message, type = "info") {
    elements.uploadStatus.textContent = message;
    elements.uploadStatus.dataset.type = type;
  }

  function normalizeDocument(raw) {
    return {
      document_id: String(raw.document_id),
      filename: String(raw.filename || "Untitled document"),
      status: String(raw.status || raw.document_status || "PROCESSING").toUpperCase(),
      created_at: raw.created_at || null
    };
  }

  function getSelectedDocument() {
    return state.documents.find((doc) => doc.document_id === state.selectedDocumentId) || null;
  }

  function isSelectedDocumentReady() {
    return getSelectedDocument()?.status === READY_STATUS;
  }

  function updateControls() {
    const selected = getSelectedDocument();
    const ready = selected?.status === READY_STATUS;
    const busy = state.isUploading || state.isProcessing;

    elements.sendButton.disabled = !ready || busy;
    elements.userInput.disabled = !ready || busy;
    elements.documentSelect.disabled = state.documents.length === 0 || busy;
    elements.uploadButton.disabled = busy;
    elements.modelSelect.disabled = busy;
    elements.clearButton.disabled = state.isProcessing;

    elements.userInput.placeholder = !selected
      ? "Select a ready document to ask a question…"
      : selected.status !== READY_STATUS
        ? `Document is ${selected.status.toLowerCase()}…`
        : "Ask a question about this document…";

    elements.activeDocumentName.textContent = selected
      ? selected.filename
      : "No document selected";

    elements.activeDocumentDot.dataset.status = selected?.status || "NONE";

    document.querySelectorAll(".suggestion-button, .followup-button").forEach((button) => {
      button.disabled = !ready || busy;
    });
  }

  function renderDocuments() {
    elements.documentSelect.replaceChildren();

    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = state.documents.length ? "Choose a document" : "No documents yet";
    elements.documentSelect.appendChild(placeholder);

    for (const doc of state.documents) {
      const option = document.createElement("option");
      option.value = doc.document_id;
      option.textContent = `${doc.filename} — ${doc.status}`;
      option.title = `${doc.filename} (${doc.status})`;
      elements.documentSelect.appendChild(option);
    }

    elements.documentSelect.value = state.selectedDocumentId || "";
    elements.documentCount.textContent = String(state.documents.length);
    updateControls();
  }

  function renderChat() {
    elements.messages.replaceChildren();
    elements.welcome.hidden = state.chatHistory.length > 0;

    for (const message of state.chatHistory) {
      const article = document.createElement("article");
      article.className = `message message-${message.role}`;

      const label = document.createElement("div");
      label.className = "message-label";
      label.textContent = message.role === "user" ? "You" : "Insight-AI";

      const content = document.createElement("div");
      content.className = "message-content";
      // Render model/document content as text; never inject it as HTML.
      content.textContent = message.content;

      article.append(label, content);
      elements.messages.appendChild(article);
    }

    elements.chatContainer.scrollTop = elements.chatContainer.scrollHeight;
  }

  function renderFollowups(questions) {
    elements.followupButtons.replaceChildren();
    const validQuestions = Array.isArray(questions)
      ? questions.filter((question) => typeof question === "string" && question.trim()).slice(0, 3)
      : [];

    elements.followupContainer.hidden = validQuestions.length === 0;

    for (const question of validQuestions) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "followup-button";
      button.textContent = question;
      button.addEventListener("click", () => processQuery(question));
      elements.followupButtons.appendChild(button);
    }

    updateControls();
  }

  function resetConversation() {
    state.chatHistory = [];
    elements.followupButtons.replaceChildren();
    elements.followupContainer.hidden = true;
    renderChat();
  }

  async function apiGetDocuments() {
    const response = await window.InsightAuth.authenticatedFetch(`${API_BASE}/documents`);
    const data = await window.InsightAuth.parseResponse(response);
    if (!Array.isArray(data)) {
      throw new Error("The documents endpoint must return a JSON array.");
    }
    return data.map(normalizeDocument);
  }

  async function refreshDocuments({ quiet = false } = {}) {
    if (state.isLoadingDocuments) return;

    state.isLoadingDocuments = true;

    try {
      const previousSelection = state.selectedDocumentId;
      const serverDocuments = await apiGetDocuments();

      state.documents = mergeServerDocuments(serverDocuments);

      const selectedStillExists = state.documents.some(
        (doc) => doc.document_id === previousSelection
      );

      if (!selectedStillExists) {
        state.selectedDocumentId = state.documents[0]?.document_id || null;
        resetConversation();
      }

      synchronizeDocumentPolling();
      renderDocuments();

      const selected = getSelectedDocument();

      if (!quiet) {
        if (selected?.status === READY_STATUS) {
          setNotice(`Ready to chat with ${selected.filename}.`, "success");
        } else if (selected && PROCESSING_STATUSES.has(selected.status)) {
          setNotice(
            `${selected.filename} is being processed. You can chat when it is ready.`,
            "info"
          );
        } else if (selected?.status === FAILED_STATUS) {
          setNotice(
            `${selected.filename} failed to process. Upload it again or inspect the server logs.`,
            "error"
          );
        } else if (selected?.status === TIMEOUT_STATUS) {
          setNotice(
            `${selected.filename} exceeded the frontend monitoring timeout. Refresh to check its current server status.`,
            "warning"
          );
        } else {
          setNotice("No documents yet. Upload a PDF to get started.", "info");
        }
      }
    } finally {
      state.isLoadingDocuments = false;
    }
  }

  function mergeServerDocuments(serverDocuments) {
    const previousDocuments = new Map(
      state.documents.map((doc) => [doc.document_id, doc])
    );

    // Preserve a local TIMEOUT label while the backend still reports a
    // processing state. A later READY/FAILED response replaces that label.
    const mergedDocuments = serverDocuments.map((serverDocument) => {
      const previous = previousDocuments.get(serverDocument.document_id);

      if (
        previous?.status === TIMEOUT_STATUS &&
        PROCESSING_STATUSES.has(serverDocument.status)
      ) {
        return { ...serverDocument, status: TIMEOUT_STATUS };
      }

      return serverDocument;
    });

    const serverIds = new Set(
      serverDocuments.map((doc) => doc.document_id)
    );

    // The server now knows about these documents; local preservation is no
    // longer needed.
    for (const documentId of serverIds) {
      state.locallyAcceptedDocuments.delete(documentId);
    }

    // Preserve accepted documents that are not yet visible in GET /documents.
    for (const [documentId, entry] of state.locallyAcceptedDocuments) {
      if (serverIds.has(documentId)) continue;

      const document = entry.document;
      const elapsed = Date.now() - entry.acceptedAt;

      if (elapsed >= MAX_POLL_DURATION_MS) {
        state.locallyAcceptedDocuments.delete(documentId);
        document.status = TIMEOUT_STATUS;
      }

      mergedDocuments.unshift(document);
    }

    // Keep timed-out documents visible even if the server's list endpoint
    // currently omits non-READY records.
    const mergedIds = new Set(
      mergedDocuments.map((doc) => doc.document_id)
    );

    for (const previous of state.documents) {
      if (
        previous.status === TIMEOUT_STATUS &&
        !serverIds.has(previous.document_id) &&
        !mergedIds.has(previous.document_id)
      ) {
        mergedDocuments.push(previous);
      }
    }

    return mergedDocuments;
  }

  function synchronizeDocumentPolling() {
    // Existing PROCESSING documents observed at login/startup begin their own
    // monitoring window now. Newly uploaded documents retain their acceptedAt.
    for (const doc of state.documents) {
      if (PROCESSING_STATUSES.has(doc.status)) {
        startDocumentPolling(doc.document_id);
      }
    }

    // Stop monitoring documents that have reached a terminal/local timeout.
    for (const documentId of state.pollingDocuments.keys()) {
      const document = state.documents.find(
        (doc) => doc.document_id === documentId
      );

      if (
        document &&
        (document.status === READY_STATUS ||
          document.status === FAILED_STATUS ||
          document.status === TIMEOUT_STATUS)
      ) {
        stopDocumentPolling(documentId);
      }
    }

    if (state.pollingDocuments.size > 0) {
      scheduleDocumentPolling();
    } else {
      stopDocumentPolling();
    }
  }

  function startDocumentPolling(documentId) {
    if (!state.user || !documentId) return;

    // Don't reset an existing document's deadline on every refresh.
    if (!state.pollingDocuments.has(documentId)) {
      const acceptedEntry = state.locallyAcceptedDocuments.get(documentId);
      state.pollingDocuments.set(documentId, {
        startedAt: acceptedEntry?.acceptedAt ?? Date.now()
      });
    }

    scheduleDocumentPolling();
  }

  function scheduleDocumentPolling(delay = state.pollNextDelay) {
    if (state.pollTimer !== null) return;
    if (!state.user || state.pollingDocuments.size === 0) return;

    state.pollTimer = window.setTimeout(() => {
      void pollDocumentStatuses();
    }, delay);
  }

  function markDocumentTimedOut(documentId) {
    state.pollingDocuments.delete(documentId);

    const document = state.documents.find(
      (doc) => doc.document_id === documentId
    );

    if (document && PROCESSING_STATUSES.has(document.status)) {
      document.status = TIMEOUT_STATUS;

      if (state.selectedDocumentId === documentId) {
        setNotice(
          `${document.filename} exceeded the 10-minute monitoring timeout. ` +
            "Backend processing may still continue. Refresh the document list to check again.",
          "warning"
        );
      }
    }
  }

  async function pollDocumentStatuses() {
    state.pollTimer = null;

    if (!state.user) {
      stopDocumentPolling();
      return;
    }

    // Expire each document independently, based on its own accepted/observed time.
    const now = Date.now();

    for (const [documentId, tracking] of state.pollingDocuments) {
      if (now - tracking.startedAt >= MAX_POLL_DURATION_MS) {
        markDocumentTimedOut(documentId);
      }
    }

    if (state.pollingDocuments.size === 0) {
      renderDocuments();
      return;
    }

    // Avoid overlapping the initial/manual document refresh with this poll.
    if (state.isLoadingDocuments) {
      scheduleDocumentPolling();
      return;
    }

    try {
      state.isLoadingDocuments = true;

      const serverDocuments = await apiGetDocuments();
      const serverIds = new Set(
        serverDocuments.map((doc) => doc.document_id)
      );

      state.documents = mergeServerDocuments(serverDocuments);

      for (const [documentId, tracking] of state.pollingDocuments) {
        const doc = state.documents.find(
          (item) => item.document_id === documentId
        );

        // The backend may briefly omit a just-accepted document. Keep
        // monitoring it until its per-document deadline expires.
        if (!doc) {
          console.warn(
            `Document ${documentId} is not yet available in GET /documents.`
          );
          continue;
        }

        if (doc.status === READY_STATUS || doc.status === FAILED_STATUS) {
          state.pollingDocuments.delete(documentId);

          if (state.selectedDocumentId === documentId) {
            if (doc.status === READY_STATUS) {
              setNotice(`${doc.filename} is ready for questions.`, "success");
            } else {
              setNotice(`${doc.filename} failed to process.`, "error");
            }
          }

          continue;
        }

        if (Date.now() - tracking.startedAt >= MAX_POLL_DURATION_MS) {
          markDocumentTimedOut(documentId);
          continue;
        }

        if (!serverIds.has(documentId)) {
          console.warn(
            `Document ${documentId} is not yet available in GET /documents.`
          );
        }
      }

      // A successful status request resets transient-network backoff.
      state.pollNextDelay = POLL_INTERVAL_MS;
      renderDocuments();

    } catch (error) {
      console.warn("Document polling failed:", error.message);

      // Exponential backoff for transient GET failures, capped at 15 seconds.
      state.pollNextDelay = Math.min(
        state.pollNextDelay * 2,
        MAX_POLL_INTERVAL_MS
      );

    } finally {
      state.isLoadingDocuments = false;
    }

    if (state.pollingDocuments.size > 0) {
      scheduleDocumentPolling();
    } else {
      stopDocumentPolling();
      renderDocuments();
    }
  }

  function stopDocumentPolling(documentId = null) {
    if (documentId) {
      state.pollingDocuments.delete(documentId);
    } else {
      state.pollingDocuments.clear();
    }

    if (state.pollingDocuments.size === 0) {
      if (state.pollTimer !== null) {
        window.clearTimeout(state.pollTimer);
        state.pollTimer = null;
      }

      state.pollNextDelay = POLL_INTERVAL_MS;
    }
  }

  async function uploadDocument(file) {
    if (!file || state.isUploading || state.isProcessing) return;

    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setNotice("Please choose a PDF file.", "error");
      return;
    }
    if (file.size === 0) {
      setNotice("The selected file is empty.", "error");
      return;
    }
    if (file.size > MAX_FILE_SIZE) {
      setNotice("The PDF exceeds the 20 MB upload limit.", "error");
      return;
    }

    state.isUploading = true;
    updateControls();
    setNotice(`Uploading ${file.name}…`, "info");

    const body = new FormData();
    body.append("file", file);

    try {
      const response = await window.InsightAuth.authenticatedFetch(
        `${API_BASE}/documents`,
        {
          method: "POST",
          body
        }
      );

      const data = await window.InsightAuth.parseResponse(response);

      if (response.status !== 202) {
        throw new Error(
          `Expected HTTP 202 from upload endpoint, received ${response.status}.`
        );
      }

      if (!data.document_id || !data.job_id || !data.filename) {
        throw new Error(
          "Upload response must include document_id, job_id and filename."
        );
      }

      const acceptedAt = Date.now();

      const newDocument = normalizeDocument({
        document_id: data.document_id,
        filename: data.filename,
        status: data.document_status || "PROCESSING",
        created_at: data.created_at
      });

      state.locallyAcceptedDocuments.set(
        newDocument.document_id,
        {
          document: newDocument,
          acceptedAt
        }
      );

      state.documents = [
        newDocument,
        ...state.documents.filter(
          (doc) => doc.document_id !== newDocument.document_id
        )
      ];

      state.selectedDocumentId = newDocument.document_id;
      resetConversation();
      renderDocuments();

      setNotice(
        data.message || `${newDocument.filename} accepted for processing.`,
        "success"
      );

      // Monitor this document from the instant HTTP 202 is accepted.
      if (
        newDocument.status !== READY_STATUS &&
        newDocument.status !== FAILED_STATUS
      ) {
        state.pollingDocuments.set(newDocument.document_id, {
          startedAt: acceptedAt
        });
        startDocumentPolling(newDocument.document_id);
      }
    } catch (error) {
      console.error("Document upload failed:", error);
      setNotice(`Upload failed: ${error.message}`, "error");
    } finally {
      state.isUploading = false;
      updateControls();
      elements.pdfInput.value = "";
    }
  }

  async function sendChatRequest(query, documentId, model) {
    const response = await window.InsightAuth.authenticatedFetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        document_id: documentId,
        query,
        model
      })
    });

    const data = await window.InsightAuth.parseResponse(response);
    if (typeof data.answer !== "string") {
      throw new Error("The chat API response is missing a string 'answer'.");
    }
    return data;
  }

  async function processQuery(rawQuery) {
    const query = String(rawQuery || "").trim();
    const selected = getSelectedDocument();

    if (!query || state.isProcessing || state.isUploading) return;
    if (!selected || selected.status !== READY_STATUS) {
      setNotice("Select a document whose status is READY before asking questions.", "error");
      return;
    }

    state.isProcessing = true;
    elements.followupContainer.hidden = true;
    elements.followupButtons.replaceChildren();

    const userMessage = { role: "user", content: query };
    const assistantMessage = { role: "assistant", content: "Thinking…" };
    state.chatHistory.push(userMessage, assistantMessage);
    updateControls();
    renderChat();

    try {
      const result = await sendChatRequest(query, selected.document_id, elements.modelSelect.value);
      assistantMessage.content = result.answer;
      renderFollowups(result.follow_ups);
    } catch (error) {
      assistantMessage.content = `I couldn't complete that request: ${error.message}`;
      renderFollowups([]);
      console.error("Chat request failed:", error);
    } finally {
      state.isProcessing = false;
      updateControls();
      renderChat();
      elements.userInput.focus();
    }
  }

  elements.documentSelect.addEventListener("change", () => {
    const nextId = elements.documentSelect.value || null;
    if (nextId === state.selectedDocumentId) return;

    state.selectedDocumentId = nextId;
    resetConversation();
    renderDocuments();

    const selected = getSelectedDocument();
    if (!selected) {
      setNotice("Select a document to continue.", "info");
    } else if (selected.status === READY_STATUS) {
      setNotice(`${selected.filename} is ready for questions.`, "success");
    } else if (selected.status === "FAILED") {
      setNotice(`${selected.filename} could not be processed.`, "error");
    } else {
      setNotice(`${selected.filename} is ${selected.status.toLowerCase()}.`, "info");
    }
  });

  elements.chatForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const query = elements.userInput.value.trim();
    if (!query) return;
    elements.userInput.value = "";
    await processQuery(query);
  });

  elements.userInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      elements.chatForm.requestSubmit();
    }
  });

  elements.uploadButton.addEventListener("click", () => {
    if (!state.isUploading && !state.isProcessing) elements.pdfInput.click();
  });

  elements.pdfInput.addEventListener("change", () => {
    const file = elements.pdfInput.files?.[0];
    if (file) uploadDocument(file);
  });

  elements.clearButton.addEventListener("click", () => {
    if (state.isProcessing) return;
    resetConversation();
    elements.userInput.value = "";
    elements.userInput.focus();
  });

  document.querySelectorAll(".suggestion-button").forEach((button) => {
    button.addEventListener("click", () => processQuery(button.textContent));
  });

  window.InsightApp = Object.freeze({
    async onAuthenticated(user) {
      state.user = user;
      state.documents = [];
      state.selectedDocumentId = null;
      resetConversation();
      renderDocuments();
      setNotice("Loading your documents…", "info");

      try {
        await refreshDocuments();
      } catch (error) {
        setNotice(`Unable to load documents: ${error.message}`, "error");
        console.error("Document loading failed:", error);
      }
    },

    onUnauthenticated() {
      state.user = null;
      state.documents = [];
      state.selectedDocumentId = null;

      state.isUploading = false;
      state.isProcessing = false;
      state.isLoadingDocuments = false;

      stopDocumentPolling();
      state.locallyAcceptedDocuments.clear();

      resetConversation();
      renderDocuments();

      setNotice(
        "Sign in to access your documents.",
        "info"
      );
    }
  });

  window.addEventListener("insight:unauthenticated", () => {
    window.InsightApp.onUnauthenticated();
  });
})();
