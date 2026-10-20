"""Regression tests for the explicit public download inventory."""
from pathlib import Path
import tempfile
import unittest
import zipfile
from build_site import bundle


class BundlePrivacyTests(unittest.TestCase):
    def test_unlisted_files_never_ship(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            for name in ("SKILL.md", ".env.local", ".git/config", ".DS_Store", "notes.md", "credentials.json"):
                file = source / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text("synthetic fixture only", encoding="utf-8")
            target = root / "public.zip"
            bundle(target, [(source, "skill")], allowed={"skill/SKILL.md"})
            with zipfile.ZipFile(target) as archive:
                self.assertEqual(archive.namelist(), ["skill/SKILL.md"])

    def test_missing_approved_file_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "Missing approved"):
                bundle(root / "missing.zip", [(root, "skill")], allowed={"skill/SKILL.md"})

    def test_symlink_cannot_substitute_approved_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root / "outside.txt"
            outside.write_text("synthetic outside fixture", encoding="utf-8")
            source = root / "source"
            source.mkdir()
            try:
                (source / "SKILL.md").symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("Symlink creation unavailable")
            with self.assertRaisesRegex(ValueError, "Missing approved"):
                bundle(root / "symlink.zip", [(source, "skill")], allowed={"skill/SKILL.md"})


if __name__ == "__main__":
    unittest.main()
