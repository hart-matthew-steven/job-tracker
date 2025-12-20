// src/api.ts
import type {
  AddNoteIn,
  ChangePasswordIn,
  ConfirmUploadIn,
  CreateJobIn,
  DocumentItem,
  Job,
  LoginIn,
  LoginOut,
  MessageOut,
  Note,
  PatchJobIn,
  PresignUploadIn,
  PresignUploadOut,
  RegisterIn,
  ResendVerificationIn,
  UpdateSettingsIn,
  UserMeOut,
  UserSettingsOut,
  CreateSavedViewIn,
  PatchSavedViewIn,
  SavedView,
  JobActivity,
  CreateInterviewIn,
  JobInterview,
  PatchInterviewIn,
} from "./types/api";

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "http://matts-macbook.local:8000").replace(
  /\/$/,
  ""
);

const TOKEN_KEY = "access_token";

export function setAccessToken(token: string | null): void {
  if (!token) localStorage.removeItem(TOKEN_KEY);
  else localStorage.setItem(TOKEN_KEY, token);
}

export function getAccessToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function logout(): void {
  setAccessToken(null);
}

/**
 * Only attach Authorization for calls to *our* API base.
 * (Presigned S3 URLs, etc. must never receive Authorization headers.)
 */
function isApiPath(path: string): boolean {
  return typeof path === "string" && path.startsWith("/");
}

type JsonRequestOptions = Omit<RequestInit, "headers"> & { headers?: Record<string, string> };

