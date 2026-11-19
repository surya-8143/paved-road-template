"""Build a deterministic Python 3.12/x86_64 Lambda ZIP from hashed wheels."""

import csv
import hashlib
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


def main() -> None:
    if sys.version_info[:2] != (3, 12) or sys.platform != "linux":
        raise SystemExit("Run this script with Python 3.12 inside Linux/WSL")
    root = Path(__file__).resolve().parents[1]
    output_dir = root / "build"
    output_dir.mkdir(exist_ok=True)
    # Native Linux temp storage avoids DrvFS permission/metadata limitations.
    with tempfile.TemporaryDirectory(prefix="paved-road-lambda-") as temporary:
        staging = Path(temporary) / "package"
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--require-hashes",
                "--only-binary=:all:",
                "--no-compile",
                "--platform",
                "manylinux2014_x86_64",
                "--implementation",
                "cp",
                "--python-version",
                "3.12",
                "--target",
                str(staging),
                "-r",
                str(root / "requirements.txt"),
            ],
            check=True,
        )
        shutil.copytree(
            root / "app", staging / "app", ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
        )
        # Lambda imports modules; it does not use pip-generated console scripts.
        # Their shebangs embed the builder's virtualenv path, so omit them and
        # their RECORD entries to keep artifacts independent of that path.
        for record in staging.glob("*.dist-info/RECORD"):
            with record.open(newline="", encoding="utf-8") as source:
                rows = [row for row in csv.reader(source) if not row[0].startswith("../")]
            with record.open("w", newline="", encoding="utf-8") as target:
                csv.writer(target, lineterminator="\n").writerows(rows)
        archive = Path(temporary) / "lambda.zip"
        with zipfile.ZipFile(
            archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as bundle:
            for path in sorted(staging.rglob("*")):
                if path.is_file() and path.relative_to(staging).parts[0] != "bin":
                    member = zipfile.ZipInfo(
                        path.relative_to(staging).as_posix(), date_time=(2020, 1, 1, 0, 0, 0)
                    )
                    member.create_system = 3
                    member.external_attr = 0o100644 << 16
                    member.compress_type = zipfile.ZIP_DEFLATED
                    bundle.writestr(member, path.read_bytes(), compresslevel=9)
        output = output_dir / "lambda.zip"
        shutil.copyfile(archive, output)
    print(f"SHA256 {hashlib.sha256(output.read_bytes()).hexdigest()}  {output}")


if __name__ == "__main__":
    main()
