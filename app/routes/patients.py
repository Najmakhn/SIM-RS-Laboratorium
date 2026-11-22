from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from ..db import get_db, query
from ..services import next_no_rm
from .auth import roles_required

bp = Blueprint("patients", __name__, url_prefix="/patients")
PER_PAGE = 12


def _form():
    f = request.form
    d = {k: f.get(k, "").strip() for k in ("nama", "jenis_kelamin", "tgl_lahir", "alamat", "no_hp")}
    err = []
    if not d["nama"]:
        err.append("Nama wajib diisi.")
    if d["jenis_kelamin"] not in ("L", "P"):
        err.append("Pilih jenis kelamin.")
    try:
        if date.fromisoformat(d["tgl_lahir"]) > date.today():
            err.append("Tanggal lahir tidak boleh di masa depan.")
    except ValueError:
        err.append("Tanggal lahir tidak valid.")
    return d, err


@bp.route("/")
def index():
    q = request.args.get("q", "").strip()
    hal = max(request.args.get("hal", 1, type=int), 1)
    like = f"%{q}%"
    w, a = "nama LIKE ? OR no_rm LIKE ? OR no_hp LIKE ? OR alamat LIKE ?", [like] * 4
    total = query(f"SELECT COUNT(*) c FROM patient WHERE {w}", a, one=True)["c"]
    rows = query(f"""SELECT p.*, (SELECT COUNT(*) FROM lab_order o WHERE o.patient_id=p.id) n_order
                     FROM patient p WHERE {w} ORDER BY nama LIMIT ? OFFSET ?""", (*a, PER_PAGE, (hal - 1) * PER_PAGE))
    return render_template("patients/list.html", rows=rows, q=q, hal=hal, total=total, per_page=PER_PAGE)


@bp.route("/baru", methods=["GET", "POST"])
@roles_required("admin", "dokter", "analis")
def baru():
    if request.method == "POST":
        d, err = _form()
        if err:
            [flash(e, "danger") for e in err]
            return render_template("patients/form.html", p=d, mode="baru", no_rm=next_no_rm(get_db()))
        db = get_db()
        no_rm = next_no_rm(db)
        cur = db.execute("INSERT INTO patient(no_rm,nama,jenis_kelamin,tgl_lahir,alamat,no_hp) VALUES (?,?,?,?,?,?)",
                         (no_rm, d["nama"], d["jenis_kelamin"], d["tgl_lahir"], d["alamat"], d["no_hp"]))
        db.commit()
        flash(f"Pasien {d['nama']} terdaftar dengan No. RM {no_rm}.", "success")
        return redirect(url_for("patients.detail", pid=cur.lastrowid))
    return render_template("patients/form.html", p={}, mode="baru", no_rm=next_no_rm(get_db()))


@bp.route("/<int:pid>")
def detail(pid):
    p = query("SELECT * FROM patient WHERE id=?", (pid,), one=True) or abort(404, "Pasien tidak ditemukan.")
    orders = query("""SELECT o.*, d.nama dokter, b.total, b.status bayar,
                      (SELECT GROUP_CONCAT(t.nama, ', ') FROM order_test ot JOIN lab_test t ON t.id=ot.test_id
                        WHERE ot.order_id=o.id) tests
                      FROM lab_order o JOIN doctor d ON d.id=o.doctor_id LEFT JOIN billing b ON b.order_id=o.id
                      WHERE o.patient_id=? ORDER BY o.tgl_order DESC""", (pid,))
    # riwayat nilai per parameter (tren)
    hist = query("""SELECT tp.nama, tp.satuan, r.nilai, r.flag, substr(o.tgl_order,1,10) tgl
                    FROM order_result r JOIN lab_order o ON o.id=r.order_id
                    JOIN test_parameter tp ON tp.id=r.parameter_id
                    WHERE o.patient_id=? AND o.status='selesai' AND tp.tipe='angka' ORDER BY o.tgl_order""", (pid,))
    trend = {}
    for h in hist:
        trend.setdefault(h["nama"], []).append(h)
    return render_template("patients/detail.html", p=p, orders=orders, trend=trend)


@bp.route("/<int:pid>/edit", methods=["GET", "POST"])
@roles_required("admin", "dokter", "analis")
def edit(pid):
    p = query("SELECT * FROM patient WHERE id=?", (pid,), one=True) or abort(404)
    if request.method == "POST":
        d, err = _form()
        if err:
            [flash(e, "danger") for e in err]
            return render_template("patients/form.html", p={**d, "id": pid, "no_rm": p["no_rm"]}, mode="edit",
                                   no_rm=p["no_rm"])
        db = get_db()
        db.execute("UPDATE patient SET nama=?,jenis_kelamin=?,tgl_lahir=?,alamat=?,no_hp=? WHERE id=?",
                   (d["nama"], d["jenis_kelamin"], d["tgl_lahir"], d["alamat"], d["no_hp"], pid))
        db.commit()
        flash("Data pasien diperbarui.", "success")
        return redirect(url_for("patients.detail", pid=pid))
    return render_template("patients/form.html", p=p, mode="edit", no_rm=p["no_rm"])


@bp.route("/<int:pid>/hapus", methods=["POST"])
@roles_required("admin")
def hapus(pid):
    n = query("SELECT COUNT(*) c FROM lab_order WHERE patient_id=?", (pid,), one=True)["c"]
    if n:
        flash("Pasien memiliki riwayat order lab dan tidak dapat dihapus.", "danger")
        return redirect(url_for("patients.detail", pid=pid))
    db = get_db()
    db.execute("DELETE FROM patient WHERE id=?", (pid,))
    db.commit()
    flash("Pasien dihapus.", "info")
    return redirect(url_for("patients.index"))
