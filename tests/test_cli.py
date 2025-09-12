# tests/test_cli.py
from subprocess import run, PIPE
import os, sys, pathlib

def test_cli_runs():
    root = pathlib.Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root)

    result = run(
        [sys.executable, "-m", "src.cli", "demo-model"],
        stdout=PIPE, stderr=PIPE, text=True,
        cwd=root, env=env
    )
    assert "demo-model" in result.stdout, result.stderr
