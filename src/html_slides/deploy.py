from __future__ import annotations

import argparse
import html
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_MANIFEST = "slides.deploy.json"
DEFAULT_DIST = "dist"
SITE_ASSETS = ("favicon.svg",)
EXCLUDED_NAMES = {
    ".DS_Store",
    ".git",
    ".references",
    "__pycache__",
}


@dataclass(frozen=True)
class Deck:
    id: str
    title: str
    source: Path
    entry: str


def parser() -> argparse.ArgumentParser:
    argument_parser = argparse.ArgumentParser(
        description="Build selected HTML slide decks for GitHub Pages."
    )
    argument_parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(DEFAULT_MANIFEST),
        help="Path to the deck deployment manifest.",
    )
    argument_parser.add_argument(
        "--dist",
        type=Path,
        default=Path(DEFAULT_DIST),
        help="Directory to write the static Pages artifact.",
    )
    argument_parser.add_argument(
        "--decks",
        default="all",
        help="Comma-separated deck ids to deploy, or 'all'.",
    )
    return argument_parser


def load_decks(manifest_path: Path) -> list[Deck]:
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"Manifest does not exist: {manifest_path}") from None
    except json.JSONDecodeError as error:
        raise SystemExit(f"Manifest is not valid JSON: {manifest_path}: {error}") from None

    raw_decks = payload.get("decks")
    if not isinstance(raw_decks, list):
        raise SystemExit(f"Manifest must contain a 'decks' list: {manifest_path}")

    decks: list[Deck] = []
    seen_ids: set[str] = set()
    for index, raw_deck in enumerate(raw_decks, start=1):
        deck = parse_deck(raw_deck, index, manifest_path.parent)
        if deck.id in seen_ids:
            raise SystemExit(f"Duplicate deck id in manifest: {deck.id}")
        seen_ids.add(deck.id)
        decks.append(deck)
    return decks


def parse_deck(raw_deck: Any, index: int, base_path: Path) -> Deck:
    if not isinstance(raw_deck, dict):
        raise SystemExit(f"Deck entry #{index} must be an object.")

    missing = [
        field
        for field in ("id", "title", "source", "entry")
        if not isinstance(raw_deck.get(field), str) or not raw_deck[field].strip()
    ]
    if missing:
        raise SystemExit(
            f"Deck entry #{index} is missing required string field(s): "
            + ", ".join(missing)
        )

    deck_id = raw_deck["id"].strip()
    if "/" in deck_id or "\\" in deck_id or deck_id in {".", ".."}:
        raise SystemExit(f"Deck id must be a single URL path segment: {deck_id}")

    source = (base_path / raw_deck["source"]).resolve()
    entry = raw_deck["entry"].strip().lstrip("/")
    if Path(entry).is_absolute() or ".." in Path(entry).parts:
        raise SystemExit(f"Deck entry must be relative to its source: {entry}")

    return Deck(
        id=deck_id,
        title=raw_deck["title"].strip(),
        source=source,
        entry=entry,
    )


def select_decks(decks: list[Deck], selected: str) -> list[Deck]:
    if selected.strip().lower() == "all":
        return decks

    requested = [deck_id.strip() for deck_id in selected.split(",") if deck_id.strip()]
    if not requested:
        raise SystemExit("--decks must be 'all' or a comma-separated list of deck ids.")

    by_id = {deck.id: deck for deck in decks}
    missing = [deck_id for deck_id in requested if deck_id not in by_id]
    if missing:
        raise SystemExit("Unknown deck id(s): " + ", ".join(missing))

    return [by_id[deck_id] for deck_id in requested]


def build_pages(decks: list[Deck], dist: Path, repo_root: Path) -> None:
    if dist.exists():
        shutil.rmtree(dist)
    dist.mkdir(parents=True)
    (dist / ".nojekyll").write_text("", encoding="utf-8")

    for name in SITE_ASSETS:
        source = repo_root / name
        if source.is_file():
            shutil.copy2(source, dist / name)

    for deck in decks:
        build_deck(deck, dist / deck.id)

    write_index(decks, dist / "index.html")


def build_deck(deck: Deck, destination: Path) -> None:
    entry_path = deck.source / deck.entry
    if not deck.source.is_dir():
        raise SystemExit(f"Deck source does not exist: {deck.source}")
    if not entry_path.is_file():
        raise SystemExit(f"Deck entry does not exist: {entry_path}")

    shutil.copytree(deck.source, destination, ignore=ignore_deploy_extras)

    copied_entry = destination / deck.entry
    index_path = destination / "index.html"
    if copied_entry != index_path:
        if index_path.exists():
            raise SystemExit(
                f"Cannot create {index_path}; deck already contains an index.html."
            )
        copied_entry.replace(index_path)

    page = index_path.read_text(encoding="utf-8")
    index_path.write_text(
        page.replace('href="/favicon.', 'href="../favicon.'),
        encoding="utf-8",
    )


def ignore_deploy_extras(directory: str, names: list[str]) -> set[str]:
    ignored = {name for name in names if name in EXCLUDED_NAMES}
    ignored.update(name for name in names if name.endswith((".pyc", ".pyo")))
    return ignored


def write_index(decks: list[Deck], index_path: Path) -> None:
    links = "\n".join(
        f'      <li><a href="{html.escape(deck.id)}/">{html.escape(deck.title)}</a></li>'
        for deck in decks
    )
    index_path.write_text(
        f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Slides</title>
    <link rel="icon" href="favicon.svg" type="image/svg+xml">
    <style>
      body {{
        font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        margin: 3rem auto;
        max-width: 52rem;
        padding: 0 1.5rem;
        line-height: 1.5;
      }}
      a {{ color: #155eef; }}
    </style>
  </head>
  <body>
    <h1>Slides</h1>
    <ul>
{links}
    </ul>
  </body>
</html>
""",
        encoding="utf-8",
    )


def main() -> None:
    args = parser().parse_args()
    manifest_path = args.manifest.resolve()
    dist = args.dist.resolve()
    decks = select_decks(load_decks(manifest_path), args.decks)

    build_pages(decks, dist, manifest_path.parent)
    print(f"Built {len(decks)} deck(s) in {dist}")
    for deck in decks:
        print(f"- {deck.id}: {deck.title}")
