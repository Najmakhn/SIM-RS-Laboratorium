"""Data contoh: katalog pemeriksaan, pasien, dokter, dan order 14 hari terakhir."""
import random
from datetime import date, datetime, timedelta

from werkzeug.security import generate_password_hash

from .services import evaluate, int_to_rm, log_status, ref_text

# kode, nama, kategori, jenis sampel, tarif
TESTS = [
    ("DL",    "Darah Lengkap",       "Hematologi",    "Darah EDTA",   85000),
    ("GDS",   "Gula Darah Sewaktu",  "Kimia Klinik",  "Serum",        25000),
    ("GDP",   "Gula Darah Puasa",    "Kimia Klinik",  "Serum",        25000),
    ("HBA1C", "HbA1c",               "Kimia Klinik",  "Darah EDTA",  180000),
    ("LIP",   "Profil Lipid",        "Kimia Klinik",  "Serum",       120000),
    ("GIN",   "Fungsi Ginjal",       "Kimia Klinik",  "Serum",        70000),
    ("HAT",   "Fungsi Hati",         "Kimia Klinik",  "Serum",        75000),
    ("URAT",  "Asam Urat",           "Kimia Klinik",  "Serum",        30000),
    ("ELEK",  "Elektrolit",          "Kimia Klinik",  "Serum",       110000),
    ("UL",    "Urin Lengkap",        "Urinalisis",    "Urin",         45000),
]
NEG = "Negatif|Trace|+1|+2|+3"
# test_kode: (nama, satuan, tipe, (minL,maxL), (minP,maxP), (krit_min,krit_max), pilihan, normal, desimal)
N = None
PARAMS = {
    "DL": [
        ("Hemoglobin", "g/dL", "angka", (13, 17), (12, 16), (7, 20), N, N, 1),
        ("Leukosit", "/µL", "angka", (4000, 10000), (4000, 10000), (2000, 30000), N, N, 0),
        ("Trombosit", "/µL", "angka", (150000, 400000), (150000, 400000), (20000, 1000000), N, N, 0),
        ("Hematokrit", "%", "angka", (40, 52), (37, 47), (20, 60), N, N, 0),
    ],
    "GDS": [("Gula darah sewaktu", "mg/dL", "angka", (N, 200), (N, 200), (50, 500), N, N, 0)],
    "GDP": [("Gula darah puasa", "mg/dL", "angka", (70, 100), (70, 100), (50, 400), N, N, 0)],
    "HBA1C": [("HbA1c", "%", "angka", (4.0, 5.6), (4.0, 5.6), (N, N), N, N, 1)],
    "LIP": [
        ("Kolesterol total", "mg/dL", "angka", (N, 200), (N, 200), (N, N), N, N, 0),
        ("HDL", "mg/dL", "angka", (40, N), (50, N), (N, N), N, N, 0),
        ("LDL", "mg/dL", "angka", (N, 130), (N, 130), (N, N), N, N, 0),
        ("Trigliserida", "mg/dL", "angka", (N, 150), (N, 150), (N, 1000), N, N, 0),
    ],
    "GIN": [
        ("Ureum", "mg/dL", "angka", (10, 50), (10, 50), (N, N), N, N, 0),
        ("Kreatinin", "mg/dL", "angka", (0.7, 1.3), (0.6, 1.1), (N, 10), N, N, 2),
    ],
    "HAT": [
        ("SGOT (AST)", "U/L", "angka", (N, 37), (N, 31), (N, N), N, N, 0),
        ("SGPT (ALT)", "U/L", "angka", (N, 42), (N, 32), (N, N), N, N, 0),
    ],
    "URAT": [("Asam urat", "mg/dL", "angka", (3.4, 7.0), (2.4, 5.7), (N, N), N, N, 1)],
    "ELEK": [
        ("Natrium", "mmol/L", "angka", (135, 145), (135, 145), (120, 160), N, N, 0),
        ("Kalium", "mmol/L", "angka", (3.5, 5.0), (3.5, 5.0), (2.5, 6.5), N, N, 1),
        ("Klorida", "mmol/L", "angka", (98, 107), (98, 107), (N, N), N, N, 0),
    ],
    "UL": [
        ("Warna", "", "pilihan", (N, N), (N, N), (N, N), "Kuning muda|Kuning|Kuning tua|Merah|Coklat", "Kuning", 0),
        ("Kejernihan", "", "pilihan", (N, N), (N, N), (N, N), "Jernih|Agak keruh|Keruh", "Jernih", 0),
        ("pH", "", "angka", (4.5, 8.0), (4.5, 8.0), (N, N), N, N, 1),
        ("Berat jenis", "", "angka", (1.003, 1.030), (1.003, 1.030), (N, N), N, N, 3),
        ("Protein", "", "pilihan", (N, N), (N, N), (N, N), NEG, "Negatif", 0),
        ("Glukosa", "", "pilihan", (N, N), (N, N), (N, N), NEG, "Negatif", 0),
        ("Keton", "", "pilihan", (N, N), (N, N), (N, N), NEG, "Negatif", 0),
        ("Leukosit sedimen", "/LPB", "angka", (0, 5), (0, 5), (N, N), N, N, 0),
        ("Eritrosit sedimen", "/LPB", "angka", (0, 2), (0, 2), (N, N), N, N, 0),
    ],
}

