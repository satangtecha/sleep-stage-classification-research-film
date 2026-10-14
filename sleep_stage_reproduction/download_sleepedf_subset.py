"""Download a small, official PhysioNet Sleep-EDF subset for a pilot run."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import subprocess


BASE = "https://physionet.org/files/sleep-edfx/1.0.0/sleep-cassette/"
FILES = [
    "SC4001E0-PSG.edf", "SC4001EC-Hypnogram.edf",
    "SC4002E0-PSG.edf", "SC4002EC-Hypnogram.edf",
    "SC4011E0-PSG.edf", "SC4011EH-Hypnogram.edf",
    "SC4012E0-PSG.edf", "SC4012EC-Hypnogram.edf",
    "SC4021E0-PSG.edf", "SC4021EH-Hypnogram.edf",
    "SC4022E0-PSG.edf", "SC4022EJ-Hypnogram.edf",
    "SC4031E0-PSG.edf", "SC4031EC-Hypnogram.edf",
    "SC4032E0-PSG.edf", "SC4032EP-Hypnogram.edf",
    "SC4041E0-PSG.edf", "SC4041EC-Hypnogram.edf",
    "SC4042E0-PSG.edf", "SC4042EC-Hypnogram.edf",
    "SC4051E0-PSG.edf", "SC4051EC-Hypnogram.edf",
    "SC4052E0-PSG.edf", "SC4052EC-Hypnogram.edf",
]

# Expected sizes for PSG files listed by the official PhysioNet directory.
# Hypnogram files are small and are treated as complete when they exceed 1 KB.
EXPECTED_BYTES = {
    "SC4021E0-PSG.edf": 51147008,
    "SC4022E0-PSG.edf": 50271488,
    "SC4031E0-PSG.edf": 51438848,
    "SC4032E0-PSG.edf": 49833728,
    "SC4041E0-PSG.edf": 46878848,
    "SC4042E0-PSG.edf": 50928128,
    "SC4051E0-PSG.edf": 49651328,
    "SC4052E0-PSG.edf": 51183488,
}


def one(name, out):
    target = out / name
    expected = EXPECTED_BYTES.get(name)
    complete = target.exists() and (
        target.stat().st_size == expected if expected else target.stat().st_size > 1000
    )
    if complete:
        return f"exists {name} {target.stat().st_size:,} bytes"
    # curl resumes partial files left by an interrupted request.
    subprocess.run(["curl.exe", "-L", "--retry", "5", "-C", "-", "-o", str(target), BASE + name], check=True)
    return f"saved {name} {target.stat().st_size:,} bytes"


def main():
    out = Path(__file__).parent / "data" / "sleep-edf"
    out.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        fs = [pool.submit(one, name, out) for name in FILES]
        for f in as_completed(fs):
            print(f.result())


if __name__ == "__main__":
    main()
