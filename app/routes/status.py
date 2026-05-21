from flask import Blueprint, jsonify
from app.scheduler import scheduler, list_jobs

status_bp = Blueprint("status", __name__)


@status_bp.route("/api/scheduler/status", methods=["GET"])
def scheduler_status():
    running = scheduler.running
    jobs = list_jobs()
    return jsonify({"running": running, "jobs": jobs})


@status_bp.route("/api/health", methods=["GET"])
def health():
    from app.models import db
    db_ok = False
    try:
        db.session.execute(db.text("SELECT 1"))
        db_ok = True
    except Exception:
        pass
    return jsonify({
        "status": "ok",
        "scheduler_running": scheduler.running,
        "db": "ok" if db_ok else "error",
    })
