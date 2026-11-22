from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..db import get_db, query
from ..services import METODE_BAYAR, now_str
from .auth import roles_required

bp = Blueprint("billing", __name__, url_prefix="/billing")


@bp.route("/")
def index():
    q = request.args.get("q", "").strip()
    st = request.args.get("status", "")
    w, a = "(p.nama LIKE ? OR p.no_rm LIKE ? OR o.no_order LIKE ?) AND o.status!='batal'", [f"%{q}%"] * 3
    if st:
        w += " AND b.status=?"; a.append(st)
    rows = query(f"""SELECT b.*, o.no_order, o.kode_antrian, o.tgl_order, o.status ostatus, p.nama pasien, p.no_rm,
                     (SELECT GROUP_CONCAT(t.nama || '|' || ot.tarif, ';') FROM order_test ot
                       JOIN lab_test t ON t.id=ot.test_id WHERE ot.order_id=o.id) items
                     FROM billing b JOIN lab_order o ON o.id=b.order_id JOIN patient p ON p.id=o.patient_id
                     WHERE {w} ORDER BY o.tgl_order DESC LIMIT 60""", a)
    sums = query("SELECT b.status, SUM(b.total) s, COUNT(*) c FROM billing b JOIN lab_order o ON o.id=b.order_id "
                 "WHERE o.status!='batal' GROUP BY b.status")
    sums = {r["status"]: r for r in sums}
    return render_template("billing.html", rows=rows, q=q, st=st, sums=sums)


@bp.route("/<int:bid>/bayar", methods=["POST"])
@roles_required("admin")
def bayar(bid):
    metode = request.form.get("metode")
    if metode not in METODE_BAYAR:
        flash("Pilih metode pembayaran.", "danger")
    else:
        db = get_db()
        db.execute("UPDATE billing SET status='lunas', dibayar_at=?, metode=? WHERE id=?", (now_str(), metode, bid))
        db.commit()
        flash("Pembayaran dicatat sebagai lunas.", "success")
    return redirect(request.referrer or url_for("billing.index"))
