"""Antarmuka baris perintah sidik-jari."""
from __future__ import annotations

import argparse
import json
import sys

from sidik_jari import VERSI
from sidik_jari.inti import (
    FORMAT_JSON,
    Galat,
    ambil_git,
    ambil_url,
    cocokkan,
    kumpulkan_file,
    tulis_json,
    waktu_sekarang,
)


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sidik-jari",
        description="Buktikan bahwa yang diuji/di-deploy memang build terbaru.",
    )
    sub = p.add_subparsers(dest="perintah", required=True)

    b = sub.add_parser("buat", help="kumpulkan sidik jari file/git/URL")
    b.add_argument("file", nargs="*", default=[], metavar="FILE",
                   help="file yang dihitung sha256-nya")
    b.add_argument("-p", "--penanda", action="append", default=[], metavar="PENANDA",
                   help="teks yang dicari di file (boleh dipakai berulang)")
    b.add_argument("--git", metavar="DIR",
                   help="rekam kondisi repo git (commit, branch, bersih/kotor)")
    b.add_argument("--url", metavar="URL",
                   help="rekam kondisi sebuah URL (status, sha256 body, header)")
    b.add_argument("--cari-di-url", action="append", default=[], metavar="TEKS",
                   help="teks yang dicari di body URL; @commit = 12 hex commit dari --git")
    b.add_argument("-o", "--keluaran", metavar="FILE",
                   help="simpan laporan JSON ke FILE (ditulis atomik)")
    b.add_argument("--json", action="store_true",
                   help="cetak laporan sebagai JSON ke stdout")

    c = sub.add_parser("cocokkan", help="hitung ulang dari isi sidik.json dan bandingkan")
    c.add_argument("sidik", metavar="SIDIK_JSON", help="file sidik jari hasil buat")
    c.add_argument("--tanpa-url", action="store_true",
                   help="jangan periksa bagian URL")

    sub.add_parser("versi", help="cetak versi")
    return p


def _buat(argumen) -> dict:
    if argumen.cari_di_url and not argumen.url:
        raise Galat("--cari-di-url butuh --url")
    daftar_file = kumpulkan_file(argumen.file, argumen.penanda)
    data_git = ambil_git(argumen.git) if argumen.git else None
    data_url = None
    if argumen.url:
        data_url = ambil_url(
            argumen.url,
            argumen.cari_di_url,
            data_git["commit_12"] if data_git else None,
        )
    return {
        "format": FORMAT_JSON,
        "dibuat": waktu_sekarang(),
        "file": daftar_file,
        "git": data_git,
        "url": data_url,
    }


def _cetak_teks(data: dict) -> None:
    print(f"sidik-jari {VERSI} — laporan buat ({data['dibuat']})")
    for entri in data["file"]:
        print(f"  FILE {entri['path']}")
        print(f"    ukuran {entri['ukuran']} byte, sha256 {entri['sha256']}, "
              f"sha256_16 {entri['sha256_16']}")
        for p in entri["penanda"]:
            if p["ditemukan"]:
                print(f"    penanda {p['penanda']!r}: ditemukan "
                      f"({p['jumlah']}x, offset pertama {p['offset_pertama']})")
            else:
                print(f"    penanda {p['penanda']!r}: tidak ditemukan")
    g = data["git"]
    if g:
        status = "bersih" if g["bersih"] else "kotor"
        print(f"  GIT {g['dir']}: branch {g['branch']}, commit {g['commit']}, "
              f"{status}, {g['jumlah_file_berubah']} file berubah")
    u = data["url"]
    if u:
        print(f"  URL {u['url']}: status {u['status']}, ukuran {u['ukuran']} byte, "
              f"sha256 {u['sha256']}")
        if u["etag"]:
            print(f"    ETag {u['etag']}")
        if u["last_modified"]:
            print(f"    Last-Modified {u['last_modified']}")
        if u["x_vercel_id"]:
            print(f"    X-Vercel-Id {u['x_vercel_id']}")
        for c in u["cari"]:
            print(f"    cari {c['teks']!r}: {'ada' if c['ada'] else 'tidak ada'}")


def main(argv=None) -> int:
    argumen = _parser().parse_args(argv)
    try:
        if argumen.perintah == "versi":
            print(f"sidik-jari {VERSI}")
            return 0
        if argumen.perintah == "buat":
            data = _buat(argumen)
            if argumen.json:
                print(json.dumps(data, ensure_ascii=False, indent=2))
            else:
                _cetak_teks(data)
            if argumen.keluaran:
                tulis_json(argumen.keluaran, data)
                aliran = sys.stderr if argumen.json else sys.stdout
                print(f"disimpan: {argumen.keluaran}", file=aliran)
            return 0
        if argumen.perintah == "cocokkan":
            kode, baris = cocokkan(argumen.sidik, tanpa_url=argumen.tanpa_url)
            for satu in baris:
                print(satu)
            return kode
    except (Galat, OSError) as e:
        print(f"galat: {e}", file=sys.stderr)
        return 2
    return 1  # tidak seharusnya sampai sini
