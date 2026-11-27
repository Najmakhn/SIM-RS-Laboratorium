"""Koneksi database SQLite + helper query."""
import sqlite3
from pathlib import Path

from flask import current_app, g

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = ROOT / "migrations"


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query(sql, args=(), one=False):
    cur = get_db().execute(sql, args)
    rows = cur.fetchall()
    cur.close()
    return (rows[0] if rows else None) if one else rows


def execute(sql, args=()):
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    return cur.lastrowid


def init_db(db_path=None, seed=True):
    """Buat ulang semua tabel dari schema.sql, lalu (opsional) isi data contoh."""
    path = db_path or current_app.config["DATABASE"]
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript((ROOT / "schema.sql").read_text(encoding="utf-8"))
    if seed:
        from .seed import seed_all
        seed_all(conn)
    conn.commit()
    conn.close()


def daftar_migrasi(folder=None):
    """File migrations/NNNN_nama.sql sebagai daftar (nomor, path), urut dari nomor terkecil."""
    folder = Path(folder or MIGRATIONS_DIR)
    hasil = sorted((int(p.name[:4]), p) for p in folder.glob("[0-9][0-9][0-9][0-9]_*.sql"))
    nomor = [n for n, _ in hasil]
    dobel = sorted({n for n in nomor if nomor.count(n) > 1})
    if dobel:
        raise RuntimeError(f"Nomor migrasi dobel: {dobel}. Ganti nomor salah satu file di {folder}.")
    return hasil


def jalankan_migrasi(conn, folder=None):
    """Jalankan migrasi yang nomornya lebih besar dari PRAGMA user_version.

    Tiap file dijalankan dalam satu transaksi: kalau gagal, perubahan file itu dibatalkan
    dan versi database tidak berubah. Mengembalikan daftar nama file yang dijalankan.
    """
    versi = conn.execute("PRAGMA user_version").fetchone()[0]
    dijalankan = []
    for nomor, path in daftar_migrasi(folder):
        if nomor <= versi:
            continue
        sql = path.read_text(encoding="utf-8")
        try:
            conn.executescript(f"BEGIN;\n{sql}\n;PRAGMA user_version = {nomor};\nCOMMIT;")
        except sqlite3.Error as e:
            conn.rollback()
            raise RuntimeError(f"Migrasi {path.name} gagal: {e}") from e
        dijalankan.append(path.name)
    return dijalankan


def migrate(db_path=None, folder=None):
    """Buka database lalu jalankan migrasi yang belum pernah dijalankan."""
    conn = sqlite3.connect(db_path or current_app.config["DATABASE"])
    try:
        return jalankan_migrasi(conn, folder)
    finally:
        conn.close()