function buildHeaders(options: JsonRequestOptions = {}, { includeAuth = true } = {}): Record<string, string> {
  const headers: Record<string, string> = { ...(options.headers ?? {}) };
  if (includeAuth) {
    const token = getAccessToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

async function parseError(res: Response): Promise<string> {
  const contentType = res.headers.get("content-type") || "";

  if (contentType.includes("application/json")) {
    try {
      const data: unknown = await res.json();
      if (typeof data === "object" && data) {
        const obj = data as Record<string, unknown>;
        const msg = obj.detail ?? obj.message;
        if (typeof msg === "string" && msg) return msg;
      }
      return `HTTP ${res.status} ${res.statusText}`;
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
let refreshPromise: Promise<string | null> | null = null;

/**
 * POST /auth/refresh
 * Uses HttpOnly refresh cookie (credentials: include)
 * Returns { access_token, token_type }
 */
async function tryRefreshAccessToken(): Promise<string | null> {
  if (refreshPromise) return refreshPromise;

  refreshPromise = (async () => {
    try {
      const res = await fetch(`${API_BASE}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
      });

      if (!res.ok) return null;

      const data: unknown = await res.json().catch(() => null);
      const accessToken =
        typeof data === "object" && data && "access_token" in data ? (data as { access_token?: unknown }).access_token : null;

      if (typeof accessToken === "string" && accessToken) {
        setAccessToken(accessToken);
        return accessToken;
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
async function requestJson<T = unknown>(path: string, options: JsonRequestOptions = {}): Promise<T> {
  const includeAuth = isApiPath(path);
  const baseHeaders = buildHeaders(options, { includeAuth });

  const doFetch = (hdrs: Record<string, string>) =>
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

  if (res.status === 204) return null as T;

  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) return (await res.json()) as T;

  return (await res.text()) as T;
}

/**
 * Void request helper (same refresh logic).
 */
async function requestVoid(path: string, options: JsonRequestOptions = {}): Promise<void> {
  const includeAuth = isApiPath(path);
  const baseHeaders = buildHeaders(options, { includeAuth });

  const doFetch = (hdrs: Record<string, string>) =>
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
export function registerUser(payload: RegisterIn): Promise<MessageOut> {
  return requestJson<MessageOut>(`/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function verifyEmail(token: string): Promise<MessageOut> {
  return requestJson<MessageOut>(`/auth/verify?token=${encodeURIComponent(token)}`);
}

export function resendVerification(payload: ResendVerificationIn): Promise<MessageOut> {
  return requestJson<MessageOut>(`/auth/resend-verification`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function loginUser(payload: LoginIn): Promise<LoginOut> {
  // ✅ MUST include credentials so browser stores HttpOnly refresh cookie
  const res = await requestJson<LoginOut>(`/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    credentials: "include",
  });

  if (res?.access_token) setAccessToken(res.access_token);
  return res;
}

export async function logoutUser(): Promise<void> {
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
export function getCurrentUser(): Promise<UserMeOut> {
  return requestJson<UserMeOut>(`/users/me`);
}

export function changePassword(payload: ChangePasswordIn): Promise<MessageOut> {
  return requestJson<MessageOut>(`/users/me/change-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function getMySettings(): Promise<UserSettingsOut> {
  return requestJson<UserSettingsOut>(`/users/me/settings`);
}

export function updateMySettings(payload: UpdateSettingsIn): Promise<MessageOut> {
  return requestJson<MessageOut>(`/users/me/settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

/** -------------------
 * Saved views
 * ------------------- */
export function listSavedViews(): Promise<SavedView[]> {
  return requestJson<SavedView[]>(`/saved-views`);
}

export function createSavedView(payload: CreateSavedViewIn): Promise<SavedView> {
  return requestJson<SavedView>(`/saved-views`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function patchSavedView(viewId: number | string, payload: PatchSavedViewIn): Promise<SavedView> {
  return requestJson<SavedView>(`/saved-views/${viewId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function deleteSavedView(viewId: number | string): Promise<MessageOut> {
  return requestJson<MessageOut>(`/saved-views/${viewId}`, { method: "DELETE" });
}

/** -------------------
 * Jobs
 * ------------------- */
export function listJobs(
  opts: { q?: string; tag_q?: string; tag?: string | string[]; status?: string | string[] } = {}
): Promise<Job[]> {
  const params = new URLSearchParams();

  const q = String(opts.q ?? "").trim();
  if (q) params.set("q", q);

  const tagQ = String(opts.tag_q ?? "").trim();
  if (tagQ) params.set("tag_q", tagQ);

  const tagsRaw = Array.isArray(opts.tag) ? opts.tag : opts.tag ? [opts.tag] : [];
  for (const t of tagsRaw) {
    const v = String(t ?? "").trim();
    if (v) params.append("tag", v);
  }

  const statusesRaw = Array.isArray(opts.status) ? opts.status : opts.status ? [opts.status] : [];
  for (const s of statusesRaw) {
    const v = String(s ?? "").trim();
    if (v) params.append("status", v);
  }

  const qs = params.toString();
  return requestJson<Job[]>(`/jobs${qs ? `?${qs}` : ""}`);
}

export function getJob(jobId: number | string): Promise<Job> {
  return requestJson<Job>(`/jobs/${jobId}`);
}

export function createJob(payload: CreateJobIn): Promise<Job> {
  return requestJson<Job>(`/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function patchJob(jobId: number | string, payload: PatchJobIn): Promise<Job> {
  return requestJson<Job>(`/jobs/${jobId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

/** -------------------
 * Job activity
 * ------------------- */
export function listJobActivity(jobId: number | string, opts: { limit?: number } = {}): Promise<JobActivity[]> {
  const limit = Math.max(1, Math.min(Number(opts.limit ?? 50) || 50, 200));
  return requestJson<JobActivity[]>(`/jobs/${jobId}/activity?limit=${encodeURIComponent(String(limit))}`);
}

/** -------------------
 * Interviews
 * ------------------- */
export function listInterviews(jobId: number | string): Promise<JobInterview[]> {
  return requestJson<JobInterview[]>(`/jobs/${jobId}/interviews`);
}

export function createInterview(jobId: number | string, payload: CreateInterviewIn): Promise<JobInterview> {
  return requestJson<JobInterview>(`/jobs/${jobId}/interviews`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function patchInterview(
  jobId: number | string,
  interviewId: number | string,
  payload: PatchInterviewIn
): Promise<JobInterview> {
  return requestJson<JobInterview>(`/jobs/${jobId}/interviews/${interviewId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function deleteInterview(jobId: number | string, interviewId: number | string): Promise<MessageOut> {
  return requestJson<MessageOut>(`/jobs/${jobId}/interviews/${interviewId}`, { method: "DELETE" });
}

/** -------------------
 * Notes
 * ------------------- */
export function listNotes(jobId: number | string): Promise<Note[]> {
  return requestJson<Note[]>(`/jobs/${jobId}/notes`);
}

export function addNote(jobId: number | string, payload: AddNoteIn): Promise<Note> {
  return requestJson<Note>(`/jobs/${jobId}/notes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function deleteNote(jobId: number | string, noteId: number | string): Promise<MessageOut | null> {
  return requestJson<MessageOut | null>(`/jobs/${jobId}/notes/${noteId}`, { method: "DELETE" });
}

/** -------------------
 * Documents
 * ------------------- */
export function listDocuments(jobId: number | string): Promise<DocumentItem[]> {
  return requestJson<DocumentItem[]>(`/jobs/${jobId}/documents`);
}

export function presignDocumentUpload(jobId: number | string, payload: PresignUploadIn): Promise<PresignUploadOut> {
  return requestJson<PresignUploadOut>(`/jobs/${jobId}/documents/presign-upload`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function confirmDocumentUpload(jobId: number | string, payload: ConfirmUploadIn): Promise<MessageOut> {
  return requestJson<MessageOut>(`/jobs/${jobId}/documents/confirm-upload`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function presignDocumentDownload(jobId: number | string, docId: number | string): Promise<{ download_url: string } & Record<string, unknown>> {
  return requestJson<{ download_url: string } & Record<string, unknown>>(
    `/jobs/${jobId}/documents/${docId}/presign-download`
  );
}

export function deleteDocument(jobId: number | string, docId: number | string): Promise<MessageOut | null> {
  return requestJson<MessageOut | null>(`/jobs/${jobId}/documents/${docId}`, { method: "DELETE" });
}

/**
 * Presigned S3 upload (not your API base).
 * This must be a PUT to the presigned URL.
 * IMPORTANT: Do NOT attach Authorization header here.
 */
export async function uploadToS3PresignedUrl(uploadUrl: string, file: File): Promise<void> {
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