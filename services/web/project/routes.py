"""HTTP routes.

Security model
--------------
- `user_token` is a bearer credential. It never appears in a URL, QR code,
  or HTML rendered for anyone but its owner.
- Authentication uses Flask sessions (signed cookies). The user_token is
  also kept in the user's own localStorage as a portable recovery code
  (paste it on a new device to log in).
- Cross-user identifiers in URLs and QR codes are public:
    * `User.id` — integer, fine to expose
    * `Stempel.token` — one-time random UUID for claiming a stamp
    * `RedeemRequest.redeem_token` — one-time random UUID for redemption
"""

import random
import string
from functools import wraps

from flask import (
    Blueprint,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from .models import RedeemRequest, Stempel, User, db

bp = Blueprint("main", __name__)


# ---------- helpers ----------


def _random_id(size: int = 6) -> str:
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choice(chars) for _ in range(size))


def current_user() -> User | None:
    token = session.get("user_token")
    if not token:
        return None
    return db.session.query(User).filter_by(user_token=token).first()


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if current_user() is None:
            return redirect(url_for("main.client_login"))
        return view(*args, **kwargs)

    return wrapper


def api_login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if current_user() is None:
            return jsonify(error="unauthorized"), 401
        return view(*args, **kwargs)

    return wrapper


def _login(user: User) -> None:
    session["user_token"] = user.user_token
    session.permanent = True


def _stamp_cards(client_token: str):
    rows = (
        db.session.query(
            Stempel.host_id,
            db.func.count(Stempel.client_id).label("count_stamp"),
        )
        .filter_by(client_id=client_token, used=False)
        .group_by(Stempel.host_id)
        .all()
    )
    cards = []
    for host_id, count in rows:
        host = db.session.get(User, host_id)
        cards.append(
            {
                "host_id": host_id,
                "host_label": host.label if host else f"user-{host_id}",
                "count_stamp": count,
            }
        )
    cards.sort(key=lambda c: c["host_label"].lower())
    return cards


def _claim_for(user: User, claim: str) -> tuple[dict | None, int]:
    """Server-side stamp claim. Returns (error_dict_or_None, status)."""
    stemp = db.session.query(Stempel).filter_by(token=claim).first()
    if stemp is None:
        return {"error": "unknown claim"}, 404
    if stemp.client_id != "":
        return {"error": "already used"}, 409
    if stemp.host_id == user.id:
        return {"error": "cannot self-stamp"}, 400
    stemp.client_id = user.user_token
    db.session.commit()
    return None, 200


# ---------- landing / auth ----------


@bp.route("/")
def landing():
    if current_user() is not None:
        return redirect(url_for("main.me"))
    return render_template("landing.html")


@bp.route("/login")
def client_login():
    return render_template(
        "login.html",
        pending_claim=request.args.get("claim", ""),
        pending_redeem=request.args.get("redeem", ""),
    )


@bp.route("/login", methods=["POST"])
def login_submit():
    """Log in (or create a new user) and set the session cookie.

    `password` carries the user_token. Optional `pending_claim` / `pending_redeem`
    auto-execute that flow once logged in.
    """
    token = (request.form.get("password") or "").strip()
    pending_claim = request.form.get("pending_claim", "")
    pending_redeem = request.form.get("pending_redeem", "")

    if token:
        user = db.session.query(User).filter_by(user_token=token).first()
        if user is None:
            return render_template(
                "login.html",
                error="No card found for that token.",
                pending_claim=pending_claim,
                pending_redeem=pending_redeem,
            )
    else:
        user = User(email=f"{_random_id()}@anon.local")
        user.set_password(_random_id())
        user.set_user_token()
        db.session.add(user)
        db.session.commit()

    _login(user)

    if pending_claim:
        _claim_for(user, pending_claim)  # silent best-effort
    if pending_redeem:
        return redirect(url_for("main.redeem_page", redeem=pending_redeem))
    return redirect(url_for("main.me"))


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("main.landing"))


# ---------- me ----------


@bp.route("/me")
@login_required
def me():
    user = current_user()
    used = bool(session.pop("flash_used", None))
    info = session.pop("flash_info", None)
    return render_template(
        "me.html",
        user_data=user,
        cards=_stamp_cards(user.user_token),
        used=used,
        info=info,
    )


@bp.route("/me/name", methods=["POST"])
@api_login_required
def set_name():
    user = current_user()
    user.display_name = (request.form.get("name") or "").strip()[:120]
    db.session.commit()
    return jsonify(ok=True, label=user.label)


@bp.route("/api/token")
@api_login_required
def reveal_token():
    """Return own token (e.g. to copy to clipboard). Auth-gated."""
    return jsonify(token=current_user().user_token)


# ---------- giving a stamp ----------


@bp.route("/api/stamp", methods=["POST"])
@api_login_required
def api_stamp():
    user = current_user()
    s = db.session.query(Stempel).filter_by(host_id=user.id, client_id="").first()
    if s is None:
        s = Stempel(host_id=user.id, client_id="")
        s.set_token()
        db.session.add(s)
        db.session.commit()
    return jsonify(claim=s.token)


@bp.route("/api/claim_status/<claim>")
def claim_status(claim):
    open_count = db.session.query(Stempel).filter_by(token=claim, client_id="").count()
    return jsonify(used=open_count < 1)


@bp.route("/scan/<claim>")
def scan_claim(claim):
    """A user opened a stamp QR. If logged in, claim server-side; else login."""
    user = current_user()
    if user is None:
        return redirect(url_for("main.client_login", claim=claim))
    err, _ = _claim_for(user, claim)
    if err:
        return render_template("error.html", title=err["error"])
    return redirect(url_for("main.me"))


# ---------- redeeming ----------


@bp.route("/api/count", methods=["POST"])
@api_login_required
def api_count():
    user = current_user()
    try:
        host_id = int(request.form.get("host_id", ""))
    except ValueError:
        return jsonify(error="bad host_id"), 400
    count = (
        db.session.query(Stempel)
        .filter_by(client_id=user.user_token, host_id=host_id, used=False)
        .count()
    )
    return jsonify(number_valid=count)


@bp.route("/api/redeem_request", methods=["POST"])
@api_login_required
def api_redeem_request():
    user = current_user()
    try:
        host_id = int(request.form.get("host_id", ""))
    except ValueError:
        return jsonify(error="bad host_id"), 400
    rr = RedeemRequest(host_id=host_id, client_id=user.user_token)
    rr.set_token()
    db.session.add(rr)
    db.session.commit()
    return jsonify(redeem=rr.redeem_token)


@bp.route("/r/<redeem>")
def redeem_page(redeem):
    """The host scanned a redeem QR. If logged in, execute; else login."""
    host = current_user()
    if host is None:
        return redirect(url_for("main.client_login", redeem=redeem))

    needed = current_app.config["STAMPS_TO_REDEEM"]
    rr = db.session.query(RedeemRequest).filter_by(redeem_token=redeem).first()
    if rr is None or rr.consumed:
        return render_template("error.html", title="Invalid or already-used redemption.")
    if rr.host_id != host.id:
        return render_template("error.html", title="That card isn't yours to redeem.")

    stamps = (
        db.session.query(Stempel)
        .filter_by(client_id=rr.client_id, host_id=host.id, used=False)
        .limit(needed)
        .all()
    )
    if len(stamps) < needed:
        return render_template("error.html", title="Not enough stamps yet.")

    for s in stamps:
        s.used = True
    rr.consumed = True
    db.session.commit()

    session["flash_used"] = True
    session["flash_info"] = f"{needed} stamps redeemed."
    return redirect(url_for("main.me"))
