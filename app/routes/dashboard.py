from datetime import date, timedelta

from flask import Blueprint, redirect, render_template, request, url_for

from ..db import query
from ..services import BULAN

bp = Blueprint("dashboard", __name__)


@bp.route("/")
def index():
    t = date.today().isoformat()
    like = t + "%"
    cnt = lambda where, args=(): query(
        f"SELECT COUNT(*) c FROM lab_order WHERE tgl_order LIKE ? {where}", (like, *args), one=True)["c"]

    stat = {
        "total": cnt("AND status!='batal'"),
        "menunggu": cnt("AND status='menunggu'"),
        "proses": cnt("AND status IN ('dipanggil','sampel_diambil','diperiksa')"),
        "selesai": cnt("AND status='selesai'"),
    }
    stat["abnormal"] = query(
        """SELECT COUNT(DISTINCT o.id) c FROM lab_order o JOIN order_result r ON r.order_id=o.id
           WHERE o.tgl_order LIKE ? AND r.flag!='N'""", (like,), one=True)["c"]
    stat["kritis"] = query(
        """SELECT COUNT(DISTINCT o.id) c FROM lab_order o JOIN order_result r ON r.order_id=o.id
           WHERE o.tgl_order LIKE ? AND r.flag IN ('HH','LL')""", (like,), one=True)["c"]
    stat["pendapatan"] = query(
        """SELECT COALESCE(SUM(b.total),0) s FROM billing b JOIN lab_order o ON o.id=b.order_id
           WHERE o.tgl_order LIKE ? AND o.status!='batal'""", (like,), one=True)["s"]
    tat = query(
        """SELECT AVG((julianday(waktu_validasi)-julianday(tgl_order))*1440) m FROM lab_order
           WHERE status='selesai' AND tgl_order >= ?""", ((date.today() - timedelta(days=14)).isoformat(),),
        one=True)["m"]
    stat["tat"] = round(tat) if tat else 0

    # tren 7 hari
    days = [date.today() - timedelta(days=i) for i in range(6, -1, -1)]
    rows = {r["d"]: r["c"] for r in query(
        """SELECT substr(tgl_order,1,10) d, COUNT(*) c FROM lab_order WHERE tgl_order >= ? AND status!='batal'
           GROUP BY d""", (days[0].isoformat(),))}
    trend = {"labels": [f"{d.day} {BULAN[d.month-1]}" for d in days],
             "data": [rows.get(d.isoformat(), 0) for d in days]}

    status_dist = {r["status"]: r["c"] for r in query(
        "SELECT status, COUNT(*) c FROM lab_order WHERE tgl_order LIKE ? GROUP BY status", (like,))}

    top = query(
        """SELECT t.nama, COUNT(*) c FROM order_test ot JOIN lab_test t ON t.id=ot.test_id
           JOIN lab_order o ON o.id=ot.order_id WHERE o.tgl_order >= ? AND o.status!='batal'
           GROUP BY t.id ORDER BY c DESC LIMIT 6""", ((date.today() - timedelta(days=30)).isoformat(),))

    antrian = query(
        """SELECT o.*, p.nama pasien, p.no_rm, GROUP_CONCAT(t.nama, ', ') tests
           FROM lab_order o JOIN patient p ON p.id=o.patient_id
           JOIN order_test ot ON ot.order_id=o.id JOIN lab_test t ON t.id=ot.test_id
           WHERE o.tgl_order LIKE ? AND o.status NOT IN ('selesai','batal')
           GROUP BY o.id ORDER BY (o.prioritas='cito') DESC, o.tgl_order LIMIT 8""", (like,))

    kritis = query(
        """SELECT o.id, o.kode_antrian, p.nama pasien, tp.nama param, r.nilai, tp.satuan, r.flag
           FROM order_result r JOIN lab_order o ON o.id=r.order_id JOIN patient p ON p.id=o.patient_id
           JOIN test_parameter tp ON tp.id=r.parameter_id
           WHERE r.flag IN ('HH','LL') ORDER BY o.tgl_order DESC LIMIT 5""")

    return render_template("dashboard.html", stat=stat, trend=trend, status_dist=status_dist,
                           top=top, antrian=antrian, kritis=kritis)


@bp.route("/search")
def search():
    """Pencarian global: pasien, order, no. antrian, barcode, pemeriksaan."""
    q = request.args.get("q", "").strip()
    if not q:
        return redirect(url_for("dashboard.index"))
    # barcode / no. order persis -> langsung buka order
    hit = query("SELECT id FROM lab_order WHERE barcode=? OR no_order=?", (q, q), one=True)
    if hit:
        return redirect(url_for("orders.detail", oid=hit["id"]))
    like = f"%{q}%"
    pasien = query("""SELECT * FROM patient WHERE nama LIKE ? OR no_rm LIKE ? OR no_hp LIKE ?
                      ORDER BY nama LIMIT 15""", (like, like, like))
    orders = query("""SELECT o.id, o.no_order, o.kode_antrian, o.status, o.tgl_order, p.nama pasien, p.no_rm
                      FROM lab_order o JOIN patient p ON p.id=o.patient_id
                      WHERE o.no_order LIKE ? OR o.kode_antrian LIKE ? OR o.barcode LIKE ? OR p.nama LIKE ?
                      ORDER BY o.tgl_order DESC LIMIT 15""", (like, like, like, like))
    tests = query("SELECT * FROM lab_test WHERE nama LIKE ? OR kode LIKE ? ORDER BY nama LIMIT 10", (like, like))
    return render_template("search.html", q=q, pasien=pasien, orders=orders, tests=tests)


@bp.route("/api/patients")
def api_patients():
    from flask import jsonify
    q = request.args.get("q", "").strip()
    rows = query("""SELECT id, no_rm, nama, jenis_kelamin, tgl_lahir FROM patient
                    WHERE nama LIKE ? OR no_rm LIKE ? ORDER BY nama LIMIT 8""", (f"%{q}%", f"%{q}%"))
    from ..services import age_of
    return jsonify([{**dict(r), "umur": age_of(r["tgl_lahir"])} for r in rows])
