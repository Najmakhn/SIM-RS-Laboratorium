"""Order laboratorium - inti alur 6 langkah."""
import random
from datetime import date

from flask import (Blueprint, abort, flash, g, jsonify, redirect, render_template, request, url_for)

from ..db import get_db, query
from ..services import (ASAL, evaluate, log_status, next_order_numbers, now_str, ref_text)
from .auth import roles_required

bp = Blueprint("orders", __name__, url_prefix="/orders")
PER_PAGE = 12

BASE_SELECT = """
    SELECT o.*, p.nama pasien, p.no_rm, p.jenis_kelamin, d.nama dokter,
           (SELECT GROUP_CONCAT(t.nama, ', ') FROM order_test ot JOIN lab_test t ON t.id=ot.test_id
             WHERE ot.order_id=o.id) tests,
           b.total, b.status bayar
    FROM lab_order o JOIN patient p ON p.id=o.patient_id JOIN doctor d ON d.id=o.doctor_id
    LEFT JOIN billing b ON b.order_id=o.id
"""


def get_order(oid):
    o = query(BASE_SELECT + " WHERE o.id=?", (oid,), one=True)
    if o is None:
        abort(404, "Order tidak ditemukan.")
    return o


# --------------------------------------------------------------------------
# Daftar + pencarian + filter
# --------------------------------------------------------------------------
@bp.route("/")
def index():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    tanggal = request.args.get("tanggal", "")
    prioritas = request.args.get("prioritas", "")
    hal = max(int(request.args.get("hal", 1) or 1), 1)

    where, args = ["1=1"], []
    if q:
        where.append("""(p.nama LIKE ? OR p.no_rm LIKE ? OR o.no_order LIKE ? OR o.kode_antrian LIKE ?
                         OR o.barcode LIKE ? OR d.nama LIKE ? OR EXISTS (SELECT 1 FROM order_test ot
                         JOIN lab_test t ON t.id=ot.test_id WHERE ot.order_id=o.id AND t.nama LIKE ?))""")
        args += [f"%{q}%"] * 7
    if status:
        where.append("o.status=?"); args.append(status)
    if tanggal == "hari_ini":
        where.append("o.tgl_order LIKE ?"); args.append(date.today().isoformat() + "%")
    elif tanggal:
        where.append("o.tgl_order LIKE ?"); args.append(tanggal + "%")
    if prioritas:
        where.append("o.prioritas=?"); args.append(prioritas)
    w = " AND ".join(where)

    total = query(f"""SELECT COUNT(*) c FROM lab_order o JOIN patient p ON p.id=o.patient_id
                      JOIN doctor d ON d.id=o.doctor_id WHERE {w}""", args, one=True)["c"]
    rows = query(f"""{BASE_SELECT} WHERE {w} ORDER BY o.tgl_order DESC, o.id DESC LIMIT ? OFFSET ?""",
                 (*args, PER_PAGE, (hal - 1) * PER_PAGE))
    counts = {r["status"]: r["c"] for r in query(
        "SELECT status, COUNT(*) c FROM lab_order WHERE tgl_order LIKE ? GROUP BY status",
        (date.today().isoformat() + "%",))}
    return render_template("orders/list.html", rows=rows, q=q, status=status, tanggal=tanggal,
                           prioritas=prioritas, hal=hal, total=total, per_page=PER_PAGE, counts=counts)


