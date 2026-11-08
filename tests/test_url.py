"""Uji perekaman URL dengan server HTTP lokal."""
import hashlib
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alat import ServerUji, buat_repo, jalankan_cli, tulis
from sidik_jari import inti


class UjiUrl(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.dasar = self.folder.name
        self.server = ServerUji()
        self.addCleanup(self.server.henti)

    def test_dasar_status_ganda_sha256(self):
        body = b"halo dunia deploy"
        self.server.setel("/", body, 200, {"ETag": "abc123", "Last-Modified": "kemarin"})
        hasil = jalankan_cli("buat", "--url", self.server.url("/"), "--json")
        self.assertEqual(hasil.returncode, 0, hasil.stderr)
        u = json.loads(hasil.stdout)["url"]
        self.assertEqual(u["status"], 200)
        self.assertEqual(u["ukuran"], len(body))
        self.assertEqual(u["sha256"], hashlib.sha256(body).hexdigest())
        self.assertEqual(u["sha256_16"], u["sha256"][:16])
        self.assertEqual(u["etag"], "abc123")
        self.assertEqual(u["last_modified"], "kemarin")

    def test_cari_di_url_ada_dan_tidak_ada(self):
        self.server.setel("/", b"versi build nomor 42")
        hasil = jalankan_cli(
            "buat", "--url", self.server.url("/"),
            "--cari-di-url", "nomor 42", "--cari-di-url", "absen", "--json")
        self.assertEqual(hasil.returncode, 0, hasil.stderr)
        cari = json.loads(hasil.stdout)["url"]["cari"]
        self.assertTrue(cari[0]["ada"])
        self.assertFalse(cari[1]["ada"])

    def test_http_404_gagal(self):
        hasil = jalankan_cli("buat", "--url", self.server.url("/tidak-ada"))
        self.assertEqual(hasil.returncode, 2)
        self.assertIn("URL gagal", hasil.stderr)

    def test_body_lebih_dari_maks_galat(self):
        self.server.setel("/besar", b"x" * (inti.MAKS_BODY_URL + 1))
        hasil = jalankan_cli("buat", "--url", self.server.url("/besar"))
        self.assertEqual(hasil.returncode, 2)
        self.assertIn("body terlalu besar", hasil.stderr)

    def test_cari_di_url_butuh_url(self):
        hasil = jalankan_cli("buat", "--cari-di-url", "apa")
        self.assertEqual(hasil.returncode, 2)
        self.assertIn("--cari-di-url butuh --url", hasil.stderr)

    def test_at_commit_tanpa_git_galat(self):
        self.server.setel("/", b"apapun")
        hasil = jalankan_cli(
            "buat", "--url", self.server.url("/"), "--cari-di-url", "@commit")
        self.assertEqual(hasil.returncode, 2)
        self.assertIn("@commit butuh --git", hasil.stderr)

    def test_at_commit_dengan_git(self):
        repo = buat_repo(os.path.join(self.dasar, "repo"))
        commit12 = _rev(repo)[:12]
        self.server.setel("/", f"build dari commit {commit12}".encode())
        hasil = jalankan_cli(
            "buat", "--git", repo, "--url", self.server.url("/"),
            "--cari-di-url", "@commit", "--json")
        self.assertEqual(hasil.returncode, 0, hasil.stderr)
        u = json.loads(hasil.stdout)["url"]
        self.assertTrue(u["cari"][0]["ada"])
        self.assertEqual(u["cari"][0]["teks"], "@commit")


def _rev(repo):
    import subprocess
    return subprocess.run(
        ["git", "-C", repo, "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


if __name__ == "__main__":
    unittest.main()
