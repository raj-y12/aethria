"""
Longitudinal Signal Tracker.

Tracks changes in watchlist companies using cached summaries.
Low-frequency checks only.
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import difflib

from portfolio.store import PortfolioStore
from utils.feed_fetcher import FeedFetcher


logger = logging.getLogger(__name__)


class SignalTracker:
    """
    Tracks signals for watchlist companies.
    
    Uses:
    - Cached summaries for diff comparison
    - Low-frequency checks
    - No external API calls
    """
    
    def __init__(self, portfolio_store: PortfolioStore, agent_id: str = "signal_tracker_v1"):
        """
        Initialize Signal Tracker.
        
        Args:
            portfolio_store: PortfolioStore instance
            agent_id: Agent identifier
        """
        self.store = portfolio_store
        self.agent_id = agent_id
        self.feed_fetcher = FeedFetcher()
        self.logger = logging.getLogger("signals.tracker")
    
    def check_watchlist_entries(self) -> List[str]:
        """
        Check watchlist entries due for review.
        
        Returns:
            List of signal IDs created
        """
        due_entries = self.store.get_watchlist_due_for_check()
        
        if not due_entries:
            self.logger.info("No watchlist entries due for check")
            return []
        
        self.logger.info(f"Checking {len(due_entries)} watchlist entries")
        
        signal_ids = []
        
        for entry in due_entries:
            try:
                signal_id = self._check_entry(entry)
                if signal_id:
                    signal_ids.append(signal_id)
            except Exception as e:
                self.logger.error(f"Error checking entry {entry.get('id')}: {e}")
                continue

        # Also check against external feeds
        try:
            feed_signal_ids = self.check_watchlist_with_feeds()
            signal_ids.extend(feed_signal_ids)
        except Exception as e:
            self.logger.error(f"Error checking feeds: {e}")

        return signal_ids
    
    def _check_entry(self, watchlist_entry: Dict[str, Any]) -> Optional[str]:
        """
        Check a single watchlist entry for signals.
        
        Args:
            watchlist_entry: Watchlist record
        
        Returns:
            Signal ID if signal detected, None otherwise
        """
        startup_id = watchlist_entry.get("startup_id")
        cached_summary = watchlist_entry.get("cached_summary", "")
        watchlist_id = watchlist_entry.get("id")
        
        # Get current startup record
        startup = self.store.get_startup(startup_id)
        if not startup:
            self.logger.warning(f"Startup {startup_id} not found")
            return None
        
        # Generate current summary (from startup record)
        current_summary = self._generate_summary(startup)
        
        # Compare with cached summary
        signal = self._detect_signal(cached_summary, current_summary, startup)
        
        if signal:
            # Update watchlist entry
            self.store.update_watchlist_check(
                watchlist_id=watchlist_id,
                new_summary=current_summary,
                signal_detected=signal,
            )
            
            # Create signal record
            signal_id = self.store.add_signal(
                startup_id=startup_id,
                signal_type=signal["type"],
                strength=signal["strength"],
                description=signal["description"],
                affected_confidence=signal.get("affected_confidence"),
                agent_id=self.agent_id,
            )
            
            self.logger.info(
                f"Detected {signal['type']} signal for startup {startup_id} "
                f"(strength: {signal['strength']:.2f})"
            )
            
            return signal_id
        else:
            # No signal, just update check time
            self.store.update_watchlist_check(
                watchlist_id=watchlist_id,
                new_summary=current_summary,
            )
            
            return None
    
    def _generate_summary(self, startup: Dict[str, Any]) -> str:
        """
        Generate summary from startup record for comparison.
        
        Args:
            startup: Startup record
        
        Returns:
            Summary string
        """
        # Create a stable summary from key fields
        parts = [
            startup.get("name", ""),
            startup.get("sector", ""),
            startup.get("one_line", ""),
            startup.get("problem", "")[:200],
            startup.get("solution", "")[:200],
        ]
        
        return " | ".join(parts)
    
    def _detect_signal(
        self,
        cached_summary: str,
        current_summary: str,
        startup: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Detect signal by comparing cached and current summaries.
        
        Args:
            cached_summary: Previously cached summary
            current_summary: Current summary
            startup: Startup record
        
        Returns:
            Signal dict if detected, None otherwise
        """
        if not cached_summary:
            # First check - no signal
            return None
        
        # Calculate similarity
        similarity = difflib.SequenceMatcher(
            None, cached_summary.lower(), current_summary.lower()
        ).ratio()
        
        # Detect significant changes
        if similarity < 0.85:  # More than 15% change
            # Determine direction
            if len(current_summary) > len(cached_summary) * 1.1:
                # Expanded - potentially positive
                signal_type = "positive"
                strength = min(0.7, (1.0 - similarity))
            elif len(current_summary) < len(cached_summary) * 0.9:
                # Contracted - potentially negative
                signal_type = "negative"
                strength = min(0.7, (1.0 - similarity))
            else:
                # Changed but similar length - neutral
                signal_type = "neutral"
                strength = min(0.5, (1.0 - similarity))
            
            description = (
                f"Significant change detected in startup profile "
                f"(similarity: {similarity:.2f}). "
                f"Startup: {startup.get('name', 'Unknown')}"
            )
            
            return {
                "type": signal_type,
                "strength": strength,
                "description": description,
                "affected_confidence": None,  # Could be calculated if needed
            }
        
        return None

    def check_watchlist_with_feeds(self) -> List[str]:
        """
        Check watchlist entries against external feed items.

        Returns:
            List of signal IDs created from feed matches
        """
        watchlist = self.store.get_all_watchlist()
        if not watchlist:
            return []

        try:
            feed_items = self.feed_fetcher.fetch_all()
        except Exception as e:
            self.logger.warning(f"Failed to fetch feeds: {e}")
            return []

        if not feed_items:
            return []

        signal_ids = []
        for entry in watchlist:
            startup_id = entry.get("startup_id")
            startup = self.store.get_startup(startup_id)
            if not startup:
                continue

            name = startup.get("name", "")
            sector = startup.get("sector", "")
            matches = self._match_feed_items(name, sector, feed_items)

            for match in matches:
                try:
                    signal_id = self.store.add_signal(
                        startup_id=startup_id,
                        signal_type=match.get("signal_type", "neutral"),
                        strength=0.5,
                        description=f"Feed match: {match.get('title', '')} ({match.get('source', '')})",
                        agent_id=self.agent_id,
                    )
                    signal_ids.append(signal_id)
                except Exception as e:
                    self.logger.error(f"Error adding feed signal for {startup_id}: {e}")

        return signal_ids

    def _match_feed_items(self, startup_name: str, sector: str, feed_items: List[Dict]) -> List[Dict]:
        """Match feed items against a startup by keyword overlap."""
        keywords = set()
        for word in startup_name.lower().split():
            if len(word) > 2:
                keywords.add(word)
        for word in sector.lower().split():
            if len(word) > 2:
                keywords.add(word)
        keywords -= {"the", "and", "for", "with", "inc", "ltd", "corp"}

        matches = []
        for item in feed_items:
            text = (item.get("title", "") + " " + item.get("description", "")).lower()
            overlap = sum(1 for kw in keywords if kw in text)
            if overlap >= 2:
                signal_type = "press_mention"
                source = item.get("source", "")
                if "github" in source.lower():
                    signal_type = "github_activity"
                elif "product" in source.lower():
                    signal_type = "product_launch"
                matches.append({**item, "signal_type": signal_type})
        return matches
