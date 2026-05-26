from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Script(db.Model):
    __tablename__ = "scripts"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)
    description = db.Column(db.Text, default="")
    content = db.Column(db.Text, nullable=False)
    requirements = db.Column(db.Text, default="")
    env_name = db.Column(db.String(128), default="")
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "content": self.content,
            "requirements": self.requirements,
            "env_name": self.env_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Job(db.Model):
    __tablename__ = "jobs"

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.String(128), unique=True, nullable=False)
    script_name = db.Column(db.String(128), nullable=False)
    trigger = db.Column(db.String(32), nullable=False)
    trigger_args = db.Column(db.Text, default="{}")
    enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "job_id": self.job_id,
            "script_name": self.script_name,
            "trigger": self.trigger,
            "trigger_args": self.trigger_args,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ExecutionLog(db.Model):
    __tablename__ = "execution_logs"

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.String(128), nullable=False, index=True)
    status = db.Column(db.String(16), nullable=False)
    output = db.Column(db.Text, default="")
    error = db.Column(db.Text, default="")
    started_at = db.Column(db.DateTime, nullable=False)
    finished_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "job_id": self.job_id,
            "status": self.status,
            "output": self.output,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }


class ScriptEnv(db.Model):
    __tablename__ = "script_envs"

    id = db.Column(db.Integer, primary_key=True)
    env_name = db.Column(db.String(128), unique=True, nullable=False)
    requirements = db.Column(db.Text, default="")
    requirements_hash = db.Column(db.String(64), unique=True, nullable=False)
    status = db.Column(db.String(16), default="creating")  # creating | ready | failed
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "env_name": self.env_name,
            "requirements": self.requirements,
            "requirements_hash": self.requirements_hash,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
