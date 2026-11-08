"""Uji `cocokkan`: semua sama (0), BEDA (1), HILANG (1), input rusak (2), --tanpa-url."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alat import ServerUji, jalankan_cli, tulis


class UjiCocokkan(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.dasar = self.folder.name
        self.data = os.path.join(self.dasar, "data.bin")
        self.sidik = os.path.join(self.dasar, "sidik.json")

    def test_semua_sama_kode_0(self):
        tulis(self.data, b"isi awal" * 10)
        hasil = jalankan_cli("buat", self.data, "-p", "isi", "-o", self.sidik)
        self.assertEqual(hasil.returncode, 0, hasil.stderr)
        hasil = jalankan_cli("cocokkan", self.sidik)
        self.assertEqual(hasil.returncode, 0, hasil.stderr)
        self.assertIn("SAMA", hasil.stdout)
        self.assertNotIn("BEDA", hasil.stdout)
        self.assertNotIn("HILANG", hasil.stdout)

    def test_file_diubah_kode_1_dengan_beda(self):
        tulis(self.data, b"isi awal" * 10)
        hasil = jalankan_cli("buat", self.data, "-o", self.sidik)
        self.assertEqual(hasil.returncode, 0, hasil.stderr)
        tulis(self.data, b"isi awal yang diubah" * 10)
        hasil = jalankan_cli("cocokkan", self.sidik)
        self.assertEqual(hasil.returncode, 1)
        self.assertIn("BEDA", hasil.stdout)
        self.assertIn("sha256", hasil.stdout)  # lama -> baru ikut tercetak

    def test_file_hilang_kode_1(self):
        tulis(self.data, b"isi awal")
        hasil = jalankan_cli("buat", self.data, "-o", self.sidik)
        self.assertEqual(hasil.returncode, 0, hasil.stderr)
        os.remove(self.data)
        hasil = jalankan_cli("cocokkan", self.sidik)
        self.assertEqual(hasil.returncode, 1)
        self.assertIn("HILANG", hasil.stdout)

    def test_json_rusak_kode_2(self):
        with open(self.sidik, "w", encoding="utf-8") as f:
            f.write("{ ini bukan json")
        hasil = jalankan_cli("cocokkan", self.sidik)
        self.assertEqual(hasil.returncode, 2)
        self.assertIn("JSON rusak", hasil.stderr)

    def test_format_tak_dikenal_kode_2(self):
        with open(self.sidik, "w", encoding="utf-8") as f:
            f.write(json.dumps({"format": 99, "file": []}))
        hasil = jalankan_cli("cocokkan", self.sidik)
        self.assertEqual(hasil.returncode, 2)
        self.assertIn("versi format tak dikenal", hasil.stderr)

    def test_json_bukan_objek_kode_2(self):
        with open(self.sidik, "w", encoding="utf-8") as f:
            f.write("[1, 2, 3]")
        hasil = jalankan_cli("cocokkan", self.sidik)
        self.assertEqual(hasil.returncode, 2)

    def test_sidik_tidak_ada_kode_2(self):
        hasil = jalankan_cli("cocokkan", os.path.join(self.dasar, "hantu.json"))
        self.assertEqual(hasil.returncode, 2)

    def test_url_sama_bed_dan_tanpa_url(self):
        server = ServerUji()
        self.addCleanup(server.henti)
        body = b"build 77"
        server.setel("/", body)
        tulis(self.data, b"isi")
        hasil = jalankan_cli(
            "buat", self.data, "--url", server.url("/"), "-o", self.sidik)
        self.assertEqual(hasil.returncode, 0, hasil.stderr)

        # URL masih sama -> 0
        hasil = jalankan_cli("cocokkan", self.sidik)
        self.assertEqual(hasil.returncode, 0, hasil.stdout + hasil.stderr)
        self.assertIn("SAMA", hasil.stdout)

        # body berubah -> BEDA, kode 1
        server.setel("/", b"build 78")
        hasil = jalankan_cli("cocokkan", self.sidik)
        self.assertEqual(hasil.returncode, 1)
        self.assertIn("BEDA", hasil.stdout)

        # server dimatikan, --tanpa-url -> tetap 0
        server.henti()
        hasil = jalankan_cli("cocokkan", self.sidik, "--tanpa-url")
        self.assertEqual(hasil.returncode, 0, hasil.stdout + hasil.stderr)

        # server dimatikan, tanpa --tanpa-url -> BEDA/perburukan, kode 1
        hasil = jalankan_cli("cocokkan", self.sidik)
        self.assertEqual(hasil.returncode, 1)
        self.assertIn("URL", hasil.stdout)

    def test_penanda_berubah_terdeteksi(self):
        tulis(self.data, b"versi satu-dua-tiga")
        hasil = jalankan_cli("buat", self.data, "-p", "versi", "-o", self.sidik)
        self.assertEqual(hasil.returncode, 0, hasil.stderr)
        tulis(self.data, b"tidak memuat kata lagi")
        hasil = jalankan_cli("cocokkan", self.sidik)
        self.assertEqual(hasil.returncode, 1)
        self.assertIn("penanda", hasil.stdout)

    def test_simpan_o_atomi_tanpa_sisa(self):
        tulis(self.data, b"isi")
        hasil = jalankan_cli("buat", self.data, "-o", self.sidik)
        self.assertEqual(hasil.returncode, 0, hasil.stderr)
        self.assertTrue(os.path.isfile(self.sidik))
        with open(self.sidik, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["format"], 1)
        self.assertEqual(os.listdir(self.dasar).count(f".{os.path.basename(self.sidik)}.tmp-0"), 0)
        # tidak ada file sementara .tmp tersisa
        self.assertNotIn(".tmp", " ".join(os.listdir(self.dasar)))


if __name__ == "__main__":
    unittest.main()
