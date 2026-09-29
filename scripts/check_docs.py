#!/usr/bin/env python3
"""Check local Markdown links and images in this repository."""

import argparse
import os
import re
from pathlib import Path
from urllib.parse import unquote


EXCLUDED = {"node_modules", ".next", ".git", ".delegation"}
LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
FENCE = re.compile(r"^\s*```")


def markdown_files(root):
    for directory, subdirs, files in os.walk(str(root)):
        subdirs[:] = sorted(name for name in subdirs if name not in EXCLUDED)
        for filename in sorted(files):
            if filename.endswith(".md"):
                yield Path(directory) / filename


def target_path(raw):
    """Return the path part of a Markdown target, without title or anchor."""
    raw = raw.strip()
    if raw.startswith("<"):
        end = raw.find(">")
        raw = raw[1:end] if end >= 0 else raw
    else:
        raw = raw.split()[0]
    return unquote(re.split(r"[?#]", raw, maxsplit=1)[0])


def check_links(root):
    errors = []
    documents = 0
    links = 0
    old_test = (root / "TEST.md").resolve()
    for document in markdown_files(root):
        documents += 1
        in_fence = False
        for line_number, line in enumerate(document.read_text(encoding="utf-8").splitlines(), 1):
            if FENCE.match(line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            for match in LINK.finditer(line):
                raw = match.group(1).strip()
                if re.match(r"^(?:https?:|mailto:)", raw, re.I) or raw.startswith("#"):
                    continue
                path = target_path(raw)
                if not path or Path(path).is_absolute():
                    continue
                links += 1
                resolved = (document.parent / path).resolve()
                location = "{}:{}".format(document.relative_to(root), line_number)
                if resolved == old_test:
                    errors.append("{}: 旧TEST.mdへのリンク。TEST_WORLD_WEATHER.md / TEST_INSURANCE.md へ改めること".format(location))
                elif not resolved.exists():
                    errors.append("{}: リンク先が存在しません: {}".format(location, path))
    return documents, links, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--links", action="store_true", required=True)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args()
    root = args.root.resolve()
    documents, links, errors = check_links(root)
    for error in errors:
        print(error)
    if errors:
        print("{}件のエラー（{}文書、{}リンクを検査）".format(len(errors), documents, links))
        return 1
    print("OK: {}文書、{}リンクを検査。エラー0件".format(documents, links))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
