-- =====================================================================
-- SIMRS Modul Laboratorium  |  Skema database (SQLite)
-- Alur: Order masuk -> Dipanggil -> Ambil sampel -> Label barcode
--       -> Input hasil -> Validasi & kirim ke dokter
-- =====================================================================
PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS status_log;
DROP TABLE IF EXISTS billing_item;
DROP TABLE IF EXISTS billing;
DROP TABLE IF EXISTS order_result;
DROP TABLE IF EXISTS order_test;
DROP TABLE IF EXISTS lab_order;
DROP TABLE IF EXISTS test_parameter;
DROP TABLE IF EXISTS lab_test;
DROP TABLE IF EXISTS doctor;
DROP TABLE IF EXISTS patient;
DROP TABLE IF EXISTS user;

-- Pengguna sistem (peran: admin, analis, dokter)
CREATE TABLE user (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    nama          TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('admin','analis','dokter')),
    aktif         INTEGER NOT NULL DEFAULT 1
);

-- Pasien (No. RM format 00-12-34)
CREATE TABLE patient (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    no_rm          TEXT NOT NULL UNIQUE,
    nama           TEXT NOT NULL,
    jenis_kelamin  TEXT NOT NULL CHECK (jenis_kelamin IN ('L','P')),
    tgl_lahir      TEXT NOT NULL,            -- YYYY-MM-DD
    alamat         TEXT,
    no_hp          TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- Dokter pengirim order
CREATE TABLE doctor (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    nama       TEXT NOT NULL,
    spesialis  TEXT NOT NULL,
    aktif      INTEGER NOT NULL DEFAULT 1
);

-- Katalog jenis pemeriksaan (mis. Darah Lengkap, Gula Darah Sewaktu)
CREATE TABLE lab_test (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    kode          TEXT NOT NULL UNIQUE,
    nama          TEXT NOT NULL,
    kategori      TEXT NOT NULL,            -- Hematologi, Kimia Klinik, Urinalisis, ...
    jenis_sampel  TEXT NOT NULL,            -- Darah EDTA, Serum, Urin, ...
    tarif         INTEGER NOT NULL DEFAULT 0,
    aktif         INTEGER NOT NULL DEFAULT 1
);

-- Parameter per pemeriksaan beserta nilai rujukan
--   tipe 'angka'  : nilai numerik, dibandingkan dengan rujukan (L/P)
--   tipe 'pilihan': hasil teks, normal bila sama dengan nilai_normal
CREATE TABLE test_parameter (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    test_id      INTEGER NOT NULL REFERENCES lab_test(id) ON DELETE CASCADE,
    nama         TEXT NOT NULL,
    satuan       TEXT,
    tipe         TEXT NOT NULL DEFAULT 'angka' CHECK (tipe IN ('angka','pilihan')),
    ref_min_l    REAL,                      -- rujukan laki-laki
    ref_max_l    REAL,
    ref_min_p    REAL,                      -- rujukan perempuan
    ref_max_p    REAL,
    krit_min     REAL,                      -- nilai kritis bawah (opsional)
    krit_max     REAL,                      -- nilai kritis atas (opsional)
    pilihan      TEXT,                      -- daftar opsi dipisah '|', untuk tipe pilihan
    nilai_normal TEXT,                      -- opsi normal, untuk tipe pilihan
    desimal      INTEGER NOT NULL DEFAULT 1,
    urutan       INTEGER NOT NULL DEFAULT 0
);

-- Order laboratorium dari dokter
CREATE TABLE lab_order (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    no_order        TEXT NOT NULL UNIQUE,   -- LAB-YYYYMMDD-001
    kode_antrian    TEXT NOT NULL,          -- B-05
    patient_id      INTEGER NOT NULL REFERENCES patient(id),
    doctor_id       INTEGER NOT NULL REFERENCES doctor(id),
    asal            TEXT NOT NULL DEFAULT 'Rawat Jalan',   -- Rawat Jalan / IGD / Rawat Inap
    prioritas       TEXT NOT NULL DEFAULT 'rutin' CHECK (prioritas IN ('rutin','cito')),
    catatan_klinis  TEXT,
    status          TEXT NOT NULL DEFAULT 'menunggu'
                    CHECK (status IN ('menunggu','dipanggil','sampel_diambil','diperiksa','selesai','batal')),
    tgl_order       TEXT NOT NULL,          -- YYYY-MM-DD HH:MM
    -- langkah 3: ambil sampel
    waktu_sampel    TEXT,
    jenis_sampel    TEXT,
    petugas_sampel  INTEGER REFERENCES user(id),
    barcode         TEXT UNIQUE,            -- langkah 4
    -- langkah 5-6: hasil & validasi
    waktu_hasil     TEXT,
    petugas_hasil   INTEGER REFERENCES user(id),
    waktu_validasi  TEXT,
    validator_id    INTEGER REFERENCES user(id),
    catatan_hasil   TEXT
);
CREATE INDEX idx_order_status  ON lab_order(status);
CREATE INDEX idx_order_tgl     ON lab_order(tgl_order);
CREATE INDEX idx_order_patient ON lab_order(patient_id);

-- Pemeriksaan yang diminta dalam satu order
CREATE TABLE order_test (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id  INTEGER NOT NULL REFERENCES lab_order(id) ON DELETE CASCADE,
    test_id   INTEGER NOT NULL REFERENCES lab_test(id),
    tarif     INTEGER NOT NULL,             -- snapshot tarif saat order dibuat
    UNIQUE (order_id, test_id)
);

-- Hasil per parameter
CREATE TABLE order_result (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id      INTEGER NOT NULL REFERENCES lab_order(id) ON DELETE CASCADE,
    parameter_id  INTEGER NOT NULL REFERENCES test_parameter(id),
    nilai         TEXT,
    flag          TEXT NOT NULL DEFAULT 'N' CHECK (flag IN ('N','H','L','HH','LL','A')),
    rujukan_teks  TEXT,                     -- snapshot rujukan yang dipakai
    sumber        TEXT NOT NULL DEFAULT 'manual' CHECK (sumber IN ('manual','alat')),
    UNIQUE (order_id, parameter_id)
);

-- Tagihan otomatis dari tarif pemeriksaan (input billing)
CREATE TABLE billing (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id    INTEGER NOT NULL UNIQUE REFERENCES lab_order(id) ON DELETE CASCADE,
    total       INTEGER NOT NULL DEFAULT 0,
    status      TEXT NOT NULL DEFAULT 'belum' CHECK (status IN ('belum','lunas')),
    dibayar_at  TEXT,
    metode      TEXT
);

-- Jejak status order (audit trail)
CREATE TABLE status_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id  INTEGER NOT NULL REFERENCES lab_order(id) ON DELETE CASCADE,
    status    TEXT NOT NULL,
    waktu     TEXT NOT NULL,
    user_id   INTEGER REFERENCES user(id),
    keterangan TEXT
);
CREATE INDEX idx_log_order ON status_log(order_id);
