import sys
import os
import logging
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from flask import Flask, request
from app.config import Config
from app.models import db
from app.errors import register_error_handlers
from app.scheduler import configure_jobstore
from app.routes.scripts import scripts_bp
from app.routes.jobs import jobs_bp
from app.routes.status import status_bp


class JsonFormatter(logging.Formatter):
    """简易 JSON 日志格式化。"""
    def format(self, record):
        import json
        return json.dumps({
            "time": self.formatTime(record),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }, ensure_ascii=False)


def _setup_logging(app):
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO if not app.debug else logging.DEBUG)

    @app.before_request
    def start_timer():
        request._start_time = time.time()

    @app.after_request
    def log_request(response):
        duration = time.time() - request._start_time
        app.logger.info(
            "%s %s %s %.3f",
            request.method, request.path, response.status_code, duration,
        )
        return response


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    _setup_logging(app)

    db.init_app(app)
    register_error_handlers(app)

    app.register_blueprint(scripts_bp)
    app.register_blueprint(jobs_bp)
    app.register_blueprint(status_bp)

    with app.app_context():
        configure_jobstore(db.engine)
        db.create_all()

    return app
