import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from flask import Flask
from app.config import Config
from app.models import db
from app.errors import register_error_handlers
from app.routes.scripts import scripts_bp
from app.routes.jobs import jobs_bp
from app.routes.status import status_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    register_error_handlers(app)

    app.register_blueprint(scripts_bp)
    app.register_blueprint(jobs_bp)
    app.register_blueprint(status_bp)

    with app.app_context():
        db.create_all()

    return app
