"""SIMRS - Modul Laboratorium (Flask + SQLite + Bootstrap 5)."""
import os
import secrets
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, abort, g, redirect, request, session, url_for

from . import db as database
from .services import (ASAL, FLAG_META, METODE_BAYAR, STATUS, STEPS, age_of, fmt_num, fmt_rp,
                       hari_ini_indo, ref_range, tgl_indo)


def create_app(test_config=None):
    app = Flask(__name__)
    root = Path(__file__).resolve().parent.parent
    load_dotenv(root / ".env")  # baca SECRET_KEY dll. dari file .env (kalau ada)
    app.config.update(
        # Isi SECRET_KEY di file .env. Kalau kosong, dipakai kunci acak (semua user logout tiap restart).
        SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
        DATABASE=os.environ.get("SIMRS_DB", str(root / "instance" / "simrs_lab.db")),
    )
    if test_config:
        app.config.update(test_config)

    app.teardown_appcontext(database.close_db)

    # Buat database + data contoh otomatis pada jalankan pertama
    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    if not Path(app.config["DATABASE"]).exists():
        database.init_db(app.config["DATABASE"], seed=True)

    @app.cli.command("init-db")
    def init_db_cmd():
        """Reset database dan isi data contoh."""
        database.init_db(app.config["DATABASE"], seed=True)
        print("Database direset:", app.config["DATABASE"])

    # ---- sesi, peran, CSRF ------------------------------------------------
    @app.before_request
    def load_user():
        g.user = None
        uid = session.get("uid")
        if uid:
            g.user = database.query("SELECT * FROM user WHERE id=? AND aktif=1", (uid,), one=True)
        if request.endpoint and request.endpoint != "static":
            if g.user is None and request.endpoint not in ("auth.login",):
                return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))
        if request.method == "POST":
            token = session.get("csrf")
            if not token or token != request.form.get("csrf_token"):
                abort(400, "Token CSRF tidak valid. Muat ulang halaman lalu coba lagi.")

    def csrf_token():
        if "csrf" not in session:
            session["csrf"] = secrets.token_hex(16)
        return session["csrf"]

    @app.context_processor
    def inject():
        return {
            "csrf_token": csrf_token, "STATUS": STATUS, "STEPS": STEPS, "ASAL": ASAL,
            "METODE_BAYAR": METODE_BAYAR, "ref_range": ref_range, "FLAG_META": FLAG_META,
            "today": hari_ini_indo(),
        }

    # ---- filter Jinja ------------------------------------------------------
    app.jinja_env.filters["rp"] = fmt_rp
    app.jinja_env.filters["num"] = fmt_num
    app.jinja_env.filters["umur"] = age_of

    @app.template_filter("tgl")
    def tgl(v, panjang=False):
        if not v:
            return "-"
        try:
            return tgl_indo(v, panjang)
        except ValueError:
            return v

    @app.template_filter("jam")
    def jam(v):
        return v[11:16] if v and len(v) >= 16 else "-"

    @app.template_filter("angka_input")
    def angka_input(v):
        return (v or "").replace(".", ",")

    # ---- blueprint -----------------------------------------------------------
    from .routes import auth, billing, dashboard, master, orders, patients, reports
    for bp in (auth.bp, dashboard.bp, orders.bp, patients.bp, master.bp, billing.bp, reports.bp):
        app.register_blueprint(bp)

    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(400)
    def err(e):
        from flask import render_template
        return render_template("error.html", e=e), e.code

    return app
