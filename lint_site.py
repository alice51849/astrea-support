#!/usr/bin/env python3
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
import re
import sys

ROOT = Path(__file__).resolve().parent
PAGES = {
    "index.html": "https://alice51849.github.io/astrea-support/",
    "privacy.html": "https://alice51849.github.io/astrea-support/privacy.html",
    "terms.html": "https://alice51849.github.io/astrea-support/terms.html",
}
ALLOWED_EMAIL = "hourstag.app@gmail.com"
EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
FORBIDDEN_POSITIONING = (
    "daily horoscope",
    "daily fortune",
    "fortune telling",
    "fortune-telling",
    "astrology and divination app",
    "offline astrology",
    "cosmic intelligence",
)


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []
        self.ids: set[str] = set()
        self.canonical: list[str] = []
        self.h1_count = 0
        self.html_lang = ""
        self.has_viewport = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        if tag == "html":
            self.html_lang = values.get("lang", "")
        if tag == "meta" and values.get("name", "").casefold() == "viewport":
            self.has_viewport = bool(values.get("content"))
        if tag == "a" and values.get("href"):
            self.hrefs.append(values["href"])
        if values.get("id"):
            self.ids.add(values["id"])
        if tag == "link" and values.get("href"):
            if values.get("rel", "").casefold() == "canonical":
                self.canonical.append(values["href"])
            else:
                self.hrefs.append(values["href"])
        if tag == "h1":
            self.h1_count += 1


def lint_page(name: str, canonical: str) -> list[str]:
    errors: list[str] = []
    path = ROOT / name
    source = path.read_text(encoding="utf-8")
    parser = PageParser()
    parser.feed(source)
    parser.close()

    if not source.lstrip().casefold().startswith("<!doctype html>"):
        errors.append(f"{name}: missing HTML5 doctype")
    if parser.html_lang != "en":
        errors.append(f"{name}: html lang must be en")
    if not parser.has_viewport:
        errors.append(f"{name}: missing viewport metadata")
    if parser.h1_count != 1:
        errors.append(f"{name}: expected one h1, found {parser.h1_count}")
    if parser.canonical != [canonical]:
        errors.append(f"{name}: canonical mismatch {parser.canonical!r}")

    folded = source.casefold()
    for phrase in FORBIDDEN_POSITIONING:
        if phrase in folded:
            errors.append(f"{name}: forbidden rejected positioning phrase {phrase!r}")

    brand_check = source.replace("com.alice51849.Astrea", "").replace("astrea-support", "")
    if re.search(r"\bAstrea\b", brand_check):
        errors.append(f"{name}: stale public Astrea brand")

    for email in EMAIL_RE.findall(source):
        if email.casefold() != ALLOWED_EMAIL:
            errors.append(f"{name}: disallowed public email {email}")

    for href in parser.hrefs:
        parsed = urlsplit(href)
        if parsed.scheme in {"https", "mailto"}:
            if parsed.scheme == "mailto":
                address = unquote(parsed.path).casefold()
                if address != ALLOWED_EMAIL:
                    errors.append(f"{name}: disallowed mailto address {address}")
            continue
        if parsed.scheme or parsed.netloc:
            errors.append(f"{name}: unsupported link {href}")
            continue
        if not parsed.path:
            if parsed.fragment and parsed.fragment not in parser.ids:
                errors.append(f"{name}: missing local anchor #{parsed.fragment}")
            continue
        target = (path.parent / unquote(parsed.path)).resolve()
        if ROOT not in target.parents and target != ROOT:
            errors.append(f"{name}: link escapes site root: {href}")
        elif not target.is_file():
            errors.append(f"{name}: broken local link {href}")

    return errors


def lint_disclosures() -> list[str]:
    errors: list[str] = []
    privacy = (ROOT / "privacy.html").read_text(encoding="utf-8").casefold()
    required_privacy = (
        "private offline decision journal",
        "journal",
        "optional profile",
        "storekit",
        "no advertising sdk",
        "no cross-app or cross-site tracking",
        "no product analytics",
        "no journal, profile, prompt or result is uploaded to an ai model",
        ALLOWED_EMAIL,
    )
    for phrase in required_privacy:
        if phrase not in privacy:
            errors.append(f"privacy.html: missing disclosure {phrase!r}")

    support = (ROOT / "index.html").read_text(encoding="utf-8").casefold()
    for phrase in ("private offline decision journal", "one-time unlock", ALLOWED_EMAIL):
        if phrase not in support:
            errors.append(f"index.html: missing support statement {phrase!r}")

    terms = (ROOT / "terms.html").read_text(encoding="utf-8").casefold()
    if "https://www.apple.com/legal/internet-services/itunes/dev/stdeula/" not in terms:
        errors.append("terms.html: missing Apple Standard EULA URL")
    return errors


def lint_sitemap() -> list[str]:
    errors: list[str] = []
    source = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
    urls = set(re.findall(r"<loc>([^<]+)</loc>", source))
    expected = set(PAGES.values())
    if urls != expected:
        errors.append(
            f"sitemap.xml: URL mismatch missing={sorted(expected - urls)} extra={sorted(urls - expected)}"
        )
    return errors


def main() -> None:
    errors: list[str] = []
    for name, canonical in PAGES.items():
        errors.extend(lint_page(name, canonical))
    errors.extend(lint_disclosures())
    errors.extend(lint_sitemap())
    if errors:
        print("\n".join(errors), file=sys.stderr)
        raise SystemExit(1)
    print("site lint passed: HTML, local links, sitemap, disclosures, email and positioning")


if __name__ == "__main__":
    main()
