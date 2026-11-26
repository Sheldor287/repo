from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

OMG_SPEC_ROOT = "https://www.omg.org/spec/"
DEFAULT_SPECIFICATIONS = ("UML", "XMI", "SysML")
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)


@dataclass
class OMGArtifact:
    source: str
    specification: str
    version: str | None
    omg_file_id: str
    url: str
    filename: str
    format: str
    description: str
    normative_status: str | None
    local_path: str | None = None
    sha256: str | None = None
    retrieved_at: str | None = None
    http_status: int | None = None
    download_status: str = "DISCOVERED"
    error: str | None = None


def _text(cell: Any) -> str:
    return re.sub(r"\s+", " ", cell.get_text(" ", strip=True)).strip()


def _filename(url: str, description: str = "") -> str:
    parts = urlsplit(url)
    name = unquote(Path(parts.path).name)
    if name.lower() in {"doc", "download", "file"}:
        described = re.search(r"([A-Za-z0-9._-]+\.(?:xmi|json|kpar|sysml|xsd|cmof|dtd))\b", description, re.I)
        if described:
            name = described.group(1)
    if name.lower() in {"doc", "download", "file"} or not Path(name).suffix:
        query_name = unquote(Path(parts.query.rstrip("/")).name)
        if Path(query_name).suffix:
            if name.lower() in {"doc", "download", "file"}:
                name = query_name
            elif not Path(name).suffix:
                name = query_name
    return name or "artifact"


def _slug(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return value.strip("._") or "unknown"


def _normative_status(description: str) -> str | None:
    match = re.search(r"\b(non[- ]normative|normative|informative)\b", description, re.I)
    if not match:
        return None
    value = match.group(1).lower().replace(" ", "-")
    return "NON_NORMATIVE" if value.startswith("non") else value.upper()


def discover_artifacts(
    specifications: list[str] | tuple[str, ...] = DEFAULT_SPECIFICATIONS,
    *,
    session: requests.Session | None = None,
    timeout: tuple[int, int] = (15, 60),
) -> list[OMGArtifact]:
    """Discover all linked files in each OMG machine-readable catalog."""
    http = session or requests.Session()
    http.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,*/*"})
    found: dict[tuple[str, str], OMGArtifact] = {}

    for specification in specifications:
        spec = specification.strip().strip("/")
        catalog_url = urljoin(OMG_SPEC_ROOT, f"{spec}/machine-readable")
        response = http.get(catalog_url, timeout=timeout)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        for row in soup.select("table tr"):
            cells = row.find_all("td")
            if len(cells) < 5:
                continue
            file_id = _text(cells[0])
            format_ = _text(cells[2])
            description = _text(cells[3])
            version = _text(cells[4])
            link = cells[1].find("a", href=True)
            if not link:
                continue
            url = urljoin(catalog_url, link["href"].strip())
            if urlsplit(url).scheme not in {"http", "https"}:
                continue
            artifact = OMGArtifact(
                source="OMG",
                specification=spec,
                version=version or None,
                omg_file_id=file_id,
                url=url,
                filename=_filename(url, description),
                format=format_ or Path(_filename(url)).suffix.lstrip(".").upper() or "UNKNOWN",
                description=description,
                normative_status=_normative_status(description),
            )
            found[(spec.casefold(), url)] = artifact

    return sorted(found.values(), key=lambda a: (a.specification.casefold(), a.version or "", a.url))


def _manifest_records(path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _write_manifest(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def _destination(root: Path, artifact: OMGArtifact) -> Path:
    return (
        root / _slug(artifact.specification) / _slug(artifact.version or "unversioned")
        / artifact.filename
    )


def download_artifact(
    artifact: OMGArtifact,
    root: Path,
    *,
    session: requests.Session | None = None,
    max_retries: int = 3,
    timeout: tuple[int, int] = (15, 90),
) -> OMGArtifact:
    """Land one artifact, retrying transient HTTP/network failures."""
    http = session or requests.Session()
    http.headers.update({"User-Agent": USER_AGENT, "Accept": "*/*"})
    path = _destination(root, artifact)
    path.parent.mkdir(parents=True, exist_ok=True)

    # A verified existing file makes reruns resumable without another request.
    if path.is_file():
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        artifact.local_path = path.as_posix()
        artifact.sha256 = digest
        artifact.download_status = "LANDED"
        artifact.retrieved_at = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
        return artifact

    for attempt in range(1, max_retries + 1):
        try:
            response = http.get(artifact.url, timeout=timeout, allow_redirects=True)
            artifact.http_status = response.status_code
            response.raise_for_status()
            content = response.content
            content_start = content.lstrip()[:256].lower()
            if b"<meta" in content_start and (b"refresh" in content_start or b"url=" in content_start):
                raise requests.HTTPError("OMG returned an HTML redirect wrapper instead of the artifact", response=response)
            temporary = path.with_name(path.name + ".part")
            temporary.write_bytes(content)
            temporary.replace(path)
            artifact.local_path = path.as_posix()
            artifact.sha256 = hashlib.sha256(content).hexdigest()
            artifact.retrieved_at = datetime.now(timezone.utc).isoformat()
            artifact.download_status = "LANDED"
            artifact.error = None
            return artifact
        except requests.RequestException as exc:
            artifact.error = f"{type(exc).__name__}: {exc}"
            if attempt < max_retries:
                time.sleep(min(2 ** (attempt - 1), 8))
        except OSError as exc:
            artifact.error = f"{type(exc).__name__}: {exc}"
            break

    artifact.download_status = "FAILED"
    return artifact


def ingest(
    specifications: list[str] | tuple[str, ...] = DEFAULT_SPECIFICATIONS,
    output_dir: Path = Path("data/landing/omg"),
    *,
    max_retries: int = 3,
) -> list[OMGArtifact]:
    root = output_dir
    manifest = root / "manifest.json"
    artifacts = discover_artifacts(specifications)
    old_records = _manifest_records(manifest)
    records_by_key = {(row.get("specification", "").casefold(), row.get("url")): row for row in old_records}

    for artifact in artifacts:
        print(f"[{artifact.specification} {artifact.version or 'version unknown'}] {artifact.filename}")
        artifact = download_artifact(artifact, root, max_retries=max_retries)
        records_by_key[(artifact.specification.casefold(), artifact.url)] = asdict(artifact)
        _write_manifest(manifest, sorted(records_by_key.values(), key=lambda r: (str(r.get("specification", "")).casefold(), str(r.get("version") or ""), str(r.get("url", "")))))
        if artifact.download_status == "FAILED":
            print(f"  FAILED: {artifact.error}", file=sys.stderr)
        else:
            print(f"  LANDED: {artifact.local_path}")

    print(f"\nDiscovered: {len(artifacts)} artifacts; manifest: {manifest}")
    return artifacts


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover and land all files in OMG machine-readable catalogs.")
    parser.add_argument("specifications", nargs="*", help="OMG specification names (default: UML XMI SysML)")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent / "data" / "landing" / "omg")
    parser.add_argument("--retries", type=int, default=3)
    args = parser.parse_args()
    if args.retries < 1:
        parser.error("--retries must be at least 1")
    ingest(args.specifications or DEFAULT_SPECIFICATIONS, args.output_dir, max_retries=args.retries)


if __name__ == "__main__":
    main()

