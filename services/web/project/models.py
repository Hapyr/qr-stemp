import hashlib
from uuid import uuid4

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), index=True, unique=True)
    display_name = db.Column(db.String(120), default="")
    password_hash = db.Column(db.String(512))
    # SECRET. Acts as a bearer credential. Never put it in a URL, QR code,
    # or in HTML rendered for anyone else.
    user_token = db.Column(db.String(512), index=True)

    def set_user_token(self) -> None:
        self.user_token = hashlib.md5(
            self.email.encode() + self.password_hash.encode()
        ).hexdigest()

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def label(self) -> str:
        return self.display_name or f"user-{self.id}"


class Stempel(db.Model):
    """A stamp issued by host (User.id) to a client (User.user_token).

    `host_id` is the public integer User.id — safe to expose.
    `client_id` stores the recipient's user_token — server-side only, never
    rendered into pages or URLs visible to anyone other than the client.
    `token` is a one-time claim UUID embedded in the host's QR code.
    """

    id = db.Column(db.Integer, primary_key=True)
    host_id = db.Column(db.Integer, db.ForeignKey("user.id"), index=True)
    client_id = db.Column(db.String(128), default="", index=True)
    token = db.Column(db.String(128), default="", index=True)
    used = db.Column(db.Boolean, default=False)

    host = db.relationship("User", foreign_keys=[host_id])

    def set_token(self) -> None:
        self.token = str(uuid4())


class RedeemRequest(db.Model):
    """One-shot redemption ticket: client asks server for a URL the host can scan.

    The QR code only carries the random `redeem_token` — never the client's
    user_token. When the host scans it, they POST their own user_token to
    /api/redeem and the server validates ownership.
    """

    id = db.Column(db.Integer, primary_key=True)
    host_id = db.Column(db.Integer, db.ForeignKey("user.id"), index=True)
    client_id = db.Column(db.String(128))
    redeem_token = db.Column(db.String(128), unique=True, index=True)
    consumed = db.Column(db.Boolean, default=False)

    def set_token(self) -> None:
        self.redeem_token = str(uuid4())
