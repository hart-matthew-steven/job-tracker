// src/api.ts
import type {
  AddNoteIn,
  ChangePasswordIn,
  ConfirmUploadIn,
  CreateJobIn,
  DocumentItem,
  Job,
  MessageOut,
  Note,
  PatchJobIn,
  PresignUploadIn,
  PresignUploadOut,
  UpdateSettingsIn,
  UserMeOut,
  UserSettingsOut,
  CreateSavedViewIn,
  PatchSavedViewIn,
  SavedView,
  JobActivityPage,
  CreateInterviewIn,
  JobInterview,
  PatchInterviewIn,
  UpdateUiPreferencesIn,
  UiPreferencesOut,
  JobDetailsBundle,
} from "./types/api";

import API_BASE from "./lib/apiBase";
import {
  clearSession as clearAuthSession,
  ensureValidAccessToken,
  getAccessToken,
  refreshSession,
} from "./auth/tokenManager";

type LogoutListener = () => void;
const logoutListeners = new Set<LogoutListener>();

type EmailVerificationListener = (data?: { email?: string }) => void;
const emailVerificationListeners = new Set<EmailVerificationListener>();

export function subscribeToUnauthorizedLogout(listener: LogoutListener): () => void {
  logoutListeners.add(listener);
  return () => logoutListeners.delete(listener);
}

export function subscribeToEmailVerificationRequired(listener: EmailVerificationListener): () => void {
  emailVerificationListeners.add(listener);
  return () => emailVerificationListeners.delete(listener);
}

function notifyUnauthorizedLogout() {
  logoutListeners.forEach((fn) => {
    try {
      fn();
    } catch {
      // ignore listener errors
    }
  });
}

export function logout(): void {
  clearAuthSession();
}

function requiresAuth(path: string): boolean {
  if (typeof path !== "string") return false;
  if (!path.startsWith("/")) return false;
  if (path.startsWith("/auth/cognito/verification")) return false;
  return !path.startsWith("/auth/");
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

type ParsedError = { message: string; detail?: unknown };

async function parseError(res: Response): Promise<ParsedError> {
  const contentType = res.headers.get("content-type") || "";
  const fallback = `HTTP ${res.status} ${res.statusText}`;

  if (contentType.includes("application/json")) {
    try {
      const data: unknown = await res.json();
      if (typeof data === "object" && data) {
        const obj = data as Record<string, unknown>;
        const structuredDetail = obj.details ?? obj.detail;
        if (typeof structuredDetail === "string" && structuredDetail) return { message: structuredDetail, detail: structuredDetail };
        if (structuredDetail && typeof structuredDetail === "object") {
          const msg = typeof obj.message === "string" && obj.message ? obj.message : fallback;
          return { message: msg, detail: structuredDetail };
        }
        const msg = obj.message;
        if (typeof msg === "string" && msg) return { message: msg, detail: structuredDetail };
      }
      return { message: fallback };
    } catch {
      // fall through
    }
  }

  const text = await res.text().catch(() => "");
  return { message: text || fallback };
}

/**
 * JSON request helper:
 * - Adds Authorization for protected paths
 * - On 401: try refresh once, retry once
 */
export async function requestJson<T = unknown>(path: string, options: JsonRequestOptions = {}): Promise<T> {
  const includeAuth = requiresAuth(path);
  if (includeAuth) {
    await ensureValidAccessToken();
  }
  const baseHeaders = buildHeaders(options, { includeAuth });

  const doFetch = (hdrs: Record<string, string>) =>
    fetch(`${API_BASE}${path}`, {
      ...options,
      headers: hdrs,
      credentials: "omit",
    });

  let res = await doFetch(baseHeaders);

  // Attempt refresh once for API calls when authed request fails
  if (includeAuth && res.status === 401) {
    const refreshed = await refreshSession();

    if (refreshed?.accessToken) {
      const retryHeaders = { ...baseHeaders, Authorization: `Bearer ${refreshed.accessToken}` };
      res = await doFetch(retryHeaders);
    } else {
      clearAuthSession();
      notifyUnauthorizedLogout();
    }
  }

  if (!res.ok) {
    if (res.status === 401) {
      clearAuthSession();
      notifyUnauthorizedLogout();
    }

    const { message, detail } = await parseError(res);
    if (res.status === 403) {
      const payload = (typeof detail === "object" && detail !== null ? (detail as Record<string, unknown>) : {}) as {
        code?: string;
        error?: string;
        email?: string;
      };
      const code = (payload.code || payload.error || "").toString().toUpperCase();
      if (code === "EMAIL_NOT_VERIFIED") {
        emailVerificationListeners.forEach((fn) => {
          try {
            fn({ email: payload.email });
          } catch {
            // ignore listener errors
          }
        });
      }
    }

    const error = new Error(message) as Error & { detail?: unknown; status?: number };
    if (detail !== undefined) error.detail = detail;
    error.status = res.status;
    throw error;
  }

  if (res.status === 204) return null as T;

  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) return (await res.json()) as T;

  return (await res.text()) as T;
}

