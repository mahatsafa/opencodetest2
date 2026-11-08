"""Uji CLI `buat`: output JSON, batas-batas, dan galat wajar."""
import hashlib
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alat import jalankan_cli, tulis
from sidik_jari import inti


class UjiCliDasar(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.dasar = self.folder.name

    def test_versi(self):
        hasil = jalankan_cli("versi")
        self.assertEqual(hasil.returncode, 0)
        self.assertEqual(hasil.stdout.strip(), "sidik-jari 0.1.0")

    def test_buat_json_satu_file_satu_penanda(self):
        path = tulis(os.path.join(self.dasar, "data.bin"), b"halo SIDIK dunia")
        hasil = jalankan_cli("buat", path, "-p", "SIDIK", "--json")
        self.assertEqual(hasil.returncode, 0, hasil.stderr)
        data = __import__("json").loads(hasil.stdout)
        self.assertEqual(data["format"], 1)
        self.assertIn("dibuat", data)
        entri = data["file"][0]
        self.assertEqual(entri["path"], os.path.abspath(path))
        data_isi = b"halo SIDIK dunia"
        self.assertEqual(entri["ukuran"], len(data_isi))
        self.assertEqual(entri["sha256"], hashlib.sha256(b"halo SIDIK dunia").hexdigest())
        self.assertEqual(entri["sha256_16"], entri["sha256"][:16])
        p = entri["penanda"][0]
        self.assertEqual(p["penanda"], "SIDIK")
        self.assertTrue(p["ditemukan"])
        self.assertEqual(p["jumlah"], 1)
        self.assertEqual(p["offset_pertama"], 5)

    def test_buat_file_tidak_ada(self):
        hasil = jalankan_cli("buat", os.path.join(self.dasar, "hantu.bin"))
        self.assertEqual(hasil.returncode, 2)
        self.assertIn("galat", hasil.stderr.lower())


class UjiBatas(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.dasar = self.folder.name

    def test_lebih_dari_maks_file(self):
        # 101 file kecil
        path_list = []
        for i in range(inti.MAKS_FILE + 1):
            path_list.append(tulis(os.path.join(self.dasar, f"f{i:03}.bin"), b"x"))
        hasil = jalankan_cli("buat", *path_list)
        self.assertEqual(hasil.returncode, 2, hasil.stdout)
        self.assertIn(f"maks {inti.MAKS_FILE}", hasil.stderr)
        # pas di batas harus lulus
        hasil = jalankan_cli("buat", *path_list[: inti.MAKS_FILE], "--json")
        self.assertEqual(hasil.returncode, 0, hasil.stderr)

    def test_penanda_kosong(self):
        f = tulis(os.path.join(self.dasar, "a.bin"), b"isi")
        hasil = jalankan_cli("buat", f, "-p", "")
        self.assertEqual(hasil.returncode, 2)
        self.assertIn("panjang penanda", hasil.stderr)

    def test_penanda_terlalu_panjang(self):
        f = tulis(os.path.join(self.dasar, "a.bin"), b"isi")
        hasil = jalankan_cli("buat", f, "-p", "x" * 257)
        self.assertEqual(hasil.returncode, 2)
        self.assertIn("panjang penanda", hasil.stderr)
        # 256 byte masih sah
        hasil = jalankan_cli("buat", f, "-p", "x" * 256, "--json")
        self.assertEqual(hasil.returncode, 0, hasil.stderr)

    def test_kebanyakan_penanda(self):
        f = tulis(os.path.join(self.dasar, "a.bin"), b"isi")
        argumen = []
        for i in range(inti.MAKS_PENANDA + 1):
            argumen += ["-p", f"p{i}"]
        hasil = jalankan_cli("buat", f, *argumen)
        self.assertEqual(hasil.returncode, 2)
        self.assertIn(f"maks {inti.MAKS_PENANDA}", hasil.stderr)

    def test_skema_file_ditolak(self):
        f = tulis(os.path.join(self.dasar, "a.bin"), b"isi")
        url = f"file://{os.path.abspath(f)}"
        hasil = jalankan_cli("buat", "--url", url)
        self.assertEqual(hasil.returncode, 2)
        self.assertIn("hanya http/https", hasil.stderr)


if __name__ == "__main__":
    unittest.main()
