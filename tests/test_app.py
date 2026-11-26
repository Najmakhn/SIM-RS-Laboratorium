"""Tes alur utama SIMRS Lab:  python -m pytest -q   (atau: python tests/test_app.py)"""
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import create_app  # noqa: E402
from app.db import query  # noqa: E402
from app.services import evaluate  # noqa: E402


def make_client(role="admin"):
    app = create_app({"DATABASE": str(Path(tempfile.mkdtemp()) / "t.db"), "TESTING": True})
    c = app.test_client()
    login(c, role)
    return app, c


def csrf(c, url="/"):
    html = c.get(url).get_data(as_text=True)
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


def login(c, role):
    r = c.get("/login")
    tok = re.search(r'name="csrf_token" value="([^"]+)"', r.get_data(as_text=True)).group(1)
    pw = {"admin": "admin123", "analis": "analis123", "dokter": "dokter123"}[role]
    r = c.post("/login", data={"username": role, "password": pw, "csrf_token": tok})
    assert r.status_code == 302


def test_semua_halaman_terbuka():
    app, c = make_client()
    for url in ["/", "/orders/", "/orders/?q=Budi&status=diperiksa", "/orders/baru", "/patients/", "/patients/?q=00-12",
                "/patients/1", "/master/tests", "/master/tests/1", "/master/tests/baru", "/master/doctors",
                "/billing/", "/billing/?status=lunas", "/reports/", "/reports/export.csv", "/search?q=Budi"]:
        assert c.get(url).status_code == 200, url


def test_login_wajib_dan_salah_password():
    app = create_app({"DATABASE": str(Path(tempfile.mkdtemp()) / "t.db"), "TESTING": True})
    c = app.test_client()
    assert c.get("/orders/").status_code == 302
    tok = re.search(r'value="([^"]+)"', c.get("/login").get_data(as_text=True)).group(1)
    r = c.post("/login", data={"username": "admin", "password": "salah", "csrf_token": tok})
    assert "salah" in r.get_data(as_text=True)


def test_csrf_menolak_post_tanpa_token():
    app, c = make_client()
    assert c.post("/orders/1/panggil", data={}).status_code == 400


def test_flag_otomatis_sesuai_materi():
    app, c = make_client()
    with app.app_context():
        hb = query("SELECT * FROM test_parameter WHERE nama='Hemoglobin'", one=True)
        gds = query("SELECT * FROM test_parameter WHERE nama='Gula darah sewaktu'", one=True)
        assert evaluate(hb, "13,5", "L")[0] == "N"
        assert evaluate(hb, "11", "L")[0] == "L" and evaluate(hb, "11", "P")[0] == "L"
        assert evaluate(hb, "12.5", "P")[0] == "N"        # rujukan beda per jenis kelamin
        assert evaluate(gds, "210", "L")[0] == "H"        # contoh GDS 210 -> H pada materi
        assert evaluate(gds, "40", "L")[0] == "LL"


def test_budi_b05_sesuai_gambar_materi():
    app, c = make_client()
    with app.app_context():
        o = query("""SELECT o.* FROM lab_order o JOIN patient p ON p.id=o.patient_id
                     WHERE p.no_rm='00-12-34' AND o.tgl_order LIKE date('now','localtime')||'%'""", one=True)
        assert o["kode_antrian"] == "B-05" and o["status"] == "diperiksa"
        r = query("""SELECT tp.nama, r.nilai, r.flag FROM order_result r JOIN test_parameter tp ON tp.id=r.parameter_id
                     WHERE r.order_id=?""", (o["id"],))
        d = {x["nama"]: (x["nilai"], x["flag"]) for x in r}
        assert d["Gula darah sewaktu"] == ("210", "H") and d["Hemoglobin"] == ("13.5", "N")


