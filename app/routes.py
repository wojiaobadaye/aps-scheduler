import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, request, jsonify
from app.config import Config
from app.models import db, Script, Job
from app.scheduler import (
    scheduler,
    add_job_to_scheduler,
    remove_job_from_scheduler,
    pause_job,
    resume_job,
    trigger_job,
    list_jobs as sched_list_jobs,
)


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    with app.app_context():
        db.create_all()

    # ── Script CRUD ────────────────────────────────────────────

    @app.route("/api/scripts", methods=["GET"])
    def list_scripts():
        scripts = Script.query.all()
        return jsonify([s.to_dict() for s in scripts])

    @app.route("/api/scripts", methods=["POST"])
    def create_script():
        data = request.get_json(force=True)
        name = data.get("name")
        if not name:
            return jsonify({"error": "name is required"}), 400
        if Script.query.filter_by(name=name).first():
            return jsonify({"error": "script name already exists"}), 409

        script = Script(
            name=name,
            description=data.get("description", ""),
            content=data.get("content", ""),
        )
        db.session.add(script)
        db.session.commit()

        _write_script_file(name, data.get("content", ""))
        return jsonify(script.to_dict()), 201

    @app.route("/api/scripts/<int:script_id>", methods=["GET"])
    def get_script(script_id):
        script = db.session.get(Script, script_id)
        if not script:
            return jsonify({"error": "not found"}), 404
        return jsonify(script.to_dict())

    @app.route("/api/scripts/<int:script_id>", methods=["PUT"])
    def update_script(script_id):
        script = db.session.get(Script, script_id)
        if not script:
            return jsonify({"error": "not found"}), 404
        data = request.get_json(force=True)
        if "name" in data:
            script.name = data["name"]
        if "description" in data:
            script.description = data["description"]
        if "content" in data:
            script.content = data["content"]
            _write_script_file(script.name, data["content"])
        db.session.commit()
        return jsonify(script.to_dict())

    @app.route("/api/scripts/<int:script_id>", methods=["DELETE"])
    def delete_script(script_id):
        script = db.session.get(Script, script_id)
        if not script:
            return jsonify({"error": "not found"}), 404
        _remove_script_file(script.name)
        db.session.delete(script)
        db.session.commit()
        return jsonify({"message": "deleted"})

    # ── Job CRUD ──────────────────────────────────────────────

    def _sync_job_to_scheduler(job_record: Job):
        """Sync a DB Job record into APScheduler."""
        if job_record.enabled:
            add_job_to_scheduler(
                job_record.job_id,
                job_record.script_name,
                job_record.trigger,
                job_record.trigger_args,
            )
        else:
            remove_job_from_scheduler(job_record.job_id)

    @app.route("/api/jobs", methods=["GET"])
    def list_jobs():
        jobs = Job.query.all()
        return jsonify([j.to_dict() for j in jobs])

    @app.route("/api/jobs", methods=["POST"])
    def create_job():
        data = request.get_json(force=True)
        job_id = data.get("job_id")
        if not job_id:
            return jsonify({"error": "job_id is required"}), 400
        if Job.query.filter_by(job_id=job_id).first():
            return jsonify({"error": "job_id already exists"}), 409

        job = Job(
            job_id=job_id,
            script_name=data["script_name"],
            trigger=data["trigger"],
            trigger_args=data.get("trigger_args", "{}"),
            enabled=data.get("enabled", True),
        )
        db.session.add(job)
        db.session.commit()

        _sync_job_to_scheduler(job)
        return jsonify(job.to_dict()), 201

    @app.route("/api/jobs/<job_id>", methods=["GET"])
    def get_job(job_id):
        job = Job.query.filter_by(job_id=job_id).first()
        if not job:
            return jsonify({"error": "not found"}), 404
        return jsonify(job.to_dict())

    @app.route("/api/jobs/<job_id>", methods=["PUT"])
    def update_job(job_id):
        job = Job.query.filter_by(job_id=job_id).first()
        if not job:
            return jsonify({"error": "not found"}), 404
        data = request.get_json(force=True)
        for field in ("script_name", "trigger", "trigger_args", "enabled"):
            if field in data:
                setattr(job, field, data[field])
        db.session.commit()
        _sync_job_to_scheduler(job)
        return jsonify(job.to_dict())

    @app.route("/api/jobs/<job_id>", methods=["DELETE"])
    def delete_job(job_id):
        job = Job.query.filter_by(job_id=job_id).first()
        if not job:
            return jsonify({"error": "not found"}), 404
        remove_job_from_scheduler(job.job_id)
        db.session.delete(job)
        db.session.commit()
        return jsonify({"message": "deleted"})

    @app.route("/api/jobs/<job_id>/pause", methods=["POST"])
    def pause_job_route(job_id):
        job = Job.query.filter_by(job_id=job_id).first()
        if not job:
            return jsonify({"error": "not found"}), 404
        pause_job(job.job_id)
        job.enabled = False
        db.session.commit()
        return jsonify({"message": "paused"})

    @app.route("/api/jobs/<job_id>/resume", methods=["POST"])
    def resume_job_route(job_id):
        job = Job.query.filter_by(job_id=job_id).first()
        if not job:
            return jsonify({"error": "not found"}), 404
        resume_job(job.job_id)
        job.enabled = True
        db.session.commit()
        return jsonify({"message": "resumed"})

    @app.route("/api/jobs/<job_id>/trigger", methods=["POST"])
    def trigger_job_route(job_id):
        job = Job.query.filter_by(job_id=job_id).first()
        if not job:
            return jsonify({"error": "not found"}), 404
        trigger_job(job.job_id)
        return jsonify({"message": "triggered"})

    @app.route("/api/scheduler/status", methods=["GET"])
    def scheduler_status():
        running = scheduler.running
        jobs = sched_list_jobs()
        return jsonify({"running": running, "jobs": jobs})

    return app


def _write_script_file(name: str, content: str):
    scripts_dir = Config.SCRIPTS_DIR
    os.makedirs(scripts_dir, exist_ok=True)
    path = os.path.join(scripts_dir, f"{name}.py")
    with open(path, "w") as f:
        f.write(content)


def _remove_script_file(name: str):
    path = os.path.join(Config.SCRIPTS_DIR, f"{name}.py")
    if os.path.exists(path):
        os.remove(path)
