"""Download the external raw datasets required by the analysis/build scripts.

Files land in analysis/hanzi_databases/raw/ (gitignored). Safe to re-run:
existing files are skipped. If a download fails, fetch the URL manually and
place the file at the indicated path.
"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parents[1] / "raw"

DOWNLOADS = [
    (
        "https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip",
        RAW_DIR / "Unihan.zip",
    ),
    (
        "https://raw.githubusercontent.com/BYVoid/OpenCC/master/data/dictionary/STCharacters.txt",
        RAW_DIR / "opencc_STCharacters.txt",
    ),
    (
        "https://raw.githubusercontent.com/BYVoid/OpenCC/master/data/dictionary/TSCharacters.txt",
        RAW_DIR / "opencc_TSCharacters.txt",
    ),
    (
        "https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.zip",
        RAW_DIR / "cc_cedict.zip",
    ),
    (
        "https://raw.githubusercontent.com/chise/ids/master/IDS-UCS-Basic.txt",
        RAW_DIR / "chise_ids" / "IDS-UCS-Basic.txt",
    ),
    (
        "https://raw.githubusercontent.com/chise/ids/master/IDS-UCS-Ext-A.txt",
        RAW_DIR / "chise_ids" / "IDS-UCS-Ext-A.txt",
    ),
]


def main() -> int:
    failures: list[str] = []
    for url, dest in DOWNLOADS:
        if dest.exists() and dest.stat().st_size > 0:
            print(f"skip (exists): {dest.name}")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        print(f"downloading {url}")
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(request, timeout=120) as response:
                dest.write_bytes(response.read())
            print(f"  -> {dest} ({dest.stat().st_size:,} bytes)")
        except Exception as e:  # noqa: BLE001
            failures.append(f"{url} -> {dest}: {e}")
            print(f"  FAILED: {e}")
    if failures:
        print("\nSome downloads failed; fetch manually and place at the paths above:")
        for item in failures:
            print(f"  {item}")
        return 1
    print("\nAll raw datasets ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
