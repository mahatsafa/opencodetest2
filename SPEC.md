# sidik-jari — spesifikasi v0.1.0

CLI untuk membuktikan bahwa yang diuji/di-deploy memang build terbaru ("sidik jari").
Aturan asal: binary/OS = sha256 + string penanda di binary; web = hash commit + URL deploy.

## Batasan
- Python >= 3.11, HANYA standard library (hashlib, json, argparse, subprocess, urllib.request, http.server untuk uji, unittest).
- Paket `sidik_jari/`, jalankan `python3 -m sidik_jari`. Pesan CLI Bahasa Indonesia.
- Batas tertulis (konstanta) dan gagal tertutup bila dilewati:
  MAKS_FILE = 100 file per perintah, MAKS_PENANDA = 20, panjang penanda 1..256 byte,
  BACA_POTONG = 1 MiB (file dibaca bertahap, tidak pernah utuh di memori),
  MAKS_BODY_URL = 5 MiB (lebih -> error "body terlalu besar"), WAKTU_URL = 15 dtk,
  hanya skema http/https (lainnya ditolak).

## Perintah
1. `buat [FILE ...] [-p PENANDA ...] [--git DIR] [--url URL] [--cari-di-url TEKS ...] [-o sidik.json] [--json]`
   - Per file: path (absolut), ukuran, sha256 penuh, sha256_16 (16 hex pertama), untuk tiap penanda: ditemukan (bool),
     jumlah kemunculan, offset pertama. Pencarian penanda bertahap dengan overlap (len(penanda)-1) supaya penanda
     yang melintasi batas potongan tetap ketemu (WAJIB diuji).
   - `--git DIR`: commit HEAD (penuh + 12 hex), branch, bersih (git status --porcelain kosong), jumlah file berubah.
     Bukan repo git -> error jelas.
   - `--url URL`: status HTTP, sha256 body, ukuran, header ETag/Last-Modified/X-Vercel-Id bila ada.
     `--cari-di-url TEKS`: apakah TEKS ada di body. Nilai khusus `@commit` = hash commit 12 hex dari --git
     (berguna untuk halaman yang menampilkan versi/commit).
   - Cetak laporan teks ringkas; `--json` cetak JSON; `-o` simpan JSON (tulis atomik: file sementara lalu rename).
2. `cocokkan sidik.json [--tanpa-url]` -> hitung ulang semua dari isi JSON (file, penanda, git, url) dan bandingkan.
   Cetak tabel per butir: SAMA / BEDA (lama -> baru) / HILANG. Kode keluar 0 semua sama, 1 ada beda, 2 error input.
   JSON tidak valid / versi format tak dikenal -> 2.
3. `versi` -> cetak "sidik-jari 0.1.0".

## Format JSON
{"format": 1, "dibuat": ISO8601 UTC, "file": [...], "git": {...}|null, "url": {...}|null}

## Uji (unittest, `python3 -m unittest discover -s tests -v`)
- sha256 cocok hashlib untuk file kecil dan file > 3 MiB.
- penanda di tengah, di awal, di akhir, melintasi batas 1 MiB, tidak ada, berulang (jumlah benar).
- batas: >MAKS_FILE, penanda kosong/terlalu panjang, skema file:// ditolak, body > MAKS_BODY_URL ditolak (server lokal http.server di thread).
- git: repo sementara (git init, commit dengan user.name/email lokal di repo uji), bersih vs kotor, bukan repo.
- url: server lokal, sha256 body, --cari-di-url, @commit.
- cocokkan: semua sama -> 0; file diubah -> 1 dengan BEDA; file dihapus -> HILANG; JSON rusak -> 2.
- tulis atomik -o.

## Lainnya
README.md (Indonesia): tujuan, contoh untuk ISO OS (`buat bmahos.iso -p "bmahOS v0.9" -o sidik.json`),
untuk web (`buat --git . --url https://contoh.vercel.app --cari-di-url @commit`), alur cocokkan. LICENSE MIT (mahatsafa).
.gitignore: __pycache__/, *.pyc.
