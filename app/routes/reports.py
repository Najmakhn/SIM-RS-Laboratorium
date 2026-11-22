import csv
import io
from datetime import date, timedelta

from flask import Blueprint, Response, render_template, request

from ..db import query
from ..services import STATUS

bp = Blueprint("reports", __name__, url_prefix="/reports")


def _data():
    today = date.today()
    dari = request.args.get("dari") or (today - timedelta(days=6)).isoformat()
    sampai = request.args.get("sampai") or today.isoformat()
    st = request.args.get("status", "")
    w, a = "substr(o.tgl_order,1,10) BETWEEN ? AND ?", [dari, sampai]
    if st:
        w += " AND o.status=?"; a.append(st)
    rows = query(f"""SELECT o.*, p.nama pasien, p.no_rm, d.nama dokter, b.total, b.status bayar,
                     (SELECT GROUP_CONCAT(t.nama, ', ') FROM order_test ot JOIN lab_test t ON t.id=ot.test_id
                       WHERE ot.order_id=o.id) tests,
                     (SELECT COUNT(*) FROM order_result r WHERE r.order_id=o.id AND r.flag!='N') n_abn
                     FROM lab_order o JOIN patient p ON p.id=o.patient_id JOIN doctor d ON d.id=o.doctor_id
                     LEFT JOIN billing b ON b.order_id=o.id WHERE {w} ORDER BY o.tgl_order DESC""", a)
    return dari, sampai, st, rows


@bp.route("/")
def index():
    dari, sampai, st, rows = _data()
    ringkas = {"order": len(rows), "selesai": sum(r["status"] == "selesai" for r in rows),
               "abnormal": sum(1 for r in rows if r["n_abn"]),
               "pendapatan": sum((r["total"] or 0) for r in rows if r["status"] != "batal")}
    return render_template("reports.html", rows=rows, dari=dari, sampai=sampai, st=st, ringkas=ringkas)


@bp.route("/export.csv")
def export():
    dari, sampai, st, rows = _data()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["No Order", "Antrian", "Tanggal", "No RM", "Pasien", "Dokter", "Asal", "Prioritas",
                "Pemeriksaan", "Status", "Parameter abnormal", "Total (Rp)", "Pembayaran"])
    for r in rows:
        w.writerow([r["no_order"], r["kode_antrian"], r["tgl_order"], r["no_rm"], r["pasien"], r["dokter"],
                    r["asal"], r["prioritas"], r["tests"], STATUS[r["status"]]["label"], r["n_abn"],
                    r["total"], r["bayar"]])
    return Response("\ufeff" + buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=laporan-lab-{dari}_{sampai}.csv"})
