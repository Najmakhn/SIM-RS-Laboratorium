PAKET DEMO SIMRS UNTUK GITHUB PAGES

1. Ekstrak ZIP ini di komputer.
2. Upload SELURUH ISI folder SIMRS-GitHub-Pages ke ROOT repository GitHub (branch main).
   Pastikan index.html berada sejajar dengan README.md, bukan di dalam subfolder.
3. Di GitHub: Settings > Pages > Build and deployment.
   Source: Deploy from a branch
   Branch: main
   Folder: / (root)
   Klik Save.
4. Tunggu deployment selesai, lalu buka:
   https://najmakhn.github.io/SIM-RS-Laboratorium/

Catatan:
- Ini adalah frontend demo interaktif, bukan backend Flask.
- Form order, tombol status, pencarian, dan tabel demo berjalan di browser.
- Data yang ditambahkan disimpan di localStorage browser yang sama.
- run.py, app/, schema.sql, dan file proyek asli tidak perlu dihapus.
- File demo tidak memerlukan PythonAnywhere atau Render.
