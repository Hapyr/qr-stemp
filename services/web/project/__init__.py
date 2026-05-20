import os
from urllib.parse import urlparse

from flask import Flask

from .config import Config
from .models import db


def _ensure_sqlite_dir(uri: str) -> None:
    """SQLite won't create the parent directory — do it ourselves."""
    if not uri.startswith("sqlite:///"):
        return
    path = urlparse(uri).path  # e.g. /abs/path/to/file.db
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def create_app(config_object: type = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)

    _ensure_sqlite_dir(app.config["SQLALCHEMY_DATABASE_URI"])

    db.init_app(app)

    from .routes import bp as main_bp
    app.register_blueprint(main_bp)

    with app.app_context():
        db.create_all()

    return app