NAMA = [
    ("Budi Santoso", "L"), ("Siti Rahmawati", "P"), ("Agus Prasetyo", "L"), ("Dewi Lestari", "P"),
    ("Hendra Wijaya", "L"), ("Ratna Sari", "P"), ("Eko Nugroho", "L"), ("Nur Aini", "P"),
    ("Fajar Ramadhan", "L"), ("Wulandari", "P"), ("Yusuf Hidayat", "L"), ("Putri Maharani", "P"),
    ("Bambang Sutrisno", "L"), ("Lilis Suryani", "P"), ("Rizky Pratama", "L"), ("Anisa Fitri", "P"),
    ("Dimas Anggara", "L"), ("Maya Kusumawati", "P"), ("Teguh Santosa", "L"), ("Sri Wahyuni", "P"),
    ("Andika Putra", "L"), ("Indah Permata", "P"), ("Joko Widodo Kurniawan", "L"), ("Mega Puspita", "P"),
    ("Rudi Hermawan", "L"), ("Kartika Dewi", "P"), ("Samsul Arifin", "L"), ("Fitriani", "P"),
    ("Galih Saputra", "L"), ("Tri Handayani", "P"),
]
ALAMAT = ["Keputih, Surabaya", "Gubeng, Surabaya", "Rungkut, Surabaya", "Sukolilo, Surabaya",
          "Wonokromo, Surabaya", "Tegalsari, Surabaya", "Waru, Sidoarjo", "Gresik Kota"]
DOKTER = [
    ("dr. Andi Wijaya, Sp.PD", "Penyakit Dalam"), ("dr. Sari Lestari, Sp.A", "Anak"),
    ("dr. Rahmat Hidayat, Sp.JP", "Jantung"), ("dr. Linda Kartika, Sp.OG", "Kandungan"),
    ("dr. Bagus Setiawan", "Umum / IGD"),
]


def _fmt(v, p_desimal):
    return str(int(v)) if v == int(v) else repr(round(v, p_desimal))


def _gen_value(p, jk, rng, abnormal):
    """Bangkitkan nilai hasil realistis (dict param -> teks nilai)."""
    if p["tipe"] == "pilihan":
        opts = p["pilihan"].split("|")
        if abnormal:
            return rng.choice([o for o in opts if o != p["nilai_normal"]])
        return p["nilai_normal"]
    lo, hi = (p["ref_min_p"], p["ref_max_p"]) if jk == "P" else (p["ref_min_l"], p["ref_max_l"])
    lo_ = lo if lo is not None else (hi * 0.5)
    hi_ = hi if hi is not None else (lo * 1.6)
    span = hi_ - lo_
    if abnormal:
        go_high = lo is None or (hi is not None and rng.random() < 0.7)
        v = hi_ + span * rng.uniform(0.05, 0.5) if go_high else lo_ - span * rng.uniform(0.05, 0.4)
    else:
        v = rng.uniform(lo_ + span * 0.1, hi_ - span * 0.1)
    d = p["desimal"]
    v = round(v, d)
    return _fmt(max(v, 0), d)


