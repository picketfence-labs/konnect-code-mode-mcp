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


def fenced_blocks(text):
    """Return complete fenced code blocks, including their delimiters."""
    blocks = []
    current = []
    inside = False
    for line in text.splitlines():
        if FENCE.match(line):
            current.append(line)
            if inside:
                blocks.append("\n".join(current))
                current = []
                inside = False
            else:
                inside = True
            continue
        if inside:
            current.append(line)
    if inside:
        blocks.append("\n".join(current))
    return blocks


def heading_levels(text):
    prose = []
    inside = False
    for line in text.splitlines():
        if FENCE.match(line):
            inside = not inside
        elif not inside:
            prose.append(line)
    return [len(match.group(1)) for match in re.finditer(r"^(#{1,6})(?:\s|$)", "\n".join(prose), re.M)]


def check_pairs(root):
    errors = []
    documents = sorted(markdown_files(root))
    english = [path for path in documents if path.name.endswith(".en.md")]
    for translated in english:
        original = translated.with_name(translated.name[:-6] + ".md")
        relative_en = translated.relative_to(root).as_posix()
        relative_ja = original.relative_to(root).as_posix()
        if not original.is_file():
            errors.append("{}:1: 対になる日本語版がありません: {}".format(relative_en, relative_ja))
            continue
        ja_text = original.read_text(encoding="utf-8")
        en_text = translated.read_text(encoding="utf-8")
        ja_lines = ja_text.splitlines()
        en_lines = en_text.splitlines()
        ja_link = "]({})".format(translated.name)
        en_link = "]({})".format(original.name)
        if not any(ja_link in line for line in ja_lines[:12]):
            errors.append("{}:1: 先頭12行に英語版へのリンクがありません".format(relative_ja))
        if not any(en_link in line for line in en_lines[:12]):
            errors.append("{}:1: 先頭12行に日本語版へのリンクがありません".format(relative_en))
        if heading_levels(ja_text) != heading_levels(en_text):
            errors.append("{}:1: 見出しレベル列が日本語版と一致しません".format(relative_en))
        if fenced_blocks(ja_text) != fenced_blocks(en_text):
            errors.append("{}:1: fenced code block が日本語版と一致しません".format(relative_en))
    return len(english), errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--links", action="store_true")
    parser.add_argument("--pairs", action="store_true")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args()
    root = args.root.resolve()
    if not args.links and not args.pairs:
        parser.error("at least one of --links or --pairs is required")
    errors = []
    summaries = []
    if args.links:
        documents, links, link_errors = check_links(root)
        errors.extend(link_errors)
        summaries.append("{}文書、{}リンク".format(documents, links))
    if args.pairs:
        pairs, pair_errors = check_pairs(root)
        errors.extend(pair_errors)
        summaries.append("{}日英ペア".format(pairs))
    for error in errors:
        print(error)
    if errors:
        print("{}件のエラー（{}を検査）".format(len(errors), "、".join(summaries)))
        return 1
    print("OK: {}を検査。エラー0件".format("、".join(summaries)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
