-- Indeks untuk query yang sering dipakai tapi belum punya indeks di schema.sql.

-- Ambil parameter per jenis pemeriksaan, urut sesuai tampilan
-- (halaman order baru, input hasil, cetak hasil, master pemeriksaan).
CREATE INDEX IF NOT EXISTS idx_param_test ON test_parameter(test_id, urutan);

-- Cek apakah sebuah parameter sudah punya hasil sebelum boleh dihapus (master pemeriksaan).
CREATE INDEX IF NOT EXISTS idx_result_param ON order_result(parameter_id);
