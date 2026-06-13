from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path


DEFAULT_PATH = "slides/progress_reports/2026-06-15/cells_are_agents.html"


def parser() -> argparse.ArgumentParser:
    argument_parser = argparse.ArgumentParser(
        description="Serve HTML slides with browser autoreload."
    )
    argument_parser.add_argument(
        "--root", type=Path, default=Path.cwd(), help="Directory to serve."
    )
    argument_parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT", "8080")),
        help="Port to bind.",
    )
    argument_parser.add_argument("--host", default="0.0.0.0", help="Host to bind.")
    argument_parser.add_argument(
        "--open-path", default=DEFAULT_PATH, help="Path printed as the deck URL."
    )
    argument_parser.add_argument(
        "--poll",
        type=int,
        default=300,
        help="File polling interval in milliseconds, passed to live-server via CHOKIDAR_INTERVAL.",
    )
    return argument_parser


def main() -> None:
    args = parser().parse_args()
    root = args.root.resolve()
    open_path = args.open_path.strip("/")
    deck = root / open_path

    if not root.exists():
        raise SystemExit(f"Root does not exist: {root}")

    if not deck.exists():
        raise SystemExit(f"HTML file does not exist: {deck}")

    if shutil.which("npx") is None:
        raise SystemExit(
            "npx is required to run live-server, but it was not found on PATH."
        )

    env = os.environ.copy()
    env["CHOKIDAR_USEPOLLING"] = "true"
    env["CHOKIDAR_INTERVAL"] = str(args.poll)

    print(f"Serving {root}")
    print(f"Open http://localhost:{args.port}/{open_path}")
    print("Autoreload enabled by live-server. Press Ctrl+C to stop.")

    command = [
        "npx",
        "--yes",
        "live-server",
        str(root),
        f"--port={args.port}",
        f"--host={args.host}",
        "--no-browser",
    ]
    try:
        raise SystemExit(subprocess.call(command, env=env))
    except KeyboardInterrupt:
        raise SystemExit(130)
