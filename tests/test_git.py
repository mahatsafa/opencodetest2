"""Uji perekaman git: bersih, kotor, bukan repo."""
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alat import buat_repo, jalankan_cli


def _git(dirpath, *argumen):
    return subprocess.run(
        ["git", "-C", dirpath, *argumen], capture_output=True, text=True, check=True
    ).stdout.strip()


class UjiGit(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.dasar = self.folder.name
        self.repo = buat_repo(os.path.join(self.dasar, "repo"))

    def _buat_json(self, tambahan=()):
        hasil = jalankan_cli("buat", "--git", self.repo, "--json", *tambahan)
        self.assertEqual(hasil.returncode, 0, hasil.stderr)
        return __import__("json").loads(hasil.stdout)

    def test_repo_bersih(self):
        data = self._buat_json()
        rekam = data["git"]
        self.assertEqual(rekam["commit"], _git(self.repo, "rev-parse", "HEAD"))
        self.assertEqual(rekam["commit_12"], rekam["commit"][:12])
        self.assertEqual(rekam["branch"], _git(self.repo, "rev-parse", "--abbrev-ref", "HEAD"))
        self.assertTrue(rekam["bersih"])
        self.assertEqual(rekam["jumlah_file_berubah"], 0)
        self.assertEqual(rekam["dir"], os.path.abspath(self.repo))

    def test_repo_kotor(self):
        # ubah file terlacak + tambah file baru (tidak dilacak)
        with open(os.path.join(self.repo, "berkas.txt"), "ab") as f:
            f.write(b"oleh-oleh")
        with open(os.path.join(self.repo, "baru.txt"), "wb") as f:
            f.write(b"baru")
        data = self._buat_json()
        rekam = data["git"]
        self.assertFalse(rekam["bersih"])
        self.assertEqual(rekam["jumlah_file_berubah"], 2)

    def test_bukan_repo(self):
        hasil = jalankan_cli("buat", "--git", self.dasar, "--json")
        self.assertEqual(hasil.returncode, 2)
        self.assertIn("bukan repo git", hasil.stderr)


if __name__ == "__main__":
    unittest.main()
