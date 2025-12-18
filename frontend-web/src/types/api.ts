export type MessageOut = { message: string };

// -------- Auth --------
export type RegisterIn = { email: string; password: string; name?: string | null };
export type LoginIn = { email: string; password: string };
export type LoginOut = { access_token: string; token_type?: string };
export type ResendVerificationIn = { email: string };

// -------- Users / Settings --------
export type UserMeOut = {
  id: number;
  email: string;
  name?: string | null;
  auto_refresh_seconds: number;
  is_email_verified: boolean;
  created_at: string;
  email_verified_at?: string | null;
};

export type UserSettingsOut = { auto_refresh_seconds: number };
export type UpdateSettingsIn = { auto_refresh_seconds: number };
export type ChangePasswordIn = { current_password: string; new_password: string };

// -------- Jobs / Notes / Documents (minimal shapes used by UI) --------
export type Job = {
  id: number;
  company_name?: string;
  job_title?: string;
  location?: string | null;
  job_url?: string | null;
  status?: string | null;
  applied_date?: string | null;
  last_activity_at?: string | null;
  created_at?: string;
  updated_at?: string;
};

export type CreateJobIn = {
  company_name: string;
  job_title: string;
  location?: string | null;
  job_url?: string | null;
};

export type PatchJobIn = Partial<CreateJobIn> & { status?: string | null; applied_date?: string | null };

export type Note = {
  id: number;
  body?: string;
  created_at?: string;
};

export type AddNoteIn = { body: string };

export type DocumentItem = {
  id: number;
  filename?: string;
  content_type?: string;
  status?: string;
  created_at?: string;
};

export type PresignUploadIn = {
  doc_type: string;
  filename: string;
  content_type?: string | null;
  size_bytes?: number | null;
};
export type PresignUploadOut = { upload_url: string } & Record<string, unknown>;
export type ConfirmUploadIn = Record<string, unknown>;

