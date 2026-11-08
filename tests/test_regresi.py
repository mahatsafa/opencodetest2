"""Uji regresi untuk 3 bug terbukti di inti.py.

1) kumpulkan_file: dengan 2 penanda pada file berisi keduanya, penanda kedua
   dilaporkan ditemukan=False. Sebab: f.seek(0) hanya sekali sebelum loop
   penanda; harus seek(0) sebelum SETIAP cari_penanda.

2) _cocokkan_url membandingkan x_vercel_id. X-Vercel-Id berubah tiap request
   sehingga URL Vercel selalu BEDA. Perbaikan: hapus x_vercel_id dari daftar
   bidang yang dibandingkan (tetap direkam sebagai info).

3) cocokkan(): validasi isi JSON dari luar sebelum dipakai: jumlah file >
   MAKS_FILE -> Galat; tiap entri: jumlah penanda > MAKS_PENANDA atau panjang
   penanda di luar 1..256 byte -> Galat (pakai ulang validasi_penanda).
"""
import hashlib
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sidik_jari import inti
from alat import ServerUji, jalankan_cli, tulis


class UjiRegresiKumpulkanFileSeek(unittest.TestCase):
    """Bug 1: kumpulkan_file tidak seek(0) sebelum setiap cari_penanda."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.dasar = self.folder.name

    def test_dua_penanda_keduanya_ditemukan(self):
        """File berisi DUA penanda; keduanya harus ditemukan=True."""
        path = os.path.join(self.dasar, "dua.bin")
        # Penanda "PERTAMA" di offset 0, "KEDUA" di offset 20
        data = b"PERTAMA" + b"x" * 13 + b"KEDUA" + b"y" * 10
        with open(path, "wb") as f:
            f.write(data)

        hasil = inti.kumpulkan_file([path], ["PERTAMA", "KEDUA"])
        self.assertEqual(len(hasil), 1)
        penanda = hasil[0]["penanda"]

        p1 = penanda[0]
        self.assertEqual(p1["penanda"], "PERTAMA")
        self.assertTrue(p1["ditemukan"], "Penanda PERTAMA harus ditemukan")
        self.assertEqual(p1["jumlah"], 1)
        self.assertEqual(p1["offset_pertama"], 0)

        p2 = penanda[1]
        self.assertEqual(p2["penanda"], "KEDUA")
        self.assertTrue(p2["ditemukan"], "Penanda KEDUA harus ditemukan (bug: seek hilang)")
        self.assertEqual(p2["jumlah"], 1)
        self.assertEqual(p2["offset_pertama"], 20)


class UjiRegresiCocokkanUrlXVercelId(unittest.TestCase):
    """Bug 2: _cocokkan_url membandingkan x_vercel_id yang berubah tiap request."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.dasar = self.folder.name
        self.server = ServerUji()
        self.addCleanup(self.server.henti)

    def test_url_sama_tanpa_beda_x_vercel_id(self):
        """URL yang sama tidak boleh BEDA hanya karena x_vercel_id berubah."""
        # Request 1: simpan ke sidik.json dengan x_vercel_id pertama
        body1 = b"build 1"
        self.server.setel("/", body1, 200, {"X-Vercel-Id": "vercel-id-pertama"})
        path = os.path.join(self.dasar, "data.bin")
        tulis(path, b"isi file")

        hasil = jalankan_cli("buat", path, "--url", self.server.url("/"), "-o",
                           os.path.join(self.dasar, "sidik.json"))
        self.assertEqual(hasil.returncode, 0, hasil.stderr)

        # Request 2: server mengembalikan x_vercel_id YANG BEDA
        self.server.setel("/", body1, 200, {"X-Vercel-Id": "vercel-id-kedua"})

        # cocokkan tidak boleh melaporkan BEDA karena x_vercel_id
        hasil = jalankan_cli("cocokkan", os.path.join(self.dasar, "sidik.json"))
        self.assertEqual(hasil.returncode, 0, f"URL BEDA karena x_vercel_id: {hasil.stdout}")
        self.assertIn("SAMA", hasil.stdout)
        self.assertNotIn("BEDA", hasil.stdout)