def seed_all(conn):
    rng = random.Random(2026)

    # --- pengguna ---------------------------------------------------------
    users = [
        ("admin", "admin123", "Administrator Lab", "admin"),
        ("analis", "analis123", "Rina Analis Kesehatan", "analis"),
        ("analis2", "analis123", "Doni Analis Kesehatan", "analis"),
        ("dokter", "dokter123", "dr. Maya Kusuma, Sp.PK", "dokter"),
    ]
    for u, pw, nama, role in users:
        conn.execute("INSERT INTO user(username,password_hash,nama,role) VALUES (?,?,?,?)",
                     (u, generate_password_hash(pw), nama, role))
    analis_ids, dokter_user = [2, 3], 4

    # --- dokter pengirim ----------------------------------------------------
    for nama, sp in DOKTER:
        conn.execute("INSERT INTO doctor(nama,spesialis) VALUES (?,?)", (nama, sp))

    # --- katalog pemeriksaan -------------------------------------------------
    for kode, nama, kat, smp, tarif in TESTS:
        tid = conn.execute("INSERT INTO lab_test(kode,nama,kategori,jenis_sampel,tarif) VALUES (?,?,?,?,?)",
                           (kode, nama, kat, smp, tarif)).lastrowid
        for i, (pn, sat, tipe, rl, rp, kr, pil, nrm, dec) in enumerate(PARAMS[kode], 1):
            conn.execute(
                """INSERT INTO test_parameter(test_id,nama,satuan,tipe,ref_min_l,ref_max_l,ref_min_p,ref_max_p,
                   krit_min,krit_max,pilihan,nilai_normal,desimal,urutan) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (tid, pn, sat, tipe, rl[0], rl[1], rp[0], rp[1], kr[0], kr[1], pil, nrm, dec, i))

    # --- pasien ----------------------------------------------------------------
    today = date.today()
    for i, (nama, jk) in enumerate(NAMA):
        lahir = today - timedelta(days=rng.randint(20, 75) * 365 + rng.randint(0, 364))
        conn.execute("INSERT INTO patient(no_rm,nama,jenis_kelamin,tgl_lahir,alamat,no_hp) VALUES (?,?,?,?,?,?)",
                     (int_to_rm(1234 + i), nama, jk, lahir.isoformat(), rng.choice(ALAMAT),
                      "0812" + "".join(str(rng.randint(0, 9)) for _ in range(8))))
    # Budi (00-12-34) memakai data seperti contoh pada materi
    conn.execute("UPDATE patient SET nama='Budi S.', tgl_lahir=? WHERE no_rm='00-12-34'",
                 ((today - timedelta(days=45 * 365 + 90)).isoformat(),))

    tests = {r["kode"]: r for r in conn.execute("SELECT * FROM lab_test")}
    params = {}
    for r in conn.execute("SELECT * FROM test_parameter ORDER BY test_id, urutan"):
        params.setdefault(r["test_id"], []).append(r)
    patients = {r["id"]: r for r in conn.execute("SELECT * FROM patient")}
    doc_ids = [r["id"] for r in conn.execute("SELECT id FROM doctor")]

    def make_order(day, seq, pid, kodes, status, jam, prioritas="rutin", asal="Rawat Jalan",
                   catatan=None, fixed=None, lunas=None):
        dt = datetime.combine(day, datetime.min.time()) + timedelta(hours=jam[0], minutes=jam[1])
        no_order = f"LAB-{day:%Y%m%d}-{seq:03d}"
        barcode = f"L{day:%y%m%d}{seq:04d}"
        pt = patients[pid]
        total = sum(tests[k]["tarif"] for k in kodes)
        samp = ", ".join(sorted({tests[k]["jenis_sampel"] for k in kodes}))
        oid = conn.execute(
            """INSERT INTO lab_order(no_order,kode_antrian,patient_id,doctor_id,asal,prioritas,catatan_klinis,
               status,tgl_order) VALUES (?,?,?,?,?,?,?,?,?)""",
            (no_order, f"B-{seq:02d}", pid, rng.choice(doc_ids), asal, prioritas, catatan, "menunggu",
             dt.strftime("%Y-%m-%d %H:%M"))).lastrowid
        t = lambda m: (dt + timedelta(minutes=m)).strftime("%Y-%m-%d %H:%M")
        log_status(conn, oid, "menunggu", None, "Order masuk dari dokter", t(0))
        for k in kodes:
            conn.execute("INSERT INTO order_test(order_id,test_id,tarif) VALUES (?,?,?)",
                         (oid, tests[k]["id"], tests[k]["tarif"]))
        conn.execute("INSERT INTO billing(order_id,total,status) VALUES (?,?,'belum')", (oid, total))

        order = ["menunggu", "dipanggil", "sampel_diambil", "diperiksa", "selesai"]
        reach = order.index(status)
        analis = rng.choice(analis_ids)
        if reach >= 1:
            conn.execute("UPDATE lab_order SET status='dipanggil' WHERE id=?", (oid,))
            log_status(conn, oid, "dipanggil", analis, "Pasien dipanggil ke lab", t(8))
        if reach >= 2:
            conn.execute("""UPDATE lab_order SET status='sampel_diambil', waktu_sampel=?, jenis_sampel=?,
                            petugas_sampel=?, barcode=? WHERE id=?""", (t(15), samp, analis, barcode, oid))
            log_status(conn, oid, "sampel_diambil", analis, f"Sampel diambil, barcode {barcode}", t(15))
        if reach >= 3:
            for k in kodes:
                for p in params[tests[k]["id"]]:
                    if fixed and p["nama"] in fixed:
                        val, src = fixed[p["nama"]], "alat"
                    else:
                        val, src = _gen_value(p, pt["jenis_kelamin"], rng, rng.random() < 0.18), \
                                   rng.choice(["manual", "alat"])
                    flag, val = evaluate(p, val, pt["jenis_kelamin"])
                    conn.execute(
                        """INSERT INTO order_result(order_id,parameter_id,nilai,flag,rujukan_teks,sumber)
                           VALUES (?,?,?,?,?,?)""",
                        (oid, p["id"], val, flag, ref_text(p, pt["jenis_kelamin"]), src))
            conn.execute("UPDATE lab_order SET status='diperiksa', waktu_hasil=?, petugas_hasil=? WHERE id=?",
                         (t(55), analis, oid))
            log_status(conn, oid, "diperiksa", analis, "Hasil diinput", t(55))
        if reach >= 4:
            conn.execute("""UPDATE lab_order SET status='selesai', waktu_validasi=?, validator_id=? WHERE id=?""",
                         (t(rng.randint(70, 130)), dokter_user, oid))
            log_status(conn, oid, "selesai", dokter_user, "Divalidasi, hasil terkirim ke dokter", t(90))
        if lunas is None:
            lunas = reach >= 4 and rng.random() < 0.85
        if lunas:
            conn.execute("UPDATE billing SET status='lunas', dibayar_at=?, metode=? WHERE order_id=?",
                         (t(100), rng.choice(["Tunai", "QRIS", "Transfer", "BPJS", "Asuransi"]), oid))
        return oid

    paket = [["DL"], ["GDS"], ["UL"], ["DL", "GDS"], ["LIP"], ["GIN"], ["HAT"], ["URAT"],
             ["HBA1C"], ["ELEK"], ["DL", "GIN"], ["LIP", "GDP"], ["GDP", "HBA1C"], ["DL", "UL"]]
    catatan = ["Kontrol rutin DM", "Demam 3 hari", "Pra operasi", "Medical check up", "Nyeri sendi",
               "Evaluasi fungsi ginjal", "Hipertensi", None, None]
    pids = list(patients)

    # 14 hari ke belakang: semua selesai
    for back in range(14, 0, -1):
        day = today - timedelta(days=back)
        for seq in range(1, rng.randint(5, 11) + 1):
            make_order(day, seq, rng.choice(pids), rng.choice(paket), "selesai",
                       (7 + seq // 2, rng.randint(0, 59)), catatan=rng.choice(catatan),
                       asal=rng.choice(["Rawat Jalan"] * 3 + ["IGD", "Rawat Inap"]),
                       prioritas="cito" if rng.random() < 0.1 else "rutin")

    # Hari ini: antrian sesuai gambar di materi (B-05 Budi, B-07 GDS, B-09 Urin lengkap)
    budi = conn.execute("SELECT id FROM patient WHERE no_rm='00-12-34'").fetchone()["id"]
    others = [p for p in pids if p != budi]
    plan = [
        (1, rng.choice(others), ["DL"], "selesai"),
        (2, rng.choice(others), ["LIP"], "selesai"),
        (3, rng.choice(others), ["GIN"], "diperiksa"),
        (4, rng.choice(others), ["HBA1C"], "sampel_diambil"),
        (5, budi, ["DL", "GDS"], "diperiksa"),
        (6, rng.choice(others), ["ELEK"], "dipanggil"),
        (7, rng.choice(others), ["GDS"], "menunggu"),
        (8, rng.choice(others), ["HAT", "URAT"], "menunggu"),
        (9, rng.choice(others), ["UL"], "menunggu"),
        (10, rng.choice(others), ["DL", "GDS"], "menunggu"),
    ]
    for seq, pid, kodes, st in plan:
        fixed = {"Hemoglobin": "13.5", "Leukosit": "7800", "Trombosit": "250000", "Hematokrit": "41",
                 "Gula darah sewaktu": "210"} if pid == budi else None
        make_order(today, seq, pid, kodes, st, (7, 30 + seq * 4), fixed=fixed,
                   prioritas="cito" if seq == 10 else "rutin",
                   asal="IGD" if seq == 10 else "Rawat Jalan",
                   catatan="Kontrol rutin DM" if pid == budi else rng.choice(catatan), lunas=False)
