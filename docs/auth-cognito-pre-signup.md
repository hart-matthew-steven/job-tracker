# Cognito Pre Sign-up Lambda

## Purpose

Cognito’s default signup flow requires users to confirm their email before the account becomes active. We want Cognito to accept the signup immediately and let the application deliver/track verification emails later (e.g., via Resend). The Pre Sign-up trigger is the safest hook for this: it runs before Cognito sends an email and lets us flip the auto-confirm flag.

## Behavior

- Trigger: `PreSignUp_SignUp` or `PreSignUp_AdminCreateUser`.
- The Lambda sets:
  - `event.response.autoConfirmUser = true`
  - `event.response.autoVerifyEmail = false`
- No network calls, no secrets, no database writes. It simply logs the trigger and returns the event.
- Unknown trigger sources are logged (warning) and passed through unchanged.

## Why disable Cognito verification?

- Future Resend-powered emails need full control over when/how verification happens.
- Avoid duplicate emails (Cognito + Resend) while the migration is in flight.
- Keeps Cognito user state aligned with the custom UI (users show as “CONFIRMED” immediately).

## Deployment

1. Build/push the container image (see `lambda/cognito_pre_signup/README.md`).
2. In the Cognito console: User Pool → **Triggers → Pre sign-up** → select the new Lambda.
3. Save changes. The effect is immediate for all new signups/admin-created users.

## Testing

1. Attach the Lambda and create a new user (UI, CLI, or AWS console).
2. Observe CloudWatch Logs for entries like `PreSignUp_SignUp`.
3. In Cognito → Users, the new account should already be in `CONFIRMED` state without receiving a Cognito email.

## Rollback

1. Detach the Lambda from the Pre sign-up trigger.
2. Cognito reverts to its native email confirmation flow automatically.


