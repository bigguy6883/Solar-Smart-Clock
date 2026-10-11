"""Checks on the web page's own files in solar_clock/web/."""

import json
import re
from html.parser import HTMLParser
from pathlib import PurePosixPath

from PIL import Image

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


ICON_SIZES = {
    "favicon-32.png": 32,
    "apple-touch-icon.png": 180,
    "icon-192.png": 192,
    "icon-512.png": 512,
    "icon-maskable-512.png": 512,
}


def test_index_links_the_icons_and_manifest():
    refs = _index_references()
    for ref in (
        "/icons/icon.svg",
        "/icons/favicon-32.png",
        "/icons/apple-touch-icon.png",
        "/manifest.webmanifest",
    ):
        assert ref in refs, f"index.html does not link {ref}"


def test_manifest_icons_are_served_at_their_declared_size():
    site = StaticSite()
    manifest = json.loads((WEB_DIR / "manifest.webmanifest").read_text())
    assert manifest["name"] == "Solar Clock"
    assert manifest["start_url"] == "/"
    assert any(icon.get("purpose") == "maskable" for icon in manifest["icons"])
    for icon in manifest["icons"]:
        resolved = site.resolve(icon["src"])
        assert resolved is not None, f"manifest lists missing {icon['src']}"
        width, height = Image.open(resolved[0]).size
        assert f"{width}x{height}" == icon["sizes"], icon["src"]


def test_icon_files_have_the_spec_sizes():
    for name, size in ICON_SIZES.items():
        assert Image.open(WEB_DIR / "icons" / name).size == (size, size), name
    assert (WEB_DIR / "icons" / "icon.svg").read_text().startswith("<svg")
