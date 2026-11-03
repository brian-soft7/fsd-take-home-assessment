import hashlib
import os
import subprocess
import sys
import venv
from pathlib import Path

# one command to start: python run.py
ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
REQ = ROOT / "requirements.txt"
STAMP = VENV / ".req-hash"
PY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def main():
    host = os.environ.get("HOST", "127.0.0.1")
    port = os.environ.get("PORT", "8000")

    if not PY.exists():
        print("making .venv ...")
        venv.create(VENV, with_pip=True)

    # install again only when requirements.txt changed
    h = hashlib.sha256(REQ.read_bytes()).hexdigest()
    if not STAMP.exists() or STAMP.read_text() != h:
        print("installing requirements ...")
        subprocess.check_call([str(PY), "-m", "pip", "install", "-q", "-r", str(REQ)])
        STAMP.write_text(h)

    print(f"open http://{host}:{port}  (Ctrl+C to stop)")
    return subprocess.call([str(PY), "-m", "uvicorn", "app.main:app", "--host", host, "--port", port], cwd=ROOT)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