class UjiRegresiCocokkanValidasiInput(unittest.TestCase):
    """Bug 3: cocokkan() tidak memvalidasi isi JSON dari luar."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.dasar = self.folder.name
        self.sidik = os.path.join(self.dasar, "sidik.json")

    def test_terlalu_banyak_file_lebih_dari_maks_file(self):
        """Jumlah file > MAKS_FILE -> Galat saat cocokkan."""
        path = os.path.join(self.dasar, "data.bin")
        tulis(path, b"isi")

        # Buat JSON dengan 101 entri file (MAKS_FILE = 100)
        data = {
            "format": inti.FORMAT_JSON,
            "dibuat": "2026-11-08T09:15:00+00:00",
            "file": [{"path": path, "ukuran": 3, "sha256": "a" * 64,
                      "sha256_16": "a" * 16, "penanda": []}
                     for _ in range(inti.MAKS_FILE + 1)],
            "git": None,
            "url": None,
        }
        with open(self.sidik, "w", encoding="utf-8") as f:
            json.dump(data, f)

        with self.assertRaises(inti.Galat) as cm:
            inti.cocokkan(self.sidik)
        self.assertIn("terlalu banyak file", str(cm.exception).lower())

    def test_penanda_lebih_dari_maks_penanda(self):
        """Jumlah penanda per file > MAKS_PENANDA -> Galat saat cocokkan."""
        path = os.path.join(self.dasar, "data.bin")
        tulis(path, b"isi")

        data = {
            "format": inti.FORMAT_JSON,
            "dibuat": "2026-11-08T09:15:00+00:00",
            "file": [{
                "path": path,
                "ukuran": 3,
                "sha256": "a" * 64,
                "sha256_16": "a" * 16,
                "penanda": [{"penanda": f"p{i}", "ditemukan": False,
                             "jumlah": 0, "offset_pertama": None}
                            for i in range(inti.MAKS_PENANDA + 1)],
            }],
            "git": None,
            "url": None,
        }
        with open(self.sidik, "w", encoding="utf-8") as f:
            json.dump(data, f)

        with self.assertRaises(inti.Galat) as cm:
            inti.cocokkan(self.sidik)
        self.assertIn("terlalu banyak penanda", str(cm.exception).lower())

    def test_panjang_penanda_kosong(self):
        """Panjang penanda 0 byte -> Galat saat cocokkan (pakai validasi_penanda)."""
        path = os.path.join(self.dasar, "data.bin")
        tulis(path, b"isi")

        data = {
            "format": inti.FORMAT_JSON,
            "dibuat": "2026-11-08T09:15:00+00:00",
            "file": [{
                "path": path,
                "ukuran": 3,
                "sha256": "a" * 64,
                "sha256_16": "a" * 16,
                "penanda": [{"penanda": "", "ditemukan": False,
                             "jumlah": 0, "offset_pertama": None}],
            }],
            "git": None,
            "url": None,
        }
        with open(self.sidik, "w", encoding="utf-8") as f:
            json.dump(data, f)

        with self.assertRaises(inti.Galat) as cm:
            inti.cocokkan(self.sidik)
        self.assertIn("panjang penanda", str(cm.exception).lower())

    def test_panjang_penanda_lebih_dari_maks(self):
        """Panjang penanda > 256 byte -> Galat saat cocokkan (pakai validasi_penanda)."""
        path = os.path.join(self.dasar, "data.bin")
        tulis(path, b"isi")

        data = {
            "format": inti.FORMAT_JSON,
            "dibuat": "2026-11-08T09:15:00+00:00",
            "file": [{
                "path": path,
                "ukuran": 3,
                "sha256": "a" * 64,
                "sha256_16": "a" * 16,
                "penanda": [{"penanda": "x" * 257, "ditemukan": False,
                             "jumlah": 0, "offset_pertama": None}],
            }],
            "git": None,
            "url": None,
        }
        with open(self.sidik, "w", encoding="utf-8") as f:
            json.dump(data, f)

        with self.assertRaises(inti.Galat) as cm:
            inti.cocokkan(self.sidik)
        self.assertIn("panjang penanda", str(cm.exception).lower())

    def test_panjang_penanda_valid_256_byte_lulus(self):
        """Panjang penanda 256 byte valid -> tidak error, cocokkan berjalan normal."""
        path = os.path.join(self.dasar, "data.bin")
        penanda_valid = "x" * 256
        data_isi = (penanda_valid + " tambahan").encode()
        tulis(path, data_isi)

        data = {
            "format": inti.FORMAT_JSON,
            "dibuat": "2026-11-08T09:15:00+00:00",
            "file": [{
                "path": path,
                "ukuran": len(data_isi),
                "sha256": hashlib.sha256(data_isi).hexdigest(),
                "sha256_16": hashlib.sha256(data_isi).hexdigest()[:16],
                "penanda": [{"penanda": penanda_valid, "ditemukan": True,
                             "jumlah": 1, "offset_pertama": 0}],
            }],
            "git": None,
            "url": None,
        }
        with open(self.sidik, "w", encoding="utf-8") as f:
            json.dump(data, f)

        kode, baris = inti.cocokkan(self.sidik)
        self.assertEqual(kode, 0, f"Harus lulus (kode 0) untuk penanda 256 byte: {baris}")


if __name__ == "__main__":
    unittest.main()

class UjiRegresiCocokkanBentukJson(unittest.TestCase):
    """Bentuk JSON salah (bukan list/dict) harus Galat, bukan crash."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.sidik = os.path.join(self.folder.name, "sidik.json")

    def _tulis(self, file_bagian):
        data = {"format": inti.FORMAT_JSON, "dibuat": "2026-11-08T09:15:00+00:00",
                "file": file_bagian, "git": None, "url": None}
        with open(self.sidik, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def test_file_bukan_list(self):
        self._tulis("bukan-list")
        with self.assertRaises(inti.Galat):
            inti.cocokkan(self.sidik)

    def test_penanda_bukan_dict(self):
        self._tulis([{"path": "/tidak/ada", "penanda": ["teks", "lagi"]}])
        with self.assertRaises(inti.Galat):
            inti.cocokkan(self.sidik)

    def test_penanda_bukan_list(self):
        self._tulis([{"path": "/tidak/ada", "penanda": "teks"}])
        with self.assertRaises(inti.Galat):
            inti.cocokkan(self.sidik)
