from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.document_converter import DocumentConverter

DATA_DIR = Path(__file__).resolve().parent
SOURCE_DIR = DATA_DIR / "downloads"
OUTPUT_DIR = DATA_DIR / "markdown"
SOURCE_MANIFEST_PATH = SOURCE_DIR / "manifest.json"
OUTPUT_MANIFEST_PATH = OUTPUT_DIR / "manifest.json"


def load_source_manifest() -> dict:
    return json.loads(SOURCE_MANIFEST_PATH.read_text(encoding="utf-8"))


def source_paths(manifest: dict) -> list[Path]:
    paths = [SOURCE_DIR / filing["local_path"] for filing in manifest["filings"]]
    missing = [path for path in paths if not path.is_file()]
    if missing:
        missing_list = "\n".join(str(path) for path in missing)
        raise FileNotFoundError(f"Manifest files are missing:\n{missing_list}")

    discovered = set(SOURCE_DIR.rglob("*.htm")) | set(SOURCE_DIR.rglob("*.html"))
    unlisted = discovered.difference(paths)
    if unlisted:
        unlisted_list = "\n".join(str(path) for path in sorted(unlisted))
        raise ValueError(f"HTML files are missing from the manifest:\n{unlisted_list}")

    return paths


def markdown_path(source_path: Path) -> Path:
    relative_path = source_path.relative_to(SOURCE_DIR)
    return (OUTPUT_DIR / relative_path).with_suffix(".md")


def convert_filings() -> dict:
    source_manifest = load_source_manifest()
    paths = source_paths(source_manifest)
    converter = DocumentConverter(allowed_formats=[InputFormat.HTML])

    converted_manifest = deepcopy(source_manifest)
    converted_manifest["converted_at_utc"] = datetime.now(UTC).isoformat()
    converted_manifest["conversion"] = {
        "tool": "Docling",
        "version": version("docling"),
        "input_format": "html",
        "output_format": "markdown",
    }
    converted_manifest["converted_count"] = 0
    filings_by_source_path = {
        SOURCE_DIR / filing["local_path"]: filing
        for filing in converted_manifest["filings"]
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for result in converter.convert_all(paths):
        source_path = result.input.file
        output_path = markdown_path(source_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result.document.save_as_markdown(output_path)

        filing = filings_by_source_path[source_path]
        filing["source_local_path"] = filing["local_path"]
        filing["local_path"] = str(output_path.relative_to(OUTPUT_DIR))
        converted_manifest["converted_count"] += 1
        print(f"Converted {source_path.name} -> {output_path}")

    if converted_manifest["converted_count"] != len(paths):
        raise RuntimeError("Docling did not return a result for every source file")

    OUTPUT_MANIFEST_PATH.write_text(
        json.dumps(converted_manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    return converted_manifest


if __name__ == "__main__":
    manifest = convert_filings()
    print(f"Converted {manifest['converted_count']} filing(s) to {OUTPUT_DIR}")
    print(f"Manifest: {OUTPUT_MANIFEST_PATH}")
