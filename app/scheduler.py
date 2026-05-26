import sys
import os
import json
import logging
import hashlib
import subprocess
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


def compute_requirements_hash(requirements: str) -> str:
    """计算 requirements 文本的 sha256 前 12 位作为环境标识。"""
    return hashlib.sha256(requirements.strip().encode()).hexdigest()[:12]


def parse_requirements(text: str) -> list[dict]:
    """解析 requirements.txt 文本为结构化包描述列表。"""
    lines = text.strip().splitlines()
    result = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith(("#", "-")):
            continue
        for op in ("==", ">=", "<=", "!=", "~=", ">", "<"):
            if op in line:
                name, ver = line.split(op, 1)
                result.append({"name": name.strip(), "op": op, "version": ver.strip()})
                break
        else:
            result.append({"name": line, "op": None, "version": None})
    return result


def _version_tuple(v: str) -> tuple:
    """'2.1.3' -> (2, 1, 3)，用于版本比较。"""
    parts = []
    for p in v.replace("-", ".").split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(p)
    return tuple(parts)


def is_subset_compatible(new_pkgs: list[dict], env_pkgs: list[dict]) -> bool:
    """检查 new_pkgs 是否为 env_pkgs 的兼容子集。"""
    if not new_pkgs:
        return True
    env_map = {p["name"]: p for p in env_pkgs}
    for npkg in new_pkgs:
        epkg = env_map.get(npkg["name"])
        if not epkg:
            return False
        # 新包无版本约束 -> 兼容
        if npkg["op"] is None or npkg["version"] is None:
            continue
        # 环境包无版本 -> 保守认为兼容
        if epkg["op"] is None or epkg["version"] is None:
            continue
        # Known-compatible operator combinations
        if npkg["op"] == "==" and epkg["op"] == "==":
            if epkg["version"] != npkg["version"]:
                return False
            continue
        if npkg["op"] == ">=":
            if epkg["op"] == "==":
                if _version_tuple(epkg["version"]) < _version_tuple(npkg["version"]):
                    return False
                continue
            elif epkg["op"] == ">=":
                if _version_tuple(epkg["version"]) < _version_tuple(npkg["version"]):
                    return False
                continue
        # Unknown/unhandled operator combination — conservative: don't assume compatible
        return False
    return True


def match_environment(session, requirements: str) -> str | None:
    """从已有的 ready 环境中匹配兼容的环境，没有则返回 None。"""
    if not requirements.strip():
        return Config.CONDA_ENV_BASE

    from app.models import ScriptEnv

    envs = session.query(ScriptEnv).filter_by(status="ready").all()
    new_pkgs = parse_requirements(requirements)

    for env in envs:
        env_pkgs = parse_requirements(env.requirements)
        if env.requirements.strip() == requirements.strip():
            return env.env_name
        if is_subset_compatible(new_pkgs, env_pkgs):
            return env.env_name

    return None


def create_conda_env(env_name: str, requirements: str) -> str:
    """创建 Conda 环境并安装依赖。返回 'ready' 或 'failed'。"""
    req_path = None
    try:
        subprocess.run(
            [Config.CONDA_EXECUTABLE, "create", "-n", env_name, "-y", "python=3.12"],
            capture_output=True, text=True, check=True,
            timeout=Config.CONDA_CREATE_TIMEOUT,
        )
        if requirements.strip():
            req_path = os.path.join(Config.SCRIPTS_DIR, f"_{env_name}_requirements.txt")
            with open(req_path, "w") as f:
                f.write(requirements)
            subprocess.run(
                [Config.CONDA_EXECUTABLE, "run", "-n", env_name, "pip", "install", "-r", req_path],
                capture_output=True, text=True, check=True,
                timeout=Config.CONDA_CREATE_TIMEOUT,
            )
        return "ready"
    except subprocess.TimeoutExpired:
        logger.error("Conda env %s creation timed out", env_name)
        return "failed"
    except FileNotFoundError:
        logger.error("Conda executable not found: %s", Config.CONDA_EXECUTABLE)
        return "failed"
    except Exception as e:
        logger.error("Failed to create conda env %s: %s", env_name, e)
        return "failed"
    finally:
        if req_path and os.path.exists(req_path):
            os.remove(req_path)


def ensure_env(session, requirements: str) -> str:
    """确保环境存在。返回 env_name。"""
    if not requirements.strip():
        return Config.CONDA_ENV_BASE

    matched = match_environment(session, requirements)
    if matched:
        return matched

    from app.models import ScriptEnv

    req_hash = compute_requirements_hash(requirements)
    env_name = f"aps_{req_hash}"

    env_record = ScriptEnv(
        env_name=env_name,
        requirements=requirements.strip(),
        requirements_hash=req_hash,
        status="creating",
    )
    session.add(env_record)
    session.commit()

    status = create_conda_env(env_name, requirements)
    env_record.status = status
    session.commit()
    return env_name


def cleanup_unused_envs(session) -> int:
    """删除无脚本引用的孤立 conda 环境。"""
    from app.models import Script, ScriptEnv

    unused = (
        session.query(ScriptEnv)
        .filter(~session.query(Script.env_name).filter(Script.env_name == ScriptEnv.env_name).exists())
        .all()
    )
    count = 0
    for env in unused:
        try:
            subprocess.run(
                [Config.CONDA_EXECUTABLE, "env", "remove", "-n", env.env_name, "-y"],
                capture_output=True, text=True, check=True, timeout=60,
            )
            session.delete(env)
            count += 1
        except Exception as e:
            logger.warning("Failed to remove conda env %s: %s", env.env_name, e)
    session.commit()
    return count
