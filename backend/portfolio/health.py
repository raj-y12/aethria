"""
System Health & Drift Detection.

Monitors system for:
- Duplicate logic
- Agent inactivity
- Runaway loops
- Memory bloat
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict
from uuid import uuid4

from portfolio.store import PortfolioStore
from analytics.clustering import ClusterAnalyzer


logger = logging.getLogger(__name__)


class HealthMonitor:
    """
    Monitors system health and detects drift.
    """
    
    def __init__(self, portfolio_store: PortfolioStore, discovery_storage=None):
        """
        Initialize Health Monitor.
        
        Args:
            portfolio_store: PortfolioStore instance
            discovery_storage: Optional Storage instance for queue depth checks
        """
        self.store = portfolio_store
        self.discovery_storage = discovery_storage
        uid = (getattr(portfolio_store, "_tenant_user_id", None) or "").strip() or "local_health"
        self.cluster_analyzer = ClusterAnalyzer(user_id=uid)
        self.logger = logging.getLogger("health.monitor")
        self.health_records = []  # In-memory cache
    
    def check_health(self) -> List[str]:
        """
        Run all health checks.
        
        Returns:
            List of health record IDs created
        """
        record_ids = []
        
        # Check for duplicates
        duplicate_id = self._check_duplicates()
        if duplicate_id:
            record_ids.append(duplicate_id)
        
        # Check for inactivity
        inactivity_id = self._check_inactivity()
        if inactivity_id:
            record_ids.append(inactivity_id)
        
        # Check for memory bloat
        bloat_id = self._check_memory_bloat()
        if bloat_id:
            record_ids.append(bloat_id)
        
        # Check queue depths
        queue_id = self._check_queue_depths()
        if queue_id:
            record_ids.append(queue_id)

        # Run cluster analysis
        self._run_cluster_analysis()

        return record_ids
    
    def _check_duplicates(self) -> Optional[str]:
        """Check for duplicate startup records."""
        startups = self.store.get_all_startups()
        
        # Group by name (simple duplicate detection)
        by_name = defaultdict(list)
        for startup in startups:
            name = startup.get("name", "").lower().strip()
            if name:
                by_name[name].append(startup)
        
        duplicates = {name: items for name, items in by_name.items() if len(items) > 1}
        
        if duplicates:
            severity = "medium" if len(duplicates) < 5 else "high"
            description = f"Found {len(duplicates)} duplicate startup names: {list(duplicates.keys())[:5]}"
            
            self.logger.warning(description)
            
            # Could create health record here if we had a store method
            # For now, just log
            return None
        
        return None
    
    def _check_inactivity(self) -> Optional[str]:
        """Check for agent inactivity."""
        decisions = self.store.get_all_decisions()
        
        if not decisions:
            return None
        
        # Get most recent decision
        most_recent = max(
            decisions,
            key=lambda d: d.get("decided_at", ""),
            default=None
        )
        
        if not most_recent:
            return None
        
        last_decision_time = datetime.fromisoformat(most_recent.get("decided_at", ""))
        hours_since = (datetime.now() - last_decision_time).total_seconds() / 3600
        
        if hours_since > 24:  # No decisions in 24 hours
            severity = "low" if hours_since < 48 else "medium" if hours_since < 72 else "high"
            description = f"No partner decisions in {hours_since:.1f} hours"
            
            self.logger.warning(description)
            return None
        
        return None
    
    def _check_queue_depths(self) -> Optional[str]:
        """Check queue depths from discovery storage for backpressure awareness."""
        if not self.discovery_storage:
            return None
        try:
            unreviewed = self.discovery_storage.count_unreviewed()
            undecided = self.discovery_storage.count_undecided()
            watchlist_count = len(self.store.get_all_watchlist()) if hasattr(self.store, 'get_all_watchlist') else 0
            self.logger.info(
                f"Queue depths - unreviewed: {unreviewed}, undecided: {undecided}, watchlist: {watchlist_count}"
            )
            if unreviewed > 20 or undecided > 20:
                self.logger.warning(
                    f"High queue depth detected - unreviewed: {unreviewed}, undecided: {undecided}"
                )
        except Exception as e:
            self.logger.warning(f"Could not check queue depths: {e}")
        return None

    def _run_cluster_analysis(self) -> None:
        """Run sector clustering analysis on discovery storage data."""
        if not self.discovery_storage:
            return
        try:
            all_startups = self.discovery_storage.get_all()
            result = self.cluster_analyzer.analyze(all_startups)
            oversaturated = self.cluster_analyzer.get_oversaturated_sectors()
            if oversaturated:
                self.logger.warning(f"Oversaturated sectors: {oversaturated}")
        except Exception as e:
            self.logger.warning(f"Cluster analysis failed: {e}")

    def _check_memory_bloat(self) -> Optional[str]:
        """Check for memory bloat in JSON files."""
        file_sizes = {}
        for file_key, file_path in self.store.files.items():
            if file_path.exists():
                size_mb = file_path.stat().st_size / (1024 * 1024)
                file_sizes[file_key] = size_mb
        
        # Check for large files
        large_files = {k: v for k, v in file_sizes.items() if v > 10}  # > 10MB
        
        if large_files:
            severity = "medium" if max(file_sizes.values()) < 50 else "high"
            description = f"Large files detected: {large_files}"
            
            self.logger.warning(description)
            return None
        
        return None
