(() => {
  "use strict";

  const TOKEN_KEY = "insight_ai_access_token";
  let accessToken = sessionStorage.getItem(TOKEN_KEY);

  const $ = (id) => document.getElementById(id);
  const authScreen = $("authScreen");
  const appShell = $("appShell");
  const loginForm = $("loginForm");
  const registerForm = $("registerForm");
  const authMessage = $("authMessage");

  class ApiError extends Error {
    constructor(message, status, payload = null) {
      super(message);
      this.name = "ApiError";
      this.status = status;
      this.payload = payload;
    }
  }

  async function parseResponse(response) {
    const contentType = response.headers.get("content-type") || "";
    let payload = null;

    if (contentType.includes("application/json")) {
      payload = await response.json().catch(() => null);
    } else {
      const text = await response.text().catch(() => "");
      payload = text ? { detail: text } : {};
    }

    if (!response.ok) {
      let detail = payload?.detail || payload?.message || `Request failed (${response.status}).`;
      if (Array.isArray(detail)) {
        detail = detail.map((item) => item.msg || JSON.stringify(item)).join("; ");
      }
      throw new ApiError(String(detail), response.status, payload);
    }

    return payload ?? {};
  }

  function setAuthMessage(message = "", type = "info") {
    authMessage.textContent = message;
    authMessage.dataset.type = type;
  }

  function showLogin(message = "", type = "info") {
    loginForm.hidden = false;
    registerForm.hidden = true;
    setAuthMessage(message, type);
  }

  function showRegister() {
    loginForm.hidden = true;
    registerForm.hidden = false;
    setAuthMessage("");
  }

  function clearSession() {
    accessToken = null;
    sessionStorage.removeItem(TOKEN_KEY);
  }

  function showAuthentication(message = "", type = "info") {
    appShell.hidden = true;
    authScreen.hidden = false;
    showLogin(message, type);
    window.dispatchEvent(new CustomEvent("insight:unauthenticated"));
  }

  async function authenticatedFetch(url, options = {}) {
    if (!accessToken) {
      showAuthentication("Please sign in to continue.", "error");
      throw new ApiError("Authentication required.", 401);
    }

    const headers = new Headers(options.headers || {});
    headers.set("Authorization", `Bearer ${accessToken}`);

    const response = await fetch(url, { ...options, headers });

    if (response.status === 401) {
      clearSession();
      showAuthentication("Your session has expired. Please sign in again.", "error");
    }

    return response;
  }

  async function getCurrentUser() {
    const response = await authenticatedFetch("/api/auth/me");
    return parseResponse(response);
  }

  async function showApplication(user) {
    authScreen.hidden = true;
    appShell.hidden = false;
    $("currentUserLabel").textContent = user.username || user.email || "Account";

    if (window.InsightApp?.onAuthenticated) {
      await window.InsightApp.onAuthenticated(user);
    }
  }

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = $("loginButton");
    button.disabled = true;
    setAuthMessage("Signing in…");

    const form = new URLSearchParams();
    form.set("username", $("loginUsername").value.trim());
    form.set("password", $("loginPassword").value);

    try {
      // FastAPI OAuth2PasswordRequestForm expects form-urlencoded data.
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: form
      });
      const data = await parseResponse(response);

      if (!data.access_token) {
        throw new ApiError("The server did not return an access token.", response.status);
      }

      accessToken = data.access_token;
      sessionStorage.setItem(TOKEN_KEY, accessToken);

      const user = await getCurrentUser();
      loginForm.reset();
      await showApplication(user);
    } catch (error) {
      clearSession();
      showLogin(error.message || "Unable to sign in.", "error");
    } finally {
      button.disabled = false;
    }
  });

  registerForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = $("registerButton");
    button.disabled = true;
    setAuthMessage("Creating your account…");

    const payload = {
      username: $("registerUsername").value.trim(),
      email: $("registerEmail").value.trim(),
      password: $("registerPassword").value
    };

    try {
      const response = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      await parseResponse(response);
      registerForm.reset();
      $("loginUsername").value = payload.username;
      showLogin("Account created. Sign in to continue.", "success");
    } catch (error) {
      setAuthMessage(error.message || "Unable to create account.", "error");
    } finally {
      button.disabled = false;
    }
  });

  $("showRegister").addEventListener("click", showRegister);
  $("showLogin").addEventListener("click", () => showLogin());

  $("logoutButton").addEventListener("click", () => {
    clearSession();
    showAuthentication("You have signed out.", "info");
  });

  window.InsightAuth = Object.freeze({
    authenticatedFetch,
    parseResponse,
    getCurrentUser,
    getAccessToken: () => accessToken
  });

  async function initializeAuthentication() {
    if (!accessToken) {
      showAuthentication();
      return;
    }

    try {
      const user = await getCurrentUser();
      await showApplication(user);
    } catch (error) {
      clearSession();
      showAuthentication("Your session is invalid or expired. Please sign in again.", "error");
    }
  }

  document.addEventListener("DOMContentLoaded", initializeAuthentication);
})();
