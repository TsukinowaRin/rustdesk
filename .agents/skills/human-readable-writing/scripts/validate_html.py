#!/usr/bin/env python3
"""Validate self-contained, accessible human-facing HTML reports."""

from __future__ import annotations

import argparse
from html.parser import HTMLParser
import pathlib
import re
import sys
from urllib.parse import unquote, urlsplit


class ReportParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: dict[str, int] = {}
        self.ids: set[str] = set()
        self.duplicate_ids: set[str] = set()
        self.internal_links: list[str] = []
        self.local_links: list[str] = []
        self.html_lang = ""
        self.title_parts: list[str] = []
        self.in_title = False
        self.has_charset = False
        self.has_viewport = False
        self.errors: list[str] = []

    def handle_decl(self, decl: str) -> None:
        if decl.lower() != "doctype html":
            self.errors.append("doctype must be HTML5")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags[tag] = self.tags.get(tag, 0) + 1
        values = dict(attrs)
        if tag == "html":
            self.html_lang = values.get("lang") or ""
        if tag == "title":
            self.in_title = True
        if tag == "meta":
            self.has_charset = (values.get("charset") or "").lower() == "utf-8" or self.has_charset
            self.has_viewport = values.get("name", "").lower() == "viewport" or self.has_viewport
        element_id = values.get("id")
        if element_id:
            if element_id in self.ids:
                self.duplicate_ids.add(element_id)
            self.ids.add(element_id)
        href = values.get("href") or ""
        if tag == "a" and href.startswith("#") and len(href) > 1:
            self.internal_links.append(href[1:])
        elif tag == "a" and href and not urlsplit(href).scheme and not href.startswith(("#", "//", "/")):
            self.local_links.append(unquote(urlsplit(href).path))
        if href.lower().startswith("javascript:"):
            self.errors.append(f"{tag}: javascript URL is forbidden")
        if any(name.lower().startswith("on") for name, _ in attrs):
            self.errors.append(f"{tag}: inline event handler is forbidden")
        if tag in {"script", "iframe", "object", "embed"}:
            self.errors.append(f"{tag}: active or embedded content is forbidden")
        if tag == "link" and (values.get("rel") or "").lower() == "stylesheet":
            self.errors.append("external stylesheet is forbidden")
        if tag in {"img", "audio", "video", "source"}:
            source = values.get("src") or values.get("srcset") or ""
            if source.startswith(("http://", "https://", "//")):
                self.errors.append(f"{tag}: external media resource is forbidden")

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)


def validate(path: pathlib.Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    parser = ReportParser()
    parser.feed(text)
    errors = list(parser.errors)
    if not re.match(r"\s*<!doctype html>", text, re.I):
        errors.append("missing <!doctype html>")
    if parser.html_lang != "ja":
        errors.append('html lang must be "ja"')
    if not parser.has_charset:
        errors.append("missing UTF-8 charset meta")
    if not parser.has_viewport:
        errors.append("missing viewport meta")
    if not "".join(parser.title_parts).strip():
        errors.append("title must not be empty")
    for tag, expected in (("html", 1), ("head", 1), ("body", 1), ("main", 1), ("h1", 1)):
        if parser.tags.get(tag, 0) != expected:
            errors.append(f"expected exactly one <{tag}>")
    if parser.tags.get("style", 0) != 1:
        errors.append("expected exactly one embedded <style>")
    if parser.duplicate_ids:
        errors.append(f"duplicate ids: {sorted(parser.duplicate_ids)}")
    missing_links = sorted(set(parser.internal_links) - parser.ids)
    if missing_links:
        errors.append(f"missing internal link targets: {missing_links}")
    missing_files = sorted(link for link in set(parser.local_links) if not (path.parent / link).exists())
    if missing_files:
        errors.append(f"missing local link targets: {missing_files}")
    lowered = text.lower()
    for marker, message in (
        ("@media print", "missing print stylesheet"),
        ("@media (max-width", "missing responsive breakpoint"),
        (":focus-visible", "missing keyboard focus style"),
    ):
        if marker not in lowered:
            errors.append(message)
    if re.search(r"@import\s|url\(\s*['\"]?(?:https?:)?//", text, re.I):
        errors.append("external CSS resource is forbidden")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("html", type=pathlib.Path)
    args = parser.parse_args()
    errors = validate(args.html)
    if errors:
        for error in errors:
            print(f"{args.html}: {error}", file=sys.stderr)
        return 1
    print(f"HTML report OK: {args.html}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
