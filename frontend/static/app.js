
// ==========================================
// CONFIGURATION
// ==========================================

const API_URL = "/api";

// ==========================================
// APPLICATION STATE
// ==========================================

const state = {

    documents: [],

    selectedDocumentId: null,

    chatHistory: [],

    currentFollowUps: [],

    isUploading: false,

    isProcessing: false

};


// ==========================================
// DOM ELEMENTS
// ==========================================

const messagesContainer = document.getElementById("messages");

const welcomeScreen = document.getElementById("welcome-screen");

const chatContainer = document.getElementById("chat-container");

const followupContainer =
    document.getElementById("followup-container");

const followupButtons =
    document.getElementById("followup-buttons");

const chatForm = document.getElementById("chat-form");

const userInput = document.getElementById("user-input");

const sendButton = document.getElementById("send-button");

const modelSelect = document.getElementById("model-select");

const clearButton = document.getElementById("clear-chat");

const pdfInput = document.getElementById("pdf-input");

const uploadButton = document.getElementById("upload-button");

const documentSelect = document.getElementById("document-select");

const uploadStatus = document.getElementById("upload-status");

const activeDocumentName =
    document.getElementById("active-document-name");


// ==========================================
// GET SELECTED DOCUMENT
// ==========================================

function getSelectedDocument() {

    return state.documents.find(

        doc => doc.document_id === state.selectedDocumentId

    ) || null;

}


// ==========================================
// UPLOAD STATUS
// ==========================================

function setUploadStatus(message, type = "info") {

    uploadStatus.textContent = message;

    uploadStatus.dataset.type = type;

}


// ==========================================
// API RESPONSE HANDLING
// ==========================================

async function parseResponse(response) {

    const responseText = await response.text();

    let data = {};


    try {

        data = responseText ? JSON.parse(responseText) : {};


    } catch {

        data = {

            detail: responseText || "Unexpected server response."

        };

    }


    if (!response.ok) {

        let message = data.detail || "Request failed.";


        // FastAPI validation errors may return an array.
        if (Array.isArray(message)) {

            message = message.map(

                item => item.msg || JSON.stringify(item)

            ).join(", ");

        }


        throw new Error(String(message));

    }


    return data;

}


// ==========================================
// UI CONTROLS
// ==========================================

function updateControls() {

    const hasDocument = Boolean(getSelectedDocument());

    const busy = state.isProcessing || state.isUploading;


    sendButton.disabled = !hasDocument || busy;

    userInput.disabled = !hasDocument || busy;

    documentSelect.disabled =
        state.documents.length === 0 || busy;

    uploadButton.disabled = busy;

    modelSelect.disabled = busy;

    clearButton.disabled = state.isProcessing;


    document.querySelectorAll(".suggestion-button").forEach(button => {

        button.disabled = !hasDocument || busy;

    });


    if (!hasDocument) {

        userInput.placeholder = "Upload and select a PDF first...";

    } else if (busy) {

        userInput.placeholder = "Please wait...";

    } else {

        userInput.placeholder = "Ask something about your document...";

    }

}


// ==========================================
// RENDER DOCUMENT SELECTOR
// ==========================================

function renderDocuments() {

    documentSelect.replaceChildren();


    const placeholder = document.createElement("option");

    placeholder.value = "";

    placeholder.textContent = state.documents.length

        ? "Select a document"

        : "No documents uploaded";


    documentSelect.appendChild(placeholder);


    state.documents.forEach(doc => {

        const option = document.createElement("option");

        option.value = doc.document_id;

        option.textContent = doc.filename;

        option.title = doc.filename;

        documentSelect.appendChild(option);

    });


    documentSelect.value = state.selectedDocumentId || "";


    const selectedDocument = getSelectedDocument();


    activeDocumentName.textContent = selectedDocument

        ? selectedDocument.filename

        : "No document selected";


    updateControls();

}


// ==========================================
// UPLOAD PDF
// ==========================================

