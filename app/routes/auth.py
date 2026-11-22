from functools import wraps

from flask import Blueprint, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from ..db import query

bp = Blueprint("auth", __name__)


def roles_required(*roles):
    """Batasi akses route berdasarkan peran pengguna."""
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            if g.user["role"] not in roles:
                abort(403, "Peran Anda tidak memiliki akses ke fitur ini.")
            return fn(*a, **kw)
        return wrapper
    return deco


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("dashboard.index"))
    if request.method == "POST":
        u = query("SELECT * FROM user WHERE username=? AND aktif=1",
                  (request.form.get("username", "").strip(),), one=True)
        if u and check_password_hash(u["password_hash"], request.form.get("password", "")):
            session.clear()
            session["uid"] = u["id"]
            nxt = request.args.get("next", "")
            return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else url_for("dashboard.index"))
        flash("Username atau password salah.", "danger")
    return render_template("login.html")


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
