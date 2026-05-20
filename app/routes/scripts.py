from flask import Blueprint, request, jsonify
from app.models import db, Script
from app.errors import AppError
from app.script_manager import write_script_file, remove_script_file

scripts_bp = Blueprint("scripts", __name__)


def _require_fields(data, *fields):
    for f in fields:
        if f not in data or not data[f]:
            raise AppError(f"{f} is required", 400)


@scripts_bp.route("/api/scripts", methods=["GET"])
def list_scripts():
    scripts = Script.query.all()
    return jsonify([s.to_dict() for s in scripts])


@scripts_bp.route("/api/scripts", methods=["POST"])
def create_script():
    data = request.get_json(force=True)
    _require_fields(data, "name", "content")
    if Script.query.filter_by(name=data["name"]).first():
        raise AppError("script name already exists", 409)

    script = Script(
        name=data["name"],
        description=data.get("description", ""),
        content=data["content"],
    )
    db.session.add(script)
    db.session.commit()

    write_script_file(script.name, script.content)
    return jsonify(script.to_dict()), 201


@scripts_bp.route("/api/scripts/<int:script_id>", methods=["GET"])
def get_script(script_id):
    script = db.session.get(Script, script_id)
    if not script:
        raise AppError("not found", 404)
    return jsonify(script.to_dict())


@scripts_bp.route("/api/scripts/<int:script_id>", methods=["PUT"])
def update_script(script_id):
    script = db.session.get(Script, script_id)
    if not script:
        raise AppError("not found", 404)
    data = request.get_json(force=True)
    if "name" in data:
        script.name = data["name"]
    if "description" in data:
        script.description = data["description"]
    if "content" in data:
        script.content = data["content"]
        write_script_file(script.name, script.content)
    db.session.commit()
    return jsonify(script.to_dict())


@scripts_bp.route("/api/scripts/<int:script_id>", methods=["DELETE"])
def delete_script(script_id):
    script = db.session.get(Script, script_id)
    if not script:
        raise AppError("not found", 404)
    remove_script_file(script.name)
    db.session.delete(script)
    db.session.commit()
    return jsonify({"message": "deleted"})
