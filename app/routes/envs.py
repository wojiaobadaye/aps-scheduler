"""Blueprint for Conda environment management."""
from flask import Blueprint, jsonify
from app.models import db, Script, ScriptEnv
from app.scheduler import cleanup_unused_envs

envs_bp = Blueprint("envs", __name__)


@envs_bp.route("/api/envs", methods=["GET"])
def list_envs():
    envs = ScriptEnv.query.order_by(ScriptEnv.created_at.desc()).all()
    result = []
    for env in envs:
        d = env.to_dict()
        script_count = Script.query.filter_by(env_name=env.env_name).count()
        d["script_count"] = script_count
        result.append(d)
    return jsonify(result)


@envs_bp.route("/api/envs/cleanup", methods=["POST"])
def cleanup():
    count = cleanup_unused_envs(db.session)
    return jsonify({"message": f"cleaned {count} unused env(s)"})
