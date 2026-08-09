from __future__ import annotations

from flask import Flask, jsonify

from app.config import Config
from app.extensions import db, migrate
from app.utils.errors import register_error_handlers
from app.utils.logging import configure_logging


def create_app(config: type[Config] | dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    if config is not None:
        if isinstance(config, dict):
            app.config.update(config)
        else:
            app.config.from_object(config)

    configure_logging()
    db.init_app(app)
    migrate.init_app(app, db)

    from app import models  # noqa: F401
    from app.api import api_v1

    app.register_blueprint(api_v1)
    register_error_handlers(app)

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    return app
