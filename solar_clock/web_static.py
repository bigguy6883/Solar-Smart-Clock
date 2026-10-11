"""The web page's static files, served only from an allowlist built at startup."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

WEB_DIR = Path(__file__).parent / "web"

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".webmanifest": "application/manifest+json",
}


class StaticSite:
    """Maps URL paths to files under web/.

    The map is built once by walking the folder, so only files that existed at
    startup, with an extension in CONTENT_TYPES, can ever be served. A request
    for anything else, including '..' tricks, finds no entry.
    """

    def __init__(self, root: Path = WEB_DIR) -> None:
        index = root / "index.html"
        if not index.is_file():
            raise FileNotFoundError(f"Web page missing: {index}")
        self._files: dict[str, tuple[Path, str]] = {}
        for path in sorted(root.rglob("*")):
            content_type = CONTENT_TYPES.get(path.suffix)
            if content_type is not None and path.is_file():
                url = "/" + path.relative_to(root).as_posix()
                self._files[url.lower()] = (path, content_type)
        logger.info(f"Web page: {len(self._files)} files from {root}")

    def resolve(self, url_path: str) -> tuple[Path, str] | None:
        """(file, content type) for a request path, or None if it isn't served."""
        path = url_path.split("?", 1)[0].lower()
        if path == "/":
            path = "/index.html"
        return self._files.get(path)
