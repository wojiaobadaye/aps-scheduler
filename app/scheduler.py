import sys
import os
import json
import logging
import importlib.util
import traceback
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

from app.config import Config

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=4)
_retry_count: dict[str, int] = {}

scheduler = BackgroundScheduler(
    timezone=Config.SCHEDULER_TIMEZONE,
    job_defaults=Config.SCHEDULER_JOB_DEFAULTS,
    jobstores={},
)


def configure_jobstore(engine):
    """配置 SQLAlchemyJobStore，需在 create_app 中调用。幂等，可重复调用。"""
    try:
        scheduler.add_jobstore(SQLAlchemyJobStore(engine=engine))
    except ValueError:
        pass


def _execute_script(script_name: str):
    """执行脚本，带超时和异常处理。"""
    started_at = datetime.now(timezone.utc)
    status = "success"
    output = ""
    error = ""

    scripts_dir = Config.SCRIPTS_DIR
    script_path = os.path.join(scripts_dir, script_name)

    if not script_path.endswith(".py"):
        script_path += ".py"

    if not os.path.exists(script_path):
        _save_execution_log("unknown", "failed", "", f"Script not found: {script_path}", started_at, datetime.now(timezone.utc))
        return

    spec = importlib.util.spec_from_file_location(script_name.replace(".", "_"), script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    target = None
    if hasattr(module, "run"):
        target = module.run
    elif hasattr(module, "main"):
        target = module.main

    if not target:
        _save_execution_log(script_name, "failed", "", "No run() or main() function found", started_at, datetime.now(timezone.utc))
        return

    try:
        future = _executor.submit(target)
        future.result(timeout=Config.SCHEDULER_EXECUTION_TIMEOUT)
    except FuturesTimeout:
        status = "timeout"
        error = f"Execution timed out after {Config.SCHEDULER_EXECUTION_TIMEOUT}s"
        logger.warning("Job %s timed out", script_name)
    except Exception as e:
        status = "failed"
        error = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
        logger.error("Job %s failed: %s", script_name, error)

        # Auto retry
        max_retries = Config.SCHEDULER_MAX_RETRIES
        if max_retries > 0:
            retried = _retry_count.get(script_name, 0)
            if retried < max_retries:
                _retry_count[script_name] = retried + 1
                logger.info("Retrying job %s (%d/%d)", script_name, retried + 1, max_retries)
                import time
                time.sleep(Config.SCHEDULER_RETRY_DELAY)
                _execute_script(script_name)
                return
            else:
                del _retry_count[script_name]
    else:
        output = "Execution completed successfully"

    finished_at = datetime.now(timezone.utc)
    _save_execution_log(script_name, status, output, error, started_at, finished_at)
    _retry_count.pop(script_name, None)


def _save_execution_log(job_id: str, status: str, output: str, error: str,
                        started_at: datetime, finished_at: datetime):
    """保存执行日志到数据库。"""
    try:
        from app.models import db, ExecutionLog
        log = ExecutionLog(
            job_id=job_id,
            status=status,
            output=output[:500],
            error=error[:2000],
            started_at=started_at,
            finished_at=finished_at,
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        logger.error("Failed to save execution log: %s", e)


def parse_trigger(trigger: str, trigger_args: str):
    args = json.loads(trigger_args) if isinstance(trigger_args, str) else trigger_args or {}
    if trigger == "interval":
        return IntervalTrigger(**args)
    elif trigger == "cron":
        return CronTrigger(**args)
    elif trigger == "date":
        return DateTrigger(**args)
    else:
        raise ValueError(f"Unsupported trigger: {trigger}")


def add_job_to_scheduler(job_id: str, script_name: str, trigger: str, trigger_args: str):
    trig = parse_trigger(trigger, trigger_args)
    scheduler.add_job(
        func=_execute_script,
        trigger=trig,
        args=[script_name],
        id=job_id,
        replace_existing=True,
    )


def remove_job_from_scheduler(job_id: str):
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)


def pause_job(job_id: str):
    scheduler.pause_job(job_id)


def resume_job(job_id: str):
    scheduler.resume_job(job_id)


def trigger_job(job_id: str):
    job = scheduler.get_job(job_id)
    if job:
        job.func(*job.args, **job.kwargs)


def list_jobs():
    return [
        {
            "id": j.id,
            "name": j.name,
            "next_run_time": str(j.next_run_time) if j.next_run_time else None,
            "trigger": str(j.trigger),
        }
        for j in scheduler.get_jobs()
    ]


def get_job(job_id: str):
    j = scheduler.get_job(job_id)
    if not j:
        return None
    return {
        "id": j.id,
        "name": j.name,
        "next_run_time": str(j.next_run_time) if j.next_run_time else None,
        "trigger": str(j.trigger),
    }