# --------------------------------------------------------------------------
# Langkah 1: order masuk dari dokter
# --------------------------------------------------------------------------
@bp.route("/baru", methods=["GET", "POST"])
@roles_required("admin", "dokter", "analis")
def baru():
    db = get_db()
    tests = query("SELECT * FROM lab_test WHERE aktif=1 ORDER BY kategori, nama")
    doctors = query("SELECT * FROM doctor WHERE aktif=1 ORDER BY nama")
    pre = request.args.get("patient_id", type=int)
    selected = query("SELECT * FROM patient WHERE id=?", (pre,), one=True) if pre else None

    if request.method == "POST":
        pid = request.form.get("patient_id", type=int)
        did = request.form.get("doctor_id", type=int)
        test_ids = [int(x) for x in request.form.getlist("test_id") if x.isdigit()]
        errors = []
        if not pid or not query("SELECT 1 FROM patient WHERE id=?", (pid,), one=True):
            errors.append("Pilih pasien terlebih dahulu.")
        if not did:
            errors.append("Pilih dokter pengirim.")
        if not test_ids:
            errors.append("Pilih minimal satu jenis pemeriksaan.")
        asal = request.form.get("asal") if request.form.get("asal") in ASAL else ASAL[0]
        prioritas = "cito" if request.form.get("prioritas") == "cito" else "rutin"
        if errors:
            for e in errors:
                flash(e, "danger")
            selected = query("SELECT * FROM patient WHERE id=?", (pid,), one=True) if pid else None
            return render_template("orders/new.html", tests=tests, doctors=doctors, selected=selected,
                                   form=request.form, picked=set(test_ids))

        no_order, kode, _ = next_order_numbers(db)
        cur = db.execute(
            """INSERT INTO lab_order(no_order,kode_antrian,patient_id,doctor_id,asal,prioritas,catatan_klinis,
               status,tgl_order) VALUES (?,?,?,?,?,?,?,'menunggu',?)""",
            (no_order, kode, pid, did, asal, prioritas, request.form.get("catatan", "").strip() or None, now_str()))
        oid, total = cur.lastrowid, 0
        for t in test_ids:
            tarif = db.execute("SELECT tarif FROM lab_test WHERE id=?", (t,)).fetchone()["tarif"]
            db.execute("INSERT INTO order_test(order_id,test_id,tarif) VALUES (?,?,?)", (oid, t, tarif))
            total += tarif
        db.execute("INSERT INTO billing(order_id,total) VALUES (?,?)", (oid, total))  # input billing otomatis
        log_status(db, oid, "menunggu", g.user["id"], "Order masuk dari dokter")
        db.commit()
        flash(f"Order {no_order} (antrian {kode}) berhasil dibuat.", "success")
        return redirect(url_for("orders.detail", oid=oid))

    return render_template("orders/new.html", tests=tests, doctors=doctors, selected=selected,
                           form={}, picked=set())


# --------------------------------------------------------------------------
# Detail order (halaman kerja)
# --------------------------------------------------------------------------
@bp.route("/<int:oid>")
def detail(oid):
    o = get_order(oid)
    pt = query("SELECT * FROM patient WHERE id=?", (o["patient_id"],), one=True)
    groups = []
    for t in query("""SELECT t.*, ot.tarif tarif_order FROM order_test ot JOIN lab_test t ON t.id=ot.test_id
                      WHERE ot.order_id=? ORDER BY t.kategori, t.nama""", (oid,)):
        params = query("SELECT * FROM test_parameter WHERE test_id=? ORDER BY urutan", (t["id"],))
        res = {r["parameter_id"]: r for r in query("SELECT * FROM order_result WHERE order_id=?", (oid,))}
        groups.append({"test": t, "rows": [
            {"p": p, "res": res.get(p["id"]), "rujukan": ref_text(p, pt["jenis_kelamin"])} for p in params]})
    log = query("""SELECT s.*, u.nama petugas FROM status_log s LEFT JOIN user u ON u.id=s.user_id
                   WHERE s.order_id=? ORDER BY s.id""", (oid,))
    abnormal = sum(1 for g_ in groups for r in g_["rows"] if r["res"] and r["res"]["flag"] != "N")
    petugas = {r["id"]: r["nama"] for r in query("SELECT id,nama FROM user")}
    from datetime import datetime
    return render_template("orders/detail.html", o=o, pt=pt, groups=groups, log=log, abnormal=abnormal,
                           petugas=petugas, now_local=datetime.now().strftime("%Y-%m-%dT%H:%M"))


def _require(o, *allowed):
    if o["status"] not in allowed:
        flash("Langkah ini tidak tersedia untuk status order saat ini.", "warning")
        return False
    return True


# Langkah 2: pasien dipanggil ke lab
@bp.route("/<int:oid>/panggil", methods=["POST"])
@roles_required("admin", "analis")
def panggil(oid):
    o = get_order(oid)
    if _require(o, "menunggu"):
        db = get_db()
        db.execute("UPDATE lab_order SET status='dipanggil' WHERE id=?", (oid,))
        log_status(db, oid, "dipanggil", g.user["id"], "Pasien dipanggil ke lab")
        db.commit()
        flash(f"Pasien {o['pasien']} dipanggil (antrian {o['kode_antrian']}).", "success")
    return redirect(url_for("orders.detail", oid=oid))


