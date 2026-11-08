# sidik-jari

CLI untuk membuktikan bahwa yang diuji/di-deploy memang build terbaru ("sidik jari").

Masalah yang diselesaikan saat build/deploy:

- Kamu menguji binary/ISO, lalu deploy — tapi yang ter-deploy versi lama?
- Web sudah deploy? URL yang dibuka memang build dari commit terbaru?

sidik-jari merekam keadaan (sha256 file, penanda versi di dalam file, kondisi
repo git, isi sebuah URL) ke satu file `sidik.json`, lalu nanti bisa
dipanggil ulang untuk membandingkan: sudah benar/beda/hilang.

Python 3.11+, hanya standard library.

## Perintah

```
python3 -m sidik_jari <perintah> [opsi]
```

Perintah: `buat`, `cocokkan`, `versi`.

### buat

```
buat [FILE ...] [-p PENANDA ...] [--git DIR] [--url URL] [--cari-di-url TEKS ...] [-o sidik.json] [--json]
```

- Per file: path absolut, ukuran, sha256 penuh, sha256_16 (16 hex pertama),
  dan untuk tiap penanda: ditemukan (bool), jumlah kemunculan, offset pertama.
  Penanda dicari dengan overlap sehingga yang melintasi batas potongan 1 MiB tetap ketemu.
- `--git DIR`: commit HEAD (penuh + 12 hex), branch, bersih (status kotor atau tidak),
  jumlah file berubah. Bukan repo git -> error jelas.
- `--url URL`: status HTTP, sha256 + ukuran body, header ETag/Last-Modified/X-Vercel-Id bila ada.
- `--cari-di-url TEKS`: apakah TEKS ada di body URL. Nilai khusus `@commit` =
  12 hex commit dari `--git` (buat halaman yang menampilkan versi/commit).
- `--json`: cetak laporan JSON ke stdout. `-o FILE`: simpan JSON ke FILE
  (ditulis atomik: file sementara lalu rename).

Contoh untuk ISO OS:

```
python3 -m sidik_jari buat bmahos.iso -p "bmahOS v0.9" -o sidik.json
```

Contoh untuk web (deploy Vercel dsb.):

```
python3 -m sidik_jari buat --git . --url https://contoh.vercel.app --cari-di-url @commit -o sidik.json
```

### cocokkan

```
cocokkan sidik.json [--tanpa-url]
```

Hitung ulang semua dari isi JSON (file, penanda, git, url) dan bandingkan dengan
keadaan sekarang. Cetak per butir: `SAMA` / `BEDA (lama -> baru)` / `HILANG`.

Alur kerja:

1. Sebelum deploy/tearing: `buat ... -o sidik.json`
2. Setelah deploy (atau nanti): `cocokkan sidik.json`
3. Semua `SAMA` (kode keluar 0) = yang ada di lapangan memang build terbaru.

Kode keluar `cocokkan`: `0` semua sama, `1` ada beda/hilang, `2` error input
(JSON rusak, versi format tak dikenal).

`--tanpa-url` mematikan pemeriksaan bagian URL (berguna saat offline).

### versi

```
python3 -m sidik_jari versi
```

Cetak `sidik-jari 0.1.1`.

## Format JSON

```json
{"format": 1, "dibuat": "2026-11-08T09:15:00+00:00", "file": [...], "git": {...}|null, "url": {...}|null}
```

## Batas tertulis (gagal tertutup bila dilewati)

| Konstanta | Nilai | Arti |
|---|---|---|
| `MAKS_FILE` | 100 | file per perintah |
| `MAKS_PENANDA` | 20 | penanda per perintah |
| panjang penanda | 1..256 byte | |
| `BACA_POTONG` | 1 MiB | file dibaca bertahap, tidak pernah utuh di memori |
| `MAKS_BODY_URL` | 5 MiB | body URL lebih besar -> error "body terlalu besar" |
| `WAKTU_URL` | 15 dtk | timeout request URL |
| skema URL | http/https | skema lain (mis. `file://`) ditolak |

## Uji

```
python3 -m unittest discover -s tests -v
```

## LICENSE

MIT — lihat [LICENSE](LICENSE).