/**
 * Void request helper (same refresh logic).
 */
export async function requestVoid(path: string, options: JsonRequestOptions = {}): Promise<void> {
  const includeAuth = requiresAuth(path);
  if (includeAuth) {
    await ensureValidAccessToken();
  }
  const baseHeaders = buildHeaders(options, { includeAuth });

  const doFetch = (hdrs: Record<string, string>) =>
    fetch(`${API_BASE}${path}`, {
      ...options,
      headers: hdrs,
      credentials: "omit",
    });

  let res = await doFetch(baseHeaders);

  if (includeAuth && res.status === 401) {
    const refreshed = await refreshSession();

    if (refreshed?.accessToken) {
      const retryHeaders = { ...baseHeaders, Authorization: `Bearer ${refreshed.accessToken}` };
      res = await doFetch(retryHeaders);
    } else {
      clearAuthSession();
      notifyUnauthorizedLogout();
    }
  }

  if (!res.ok) {
    const { message, detail } = await parseError(res);
    if (res.status === 403) {
      const payload = (typeof detail === "object" && detail !== null ? (detail as Record<string, unknown>) : {}) as {
        code?: string;
        error?: string;
        email?: string;
      };
      const code = (payload.code || payload.error || "").toString().toUpperCase();
      if (code === "EMAIL_NOT_VERIFIED") {
        emailVerificationListeners.forEach((fn) => {
          try {
            fn({ email: payload.email });
          } catch {
            // ignore listener errors
          }
        });
      }
    }

    const error = new Error(message) as Error & { detail?: unknown; status?: number };
    if (detail !== undefined) error.detail = detail;
    error.status = res.status;
    throw error;
  }
}

export async function logoutUser(): Promise<void> {
  clearAuthSession();
  try {
    await fetch(`${API_BASE}/auth/cognito/logout`, { method: "POST", credentials: "omit" });
  } catch {
    // backend logout is best-effort
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

export function updateUiPreferences(payload: UpdateUiPreferencesIn): Promise<UiPreferencesOut> {
  return requestJson<UiPreferencesOut>(`/users/me/ui-preferences`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

/** -------------------
 * Saved views
 * ------------------- */
export function listSavedViews(): Promise<SavedView[]> {
  return requestJson<SavedView[]>(`/saved-views/`);
}

export function createSavedView(payload: CreateSavedViewIn): Promise<SavedView> {
  return requestJson<SavedView>(`/saved-views/`, {
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
  return requestJson<Job[]>(`/jobs/${qs ? `?${qs}` : ""}`);
}

export function getJobDetails(jobId: number, opts?: { activity_limit?: number }): Promise<JobDetailsBundle> {
  const params = new URLSearchParams();
  if (opts?.activity_limit) {
    params.set("activity_limit", String(opts.activity_limit));
  }
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return requestJson<JobDetailsBundle>(`/jobs/${jobId}/details${suffix}`);
}

export function getJob(jobId: number | string): Promise<Job> {
  return requestJson<Job>(`/jobs/${jobId}`);
}

export function createJob(payload: CreateJobIn): Promise<Job> {
  return requestJson<Job>(`/jobs/`, {
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
export function listJobActivity(
  jobId: number | string,
  opts: { limit?: number; cursor_id?: number | null } = {}
): Promise<JobActivityPage> {
  const params = new URLSearchParams();
  const limit = Math.max(1, Math.min(Number(opts.limit ?? 20) || 20, 200));
  params.set("limit", String(limit));
  if (typeof opts.cursor_id === "number" && Number.isFinite(opts.cursor_id)) {
    params.set("cursor_id", String(opts.cursor_id));
  }
  const qs = params.toString();
  return requestJson<JobActivityPage>(`/jobs/${jobId}/activity${qs ? `?${qs}` : ""}`);
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