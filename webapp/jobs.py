"""Trigger the ARF pipeline Cloud Run Job from the webapp.

Configuration via env vars:
    GCP_PROJECT     project id (e.g. ai-rf-497701)
    GCP_REGION      region (default asia-east1)
    PIPELINE_JOB    Cloud Run Job name (default arf-pipeline)

The webapp service account must have roles/run.invoker on the job.
"""
import os
from datetime import date


def is_enabled() -> bool:
    """True if the env is configured to trigger the pipeline job."""
    return bool(os.getenv("GCP_PROJECT") and os.getenv("PIPELINE_JOB", "arf-pipeline"))


def trigger_pipeline(as_of: date | None = None) -> str:
    """Kick off the Cloud Run Job; return the execution name.

    Raises RuntimeError if the env isn't configured.
    """
    project = os.getenv("GCP_PROJECT")
    region = os.getenv("GCP_REGION", "asia-east1")
    job = os.getenv("PIPELINE_JOB", "arf-pipeline")
    if not project:
        raise RuntimeError("GCP_PROJECT env var required to trigger pipeline")

    from google.cloud import run_v2  # type: ignore[import]

    client = run_v2.JobsClient()
    job_name = f"projects/{project}/locations/{region}/jobs/{job}"

    overrides = None
    if as_of is not None:
        overrides = run_v2.RunJobRequest.Overrides(
            container_overrides=[
                run_v2.RunJobRequest.Overrides.ContainerOverride(
                    env=[
                        run_v2.EnvVar(name="AS_OF", value=as_of.isoformat()),
                        run_v2.EnvVar(name="TRIGGER_SOURCE", value="webapp"),
                    ],
                )
            ],
        )

    request = run_v2.RunJobRequest(name=job_name, overrides=overrides)
    op = client.run_job(request=request)
    # op.metadata.name is the execution resource; don't block on op.result().
    try:
        return op.metadata.name  # type: ignore[no-any-return]
    except Exception:
        return job_name


def get_execution_status(execution_name: str) -> dict:
    """Query the status of a pipeline Cloud Run Job execution.

    Returns a dict with:
        status: 'running' | 'succeeded' | 'failed' | 'cancelled' | 'unknown'
        percent: int (0 to 100)
        message: str
    """
    project = os.getenv("GCP_PROJECT")
    if not project:
        return {"status": "unknown", "percent": 0, "message": "GCP_PROJECT not configured"}

    from google.cloud import run_v2  # type: ignore[import]
    client = run_v2.ExecutionsClient()
    try:
        execution = client.get_execution(name=execution_name)
        
        # Check conditions
        is_succeeded = False
        is_failed = False
        
        # Check execution conditions
        for cond in getattr(execution, "conditions", []):
            if cond.type == "Succeeded":
                if cond.status == "True":
                    is_succeeded = True
                elif cond.status == "False":
                    is_failed = True

        if is_succeeded:
            return {"status": "succeeded", "percent": 100, "message": "运行成功 ✓"}
        elif is_failed:
            return {"status": "failed", "percent": 100, "message": "运行失败 ❌"}
        elif getattr(execution, "cancelled", False):
            return {"status": "cancelled", "percent": 100, "message": "运行被取消 🛑"}
            
        return {"status": "running", "percent": 50, "message": "正在执行异步管道任务..."}
    except Exception as exc:
        return {"status": "unknown", "percent": 0, "message": f"查询状态失败: {exc}"}
