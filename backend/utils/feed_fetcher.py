"""
Lightweight feed fetcher for external signal sources.
Uses only stdlib (urllib, xml.etree). Caches results for 1 hour.
"""
import json
import logging
import os
import time
import fcntl
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from utils.timeutil import utcnow
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from batch2.repository import Batch2State
from batch2.store import feed_cache_get, feed_cache_set
import env_config

logger = logging.getLogger(__name__)

CACHE_FILE = "data/portfolio/feed_cache.json"
CACHE_TTL_SECONDS = 3600  # 1 hour

RSS_FEEDS = [
    ("TechCrunch", "https://techcrunch.com/feed/"),
    ("VentureBeat", "https://venturebeat.com/feed/"),
]

GITHUB_TRENDING_URL = "https://github.com/trending"


class FeedItem:
    """A single feed item."""
    def __init__(self, title: str, description: str, url: str, source: str, fetched_at: str):
        self.title = title
        self.description = description
        self.url = url
        self.source = source
        self.fetched_at = fetched_at

    def to_dict(self) -> Dict[str, str]:
        return {
            "title": self.title,
            "description": self.description,
            "url": self.url,
            "source": self.source,
            "fetched_at": self.fetched_at,
        }


class FeedFetcher:
    """Fetches and caches external signal feeds."""

    def __init__(self, cache_file: str = CACHE_FILE, user_id: Optional[str] = None, batch2_state: Optional[Batch2State] = None):
        self.cache_path = Path(cache_file)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.user_id = (user_id or "").strip() or None
        self.batch2_state = batch2_state
        self.logger = logging.getLogger("feed_fetcher")

    def fetch_all(self) -> List[Dict[str, str]]:
        """Fetch all feeds. Returns cached results if within TTL."""
        cached = self._read_cache()
        if cached is not None:
            return cached

        items: List[Dict[str, str]] = []

        # RSS feeds
        for name, url in RSS_FEEDS:
            try:
                rss_items = self._fetch_rss(name, url)
                items.extend(rss_items)
            except Exception as e:
                self.logger.warning(f"Failed to fetch RSS from {name}: {e}")

        # GitHub trending
        try:
            gh_items = self._fetch_github_trending()
            items.extend(gh_items)
        except Exception as e:
            self.logger.warning(f"Failed to fetch GitHub trending: {e}")

        self._write_cache(items)
        return items

    def _fetch_rss(self, source_name: str, url: str) -> List[Dict[str, str]]:
        """Parse RSS feed and extract items."""
        import re
        now = utcnow().isoformat()
        req = urllib.request.Request(url, headers={"User-Agent": "Aethria/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            xml_data = resp.read()

        root = ET.fromstring(xml_data)
        items = []

        # Handle both RSS 2.0 and Atom
        for item in root.iter("item"):
            title_el = item.find("title")
            desc_el = item.find("description")
            link_el = item.find("link")
            title = title_el.text if title_el is not None and title_el.text else ""
            description = desc_el.text if desc_el is not None and desc_el.text else ""
            # Strip HTML tags from description
            description = re.sub(r"<[^>]+>", "", description)[:500]
            link = link_el.text if link_el is not None and link_el.text else ""
            if title:
                items.append({
                    "title": title,
                    "description": description,
                    "url": link,
                    "source": source_name,
                    "fetched_at": now,
                })

        self.logger.info(f"Fetched {len(items)} items from {source_name}")
        return items[:20]  # Limit per source

    def _fetch_github_trending(self) -> List[Dict[str, str]]:
        """Scrape GitHub trending page for repo names and descriptions."""
        import re
        now = utcnow().isoformat()
        req = urllib.request.Request(GITHUB_TRENDING_URL, headers={"User-Agent": "Aethria/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="replace")
        except Exception:
            return []

        items = []
        # Extract repo names and descriptions from trending page
        repo_pattern = re.compile(r'<h2[^>]*class="[^"]*lh-condensed[^"]*"[^>]*>.*?<a[^>]*href="(/[^"]+)"[^>]*>\s*(.*?)\s*</a>', re.DOTALL)
        desc_pattern = re.compile(r'<p[^>]*class="[^"]*col-9[^"]*"[^>]*>\s*(.*?)\s*</p>', re.DOTALL)

        repos = repo_pattern.findall(html)
        descs = desc_pattern.findall(html)

        for i, (path, name) in enumerate(repos[:15]):
            clean_name = re.sub(r"<[^>]+>", "", name).strip().replace("\n", "").replace("  ", " ")
            desc = re.sub(r"<[^>]+>", "", descs[i]).strip() if i < len(descs) else ""
            items.append({
                "title": clean_name or path.strip("/"),
                "description": desc[:300],
                "url": f"https://github.com{path.strip()}",
                "source": "GitHub Trending",
                "fetched_at": now,
            })

        self.logger.info(f"Fetched {len(items)} repos from GitHub Trending")
        return items

    def _read_cache(self) -> Optional[List[Dict[str, str]]]:
        """Read cache if within TTL."""
        if self.user_id and self.batch2_state is None and not env_config.local_fallback_allowed():
            raise RuntimeError("FeedFetcher: batch2_asyncpg_snapshot_required")
        if self.user_id and self.batch2_state is not None:
            row = feed_cache_get(user_id=self.user_id, state=self.batch2_state)
            if row:
                cached_at = float(row.get("cached_at") or 0)
                if time.time() - cached_at < CACHE_TTL_SECONDS:
                    items = row.get("items")
                    return items if isinstance(items, list) else []
            return None
        if not self.cache_path.exists():
            return None
        try:
            with open(self.cache_path, "r") as f:
                data = json.load(f)
            cached_at = data.get("cached_at", 0)
            if time.time() - cached_at < CACHE_TTL_SECONDS:
                return data.get("items", [])
        except (json.JSONDecodeError, IOError, KeyError):
            pass
        return None

    def _write_cache(self, items: List[Dict[str, str]]) -> None:
        """Write items to cache with timestamp."""
        if self.user_id and self.batch2_state is None and not env_config.local_fallback_allowed():
            raise RuntimeError("FeedFetcher: batch2_asyncpg_snapshot_required")
        if self.user_id and self.batch2_state is not None:
            feed_cache_set(items, user_id=self.user_id, state=self.batch2_state)
            return
        data = {"cached_at": time.time(), "items": items}
        temp_path = self.cache_path.with_suffix(".tmp")
        with open(temp_path, "w") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        temp_path.replace(self.cache_path)
