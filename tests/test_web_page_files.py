"""Checks on the web page's own files in solar_clock/web/."""

import re
from html.parser import HTMLParser
from pathlib import PurePosixPath

from solar_clock.web_static import WEB_DIR, StaticSite

# Relative module imports in the page's JavaScript, e.g. from "./format.js".
JS_IMPORT = re.compile(
    r"""^\s*(?:import|export)\b[^;]*?\bfrom\s+["'](\.[^"']+)["']""", re.MULTILINE
)


class _References(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.refs: list[str] = []

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name in ("href", "src") and value:
                self.refs.append(value)


def _index_references() -> list[str]:
    parser = _References()
    parser.feed((WEB_DIR / "index.html").read_text())
    return parser.refs


def test_every_index_reference_is_served():
    site = StaticSite()
    refs = _index_references()
    assert "/js/app.js" in refs
    for ref in refs:
        assert ref.startswith("/"), f"{ref} should be an absolute path"
        assert site.resolve(ref) is not None, f"index.html points at missing {ref}"


def test_every_javascript_import_is_served():
    site = StaticSite()
    scripts = sorted(WEB_DIR.glob("js/**/*.js"))
    assert scripts, "no JavaScript found"
    for script in scripts:
        url_dir = PurePosixPath("/" + script.parent.relative_to(WEB_DIR).as_posix())
        for target in JS_IMPORT.findall(script.read_text()):
            parts: list[str] = []
            for part in (url_dir / target).parts[1:]:
                if part == "..":
                    parts.pop()
                elif part != ".":
                    parts.append(part)
            url = "/" + "/".join(parts)
            assert site.resolve(url) is not None, f"{script.name} imports missing {url}"
