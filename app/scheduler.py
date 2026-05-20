import sys
import os
import importlib.util

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
import json


scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
_job_store = {}


def _execute_script(script_name: str):
    scripts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts")
    script_path = os.path.join(scripts_dir, script_name)

    if not script_path.endswith(".py"):
        script_path += ".py"

    if not os.path.exists(script_path):
        raise FileNotFoundError(f"Script not found: {script_path}")

    spec = importlib.util.spec_from_file_location(script_name.replace(".", "_"), script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if hasattr(module, "run"):
        module.run()
    elif hasattr(module, "main"):
        module.main()


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
        scheduler.modify_job(job_id, next_run_time=None)
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
