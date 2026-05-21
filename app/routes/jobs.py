from flask import Blueprint, request, jsonify
from app.models import db, Job
from app.errors import AppError
from app.scheduler import (
    add_job_to_scheduler,
    remove_job_from_scheduler,
    pause_job as sched_pause,
    resume_job as sched_resume,
    trigger_job as sched_trigger,
    list_jobs as sched_list_jobs,
)

jobs_bp = Blueprint("jobs", __name__)


def _require_fields(data, *fields):
    for f in fields:
        if f not in data or not data[f]:
            raise AppError(f"{f} is required", 400)


def _sync_job_to_scheduler(job_record: Job):
    if job_record.enabled:
        add_job_to_scheduler(
            job_record.job_id,
            job_record.script_name,
            job_record.trigger,
            job_record.trigger_args,
        )
    else:
        remove_job_from_scheduler(job_record.job_id)


@jobs_bp.route("/api/jobs", methods=["GET"])
def list_jobs():
    jobs = Job.query.all()
    return jsonify([j.to_dict() for j in jobs])


@jobs_bp.route("/api/jobs", methods=["POST"])
def create_job():
    data = request.get_json(force=True)
    _require_fields(data, "job_id", "script_name", "trigger")
    if Job.query.filter_by(job_id=data["job_id"]).first():
        raise AppError("job_id already exists", 409)

    job = Job(
        job_id=data["job_id"],
        script_name=data["script_name"],
        trigger=data["trigger"],
        trigger_args=data.get("trigger_args", "{}"),
        enabled=data.get("enabled", True),
    )
    db.session.add(job)
    db.session.commit()

    _sync_job_to_scheduler(job)
    return jsonify(job.to_dict()), 201


@jobs_bp.route("/api/jobs/<job_id>", methods=["GET"])
def get_job(job_id):
    job = Job.query.filter_by(job_id=job_id).first()
    if not job:
        raise AppError("not found", 404)
    return jsonify(job.to_dict())


@jobs_bp.route("/api/jobs/<job_id>", methods=["PUT"])
def update_job(job_id):
    job = Job.query.filter_by(job_id=job_id).first()
    if not job:
        raise AppError("not found", 404)
    data = request.get_json(force=True)
    for field in ("script_name", "trigger", "trigger_args", "enabled"):
        if field in data:
            setattr(job, field, data[field])
    db.session.commit()
    _sync_job_to_scheduler(job)
    return jsonify(job.to_dict())


@jobs_bp.route("/api/jobs/<job_id>", methods=["DELETE"])
def delete_job(job_id):
    job = Job.query.filter_by(job_id=job_id).first()
    if not job:
        raise AppError("not found", 404)
    remove_job_from_scheduler(job.job_id)
    db.session.delete(job)
    db.session.commit()
    return jsonify({"message": "deleted"})


@jobs_bp.route("/api/jobs/<job_id>/pause", methods=["POST"])
def pause_job_route(job_id):
    job = Job.query.filter_by(job_id=job_id).first()
    if not job:
        raise AppError("not found", 404)
    sched_pause(job.job_id)
    job.enabled = False
    db.session.commit()
    return jsonify({"message": "paused"})


@jobs_bp.route("/api/jobs/<job_id>/resume", methods=["POST"])
def resume_job_route(job_id):
    job = Job.query.filter_by(job_id=job_id).first()
    if not job:
        raise AppError("not found", 404)
    sched_resume(job.job_id)
    job.enabled = True
    db.session.commit()
    return jsonify({"message": "resumed"})


@jobs_bp.route("/api/jobs/<job_id>/trigger", methods=["POST"])
def trigger_job_route(job_id):
    job = Job.query.filter_by(job_id=job_id).first()
    if not job:
        raise AppError("not found", 404)
    sched_trigger(job.job_id)
    return jsonify({"message": "triggered"})


@jobs_bp.route("/api/jobs/<job_id>/logs", methods=["GET"])
def job_logs(job_id):
    from app.models import ExecutionLog
    limit = request.args.get("limit", 20, type=int)
    logs = (
        ExecutionLog.query
        .filter_by(job_id=job_id)
        .order_by(ExecutionLog.started_at.desc())
        .limit(min(limit, 100))
        .all()
    )
    return jsonify([log.to_dict() for log in logs])
