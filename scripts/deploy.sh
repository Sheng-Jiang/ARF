#!/usr/bin/env bash
#
# Deploy ARF to Cloud Run. Pins the project + region so every build targets the
# same environment regardless of the operator's local `gcloud config`.
#
# Usage:
#   scripts/deploy.sh           # deploy both the webapp and the batch job
#   scripts/deploy.sh webapp    # webapp (Cloud Run service) only
#   scripts/deploy.sh job       # batch pipeline (Cloud Run job) only
#
set -euo pipefail

PROJECT="ai-rf-497701"
REGION="asia-east1"

target="${1:-all}"

deploy_webapp() {
  echo "==> Building + deploying webapp (project=${PROJECT}, region=${REGION})"
  gcloud builds submit --config cloudbuild.yaml \
    --project "${PROJECT}" \
    --substitutions "_REGION=${REGION}" \
    .
}

deploy_job() {
  echo "==> Building + deploying batch job (project=${PROJECT}, region=${REGION})"
  gcloud builds submit --config cloudbuild.job.yaml \
    --project "${PROJECT}" \
    --substitutions "_REGION=${REGION}" \
    .
}

case "${target}" in
  webapp) deploy_webapp ;;
  job)    deploy_job ;;
  all)    deploy_job && deploy_webapp ;;
  *) echo "Unknown target '${target}' (expected: webapp | job | all)" >&2; exit 2 ;;
esac

echo "==> Done."
