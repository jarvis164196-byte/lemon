import argparse
import os
import secrets
import webbrowser
from pathlib import Path

import uvicorn

from .server import create_app


def main():
    parser = argparse.ArgumentParser(description="Lemon — local reference-guided photo grading")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(os.environ.get("LEMON_DATA_DIR", Path.home() / ".local/share/lemon")),
    )
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Use a port between 1024 and 65535.")
    os.umask(0o077)
    token = secrets.token_urlsafe(32)
    app = create_app(args.data_dir, token, args.port)
    url = f"http://127.0.0.1:{args.port}/#token={token}"
    print("Lemon · local editing, optional consent-based vision\nPrivate launch URL: " + url, flush=True)
    if not args.no_browser:
        import threading

        threading.Timer(1, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False)


if __name__ == "__main__":
    main()