# Langkah 3 + 4: cek identitas, ambil sampel, barcode
@bp.route("/<int:oid>/sampel", methods=["POST"])
@roles_required("admin", "analis")
def sampel(oid):
    o = get_order(oid)
    if not _require(o, "menunggu", "dipanggil"):
        return redirect(url_for("orders.detail", oid=oid))
    if not request.form.get("identitas_ok"):
        flash("Konfirmasi pengecekan identitas pasien (nama + no. RM) terlebih dahulu.", "danger")
        return redirect(url_for("orders.detail", oid=oid))
    jenis = request.form.get("jenis_sampel", "").strip()
    waktu = request.form.get("waktu_sampel", "").replace("T", " ")[:16] or now_str()
    if not jenis:
        flash("Jenis sampel wajib diisi.", "danger")
        return redirect(url_for("orders.detail", oid=oid))
    db = get_db()
    _, _, barcode = next_order_numbers(db, date.fromisoformat(o["tgl_order"][:10]))
    # barcode unik: bila bentrok, tambahkan id order
    if db.execute("SELECT 1 FROM lab_order WHERE barcode=?", (barcode,)).fetchone():
        barcode = f"{barcode}{oid}"
    db.execute("""UPDATE lab_order SET status='sampel_diambil', waktu_sampel=?, jenis_sampel=?,
                  petugas_sampel=?, barcode=? WHERE id=?""", (waktu, jenis, g.user["id"], barcode, oid))
    log_status(db, oid, "sampel_diambil", g.user["id"], f"Sampel {jenis} diambil, barcode {barcode}")
    db.commit()
    flash(f"Sampel dicatat. Barcode {barcode} siap dicetak.", "success")
    return redirect(url_for("orders.label", oid=oid) if request.form.get("cetak") else
                    url_for("orders.detail", oid=oid))


@bp.route("/<int:oid>/label")
def label(oid):
    o = get_order(oid)
    if not o["barcode"]:
        abort(404, "Barcode belum dibuat (sampel belum diambil).")
    return render_template("orders/label.html", o=o)


# Langkah 5: periksa & input hasil per nilai
@bp.route("/<int:oid>/hasil", methods=["POST"])
@roles_required("admin", "analis")
def hasil(oid):
    o = get_order(oid)
    if not _require(o, "sampel_diambil", "diperiksa"):
        return redirect(url_for("orders.detail", oid=oid))
    db = get_db()
    params = query("""SELECT tp.* FROM test_parameter tp JOIN order_test ot ON ot.test_id=tp.test_id
                      WHERE ot.order_id=? ORDER BY tp.test_id, tp.urutan""", (oid,))
    errors, rows = [], []
    for p in params:
        raw = request.form.get(f"nilai_{p['id']}", "").strip()
        if raw == "":
            continue
        try:
            flag, norm = evaluate(p, raw, o["jenis_kelamin"])
            if p["tipe"] == "pilihan" and raw not in p["pilihan"].split("|"):
                raise ValueError
        except ValueError:
            errors.append(f"Nilai '{p['nama']}' tidak valid.")
            continue
        sumber = "alat" if request.form.get(f"alat_{p['id']}") else "manual"
        rows.append((oid, p["id"], norm, flag, ref_text(p, o["jenis_kelamin"]), sumber))
    if errors:
        for e in errors:
            flash(e, "danger")
        return redirect(url_for("orders.detail", oid=oid))
    if not rows:
        flash("Belum ada nilai yang diisi.", "warning")
        return redirect(url_for("orders.detail", oid=oid))
    db.execute("DELETE FROM order_result WHERE order_id=?", (oid,))
    db.executemany("""INSERT INTO order_result(order_id,parameter_id,nilai,flag,rujukan_teks,sumber)
                      VALUES (?,?,?,?,?,?)""", rows)
    db.execute("""UPDATE lab_order SET status='diperiksa', waktu_hasil=?, petugas_hasil=?, catatan_hasil=?
                  WHERE id=?""", (now_str(), g.user["id"], request.form.get("catatan_hasil", "").strip() or None, oid))
    if o["status"] != "diperiksa":
        log_status(db, oid, "diperiksa", g.user["id"], "Hasil diinput")
    else:
        log_status(db, oid, "diperiksa", g.user["id"], "Hasil diperbarui")
    db.commit()
    flash(f"{len(rows)} nilai hasil tersimpan. Flag dihitung otomatis dari nilai rujukan.", "success")
    return redirect(url_for("orders.detail", oid=oid))


