"""Source Ingestion and Normalization Engine

Deterministic normalization of URLs, content hashing, and metadata sanitization.
"""

import hashlib
import re
from datetime import datetime, timezone
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
from typing import Dict, Optional, Any


def compute_sha256(content: str) -> str:
    """Computes deterministic SHA-256 hash of UTF-8 content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def normalize_url(raw_url: Optional[str]) -> Optional[str]:
    """Normalizes URL by lowercasing scheme/netloc, stripping fragments and tracking params."""
    if not raw_url:
        return None
    url = raw_url.strip()
    if not url:
        return None
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return url

    # Lowercase netloc and scheme
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]

    # Remove tracking query parameters
    tracking_prefixes = ("utm_", "fbclid", "gclid", "ref", "mc_eid")
    query_tuples = parse_qsl(parsed.query, keep_blank_values=False)
    filtered_query = [
        (k, v) for k, v in query_tuples if not any(k.lower().startswith(p) for p in tracking_prefixes)
    ]
    new_query = urlencode(filtered_query)

    # Clean path (strip trailing slashes if not root)
    path = parsed.path
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")

    # Strip fragments for canonical identity
    return urlunparse((scheme, netloc, path, parsed.params, new_query, ""))


def normalize_source(
    raw_text: str,
    title: str,
    retrieval_date: Optional[str] = None,
    url: Optional[str] = None,
    publisher: Optional[str] = None,
    author: Optional[str] = None,
    publication_date: Optional[str] = None,
    source_type: str = "WEB",
    trust_tier: str = "UNTRUSTED_RETRIEVAL",
) -> Dict[str, Any]:
    """Cleans and constructs an immutable Source Record."""
    clean_title = re.sub(r"\s+", " ", title).strip()
    clean_publisher = re.sub(r"\s+", " ", publisher).strip() if publisher else None
    clean_author = re.sub(r"\s+", " ", author).strip() if author else None
    clean_url = normalize_url(url)
    content_hash = compute_sha256(raw_text)

    now_iso = datetime.now(timezone.utc).isoformat()
    r_date = retrieval_date.strip() if retrieval_date else now_iso

    # Deterministic source_id generation from content hash prefix
    source_id = f"src_{content_hash[:16]}"

    return {
        "source_id": source_id,
        "url": clean_url,
        "title": clean_title,
        "publisher": clean_publisher,
        "author": clean_author,
        "publication_date": publication_date.strip() if publication_date else None,
        "retrieval_date": r_date,
        "source_type": source_type,
        "trust_tier": trust_tier,
        "raw_content_sha256": content_hash,
        "created_at": now_iso,
    }
