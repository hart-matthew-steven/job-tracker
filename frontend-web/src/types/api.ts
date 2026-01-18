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
export type UiPreferences = Record<string, boolean>;

export type UserMeOut = {
  id: number;
  email: string;
  name?: string | null;
  auto_refresh_seconds: number;
  created_at: string;
  is_email_verified: boolean;
  email_verified_at?: string | null;
  must_change_password?: boolean;
  ui_preferences?: UiPreferences;
};

export type UserSettingsOut = {
  auto_refresh_seconds: number;
  theme: string;
  default_jobs_sort: string;
  default_jobs_view: string;
  data_retention_days: number;
};
export type UpdateSettingsIn = UserSettingsOut;
export type UiPreferencesOut = { ui_preferences: UiPreferences };
export type UpdateUiPreferencesIn = { preferences: Record<string, boolean> };
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
  last_action_at?: string | null;
  next_action_at?: string | null;
  next_action_title?: string | null;
  priority?: string | null;
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
  priority?: string | null;
  next_action_at?: string | null;
  next_action_title?: string | null;
  last_action_at?: string | null;
};

export type JobDetailsBundle = {
  job: Job;
  notes: Note[];
  interviews: JobInterview[];
  activity: JobActivityPage;
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

export type JobActivityPage = {
  items: JobActivity[];
  next_cursor?: number | null;
};

export type JobBoardCard = {
  id: number;
  status: string;
  company_name: string;
  job_title: string;
  location?: string | null;
  updated_at: string;
  last_activity_at?: string | null;
  last_action_at?: string | null;
  next_action_at?: string | null;
  next_action_title?: string | null;
  priority: string;
  tags: string[];
  needs_follow_up: boolean;
};

export type JobsBoardResponse = {
  statuses: string[];
  jobs: JobBoardCard[];
  meta?: Record<string, unknown>;
};

export type ActivityMetrics = {
  range_days: number;
  total_events: number;
  per_type: Record<string, number>;
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

// -------- Billing / Credits --------
export type CreditsBalance = {
  currency: string;
  balance_cents: number;
  balance_dollars: string;
  lifetime_granted_cents: number;
  lifetime_spent_cents: number;
  as_of: string;
};

export type CreditPack = {
  key: string;
  price_id: string;
  credits: number;
  currency: string;
  display_price_dollars: string;
};

export type StripeCheckoutSessionOut = {
  checkout_session_id: string;
  checkout_url: string;
  currency: string;
  pack_key: string;
  credits_granted: number;
};


// -------- AI Assistant --------
export type AiPurpose = "general" | "cover_letter" | "thank_you" | "resume_tailoring";

export type AiConversationSummary = {
  id: number;
  title?: string | null;
  created_at: string;
  updated_at: string;
  message_count: number;
};

export type AiConversationListResponse = {
  conversations: AiConversationSummary[];
  next_offset?: number | null;
};

export type AiMessage = {
  id: number;
  role: string;
  content_text: string;
  created_at: string;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  total_tokens?: number | null;
  credits_charged?: number | null;
  model?: string | null;
  balance_remaining_cents?: number | null;
};

export type AiConversationDetail = {
  id: number;
  title?: string | null;
  created_at: string;
  updated_at: string;
  messages: AiMessage[];
  next_offset?: number | null;
};

export type AiConversationCreateIn = {
  title?: string | null;
  message?: string | null;
  purpose?: AiPurpose | null;
};

export type AiConversationMessageIn = {
  content: string;
  request_id?: string | null;
  purpose?: AiPurpose | null;
};

export type AiConversationMessageResponse = {
  conversation_id: number;
  user_message: AiMessage;
  assistant_message: AiMessage;
  credits_used_cents: number;
  credits_refunded_cents: number;
  credits_reserved_cents: number;
  credits_remaining_cents: number;
  credits_remaining_dollars: string;
};

export type AiConfig = {
  max_input_chars: number;
};

export type AiConversationUpdateIn = {
  title?: string | null;
};
