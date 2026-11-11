
// ==========================================
// AUTHENTICATION CONFIGURATION
// ==========================================

const AUTH_TOKEN_KEY = "insight_ai_access_token";

let accessToken = sessionStorage.getItem(AUTH_TOKEN_KEY);


// ==========================================
// DOM ELEMENTS
// ==========================================

const authScreen = document.getElementById("authScreen");
const appShell = document.getElementById("appShell");

const loginForm = document.getElementById("loginForm");
const registerForm = document.getElementById("registerForm");

const authMessage = document.getElementById("authMessage");


// ==========================================
// UI HELPERS
// ==========================================

function setAuthMessage(message, type = "info") {

    authMessage.textContent = message;
    authMessage.dataset.type = type;

}


function showLoginForm(message = "", type = "info") {

    loginForm.hidden = false;
    registerForm.hidden = true;

    setAuthMessage(message, type);

}


function showRegisterForm() {

    loginForm.hidden = true;
    registerForm.hidden = false;

    setAuthMessage("");

}


function showAuthScreen(message = "", type = "info") {

    appShell.hidden = true;
    authScreen.hidden = false;

    showLoginForm(message, type);

}

async function showApplication(user) {

    authScreen.hidden = true;
    appShell.hidden = false;

    document.getElementById("currentUserLabel").textContent =
        `Logged in as ${user.username}`;

    if (typeof window.initializeUserDocuments === "function") {

        await window.initializeUserDocuments(user.id);

    }

}

// ==========================================
// TOKEN MANAGEMENT
// ==========================================

function clearAccessToken() {

    accessToken = null;

    sessionStorage.removeItem(AUTH_TOKEN_KEY);

}


// ==========================================
// API ERROR HANDLING
// ==========================================

async function getApiError(response) {

    const data = await response.json().catch(() => ({}));

    let detail = data.detail || "Request failed.";

    if (Array.isArray(detail)) {

        detail = detail.map(
            item => item.msg || JSON.stringify(item)
        ).join(", ");

    }

    return String(detail);

}


// ==========================================
// GET CURRENT USER
// ==========================================

async function getCurrentUser() {

    if (!accessToken) {

        throw new Error("Authentication required.");

    }

    const response = await fetch("/api/auth/me", {

        method: "GET",

        headers: {
            "Authorization": `Bearer ${accessToken}`
        }

    });

    if (!response.ok) {

        throw new Error(await getApiError(response));

    }

    return await response.json();

}


// ==========================================
// AUTHENTICATED API REQUEST
// ==========================================

async function authenticatedFetch(url, options = {}) {

    if (!accessToken) {

        showAuthScreen(
            "Please log in to continue.",
            "error"
        );

        throw new Error("Authentication required.");

    }

    const headers = new Headers(options.headers || {});

    headers.set(
        "Authorization",
        `Bearer ${accessToken}`
    );

    const response = await fetch(url, {

        ...options,

        headers

    });


    // Token expired, invalid or user no longer authenticated.
    if (response.status === 401) {

        clearAccessToken();

        showAuthScreen(
            "Your session has expired. Please log in again.",
            "error"
        );

        throw new Error("Authentication required.");

    }

    return response;

}


// ==========================================
// USER REGISTRATION
// ==========================================

registerForm.addEventListener("submit", async event => {

    event.preventDefault();

    const button = document.getElementById("registerButton");

    button.disabled = true;

    setAuthMessage("Creating your account...");

    const payload = {

        username: document
            .getElementById("registerUsername")
            .value.trim(),

        email: document
            .getElementById("registerEmail")
            .value.trim(),

        password: document
            .getElementById("registerPassword")
            .value

    };


    try {

        const response = await fetch("/api/auth/register", {

            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify(payload)

        });


        if (!response.ok) {

            throw new Error(await getApiError(response));

        }

        registerForm.reset();

        // Pre-fill the login username after registration.
        document.getElementById("loginUsername").value =
            payload.username;

        showLoginForm(
            "Registration successful. Please log in.",
            "success"
        );


    } catch (error) {

        setAuthMessage(error.message, "error");

    } finally {

        button.disabled = false;

    }

});


// ==========================================
// USER LOGIN
// ==========================================

loginForm.addEventListener("submit", async event => {

    event.preventDefault();

    const button = document.getElementById("loginButton");

    button.disabled = true;

    setAuthMessage("Logging in...");


    const username = document
        .getElementById("loginUsername")
        .value.trim();

    const password = document
        .getElementById("loginPassword")
        .value;


    try {

        // OAuth2PasswordRequestForm expects
        // application/x-www-form-urlencoded.

        const formData = new URLSearchParams();

        formData.set("username", username);
        formData.set("password", password);


        const response = await fetch("/api/auth/login", {

            method: "POST",

            headers: {
                "Content-Type": "application/x-www-form-urlencoded"
            },

            body: formData

        });


        if (!response.ok) {

            throw new Error(await getApiError(response));

        }


        const data = await response.json();

        if (!data.access_token) {

            throw new Error("Access token was not returned by the server.");

        }


        // Store JWT in the current browser tab's session.
        accessToken = data.access_token;

        sessionStorage.setItem(
            AUTH_TOKEN_KEY,
            accessToken
        );


        // Validate the token and retrieve user information.
        const user = await getCurrentUser();


        // Show the main application.
        showApplication(user);

        loginForm.reset();


    } catch (error) {

        clearAccessToken();

        showAuthScreen(error.message, "error");

    } finally {

        button.disabled = false;

    }

});


// ==========================================
// SWITCH BETWEEN LOGIN AND REGISTER
// ==========================================

document.getElementById("showRegister")
    .addEventListener("click", showRegisterForm);


document.getElementById("showLogin")
    .addEventListener("click", () => {

        showLoginForm();

    });


// ==========================================
// LOGOUT
// ==========================================

document.getElementById("logoutButton")
    .addEventListener("click", () => {

        clearAccessToken();

        // Reload the page to clear the previous UI state.
        window.location.reload();

    });


// ==========================================
// APPLICATION STARTUP
// ==========================================

async function initializeAuthentication() {

    if (!accessToken) {

        showAuthScreen();

        return;

    }


    try {

        // Validate an existing token after page refresh.
        const user = await getCurrentUser();

        showApplication(user);


    } catch (error) {

        clearAccessToken();

        showAuthScreen(
            "Your session is invalid or has expired. Please log in again.",
            "error"
        );

    }

}


document.addEventListener(
    "DOMContentLoaded",
    initializeAuthentication
);
