#!/usr/bin/env sh
set -e

# If the database already has tables but no alembic_version row, it was
# created before Flask-Migrate was introduced. Stamp it as the baseline
# so the next upgrade only applies new migrations (e.g. adding columns)
# without trying to recreate the tables.
python <<'PY'
import sqlite3, os, sys
from urllib.parse import urlparse
from project import create_app
from project.config import Config

uri = os.environ.get("DATABASE_URL") or Config.SQLALCHEMY_DATABASE_URI
if uri.startswith("sqlite:///"):
    path = urlparse(uri).path
    if os.path.exists(path):
        con = sqlite3.connect(path)
        tables = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        if "user" in tables and "alembic_version" not in tables:
            print("Existing DB without alembic version — stamping baseline.")
            from flask_migrate import stamp
            app = create_app()
            with app.app_context():
                stamp(revision="0001_baseline")
        con.close()
PY

flask db upgrade

exec "$@"
