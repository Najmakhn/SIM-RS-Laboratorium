"""Logika bisnis laboratorium: nilai rujukan, flag otomatis, penomoran, status."""
from datetime import date, datetime

# ---- Alur 6 langkah (sesuai materi kuliah tamu) ---------------------------
STEPS = [
    (1, "Order lab masuk dari dokter"),
    (2, "Pasien dipanggil ke lab"),
    (3, "Cek identitas, ambil sampel"),
    (4, "Label sampel dengan barcode"),
    (5, "Periksa, input hasil per nilai"),
    (6, "Validasi, hasil terkirim ke dokter"),
]

STATUS = {
    "menunggu":       {"label": "Menunggu",       "badge": "st-wait", "step": 1},
    "dipanggil":      {"label": "Dipanggil",      "badge": "st-call", "step": 2},
    "sampel_diambil": {"label": "Sampel diambil", "badge": "st-samp", "step": 4},
    "diperiksa":      {"label": "Diperiksa",      "badge": "st-test", "step": 5},
    "selesai":        {"label": "Selesai",        "badge": "st-done", "step": 6},
    "batal":          {"label": "Batal",          "badge": "st-void", "step": 0},
}
ASAL = ["Rawat Jalan", "IGD", "Rawat Inap"]
METODE_BAYAR = ["Tunai", "QRIS", "Transfer", "BPJS", "Asuransi"]


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


# ---- Format angka gaya Indonesia (7.800 ; 13,5) ---------------------------
def fmt_num(v, dec=0):
    if v is None or v == "":
        return "-"
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    s = f"{f:,.{dec}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_rp(v):
    return "Rp " + fmt_num(v or 0, 0)


def parse_num(text):
    """'13,5' / '13.5' -> 13.5 ; raise ValueError bila bukan angka."""
    t = str(text).strip().replace(" ", "").replace(",", ".")
    if t == "":
        raise ValueError("kosong")
    return float(t)


def age_of(tgl_lahir, today=None):
    today = today or date.today()
    y, m, d = map(int, tgl_lahir.split("-"))
    return today.year - y - ((today.month, today.day) < (m, d))


# ---- Nilai rujukan & flag --------------------------------------------------
def ref_range(p, jk):
    """Kembalikan (min, max) rujukan untuk jenis kelamin 'L'/'P'."""
    if jk == "P":
        lo, hi = p["ref_min_p"], p["ref_max_p"]
        if lo is None and hi is None:
            lo, hi = p["ref_min_l"], p["ref_max_l"]
    else:
        lo, hi = p["ref_min_l"], p["ref_max_l"]
        if lo is None and hi is None:
            lo, hi = p["ref_min_p"], p["ref_max_p"]
    return lo, hi


def ref_text(p, jk):
    if p["tipe"] == "pilihan":
        return p["nilai_normal"] or "-"
    lo, hi = ref_range(p, jk)
    d = p["desimal"]
    if lo is not None and hi is not None:
        return f"{fmt_num(lo, d)} – {fmt_num(hi, d)}"
    if hi is not None:
        return f"< {fmt_num(hi, d)}"
    if lo is not None:
        return f"> {fmt_num(lo, d)}"
    return "-"


def evaluate(p, nilai, jk):
    """Hitung flag otomatis. Return (flag, nilai_normalisasi).
    Flag: N normal, H/L tinggi/rendah, HH/LL kritis, A abnormal (kualitatif)."""
    if p["tipe"] == "pilihan":
        return ("N" if nilai == p["nilai_normal"] else "A"), nilai
    v = parse_num(nilai)
    lo, hi = ref_range(p, jk)
    if p["krit_min"] is not None and v < p["krit_min"]:
        flag = "LL"
    elif p["krit_max"] is not None and v > p["krit_max"]:
        flag = "HH"
    elif lo is not None and v < lo:
        flag = "L"
    elif hi is not None and v > hi:
        flag = "H"
    else:
        flag = "N"
    return flag, repr(v) if v != int(v) else str(int(v))


FLAG_META = {
    "N": ("–", "fl-n", "Normal"),
    "H": ("H", "fl-h", "Di atas rujukan"),
    "L": ("L", "fl-l", "Di bawah rujukan"),
    "HH": ("HH", "fl-c", "Kritis tinggi"),
    "LL": ("LL", "fl-c", "Kritis rendah"),
    "A": ("A", "fl-h", "Abnormal"),
}


# ---- Penomoran -------------------------------------------------------------
def rm_to_int(no_rm):
    return int(no_rm.replace("-", ""))


def int_to_rm(n):
    return f"{n // 10000:02d}-{(n // 100) % 100:02d}-{n % 100:02d}"


def next_no_rm(db):
    row = db.execute("SELECT no_rm FROM patient").fetchall()
    top = max((rm_to_int(r["no_rm"]) for r in row), default=1233)
    return int_to_rm(top + 1)


def next_order_numbers(db, day=None):
    """(no_order, kode_antrian, barcode) berikutnya untuk tanggal `day`."""
    day = day or date.today()
    prefix = day.strftime("%Y-%m-%d")
    n = db.execute("SELECT COUNT(*) c FROM lab_order WHERE tgl_order LIKE ?",
                   (prefix + "%",)).fetchone()["c"] + 1
    while True:
        no_order = f"LAB-{day:%Y%m%d}-{n:03d}"
        if not db.execute("SELECT 1 FROM lab_order WHERE no_order=?", (no_order,)).fetchone():
            break
        n += 1
    return no_order, f"B-{n:02d}", f"L{day:%y%m%d}{n:04d}"


def log_status(db, order_id, status, user_id=None, ket=None, waktu=None):
    db.execute(
        "INSERT INTO status_log(order_id,status,waktu,user_id,keterangan) VALUES (?,?,?,?,?)",
        (order_id, status, waktu or now_str(), user_id, ket),
    )


# ---- Tanggal berbahasa Indonesia -----------------------------------------
BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
BULAN_PANJANG = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus",
                 "September", "Oktober", "November", "Desember"]
HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]


def tgl_indo(d, panjang=False):
    if isinstance(d, str):
        d = datetime.strptime(d[:10], "%Y-%m-%d")
    nama = BULAN_PANJANG if panjang else BULAN
    return f"{d.day} {nama[d.month - 1]} {d.year}"


def hari_ini_indo():
    d = datetime.now()
    return f"{HARI[d.weekday()]}, {tgl_indo(d, True)}"
