# GuardDuty Scan Forwarder Lambda (EventBridge → FastAPI callback)

This Lambda receives **EventBridge** events from **Amazon GuardDuty Malware Protection for S3** and forwards the scan result to the backend document callback endpoint:

`POST /jobs/{job_id}/documents/{document_id}/scan-result`

It extracts `document_id` from the S3 key format:

`<prefix>/jobs/<job_id>/<doc_type>/<document_id>/<uuid>_<original_filename>`

## Environment variables (provided at deploy time)

Do **not** commit secrets to git.

- `BACKEND_BASE_URL`: e.g. `https://api.example.com`
- `SETTINGS_BUNDLE_SECRET_ARN`: ARN of the shared Secrets Manager JSON bundle. The Lambda expects this JSON blob to include a `DOC_SCAN_SHARED_SECRET` key; it loads the bundle once per cold start and reads the shared secret from that key before calling the FastAPI callback. Keeping the scan secret in the same bundle as the backend/App Runner services ensures both sides stay in sync without proliferating new env vars.

## Result mapping

GuardDuty scan status → backend scan status:

- `NO_THREATS_FOUND` → `CLEAN`
- `THREATS_FOUND` → `INFECTED`
- anything else / missing → `ERROR`

## Verdict source of truth (important)

GuardDuty’s EventBridge event may not include S3 object tags. The authoritative verdict is the S3 object tag:

- `GuardDutyMalwareScanStatus = NO_THREATS_FOUND | THREATS_FOUND | FAILED | ACCESS_DENIED | UNSUPPORTED`

This Lambda:
- First tries to read `GuardDutyMalwareScanStatus` from the EventBridge event payload
- If missing, calls S3 `GetObjectTagging` for `(bucket, key)` and reads the tag value

Required IAM permissions (scope as tightly as possible):
- `s3:GetObjectTagging` on `arn:aws:s3:::job-tracker-documents-0407/job-tracker/*`
- `secretsmanager:GetSecretValue` on the `SETTINGS_BUNDLE_SECRET_ARN`

## Build + push to ECR (example)

```bash
cd lambda/guardduty_scan_forwarder

export AWS_REGION="us-east-1"
export ACCOUNT_ID="<YOUR_AWS_ACCOUNT_ID>"
export REPO="job-tracker-guardduty-scan-forwarder"
export IMAGE_URI="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${REPO}:latest"

aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

docker buildx build \
  --platform linux/amd64 \
  --provenance=false \
  --sbom=false \
  --output type=image,oci-mediatypes=false,compression=gzip,push=true \
  -t "$IMAGE_URI" \
  .
```

In the Lambda console, use the image **digest URI** (`...@sha256:...`) for stability.