async function uploadDocument(file) {

    if (!file) {

        return;

    }


    if (

        !file.name.toLowerCase().endsWith(".pdf") ||

        (file.type && file.type !== "application/pdf")

    ) {

        setUploadStatus(

            "Please select a valid PDF file.",

            "error"

        );

        return;

    }


    if (file.size === 0) {

        setUploadStatus(

            "The selected file is empty.",

            "error"

        );

        return;

    }


    state.isUploading = true;


    setUploadStatus(

        `Uploading and indexing ${file.name}...`,

        "info"

    );


    updateControls();


    const formData = new FormData();

    formData.append("file", file);


    try {

        // JWT is automatically attached by authenticatedFetch.
        const response = await authenticatedFetch(

            `${API_URL}/documents`,

            {

                method: "POST",

                body: formData

            }

        );


        const data = await parseResponse(response);


        if (!data.document_id || !data.filename) {

            throw new Error(

                "The server did not return a document ID and filename."

            );

        }


        const uploadedDocument = {

            document_id: data.document_id,

            filename: data.filename,

            uploaded_at: new Date().toISOString()

        };


        // Avoid duplicate document entries.
        const existingIndex = state.documents.findIndex(

            doc => doc.document_id === uploadedDocument.document_id

        );


        if (existingIndex >= 0) {

            state.documents[existingIndex] = uploadedDocument;

        } else {

            state.documents.push(uploadedDocument);

        }


        // Automatically select the uploaded document.
        state.selectedDocumentId = uploadedDocument.document_id;


        // A new document starts a fresh chat.
        resetConversation();

        renderDocuments();


        const result = data.result || {};

        const pages = result.pages_extracted;

        const chunks = result.chunks_created;


        let statusMessage = `Ready: ${uploadedDocument.filename}`;


        if (pages !== undefined && chunks !== undefined) {

            statusMessage += ` (${pages} pages, ${chunks} chunks)`;

        }


        setUploadStatus(statusMessage, "success");


    } catch (error) {

        console.error("Document upload failed:", error);


        setUploadStatus(

            `Upload failed: ${error.message}`,

            "error"

        );


    } finally {

        state.isUploading = false;

        updateControls();

        pdfInput.value = "";

    }

}


// ==========================================
// DOCUMENT SELECTION
// ==========================================

documentSelect.addEventListener("change", () => {

    const newDocumentId = documentSelect.value;


    if (newDocumentId === state.selectedDocumentId) {

        return;

    }


    state.selectedDocumentId = newDocumentId || null;


    // Do not mix chats from different documents.
    resetConversation();

    renderDocuments();


    const selectedDocument = getSelectedDocument();


    if (selectedDocument) {

        setUploadStatus(

            `Selected: ${selectedDocument.filename}`,

            "success"

        );

    } else {

        setUploadStatus(

            "Select a document to start chatting.",

            "info"

        );

    }

});


// ==========================================
// CHAT API REQUEST
// ==========================================

async function getResponse(query, documentId, model) {

    // JWT is automatically attached by authenticatedFetch.
    const response = await authenticatedFetch(

        `${API_URL}/chat`,

        {

            method: "POST",

            headers: {

                "Content-Type": "application/json"

            },

            body: JSON.stringify({

                document_id: documentId,

                query: query,

                model: model

            })

        }

    );


    return await parseResponse(response);

}


// ==========================================
// PROCESS QUERY
// ==========================================

async function processQuery(query) {

    if (

        !query ||

        !query.trim() ||

        state.isProcessing ||

        state.isUploading

    ) {

        return;

    }


    query = query.trim();


    const selectedDocument = getSelectedDocument();


    if (!selectedDocument) {

        setUploadStatus(

            "Upload and select a PDF before asking questions.",

            "error"

        );

        return;

    }


    // Capture selected values for this request.
    const documentId = selectedDocument.document_id;

    const model = modelSelect.value;


    state.isProcessing = true;

    state.currentFollowUps = [];


    followupContainer.classList.add("hidden");


    state.chatHistory.push({

        role: "user",

        content: query

    });


    const assistantMessage = {

        role: "assistant",

        content: "Thinking..."

    };


    state.chatHistory.push(assistantMessage);


    updateControls();

    renderChat();


    try {

        const result = await getResponse(

            query,

            documentId,

            model

        );


        assistantMessage.content = result.answer;


        state.currentFollowUps = Array.isArray(result.follow_ups)

            ? result.follow_ups.slice(0, 3)

            : [];


    } catch (error) {

        console.error("Chat error:", error);


        assistantMessage.content =

            `Sorry, something went wrong: ${error.message}`;


    } finally {

        state.isProcessing = false;


        updateControls();

        renderChat();

        renderFollowups(state.currentFollowUps);

        userInput.focus();

    }

}


// ==========================================
// RENDER CHAT HISTORY
// ==========================================

