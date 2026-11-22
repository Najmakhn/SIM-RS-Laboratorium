"""Master data: katalog pemeriksaan (beserta parameter & nilai rujukan) dan dokter."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from ..db import get_db, query
from .auth import roles_required

bp = Blueprint("master", __name__, url_prefix="/master")


def _f(v):
    v = (v or "").strip().replace(",", ".")
    return float(v) if v else None


@bp.route("/tests")
def tests():
    q = request.args.get("q", "").strip()
    kat = request.args.get("kategori", "")
    w, a = "(t.nama LIKE ? OR t.kode LIKE ?)", [f"%{q}%"] * 2
    if kat:
        w += " AND t.kategori=?"; a.append(kat)
    rows = query(f"""SELECT t.*, (SELECT COUNT(*) FROM test_parameter WHERE test_id=t.id) n_param
                     FROM lab_test t WHERE {w} ORDER BY t.kategori, t.nama""", a)
    kats = [r["kategori"] for r in query("SELECT DISTINCT kategori FROM lab_test ORDER BY 1")]
    return render_template("master/tests.html", rows=rows, q=q, kat=kat, kats=kats)


@bp.route("/tests/baru", methods=["GET", "POST"])
@bp.route("/tests/<int:tid>", methods=["GET", "POST"])
@roles_required("admin")
def test_form(tid=None):
    t = query("SELECT * FROM lab_test WHERE id=?", (tid,), one=True) if tid else None
    if tid and not t:
        abort(404)
    if request.method == "POST":
        db = get_db()
        f = request.form
        try:
            data = (f["kode"].strip().upper(), f["nama"].strip(), f["kategori"].strip(),
                    f["jenis_sampel"].strip(), int(f["tarif"] or 0), 1 if f.get("aktif") else 0)
            if not all(data[:4]):
                raise ValueError("Kode, nama, kategori, dan jenis sampel wajib diisi.")
            if tid:
                db.execute("UPDATE lab_test SET kode=?,nama=?,kategori=?,jenis_sampel=?,tarif=?,aktif=? WHERE id=?",
                           (*data, tid))
            else:
                tid = db.execute("INSERT INTO lab_test(kode,nama,kategori,jenis_sampel,tarif,aktif) VALUES (?,?,?,?,?,?)",
                                 data).lastrowid
            # parameter: dikirim sebagai daftar kolom paralel
            ids = f.getlist("p_id")
            keep = []
            for i, pid in enumerate(ids):
                nama = f.getlist("p_nama")[i].strip()
                if not nama:
                    continue
                tipe = f.getlist("p_tipe")[i]
                vals = (nama, f.getlist("p_satuan")[i].strip(), tipe,
                        _f(f.getlist("p_minl")[i]), _f(f.getlist("p_maxl")[i]),
                        _f(f.getlist("p_minp")[i]), _f(f.getlist("p_maxp")[i]),
                        _f(f.getlist("p_kmin")[i]), _f(f.getlist("p_kmax")[i]),
                        f.getlist("p_pilihan")[i].strip() or None, f.getlist("p_normal")[i].strip() or None,
                        int(f.getlist("p_desimal")[i] or 0), i + 1)
                if pid:
                    db.execute("""UPDATE test_parameter SET nama=?,satuan=?,tipe=?,ref_min_l=?,ref_max_l=?,ref_min_p=?,
                                  ref_max_p=?,krit_min=?,krit_max=?,pilihan=?,nilai_normal=?,desimal=?,urutan=?
                                  WHERE id=? AND test_id=?""", (*vals, pid, tid))
                    keep.append(int(pid))
                else:
                    keep.append(db.execute("""INSERT INTO test_parameter(nama,satuan,tipe,ref_min_l,ref_max_l,ref_min_p,
                        ref_max_p,krit_min,krit_max,pilihan,nilai_normal,desimal,urutan,test_id)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (*vals, tid)).lastrowid)
            # hapus parameter yang dibuang, bila belum punya hasil
            for r in db.execute("SELECT id FROM test_parameter WHERE test_id=?", (tid,)).fetchall():
                if r["id"] not in keep and not db.execute(
                        "SELECT 1 FROM order_result WHERE parameter_id=?", (r["id"],)).fetchone():
                    db.execute("DELETE FROM test_parameter WHERE id=?", (r["id"],))
            db.commit()
            flash("Pemeriksaan disimpan.", "success")
            return redirect(url_for("master.tests"))
        except Exception as e:  # noqa: BLE001 - tampilkan pesan ramah
            db.rollback()
            msg = "Kode pemeriksaan sudah dipakai." if "UNIQUE" in str(e) else str(e)
            flash(f"Gagal menyimpan: {msg}", "danger")
    params = query("SELECT * FROM test_parameter WHERE test_id=? ORDER BY urutan", (tid,)) if tid else []
    return render_template("master/test_form.html", t=t, params=params)


@bp.route("/doctors")
def doctors():
    q = request.args.get("q", "").strip()
    rows = query("""SELECT d.*, (SELECT COUNT(*) FROM lab_order o WHERE o.doctor_id=d.id) n_order
                    FROM doctor d WHERE nama LIKE ? OR spesialis LIKE ? ORDER BY nama""", (f"%{q}%", f"%{q}%"))
    return render_template("master/doctors.html", rows=rows, q=q)


@bp.route("/doctors/simpan", methods=["POST"])
@roles_required("admin")
def doctor_save():
    f, db = request.form, get_db()
    nama, sp = f.get("nama", "").strip(), f.get("spesialis", "").strip()
    if not nama or not sp:
        flash("Nama dan spesialisasi wajib diisi.", "danger")
    elif f.get("id"):
        db.execute("UPDATE doctor SET nama=?,spesialis=?,aktif=? WHERE id=?",
                   (nama, sp, 1 if f.get("aktif") else 0, f["id"]))
        db.commit(); flash("Dokter diperbarui.", "success")
    else:
        db.execute("INSERT INTO doctor(nama,spesialis) VALUES (?,?)", (nama, sp))
        db.commit(); flash("Dokter ditambahkan.", "success")
    return redirect(url_for("master.doctors"))
