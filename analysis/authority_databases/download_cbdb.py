from __future__ import annotations

import hashlib
import json
import shutil
import urllib.request
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TARGET_DIR = (
    PROJECT_ROOT / "apps" / "api" / "ocrforge_web" / "data" / "authority" / "cbdb"
)
LATEST_URL = (
    "https://raw.githubusercontent.com/cbdb-project/cbdb_sqlite/"
    "master/latest.json"
)


def main() -> None:
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(LATEST_URL, timeout=30) as response:
        metadata = json.loads(response.read().decode("utf-8"))
    archive = TARGET_DIR / "latest.zip"
    urllib.request.urlretrieve(metadata["download_url"], archive)
    with zipfile.ZipFile(archive) as package:
        metadata_members = [
            name for name in package.namelist() if name.endswith(".json")
        ]
        package_metadata = (
            json.loads(package.read(metadata_members[0]).decode("utf-8"))
            if metadata_members
            else metadata
        )
        package.extractall(TARGET_DIR)
    archive.unlink(missing_ok=True)
    expected = TARGET_DIR / package_metadata["sqlite_filename"]
    if not expected.exists():
        raise RuntimeError(f"CBDB database not found after extraction: {expected}")
    digest = hashlib.sha256(expected.read_bytes()).hexdigest()
    if digest != package_metadata["sha256"]:
        expected.unlink(missing_ok=True)
        raise RuntimeError("CBDB database checksum mismatch")
    stable_path = TARGET_DIR / "cbdb.sqlite3"
    stable_path.unlink(missing_ok=True)
    expected.replace(stable_path)
    shutil.copyfile(
        Path(__file__).with_name("cbdb_metadata.template.json"),
        TARGET_DIR / "README.metadata.json",
    )
    (TARGET_DIR / "release.json").write_text(
        json.dumps(package_metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(stable_path)


if __name__ == "__main__":
    main()
