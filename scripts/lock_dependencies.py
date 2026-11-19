"""Resolve hash-locked requirements on native Linux storage, then copy contents back."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="paved-road-locks-") as temporary:
    staging = Path(temporary)
    for name in (
        "requirements.in",
        "requirements-dev.in",
        "requirements.txt",
        "requirements-dev.txt",
    ):
        source = root / name
        if source.exists():
            shutil.copyfile(source, staging / name)
    environment = {**os.environ, "CUSTOM_COMPILE_COMMAND": "python scripts/lock_dependencies.py"}
    for stem in ("requirements", "requirements-dev"):
        subprocess.run(
            [
                sys.executable,
                "-m",
                "piptools",
                "compile",
                "--quiet",
                "--generate-hashes",
                "--strip-extras",
                "--resolver=backtracking",
                f"--output-file={stem}.txt",
                f"{stem}.in",
            ],
            cwd=staging,
            env=environment,
            check=True,
        )
    # Publish both only after both resolutions have succeeded.
    for stem in ("requirements", "requirements-dev"):
        (root / f"{stem}.txt").write_bytes((staging / f"{stem}.txt").read_bytes())
