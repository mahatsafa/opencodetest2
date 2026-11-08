"""Inti perhitungan sidik-jari: berkas, penanda, git, URL, cocokkan.

Semua batas tertulis di sini. Fungsi gagal tertutup: bila batas dilewati,
lempar Galat yang pesannya tampil ke pengguna (kode keluar 2 dari CLI).
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

# ---- batas tertulis ----
MAKS_FILE = 100                    # jumlah file per perintah
MAKS_PENANDA = 20                  # jumlah penanda per perintah
PENANDA_MIN = 1                    # panjang penanda (byte)
PENANDA_MAKS = 256
BACA_POTONG = 1024 * 1024          # 1 MiB; file dibaca bertahap
MAKS_BODY_URL = 5 * 1024 * 1024    # body URL maksimal 5 MiB
WAKTU_URL = 15                     # detik

FORMAT_JSON = 1


class Galat(RuntimeError):
    """Galat yang wajar: pesannya tampil ke pengguna, kode keluar 2."""


def waktu_sekarang() -> str:
    """ISO8601 UTC, contoh 2026-11-08T09:15:00+00:00."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------- berkas & penanda ----------

def sha256_dan_ukuran(path: str) -> tuple[int, str]:
    """Kembalikan (ukuran byte, hex sha256). Berkas dibaca bertahap 1 MiB."""
    digest = hashlib.sha256()
    ukuran = 0
    with open(path, "rb") as f:
        while True:
            potong = f.read(BACA_POTONG)
            if not potong:
                break
            digest.update(potong)
            ukuran += len(potong)
    return ukuran, digest.hexdigest()


def cari_penanda(f, penanda: bytes) -> tuple[bool, int, int | None]:
    """Cari penanda (bytes) di objek berkas biner mulai posisi sekarang.

    Dibaca bertahap BACA_POTONG dengan overlap len(penanda)-1 sehingga
    penanda yang melintasi batas potongan tetap ketemu. Kemunculan yang
    tumpang tindih ikut dihitung.

    Kembalikan (ditemukan, jumlah, offset_pertama atau None).
    """
    if not penanda:
        raise Galat("penanda kosong")
    overlap = len(penanda) - 1
    jumlah = 0
    offset_pertama: int | None = None
    sisa = b""
    dasar = 0  # offset berkas dari potongan yang sedang diproses
    while True:
        potongan = f.read(BACA_POTONG)
        if not potongan:
            break
        data = sisa + potongan
        mulai = 0
        while True:
            i = data.find(penanda, mulai)
            if i == -1:
                break
            jumlah += 1
            if offset_pertama is None:
                offset_pertama = dasar - len(sisa) + i
            mulai = i + 1  # lanjut 1 byte agar tumpang tindih ikut terhitung
        sisa = data[-overlap:] if overlap else b""
        dasar += len(potongan)
    ditemukan = jumlah > 0
    return ditemukan, jumlah, offset_pertama


def validasi_penanda(daftar: list[str]) -> list[bytes]:
    """Cek jumlah dan panjang penanda, kembalikan versi bytes."""
    if len(daftar) > MAKS_PENANDA:
        raise Galat(f"terlalu banyak penanda (maks {MAKS_PENANDA})")
    hasil = []
    for teks in daftar:
        b = teks.encode("utf-8")
        if not PENANDA_MIN <= len(b) <= PENANDA_MAKS:
            raise Galat(
                f"panjang penanda harus {PENANDA_MIN}..{PENANDA_MAKS} byte "
                f"(penanda {teks[:32]!r}... {len(b)} byte)"
            )
        hasil.append(b)
    return hasil


