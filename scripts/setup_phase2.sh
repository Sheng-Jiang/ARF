#!/usr/bin/env bash
# Phase 2 one-time setup: deploy the pipeline as a Cloud Run Job, create the
# service account it runs as (so it can write to the GCS bucket), schedule it
# weekly, and grant the webapp permission to trigger it on demand.
#
# Idempotent — safe to re-run.
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-ai-rf-497701}"
REGION="${REGION:-asia-east1}"
JOB="${JOB:-arf-pipeline}"
BUCKET="${BUCKET:-arf-data-ai-rf}"
JOB_SA="${JOB_SA:-arf-pipeline-runner}"
WEBAPP_SA="${WEBAPP_SA:-arf-webapp-runner}"
SCHEDULER_SA="${SCHEDULER_SA:-arf-pipeline-scheduler}"
SCHEDULE="${SCHEDULE:-0 4 * * SUN}"           # Sundays 04:00 UTC = noon Beijing; both legs snapshot Friday close (A股 Fri 15:00 CST, 港股 Fri 16:00 HKT, US Fri 16:00 ET)
TIMEZONE="${TIMEZONE:-Etc/UTC}"

echo "== Phase 2 setup =="
echo "  project:  $PROJECT_ID"
echo "  region:   $REGION"
echo "  job:      $JOB"
echo "  bucket:   $BUCKET"
echo "  schedule: $SCHEDULE ($TIMEZONE)"

gcloud config set project "$PROJECT_ID" >/dev/null

# 1. Enable required APIs (idempotent).
gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    cloudscheduler.googleapis.com \
    iam.googleapis.com \
    artifactregistry.googleapis.com

# 2. Create the pipeline-runner SA (writes to GCS) if absent.
if ! gcloud iam service-accounts describe \
        "${JOB_SA}@${PROJECT_ID}.iam.gserviceaccount.com" >/dev/null 2>&1; then
    gcloud iam service-accounts create "$JOB_SA" \
        --display-name="ARF pipeline runner"
fi
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
    --member="serviceAccount:${JOB_SA}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/storage.objectAdmin" >/dev/null

# 3. Build + deploy the job (uses cloudbuild.job.yaml).
gcloud builds submit --config=cloudbuild.job.yaml .

# 4. Attach the runner SA to the deployed job.
gcloud run jobs update "$JOB" --region="$REGION" \
    --service-account="${JOB_SA}@${PROJECT_ID}.iam.gserviceaccount.com"

# 5. Create scheduler SA (invokes the Cloud Run Job).
if ! gcloud iam service-accounts describe \
        "${SCHEDULER_SA}@${PROJECT_ID}.iam.gserviceaccount.com" >/dev/null 2>&1; then
    gcloud iam service-accounts create "$SCHEDULER_SA" \
        --display-name="ARF pipeline scheduler"
fi
gcloud run jobs add-iam-policy-binding "$JOB" --region="$REGION" \
    --member="serviceAccount:${SCHEDULER_SA}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/run.invoker" >/dev/null

# 6. Create / update the weekly Cloud Scheduler trigger.
JOB_URI="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${JOB}:run"
SCHEDULER_NAME="arf-weekly-run"
if gcloud scheduler jobs describe "$SCHEDULER_NAME" --location="$REGION" >/dev/null 2>&1; then
    ACTION=update
else
    ACTION=create
fi
gcloud scheduler jobs ${ACTION} http "$SCHEDULER_NAME" \
    --location="$REGION" \
    --schedule="$SCHEDULE" \
    --time-zone="$TIMEZONE" \
    --uri="$JOB_URI" \
    --http-method=POST \
    --oauth-service-account-email="${SCHEDULER_SA}@${PROJECT_ID}.iam.gserviceaccount.com"

# 7. Let the webapp SA trigger the job on demand (for the "Refresh now" button).
if gcloud iam service-accounts describe \
        "${WEBAPP_SA}@${PROJECT_ID}.iam.gserviceaccount.com" >/dev/null 2>&1; then
    gcloud run jobs add-iam-policy-binding "$JOB" --region="$REGION" \
        --member="serviceAccount:${WEBAPP_SA}@${PROJECT_ID}.iam.gserviceaccount.com" \
        --role="roles/run.invoker" >/dev/null
    echo "Granted webapp SA permission to run the job."
else
    echo "NOTE: webapp SA ${WEBAPP_SA} not found — create + attach it to the Cloud Run service,"
    echo "      then re-run this script (or run step 7 manually)."
fi

echo "Done."
echo "Trigger a one-off run with:"
echo "  gcloud run jobs execute $JOB --region=$REGION --wait"