function renderChat() {

    messagesContainer.replaceChildren();


    welcomeScreen.classList.toggle(

        "hidden",

        state.chatHistory.length > 0

    );


    state.chatHistory.forEach(message => {

        const messageElement = document.createElement("div");

        messageElement.className = `message ${message.role}`;


        const label = document.createElement("span");

        label.className = "message-label";


        label.textContent =

            message.role === "user"

                ? "You:"

                : "INSIGHT-AI:";


        const content = document.createElement("div");


        // textContent prevents HTML injection from document content.
        content.textContent = message.content;


        messageElement.appendChild(label);

        messageElement.appendChild(content);

        messagesContainer.appendChild(messageElement);

    });


    chatContainer.scrollTop = chatContainer.scrollHeight;

}


// ==========================================
// FOLLOW-UP QUESTIONS
// ==========================================

function renderFollowups(questions) {

    followupButtons.replaceChildren();


    if (!questions || questions.length === 0) {

        followupContainer.classList.add("hidden");

        return;

    }


    followupContainer.classList.remove("hidden");


    questions.slice(0, 3).forEach(question => {

        const button = document.createElement("button");

        button.type = "button";

        button.className = "followup-button";

        button.textContent = question;


        button.addEventListener("click", () => {

            processQuery(question);

        });


        followupButtons.appendChild(button);

    });

}


// ==========================================
// INITIAL SUGGESTED QUESTIONS
// ==========================================

function renderSuggestions() {

    const buttons = document.querySelectorAll(

        ".suggestion-button"

    );


    buttons.forEach(button => {

        button.addEventListener("click", () => {

            processQuery(button.textContent);

        });

    });

}


// ==========================================
// RESET CONVERSATION
// ==========================================

function resetConversation() {

    state.chatHistory = [];

    state.currentFollowUps = [];


    followupButtons.replaceChildren();

    followupContainer.classList.add("hidden");


    renderChat();

}


// ==========================================
// CHAT FORM SUBMISSION
// ==========================================

chatForm.addEventListener("submit", async event => {

    event.preventDefault();


    const query = userInput.value.trim();


    if (

        !query ||

        state.isProcessing ||

        state.isUploading

    ) {

        return;

    }


    if (!getSelectedDocument()) {

        setUploadStatus(

            "Upload and select a PDF first.",

            "error"

        );

        return;

    }


    userInput.value = "";

    await processQuery(query);

});


// ==========================================
// UPLOAD BUTTON
// ==========================================

uploadButton.addEventListener("click", () => {

    if (!state.isUploading && !state.isProcessing) {

        pdfInput.click();

    }

});


pdfInput.addEventListener("change", async () => {

    const file = pdfInput.files[0];


    if (file) {

        await uploadDocument(file);

    }

});


// ==========================================
// CLEAR CHAT
// ==========================================

clearButton.addEventListener("click", () => {

    if (state.isProcessing) {

        return;

    }


    resetConversation();

    userInput.value = "";

    userInput.focus();

});


// ==========================================
// INITIALIZE DOCUMENTS AFTER LOGIN
// ==========================================

async function initializeUserDocuments(userId) {

    // Start with a clean document state.
    state.documents = [];
    state.selectedDocumentId = null;

    resetConversation();
    renderDocuments();

    setUploadStatus("Loading your documents...", "info");

    try {

        const response = await authenticatedFetch(
            `${API_URL}/documents`
        );

        const documents = await parseResponse(response);

        state.documents = Array.isArray(documents)
            ? documents
            : [];

        // Automatically select the first available document.
        state.selectedDocumentId =
            state.documents[0]?.document_id || null;

        renderDocuments();

        const selectedDocument = getSelectedDocument();

        setUploadStatus(
            selectedDocument
                ? `Selected: ${selectedDocument.filename}`
                : "No documents available. Upload a PDF to start.",
            selectedDocument ? "success" : "info"
        );

    } catch (error) {

        console.error("Document loading failed:", error);

        setUploadStatus(
            `Unable to load documents: ${error.message}`,
            "error"
        );

    }

}


// Make it accessible to auth.js.
window.initializeUserDocuments = initializeUserDocuments;

// ==========================================
// INITIALIZE APPLICATION UI
// ==========================================

// Do not load any user's documents before authentication.

renderDocuments();

renderSuggestions();

renderChat();


setUploadStatus(

    "Log in to view your documents.",

    "info"

);


updateControls();