# Simulasi pembacaan nilai dari alat (LIS)
@bp.route("/<int:oid>/alat")
@roles_required("admin", "analis")
def alat(oid):
    o = get_order(oid)
    if o["status"] not in ("sampel_diambil", "diperiksa"):
        abort(400, "Sampel belum diambil.")
    rng = random.Random()
    out = {}
    from ..seed import _gen_value
    for p in query("""SELECT tp.* FROM test_parameter tp JOIN order_test ot ON ot.test_id=tp.test_id
                      WHERE ot.order_id=?""", (oid,)):
        out[p["id"]] = _gen_value(p, o["jenis_kelamin"], rng, rng.random() < 0.2)
    return jsonify(out)


# Langkah 6: validasi & kirim ke dokter
@bp.route("/<int:oid>/validasi", methods=["POST"])
@roles_required("admin", "dokter", "analis")
def validasi(oid):
    o = get_order(oid)
    if not _require(o, "diperiksa"):
        return redirect(url_for("orders.detail", oid=oid))
    db = get_db()
    total = db.execute("""SELECT COUNT(*) c FROM test_parameter tp JOIN order_test ot ON ot.test_id=tp.test_id
                          WHERE ot.order_id=?""", (oid,)).fetchone()["c"]
    isi = db.execute("SELECT COUNT(*) c FROM order_result WHERE order_id=?", (oid,)).fetchone()["c"]
    if isi < total:
        flash(f"Hasil belum lengkap ({isi}/{total} parameter). Lengkapi sebelum validasi.", "danger")
        return redirect(url_for("orders.detail", oid=oid))
    db.execute("UPDATE lab_order SET status='selesai', waktu_validasi=?, validator_id=? WHERE id=?",
               (now_str(), g.user["id"], oid))
    log_status(db, oid, "selesai", g.user["id"], "Divalidasi, hasil terkirim ke dokter " + o["dokter"])
    db.commit()
    flash(f"Hasil divalidasi dan dikirim ke {o['dokter']}.", "success")
    return redirect(url_for("orders.detail", oid=oid))


@bp.route("/<int:oid>/batal", methods=["POST"])
@roles_required("admin", "dokter")
def batal(oid):
    o = get_order(oid)
    if _require(o, "menunggu", "dipanggil"):
        db = get_db()
        db.execute("UPDATE lab_order SET status='batal' WHERE id=?", (oid,))
        log_status(db, oid, "batal", g.user["id"], request.form.get("alasan", "Order dibatalkan"))
        db.commit()
        flash("Order dibatalkan.", "info")
    return redirect(url_for("orders.detail", oid=oid))


@bp.route("/<int:oid>/cetak")
def cetak(oid):
    o = get_order(oid)
    if o["status"] != "selesai":
        flash("Hasil hanya dapat dicetak setelah divalidasi.", "warning")
        return redirect(url_for("orders.detail", oid=oid))
    pt = query("SELECT * FROM patient WHERE id=?", (o["patient_id"],), one=True)
    groups = []
    res = {r["parameter_id"]: r for r in query("SELECT * FROM order_result WHERE order_id=?", (oid,))}
    for t in query("""SELECT t.* FROM order_test ot JOIN lab_test t ON t.id=ot.test_id
                      WHERE ot.order_id=? ORDER BY t.kategori, t.nama""", (oid,)):
        ps = query("SELECT * FROM test_parameter WHERE test_id=? ORDER BY urutan", (t["id"],))
        groups.append({"test": t, "rows": [{"p": p, "res": res.get(p["id"])} for p in ps]})
    validator = query("SELECT nama FROM user WHERE id=?", (o["validator_id"],), one=True)
    analis = query("SELECT nama FROM user WHERE id=?", (o["petugas_hasil"],), one=True)
    return render_template("orders/cetak.html", o=o, pt=pt, groups=groups, validator=validator, analis=analis)
