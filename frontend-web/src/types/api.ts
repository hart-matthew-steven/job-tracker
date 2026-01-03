export type MessageOut = { message: string };

// -------- Auth --------
export type CognitoTokens = {
  access_token: string;
  id_token?: string;
  refresh_token?: string;
  expires_in: number;
  token_type: string;
};

export type CognitoAuthResponse = {
  status: "OK" | "CHALLENGE";
  message?: string | null;
  next_step?: "MFA_SETUP" | "SOFTWARE_TOKEN_MFA" | "NEW_PASSWORD_REQUIRED" | "CUSTOM_CHALLENGE" | "UNKNOWN";
  challenge_name?: string | null;
  session?: string | null;
  tokens?: CognitoTokens;
};

export type CognitoSignupIn = { email: string; password: string; name: string; turnstile_token: string };
export type CognitoConfirmIn = { email: string; code: string };
export type CognitoRefreshIn = { refresh_token: string };
export type CognitoMessage = { status?: string; message?: string };
export type CognitoChallengeRequest = {
  email: string;
  challenge_name: string;
  session: string;
  responses: Record<string, string>;
};
export type CognitoMfaSetupIn = { session: string; label?: string };
export type CognitoMfaSetupOut = { secret_code: string; otpauth_uri?: string; session?: string | null };
export type CognitoMfaVerifyIn = { email: string; session: string; code: string; friendly_name?: string };
export type EmailVerificationSendIn = { email: string };
export type EmailVerificationSendOut = { status?: string; message?: string; resend_available_in_seconds?: number };
export type EmailVerificationConfirmIn = { email: string; code: string };

// -------- Users / Settings --------
export type UserMeOut = {
  id: number;
  email: string;
  name?: string | null;
  auto_refresh_seconds: number;
  created_at: string;
  is_email_verified: boolean;
  email_verified_at?: string | null;
};

export type UserSettingsOut = {
  auto_refresh_seconds: number;
  theme: string;
  default_jobs_sort: string;
  default_jobs_view: string;
  data_retention_days: number;
};
export type UpdateSettingsIn = UserSettingsOut;
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
  tags?: string[];
};

export type CreateJobIn = {
  company_name: string;
  job_title: string;
  location?: string | null;
  job_url?: string | null;
  tags?: string[];
};

export type PatchJobIn = Partial<CreateJobIn> & {
  status?: string | null;
  applied_date?: string | null;
  tags?: string[];
};

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

// -------- Saved views --------
export type SavedView = {
  id: number;
  name: string;
  data: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type CreateSavedViewIn = {
  name: string;
  data: Record<string, unknown>;
};

export type PatchSavedViewIn = Partial<CreateSavedViewIn>;

// -------- Job activity --------
export type JobActivity = {
  id: number;
  application_id: number;
  type: string;
  message?: string | null;
  data?: Record<string, unknown> | null;
  created_at: string;
};

// -------- Interviews --------
export type JobInterview = {
  id: number;
  application_id: number;
  scheduled_at: string;
  stage?: string | null;
  kind?: string | null;
  location?: string | null;
  interviewer?: string | null;
  status: string;
  notes?: string | null;
  created_at: string;
  updated_at: string;
};

export type CreateInterviewIn = {
  scheduled_at: string;
  stage?: string | null;
  kind?: string | null;
  location?: string | null;
  interviewer?: string | null;
  status?: string | null;
  notes?: string | null;
};

export type PatchInterviewIn = Partial<CreateInterviewIn>;