def test_alur_enam_langkah_end_to_end():
    app, c = make_client()
    tok = csrf(c, "/orders/baru")
    # 1. order masuk
    r = c.post("/orders/baru", data={"csrf_token": tok, "patient_id": 2, "doctor_id": 1, "asal": "IGD",
                                     "prioritas": "cito", "test_id": [1, 2], "catatan": "uji"})
    assert r.status_code == 302
    oid = int(r.headers["Location"].rstrip("/").split("/")[-1])
    with app.app_context():
        assert query("SELECT status FROM lab_order WHERE id=?", (oid,), one=True)["status"] == "menunggu"
        b = query("SELECT total FROM billing WHERE order_id=?", (oid,), one=True)
        assert b["total"] == 85000 + 25000            # tarif -> billing otomatis
    # langkah tidak berurutan ditolak
    c.post(f"/orders/{oid}/validasi", data={"csrf_token": tok})
    with app.app_context():
        assert query("SELECT status FROM lab_order WHERE id=?", (oid,), one=True)["status"] == "menunggu"
    # 2. panggil
    c.post(f"/orders/{oid}/panggil", data={"csrf_token": tok})
    # 3. tanpa cek identitas ditolak
    c.post(f"/orders/{oid}/sampel", data={"csrf_token": tok, "jenis_sampel": "Darah"})
    with app.app_context():
        assert query("SELECT status FROM lab_order WHERE id=?", (oid,), one=True)["status"] == "dipanggil"
    c.post(f"/orders/{oid}/sampel", data={"csrf_token": tok, "identitas_ok": "1", "jenis_sampel": "Darah EDTA"})
    with app.app_context():
        o = query("SELECT * FROM lab_order WHERE id=?", (oid,), one=True)
        assert o["status"] == "sampel_diambil" and o["barcode"]                    # 4. barcode
        pid = {r["nama"]: r["id"] for r in query("""SELECT tp.id, tp.nama FROM test_parameter tp
               JOIN order_test ot ON ot.test_id=tp.test_id WHERE ot.order_id=?""", (oid,))}
    assert c.get(f"/orders/{oid}/label").status_code == 200
    # 5. input hasil; validasi sebelum lengkap ditolak
    c.post(f"/orders/{oid}/hasil", data={"csrf_token": tok, f"nilai_{pid['Hemoglobin']}": "9,0"})
    c.post(f"/orders/{oid}/validasi", data={"csrf_token": tok})
    with app.app_context():
        assert query("SELECT status FROM lab_order WHERE id=?", (oid,), one=True)["status"] == "diperiksa"
    data = {"csrf_token": tok, f"nilai_{pid['Hemoglobin']}": "9,0", f"nilai_{pid['Leukosit']}": "7800",
            f"nilai_{pid['Trombosit']}": "250000", f"nilai_{pid['Hematokrit']}": "41",
            f"nilai_{pid['Gula darah sewaktu']}": "250"}
    c.post(f"/orders/{oid}/hasil", data=data)
    with app.app_context():
        fl = {r["nama"]: r["flag"] for r in query("""SELECT tp.nama, r.flag FROM order_result r
              JOIN test_parameter tp ON tp.id=r.parameter_id WHERE r.order_id=?""", (oid,))}
        assert fl["Hemoglobin"] == "L" and fl["Gula darah sewaktu"] == "H" and fl["Leukosit"] == "N"
    assert c.get(f"/orders/{oid}/cetak").status_code == 302   # belum divalidasi
    # 6. validasi
    c.post(f"/orders/{oid}/validasi", data={"csrf_token": tok})
    with app.app_context():
        o = query("SELECT * FROM lab_order WHERE id=?", (oid,), one=True)
        assert o["status"] == "selesai" and o["validator_id"]
    assert c.get(f"/orders/{oid}/cetak").status_code == 200
    # hasil terkunci setelah validasi
    c.post(f"/orders/{oid}/hasil", data={"csrf_token": tok, f"nilai_{pid['Hemoglobin']}": "15"})
    with app.app_context():
        assert query("SELECT nilai FROM order_result WHERE order_id=? AND parameter_id=?",
                     (oid, pid["Hemoglobin"]), one=True)["nilai"] == "9"
    # barcode scan -> langsung ke order
    r = c.get(f"/search?q={o['barcode']}")
    assert r.status_code == 302 and r.headers["Location"].endswith(f"/orders/{oid}")


def test_pencarian_dan_crud_pasien():
    app, c = make_client()
    tok = csrf(c, "/patients/baru")
    r = c.post("/patients/baru", data={"csrf_token": tok, "nama": "Uji Coba", "jenis_kelamin": "P",
                                       "tgl_lahir": "1999-05-05", "alamat": "Surabaya", "no_hp": "0811"})
    assert r.status_code == 302
    assert "Uji Coba" in c.get("/patients/?q=Uji").get_data(as_text=True)
    assert "Uji Coba" in c.get("/search?q=Uji").get_data(as_text=True)
    assert "Uji Coba" in c.get("/api/patients?q=Uji").get_data(as_text=True)
    bad = c.post("/patients/baru", data={"csrf_token": tok, "nama": "", "jenis_kelamin": "", "tgl_lahir": "2999-01-01"})
    assert bad.status_code == 200 and "wajib" in bad.get_data(as_text=True)


def test_hak_akses_peran():
    app, c = make_client("dokter")
    tok = csrf(c)
    assert c.get("/master/tests/baru").status_code == 403
    assert c.post("/orders/1/panggil", data={"csrf_token": tok}).status_code == 403


def test_login_dikunci_setelah_5_kali_gagal():
    app = create_app({"DATABASE": str(Path(tempfile.mkdtemp()) / "t.db"), "TESTING": True})
    c = app.test_client()
    tok = re.search(r'value="([^"]+)"', c.get("/login").get_data(as_text=True)).group(1)
    for _ in range(5):
        c.post("/login", data={"username": "analis2", "password": "salah", "csrf_token": tok})
    # percobaan ke-6 ditolak walaupun password-nya benar
    r = c.post("/login", data={"username": "analis2", "password": "analis123", "csrf_token": tok})
    assert r.status_code == 429
    assert "Terlalu banyak percobaan" in r.get_data(as_text=True)
    # username lain tidak ikut terkunci
    r = c.post("/login", data={"username": "dokter", "password": "dokter123", "csrf_token": tok})
    assert r.status_code == 302


def test_sesi_login_punya_batas_waktu():
    app = create_app({"DATABASE": str(Path(tempfile.mkdtemp()) / "t.db"), "TESTING": True})
    c = app.test_client()
    tok = re.search(r'value="([^"]+)"', c.get("/login").get_data(as_text=True)).group(1)
    r = c.post("/login", data={"username": "admin", "password": "admin123", "csrf_token": tok})
    cookie = r.headers.get("Set-Cookie", "")
    assert "session=" in cookie and "Expires=" in cookie
    assert app.permanent_session_lifetime.total_seconds() == 8 * 3600


def test_galat_server_tampil_halaman_ramah():
    app = create_app({"DATABASE": str(Path(tempfile.mkdtemp()) / "t.db"), "TESTING": False})

    @app.route("/uji-galat")
    def uji_galat():
        raise RuntimeError("galat uji")

    c = app.test_client()
    login(c, "admin")
    r = c.get("/uji-galat")
    assert r.status_code == 500
    html = r.get_data(as_text=True)
    assert "Terjadi kesalahan di server" in html
    assert "galat uji" not in html  # detail galat tidak bocor ke pengguna


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
