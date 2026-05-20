from flask import Blueprint, jsonify
from app.scheduler import scheduler, list_jobs

status_bp = Blueprint("status", __name__)


@status_bp.route("/api/scheduler/status", methods=["GET"])
def scheduler_status():
    running = scheduler.running
    jobs = list_jobs()
    return jsonify({"running": running, "jobs": jobs})
