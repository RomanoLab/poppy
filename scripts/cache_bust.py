#!/usr/bin/env python3
"""Stamp content-hash ?v= params onto local CSS/JS references in website/*.html.

The site has no build step, and we reuse filenames (Home.js, poppy.css, …) across
changes — so returning visitors can be served stale cached assets after a deploy.
This rewrites every local <link href="X.css"> / <script src="X.js"> to
"X.css?v=<hash>", where <hash> is the first 8 hex of the file's SHA-1. When a file
changes its hash changes, so browsers fetch the new copy; unchanged files keep the
same hash (and stay cached).

Idempotent: any existing ?v=… is stripped and recomputed, so it's safe to re-run.

RUN THIS AFTER EDITING ANY .css/.js IN website/ (and before deploying):
    python3 scripts/cache_bust.py

External refs (https://…, e.g. Google Fonts) and non-css/js assets are left alone.
"""
import hashlib
import pathlib
import re

WEB = pathlib.Path(__file__).resolve().parent.parent / "website"

_hashes = {}


def file_hash(name):
    if name not in _hashes:
        f = WEB / name
        _hashes[name] = hashlib.sha1(f.read_bytes()).hexdigest()[:8] if f.exists() else None
    return _hashes[name]


# Only inside <link …> / <script …> tags; only local *.css / *.js; tolerate an existing ?v=.
PAT = re.compile(
    r'(?P<pre><(?:link|script)\b[^>]*?\b(?:href|src)=")'
    r'(?P<name>[A-Za-z0-9_./-]+\.(?:css|js))'
    r'(?:\?v=[0-9a-f]+)?'
    r'(?P<post>")'
)


def repl(m):
    name = m.group("name")
    digest = file_hash(name)
    if not digest:  # referenced file not found locally → leave untouched
        return m.group(0)
    return m.group("pre") + name + "?v=" + digest + m.group("post")


def main():
    changed = 0
    for html in sorted(WEB.glob("*.html")):
        s = html.read_text()
        ns = PAT.sub(repl, s)
        if ns != s:
            html.write_text(ns)
            changed += 1
    stamped = sum(1 for v in _hashes.values() if v)
    print(f"cache_bust: updated {changed} HTML file(s); {stamped} local assets hashed")


if __name__ == "__main__":
    main()
