#!/usr/bin/env bash
# Set up Secret Manager wiring for the Ask Gemini feature.
#
# Idempotent. Creates the secret container, grants the webapp SA accessor
# permission, then prompts YOU to paste the AI Studio API key into stdin so
# the value never appears in shell history.
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-ai-rf-497701}"
SECRET_NAME="${SECRET_NAME:-gemini-api-key}"
WEBAPP_SA="${WEBAPP_SA:-876642352965-compute@developer.gserviceaccount.com}"

echo "== Gemini secret setup =="
echo "  project:    $PROJECT_ID"
echo "  secret:     $SECRET_NAME"
echo "  webapp SA:  $WEBAPP_SA"

gcloud services enable secretmanager.googleapis.com --project="$PROJECT_ID" >/dev/null

# 1. Create the secret container (no version yet).
if ! gcloud secrets describe "$SECRET_NAME" --project="$PROJECT_ID" >/dev/null 2>&1; then
    gcloud secrets create "$SECRET_NAME" \
        --replication-policy=automatic \
        --project="$PROJECT_ID"
    echo "Created secret container $SECRET_NAME."
else
    echo "Secret container $SECRET_NAME already exists."
fi

# 2. Grant the webapp service account accessor permission.
gcloud secrets add-iam-policy-binding "$SECRET_NAME" \
    --project="$PROJECT_ID" \
    --member="serviceAccount:$WEBAPP_SA" \
    --role="roles/secretmanager.secretAccessor" >/dev/null
echo "Granted secretAccessor to $WEBAPP_SA."

# 3. Prompt for the key and create a new secret version.
echo
echo "Paste your Gemini API key (input hidden). Get one at https://aistudio.google.com/app/apikey"
read -rs -p "GEMINI_API_KEY: " KEY
echo
if [ -z "$KEY" ]; then
    echo "No key entered. Skipping version creation. Re-run when ready."
    exit 1
fi
printf "%s" "$KEY" | gcloud secrets versions add "$SECRET_NAME" \
    --data-file=- \
    --project="$PROJECT_ID"
unset KEY
echo "New secret version created."

echo
echo "Next: redeploy the webapp so the secret is mounted as GEMINI_API_KEY:"
echo "  gcloud builds submit --config=cloudbuild.yaml ."
