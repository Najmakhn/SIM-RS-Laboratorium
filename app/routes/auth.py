import time
from functools import wraps

from flask import (Blueprint, abort, current_app, flash, g, redirect, render_template, request, session,
                   url_for)
from werkzeug.security import check_password_hash

from ..db import query

bp = Blueprint("auth", __name__)

MAX_GAGAL = 5             # batas percobaan login gagal berturut-turut
KUNCI_DETIK = 5 * 60      # lama akun dikunci setelah batas tercapai


def _catatan_gagal():
    """Catatan login gagal per username, disimpan di memori aplikasi (hilang saat restart)."""
    return current_app.extensions.setdefault("login_gagal", {})


def _terkunci(username):
    jumlah, terakhir = _catatan_gagal().get(username, (0, 0.0))
    if time.time() - terakhir >= KUNCI_DETIK:
        _catatan_gagal().pop(username, None)
        return False
    return jumlah >= MAX_GAGAL


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
        username = request.form.get("username", "").strip()
        if _terkunci(username):
            flash("Terlalu banyak percobaan login gagal. Coba lagi dalam 5 menit.", "danger")
            return render_template("login.html"), 429
        u = query("SELECT * FROM user WHERE username=? AND aktif=1", (username,), one=True)
        if u and check_password_hash(u["password_hash"], request.form.get("password", "")):
            _catatan_gagal().pop(username, None)
            session.clear()
            session["uid"] = u["id"]
            nxt = request.args.get("next", "")
            return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else url_for("dashboard.index"))
        jumlah, _ = _catatan_gagal().get(username, (0, 0.0))
        _catatan_gagal()[username] = (jumlah + 1, time.time())
        flash("Username atau password salah.", "danger")
    return render_template("login.html")


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
