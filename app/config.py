import os


class Config:
    SCHEDULER_API_ENABLED = True
    SCHEDULER_TIMEZONE = "Asia/Shanghai"
    SCHEDULER_JOB_DEFAULTS = {
        "max_instances": 1,
        "coalesce": True,
        "misfire_grace_time": 30,
    }
    SCHEDULER_EXECUTION_TIMEOUT = int(os.getenv("SCHEDULER_EXECUTION_TIMEOUT", "300"))
    SCHEDULER_MAX_RETRIES = int(os.getenv("SCHEDULER_MAX_RETRIES", "0"))
    SCHEDULER_RETRY_DELAY = int(os.getenv("SCHEDULER_RETRY_DELAY", "10"))
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URI", "sqlite:///scheduler.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts")
    JOBS = []
    CONDA_EXECUTABLE = os.getenv("CONDA_EXECUTABLE", "conda")
    CONDA_ENV_BASE = os.getenv("CONDA_ENV_BASE", "base")
    CONDA_CREATE_TIMEOUT = int(os.getenv("CONDA_CREATE_TIMEOUT", "300"))
