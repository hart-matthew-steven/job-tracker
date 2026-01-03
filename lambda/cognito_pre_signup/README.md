# Cognito Pre Sign-up Lambda

This Lambda is attached to the **Cognito Pre Sign-up** trigger so that every user is immediately confirmed when they register (or when an admin creates them). By auto-confirming:

- Cognito will not send verification-code emails.
- The application can handle verification later (e.g., Resend-driven workflows) without conflicting with Cognito’s native flow.

## Behavior

- Sets `event.response.autoConfirmUser = True`.
- Sets `event.response.autoVerifyEmail = False` to keep email verification under our control.
- Supports `PreSignUp_SignUp` and `PreSignUp_AdminCreateUser`. Any other trigger source is logged (warning) and returned untouched.
- No network calls, no external dependencies, and no secrets.

## Build & Push

```bash
cd lambda/cognito_pre_signup
export AWS_ACCOUNT_ID=<account-id>
export AWS_REGION=<region>
export ECR_REPO_NAME=job-tracker-cognito-pre-signup
export IMAGE_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}:latest"

aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

docker buildx build \
  --platform linux/amd64 \
  --provenance=false \
  --sbom=false \
  --output type=image,oci-mediatypes=false,compression=gzip,push=true \
  -t "$IMAGE_URI" \
  .
```

## Attach in Cognito

1. Open the Cognito User Pool in the AWS console.
2. Navigate to **Triggers → Pre sign-up**.
3. Select this Lambda (new image deployed from steps above).
4. Save changes.

## Testing

1. Deploy the Lambda and attach it to the User Pool.
2. Run a signup flow (SPA or CLI); Cognito should immediately consider the user confirmed (no confirmation email sent).
3. In the Lambda logs (CloudWatch), you should see entries for `PreSignUp_SignUp` or `PreSignUp_AdminCreateUser`.

## Notes

- The Lambda intentionally returns the event even for unsupported trigger sources to avoid blocking Cognito.
- Email verification remains off inside Cognito so we can manage it later via Resend or other tooling.
- No environment variables are required.