def kumpulkan_file(path_list: list[str], penanda_list: list[str]) -> list[dict]:
    """Hitung sha256 + ukuran + hasil penanda untuk tiap file."""
    if len(path_list) > MAKS_FILE:
        raise Galat(f"terlalu banyak file (maks {MAKS_FILE})")
    penanda_bytes = validasi_penanda(penanda_list)
    hasil = []
    for path in path_list:
        absolut = os.path.abspath(path)
        try:
            with open(absolut, "rb") as f:
                ukuran, sha = sha256_dan_ukuran(absolut)
                daftar_penanda = []
                for teks, b in zip(penanda_list, penanda_bytes):
                    f.seek(0)
                    ditemukan, jumlah, offset = cari_penanda(f, b)
                    daftar_penanda.append({
                        "penanda": teks,
                        "ditemukan": ditemukan,
                        "jumlah": jumlah,
                        "offset_pertama": offset,
                    })
        except FileNotFoundError:
            raise Galat(f"file tidak ada: {path}")
        except IsADirectoryError:
            raise Galat(f"ini direktori, bukan file: {path}")
        hasil.append({
            "path": absolut,
            "ukuran": ukuran,
            "sha256": sha,
            "sha256_16": sha[:16],
            "penanda": daftar_penanda,
        })
    return hasil


# ---------- git ----------

def jalankan_git(dirpath: str, argumen: list[str]) -> str:
    try:
        hasil = subprocess.run(
            ["git", "-C", dirpath, *argumen],
            capture_output=True, text=True, timeout=WAKTU_URL,
        )
    except FileNotFoundError:
        raise Galat("perintah git tidak tersedia")
    except subprocess.TimeoutExpired:
        raise Galat(f"git timeout saat: {' '.join(argumen)}")
    if hasil.returncode != 0:
        stderr = (hasil.stderr or "").strip().lower()
        if "not a git repository" in stderr:
            raise Galat(f"bukan repo git: {dirpath}")
        baris = stderr.splitlines()
        detail = baris[0] if baris else f"git {' '.join(argumen)} gagal"
        raise Galat(f"git gagal di {dirpath}: {detail}")
    return hasil.stdout


def ambil_git(dirpath: str) -> dict:
    """Rekam kondisi repo git di DIR (HEAD, branch, status bersih/kotor)."""
    commit = jalankan_git(dirpath, ["rev-parse", "HEAD"]).strip()
    branch = jalankan_git(dirpath, ["rev-parse", "--abbrev-ref", "HEAD"]).strip()
    status = jalankan_git(dirpath, ["status", "--porcelain"])
    baris = [b for b in status.splitlines() if b.strip()]
    return {
        "dir": os.path.abspath(dirpath),
        "commit": commit,
        "commit_12": commit[:12],
        "branch": branch,
        "bersih": not baris,
        "jumlah_file_berubah": len(baris),
    }


# ---------- URL ----------

def ambil_url(url: str, cari_list: list[str], commit_12: str | None = None) -> dict:
    """Ambil URL, rekam status/sha256/header, cari teks di body.

    Body dibaca bertahap; bila total melewati MAKS_BODY_URL -> galat.
    Body disangga paling banyak MAKS_BODY_URL (batas tertulis).
    """
    skema = urllib.parse.urlsplit(url).scheme
    if skema not in ("http", "https"):
        raise Galat(f"skema '{skema or '(kosong)'}' tidak didukung (hanya http/https)")
    permintaan = urllib.request.Request(url, headers={"User-Agent": "sidik-jari/0.1.1"})
    try:
        resp = urllib.request.urlopen(permintaan, timeout=WAKTU_URL)
    except urllib.error.HTTPError as e:
        raise Galat(f"URL gagal: HTTP {e.code}")
    except (urllib.error.URLError, OSError) as e:
        raise Galat(f"URL gagal: {e}")
    try:
        with resp:
            status = resp.status
            etag = resp.headers.get("ETag")
            last_modified = resp.headers.get("Last-Modified")
            x_vercel_id = resp.headers.get("X-Vercel-Id")
            digest = hashlib.sha256()
            ukuran = 0
            potongan_list: list[bytes] = []
            try:
                while True:
                    potongan = resp.read(BACA_POTONG)
                    if not potongan:
                        break
                    ukuran += len(potongan)
                    if ukuran > MAKS_BODY_URL:
                        raise Galat(
                            f"body terlalu besar (maks {MAKS_BODY_URL} byte)"
                        )
                    digest.update(potongan)
                    potongan_list.append(potongan)
            except OSError as e:
                raise Galat(f"URL gagal saat membaca: {e}")
    except Galat:
        raise
    body = b"".join(potongan_list)
    sha = digest.hexdigest()
    hasil_cari = []
    for teks in cari_list:
        butuh = teks
        if teks == "@commit":
            if not commit_12:
                raise Galat("@commit butuh --git")
            butuh = commit_12
        jarum = butuh.encode("utf-8")
        hasil_cari.append({"teks": teks, "ada": jarum in body})
    return {
        "url": url,
        "status": status,
        "ukuran": ukuran,
        "sha256": sha,
        "sha256_16": sha[:16],
        "etag": etag,
        "last_modified": last_modified,
        "x_vercel_id": x_vercel_id,
        "cari": hasil_cari,
    }


