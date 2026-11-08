"""Uji inti: sha256, pencarian penanda (termasuk lintas batas potongan), tulis atomik."""
import hashlib
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sidik_jari import inti


class UjiSha256(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.dasar = self.folder.name

    def test_kecil_cocok_hashlib(self):
        path = os.path.join(self.dasar, "kecil.bin")
        data = b"halo dunia sidik-jari"
        with open(path, "wb") as f:
            f.write(data)
        ukuran, sha = inti.sha256_dan_ukuran(path)
        self.assertEqual(ukuran, len(data))
        self.assertEqual(sha, hashlib.sha256(data).hexdigest())

    def test_besar_lebih_dari_3mib(self):
        ukuran = 3 * 1024 * 1024 + 700 * 1024  # 3,68 MiB
        data = os.urandom(ukuran)
        path = os.path.join(self.dasar, "besar.bin")
        with open(path, "wb") as f:
            f.write(data)
        hasil_ukuran, sha = inti.sha256_dan_ukuran(path)
        self.assertEqual(hasil_ukuran, ukuran)
        self.assertEqual(sha, hashlib.sha256(data).hexdigest())


class UjiPenanda(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.dasar = self.folder.name

    def _file(self, nama, data: bytes) -> str:
        path = os.path.join(self.dasar, nama)
        with open(path, "wb") as f:
            f.write(data)
        return path

    def _cari(self, data: bytes, penanda: bytes):
        path = self._file("uji.bin", data)
        with open(path, "rb") as f:
            return inti.cari_penanda(f, penanda)

    def test_di_awal(self):
        ditemukan, jumlah, offset = self._cari(b"MULAI" + b"x" * 100, b"MULAI")
        self.assertTrue(ditemukan)
        self.assertEqual(jumlah, 1)
        self.assertEqual(offset, 0)

    def test_di_tengah(self):
        data = b"ab" * 10 + b"SIDIK" + b"cd" * 10
        ditemukan, jumlah, offset = self._cari(data, b"SIDIK")
        self.assertTrue(ditemukan)
        self.assertEqual(jumlah, 1)
        self.assertEqual(offset, 20)

    def test_di_akhir(self):
        data = b"x" * 50 + b"AKHIR"
        ditemukan, jumlah, offset = self._cari(data, b"AKHIR")
        self.assertTrue(ditemukan)
        self.assertEqual(offset, len(data) - 5)

    def test_tidak_ada(self):
        ditemukan, jumlah, offset = self._cari(b"x" * 100, b"TIDAKADA")
        self.assertFalse(ditemukan)
        self.assertEqual(jumlah, 0)
        self.assertIsNone(offset)

    def test_berulang_jumlah_benar(self):
        ditemukan, jumlah, offset = self._cari(b"abaabaaba", b"aba")
        self.assertTrue(ditemukan)
        self.assertEqual(jumlah, 3)
        self.assertEqual(offset, 0)

    def test_berulang_tumpang_tindih(self):
        # "aa" di "aaaa" muncul di offset 0, 1, 2
        ditemukan, jumlah, offset = self._cari(b"aaaa", b"aa")
        self.assertEqual(jumlah, 3)
        self.assertEqual(offset, 0)

    def test_penanda_kosong_galat(self):
        with self.assertRaises(inti.Galat):
            self._cari(b"abc", b"")

    def test_lintas_batas_potongan_dimulai_di_batas(self):
        # penanda mulai tepat di offset BACA_POTONG (dengan BACA_POTONG di-patch kecil)
        data = b"x" * 8 + b"ABCD" + b"y" * 20
        with mock.patch.object(inti, "BACA_POTONG", 8):
            ditemukan, jumlah, offset = self._cari(data, b"ABCD")
        self.assertTrue(ditemukan)
        self.assertEqual(jumlah, 1)
        self.assertEqual(offset, 8)

    def test_lintas_batas_potongan_menggantung(self):
        # penanda menembus batas: 2 byte terakhir potongan + 2 byte awal berikut
        data = b"x" * 6 + b"ABCD" + b"y" * 20
        with mock.patch.object(inti, "BACA_POTONG", 8):
            ditemukan, jumlah, offset = self._cari(data, b"ABCD")
        self.assertTrue(ditemukan)
        self.assertEqual(jumlah, 1)
        self.assertEqual(offset, 6)

    def test_lintas_batas_potongan_berulang(self):
        # pola ABCD berulang, potongan 8 byte: 6 kemunculan, tak ada dobel/gagal
        data = b"ABCD" * 6
        with mock.patch.object(inti, "BACA_POTONG", 8):
            ditemukan, jumlah, offset = self._cari(data, b"ABCD")
        self.assertTrue(ditemukan)
        self.assertEqual(jumlah, 6)
        self.assertEqual(offset, 0)

    def test_lintas_batas_1mib_nyata_mulai_di_batas(self):
        batas = inti.BACA_POTONG
        data = b"a" * batas + b"PENANDA" + b"b" * 10
        ditemukan, jumlah, offset = self._cari(data, b"PENANDA")
        self.assertTrue(ditemukan)
        self.assertEqual(jumlah, 1)
        self.assertEqual(offset, batas)

    def test_lintas_batas_1mib_nyata_menggantung(self):
        batas = inti.BACA_POTONG
        data = b"a" * (batas - 2) + b"SIDIK" + b"z" * 10
        ditemukan, jumlah, offset = self._cari(data, b"SIDIK")
        self.assertTrue(ditemukan)
        self.assertEqual(jumlah, 1)
        self.assertEqual(offset, batas - 2)


class UjiValidasiPenanda(unittest.TestCase):
    def test_panjang_maks_ok(self):
        hasil = inti.validasi_penanda(["x" * 256])
        self.assertEqual(len(hasil[0]), 256)

    def test_panjang_lebih_galat(self):
        with self.assertRaises(inti.Galat):
            inti.validasi_penanda(["x" * 257])

    def test_kosong_galat(self):
        with self.assertRaises(inti.Galat):
            inti.validasi_penanda([""])

    def test_kebanyakan_galat(self):
        with self.assertRaises(inti.Galat):
            inti.validasi_penanda(["p"] * (inti.MAKS_PENANDA + 1))


class UjiKumpulkanFile(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.dasar = self.folder.name

    def test_terlalu_banyak_file_galat(self):
        with self.assertRaises(inti.Galat):
            inti.kumpulkan_file(["tidak-relevan.bin"] * (inti.MAKS_FILE + 1), [])

    def test_file_tidak_ada_galat(self):
        with self.assertRaises(inti.Galat):
            inti.kumpulkan_file(
                [os.path.join(self.dasar, "hantu.bin")], [])

    def test_hasil_satu_file(self):
        path = os.path.join(self.dasar, "a.bin")
        data = b"begini SIDIKJARI oke"
        with open(path, "wb") as f:
            f.write(data)
        hasil = inti.kumpulkan_file([path], ["SIDIKJARI", "absen"])
        self.assertEqual(len(hasil), 1)
        entri = hasil[0]
        self.assertEqual(entri["path"], os.path.abspath(path))
        self.assertEqual(entri["ukuran"], len(data))
        self.assertEqual(entri["sha256"], hashlib.sha256(data).hexdigest())
        self.assertEqual(entri["sha256_16"], entri["sha256"][:16])
        p1, p2 = entri["penanda"]
        self.assertEqual(p1["penanda"], "SIDIKJARI")
        self.assertTrue(p1["ditemukan"])
        self.assertEqual(p1["jumlah"], 1)
        self.assertEqual(p1["offset_pertama"], 7)
        self.assertFalse(p2["ditemukan"])
        self.assertIsNone(p2["offset_pertama"])


class UjiTulisJson(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.dasar = self.folder.name

    def test_atomi_bersih(self):
        target = os.path.join(self.dasar, "keluar.json")
        inti.tulis_json(target, {"format": 1, "isi": "contoh"})
        with open(target, "r", encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"format": 1, "isi": "contoh"})
        sisanya = os.listdir(self.dasar)
        self.assertEqual(sisanya, ["keluar.json"])  # tidak ada file sementara tinggal

    def test_overwrite_isi_lama(self):
        target = os.path.join(self.dasar, "keluar.json")
        with open(target, "w", encoding="utf-8") as f:
            f.write("data lama yang salah")
        inti.tulis_json(target, {"format": 1})
        with open(target, "r", encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"format": 1})


if __name__ == "__main__":
    unittest.main()
