// src/api.js
const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "http://matts-macbook.local:8000").replace(
  /\/$/,
  ""
);

const TOKEN_KEY = "access_token";

export function setAccessToken(token) {
  if (!token) localStorage.removeItem(TOKEN_KEY);
  else localStorage.setItem(TOKEN_KEY, token);
}

export function getAccessToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function logout() {
  setAccessToken(null);
}

/**
 * Only attach Authorization for calls to *our* API base.
 * (Presigned S3 URLs, etc. must never receive Authorization headers.)
 */
function isApiPath(path) {
  return typeof path === "string" && path.startsWith("/");
}

function buildHeaders(options = {}, { includeAuth = true } = {}) {
  const headers = { ...(options.headers ?? {}) };
  if (includeAuth) {
    const token = getAccessToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

async function parseError(res) {
  const contentType = res.headers.get("content-type") || "";

  if (contentType.includes("application/json")) {
    try {
      const data = await res.json();
      return data?.detail ?? data?.message ?? `HTTP ${res.status} ${res.statusText}`;
    } catch {
      // fall through
    }
  }

  const text = await res.text().catch(() => "");
  return text || `HTTP ${res.status} ${res.statusText}`;
}

/** -------------------
 * Refresh token (HttpOnly cookie) support
 * ------------------- */

// Prevent multiple simultaneous refresh calls
let refreshPromise = null;

/**
 * POST /auth/refresh
 * Uses HttpOnly refresh cookie (credentials: include)
 * Returns { access_token, token_type }
 */
async function tryRefreshAccessToken() {
  if (refreshPromise) return refreshPromise;

  refreshPromise = (async () => {
    try {
      const res = await fetch(`${API_BASE}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
      });

      if (!res.ok) return null;

      const data = await res.json().catch(() => null);
      if (data?.access_token) {
        setAccessToken(data.access_token);
        return data.access_token;
      }
      return null;
    } catch {
      return null;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

/**
 * JSON request helper:
 * - Adds Authorization for /paths
 * - Sends cookies (needed for refresh cookie workflows)
 * - On 401: try refresh once, retry once
 */
async function requestJson(path, options = {}) {
  const includeAuth = isApiPath(path);
  const baseHeaders = buildHeaders(options, { includeAuth });

  const doFetch = (hdrs) =>
    fetch(`${API_BASE}${path}`, {
      ...options,
      headers: hdrs,
      credentials: "include",
    });

  let res = await doFetch(baseHeaders);

  // Attempt refresh once for API calls when authed request fails
  if (includeAuth && res.status === 401) {
    const newToken = await tryRefreshAccessToken();

    if (newToken) {
      // IMPORTANT: preserve original headers (Content-Type, etc) and just overwrite Authorization
      const retryHeaders = { ...baseHeaders, Authorization: `Bearer ${newToken}` };
      res = await doFetch(retryHeaders);
    } else {
      logout();
    }
  }

  if (!res.ok) {
    const msg = await parseError(res);
    throw new Error(msg);
  }

  if (res.status === 204) return null;

  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) return await res.json();

  return await res.text();
}

/**
 * Void request helper (same refresh logic).
 */
async function requestVoid(path, options = {}) {
  const includeAuth = isApiPath(path);
  const baseHeaders = buildHeaders(options, { includeAuth });

  const doFetch = (hdrs) =>
    fetch(`${API_BASE}${path}`, {
      ...options,
      headers: hdrs,
      credentials: "include",
    });

  let res = await doFetch(baseHeaders);

  if (includeAuth && res.status === 401) {
    const newToken = await tryRefreshAccessToken();

    if (newToken) {
      const retryHeaders = { ...baseHeaders, Authorization: `Bearer ${newToken}` };
      res = await doFetch(retryHeaders);
    } else {
      logout();
    }
  }

  if (!res.ok) {
    const msg = await parseError(res);
    throw new Error(msg);
  }
}

/** -------------------
 * Auth
 * ------------------- */
export function registerUser(payload) {
  return requestJson(`/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function verifyEmail(token) {
  return requestJson(`/auth/verify?token=${encodeURIComponent(token)}`);
}

export function resendVerification(payload) {
  return requestJson(`/auth/resend-verification`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function loginUser(payload) {
  // ✅ MUST include credentials so browser stores HttpOnly refresh cookie
  const res = await requestJson(`/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    credentials: "include",
  });

  if (res?.access_token) setAccessToken(res.access_token);
  return res;
}

export async function logoutUser() {
  try {
    // ✅ sends cookie so backend can revoke + clear it
    await requestVoid(`/auth/logout`, { method: "POST", credentials: "include" });
  } catch {
    // ignore
  } finally {
    logout();
  }
}

/** -------------------
 * Users
 * ------------------- */
export function getCurrentUser() {
  return requestJson(`/users/me`);
}

export function changePassword(payload) {
  return requestJson(`/users/me/change-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function getMySettings() {
  return requestJson(`/users/me/settings`);
}

export function updateMySettings(payload) {
  return requestJson(`/users/me/settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

/** -------------------
 * Jobs
 * ------------------- */
export function listJobs() {
  return requestJson(`/jobs`);
}

export function getJob(jobId) {
  return requestJson(`/jobs/${jobId}`);
}

export function createJob(payload) {
  return requestJson(`/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function patchJob(jobId, payload) {
  return requestJson(`/jobs/${jobId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

/** -------------------
 * Notes
 * ------------------- */
export function listNotes(jobId) {
  return requestJson(`/jobs/${jobId}/notes`);
}

export function addNote(jobId, payload) {
  return requestJson(`/jobs/${jobId}/notes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function deleteNote(jobId, noteId) {
  return requestJson(`/jobs/${jobId}/notes/${noteId}`, { method: "DELETE" });
}

/** -------------------
 * Documents
 * ------------------- */
export function listDocuments(jobId) {
  return requestJson(`/jobs/${jobId}/documents`);
}

export function presignDocumentUpload(jobId, payload) {
  return requestJson(`/jobs/${jobId}/documents/presign-upload`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function confirmDocumentUpload(jobId, payload) {
  return requestJson(`/jobs/${jobId}/documents/confirm-upload`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function presignDocumentDownload(jobId, docId) {
  return requestJson(`/jobs/${jobId}/documents/${docId}/presign-download`);
}

export function deleteDocument(jobId, docId) {
  return requestJson(`/jobs/${jobId}/documents/${docId}`, { method: "DELETE" });
}

/**
 * Presigned S3 upload (not your API base).
 * This must be a PUT to the presigned URL.
 * IMPORTANT: Do NOT attach Authorization header here.
 */
export async function uploadToS3PresignedUrl(uploadUrl, file) {
  const res = await fetch(uploadUrl, {
    method: "PUT",
    headers: file?.type ? { "Content-Type": file.type } : undefined,
    body: file,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `S3 upload failed: HTTP ${res.status} ${res.statusText}`);
  }
}