# ---------- tulis JSON atomik ----------

def tulis_json(path: str, data: dict) -> None:
    """Tulis JSON secara atomik: file sementara di direktori sama, lalu rename."""
    direktori = os.path.dirname(os.path.abspath(path))
    sementara = os.path.join(
        direktori, f".{os.path.basename(path)}.tmp-{os.getpid()}"
    )
    try:
        with open(sementara, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(sementara, path)
    finally:
        if os.path.exists(sementara):
            os.remove(sementara)


# ---------- cocokkan ----------

def baca_sidik(path_json: str) -> dict:
    try:
        with open(path_json, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise Galat(f"JSON rusak: {e}")
    except UnicodeDecodeError:
        raise Galat("JSON rusak: bukan teks UTF-8")
    if not isinstance(data, dict) or data.get("format") != FORMAT_JSON:
        raise Galat("versi format tak dikenal (harus format 1)")
    return data


def _cocokkan_file(entri: dict, baris: list[str]) -> bool:
    path = entri.get("path")
    if not isinstance(path, str) or not os.path.isfile(path):
        baris.append(f"FILE {path}: HILANG")
        return False
    detail = []
    ukuran, sha = sha256_dan_ukuran(path)
    if entri.get("ukuran") != ukuran:
        detail.append(f"ukuran: {entri.get('ukuran')!r} -> {ukuran!r}")
    if entri.get("sha256") != sha:
        detail.append(f"sha256: {str(entri.get('sha256'))[:16]} -> {sha[:16]}")
    with open(path, "rb") as f:
        for plama in entri.get("penanda") or []:
            teks = str(plama.get("penanda", ""))
            ditemukan, jumlah, offset = cari_penanda(f, teks.encode("utf-8"))
            f.seek(0)
            if (plama.get("ditemukan"), plama.get("jumlah"),
                    plama.get("offset_pertama")) != (ditemukan, jumlah, offset):
                detail.append(
                    f"penanda {teks!r}: (ditemukan={plama.get('ditemukan')}, "
                    f"jumlah={plama.get('jumlah')}, "
                    f"offset={plama.get('offset_pertama')}) -> "
                    f"(ditemukan={ditemukan}, jumlah={jumlah}, offset={offset})"
                )
    if detail:
        baris.append(f"FILE {path}: BEDA ({'; '.join(detail)})")
        return False
    baris.append(f"FILE {path}: SAMA")
    return True


def _cocokkan_git(rekam: dict, baris: list[str]) -> bool:
    dir_git = str(rekam.get("dir", "."))
    try:
        baru = ambil_git(dir_git)
    except Galat as e:
        baris.append(f"GIT {dir_git}: BEDA (tidak terbaca: {e})")
        return False
    detail = []
    for bidang in ("commit", "branch", "bersih", "jumlah_file_berubah"):
        if rekam.get(bidang) != baru.get(bidang):
            detail.append(f"{bidang}: {rekam.get(bidang)!r} -> {baru.get(bidang)!r}")
    if detail:
        baris.append(f"GIT {dir_git}: BEDA ({'; '.join(detail)})")
        return False
    baris.append(f"GIT {dir_git}: SAMA")
    return True


def _cocokkan_url(rekam: dict, baris: list[str], commit_12: str | None) -> bool:
    url = rekam.get("url")
    teks_cari = [str(c.get("teks", "")) for c in (rekam.get("cari") or [])]
    try:
        baru = ambil_url(url, teks_cari, commit_12)
    except Galat as e:
        baris.append(f"URL {url}: BEDA (tidak terbaca: {e})")
        return False
    detail = []
    for bidang in ("status", "ukuran", "sha256", "etag", "last_modified"):
        if rekam.get(bidang) != baru.get(bidang):
            detail.append(f"{bidang}: {rekam.get(bidang)!r} -> {baru.get(bidang)!r}")
    lama_cari = {c.get("teks"): c for c in (rekam.get("cari") or [])}
    for hasil in baru["cari"]:
        lama = lama_cari.get(hasil["teks"])
        nilai_lama = lama.get("ada") if isinstance(lama, dict) else None
        if nilai_lama != hasil["ada"]:
            detail.append(f"cari {hasil['teks']!r}: {nilai_lama!r} -> {hasil['ada']!r}")
    if detail:
        baris.append(f"URL {url}: BEDA ({'; '.join(detail)})")
        return False
    baris.append(f"URL {url}: SAMA")
    return True


def cocokkan(path_json: str, tanpa_url: bool = False) -> tuple[int, list[str]]:
    """Hitung ulang semua dari isi sidik.json dan bandingkan.

    Kembalikan (kode_keluar, baris_laporan).
    Kode: 0 semua sama, 1 ada beda, 2 error input (lempar Galat).
    """
    data = baca_sidik(path_json)

    # Validasi input dari luar sebelum dipakai
    daftar_file = data.get("file") or []
    if not isinstance(daftar_file, list):
        raise Galat("bagian file salah bentuk (harus list)")
    if len(daftar_file) > MAKS_FILE:
        raise Galat(f"terlalu banyak file (maks {MAKS_FILE})")

    for entri in daftar_file:
        if not isinstance(entri, dict):
            raise Galat("entri file salah bentuk")
        daftar_penanda = entri.get("penanda") or []
        if not isinstance(daftar_penanda, list) or not all(
                isinstance(p, dict) for p in daftar_penanda):
            raise Galat("bagian penanda salah bentuk (harus list objek)")
        penanda_list = [str(p.get("penanda", "")) for p in daftar_penanda]
        if len(penanda_list) > MAKS_PENANDA:
            raise Galat(f"terlalu banyak penanda (maks {MAKS_PENANDA})")
        validasi_penanda(penanda_list)

    baris: list[str] = []
    sama_semua = True

    for entri in daftar_file:
        if not isinstance(entri, dict):
            raise Galat("entri file salah bentuk")
        if not _cocokkan_file(entri, baris):
            sama_semua = False

    rekam_git = data.get("git")
    if rekam_git is not None:
        if not isinstance(rekam_git, dict):
            raise Galat("bagian git salah bentuk")
        if not _cocokkan_git(rekam_git, baris):
            sama_semua = False

    rekam_url = data.get("url")
    if rekam_url is not None and not tanpa_url:
        if not isinstance(rekam_url, dict):
            raise Galat("bagian url salah bentuk")
        commit_12 = rekam_git.get("commit_12") if isinstance(rekam_git, dict) else None
        if not _cocokkan_url(rekam_url, baris, commit_12):
            sama_semua = False

    return (0 if sama_semua else 1), baris
