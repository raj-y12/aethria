"""
Portfolio Store - Authoritative Memory Layer.

Append-only, versioned storage for all portfolio data.
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from uuid import uuid4
import fcntl
import os

from portfolio.schemas import (
    StartupRecord,
    DecisionRecord,
    PortfolioRecord,
    RejectionRecord,
    WatchlistRecord,
    SignalRecord,
    AgentMetric,
    SystemHealthRecord,
)


logger = logging.getLogger(__name__)


class PortfolioStore:
    """
    Append-only portfolio memory store.
    
    Files:
    - startups.json: All discovered startups (canonical)
    - decisions.json: Partner decisions
    - portfolio.json: Accepted companies
    - rejections.json: Rejected companies
    - watchlist.json: Watchlist companies
    - signals.json: Signal updates
    - agent_metrics.json: Agent performance metrics
    """
    
    def __init__(self, data_dir: str = "data/portfolio"):
        """
        Initialize portfolio store.
        
        Args:
            data_dir: Directory for portfolio JSON files
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger("portfolio.store")
        
        # File paths
        self.files = {
            "startups": self.data_dir / "startups.json",
            "decisions": self.data_dir / "decisions.json",
            "portfolio": self.data_dir / "portfolio.json",
            "rejections": self.data_dir / "rejections.json",
            "watchlist": self.data_dir / "watchlist.json",
            "signals": self.data_dir / "signals.json",
            "agent_metrics": self.data_dir / "agent_metrics.json",
        }
        
        # Initialize all files
        for file_path in self.files.values():
            if not file_path.exists():
                self._write_file(file_path, [])
    
    def _read_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Read and parse JSON file. Thread-safe."""
        max_retries = 5
        for attempt in range(max_retries):
            try:
                with open(file_path, 'r') as f:
                    try:
                        fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                        data = json.load(f)
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                        return data if isinstance(data, list) else []
                    except (OSError, IOError):
                        data = json.load(f)
                        return data if isinstance(data, list) else []
            except (json.JSONDecodeError, IOError) as e:
                if attempt == max_retries - 1:
                    raise
                import time
                time.sleep(0.1 * (attempt + 1))
        raise ValueError("Failed to read file after retries")
    
    def _write_file(self, file_path: Path, data: List[Dict[str, Any]]):
        """Write JSON file atomically. Thread-safe."""
        temp_path = file_path.with_suffix('.tmp')
        
        max_retries = 5
        for attempt in range(max_retries):
            try:
                with open(temp_path, 'w') as f:
                    try:
                        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                        json.dump(data, f, indent=2)
                        f.flush()
                        os.fsync(f.fileno())
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                    except (OSError, IOError):
                        json.dump(data, f, indent=2)
                        f.flush()
                        os.fsync(f.fileno())
                
                temp_path.replace(file_path)
                return
            except (IOError, OSError) as e:
                if attempt == max_retries - 1:
                    raise
                import time
                time.sleep(0.1 * (attempt + 1))
                if temp_path.exists():
                    try:
                        temp_path.unlink()
                    except:
                        pass
    
    def _append_record(self, file_key: str, record: Dict[str, Any]) -> str:
        """
        Append a record to a file (append-only, versioned).
        
        Args:
            file_key: Key in self.files dict
            record: Record dict (must have 'id' field)
        
        Returns:
            Record ID
        """
        file_path = self.files[file_key]
        records = self._read_file(file_path)
        
        # Check if record exists - if so, create new version
        record_id = record.get("id")
        if not record_id:
            record_id = str(uuid4())
            record["id"] = record_id
        
        # Find existing record with same ID
        existing_idx = None
        for i, r in enumerate(records):
            if r.get("id") == record_id:
                existing_idx = i
                break
        
        if existing_idx is not None:
            # Update existing record (versioned update)
            existing = records[existing_idx]
            current_version = existing.get("version", 0)
            record["version"] = current_version + 1
            records[existing_idx] = record
            self.logger.info(f"Updated {file_key} record {record_id} to version {record['version']}")
        else:
            # New record
            record["version"] = 1
            records.append(record)
            self.logger.info(f"Added new {file_key} record {record_id}")
        
        self._write_file(file_path, records)
        return record_id
    
    # Startup methods
    def add_startup(self, scout_output: Dict[str, Any], agent_id: str = "scout_v1") -> str:
        """Add a startup to canonical record."""
        startup_id = scout_output.get("id", str(uuid4()))
        
        record: StartupRecord = {
            "id": startup_id,
            "name": scout_output.get("name", ""),
            "one_line": scout_output.get("one_line", ""),
            "sector": scout_output.get("sector", ""),
            "problem": scout_output.get("problem", ""),
            "solution": scout_output.get("solution", ""),
            "target_users": scout_output.get("target_users", ""),
            "why_now": scout_output.get("why_now", ""),
            "scout_type": scout_output.get("scout_type", ""),
            "scout_confidence": scout_output.get("confidence", 0.0),
            "discovered_at": datetime.now().isoformat(),
            "version": 1,
            "metadata": {
                "agent_id": agent_id,
                "source": "scout",
            },
        }
        
        return self._append_record("startups", record)
    
    # Decision methods
    def add_decision(
        self,
        startup_id: str,
        partner_output: Dict[str, Any],
        agent_id: str = "partner_v1",
    ) -> str:
        """Add a partner decision."""
        decision_id = str(uuid4())
        
        record: DecisionRecord = {
            "id": decision_id,
            "startup_id": startup_id,
            "decision": partner_output.get("decision", "PASS"),
            "confidence": partner_output.get("confidence", 0),
            "rationale": partner_output.get("rationale", ""),
            "next_action": partner_output.get("next_action", ""),
            "human_review_required": partner_output.get("human_review_required", False),
            "partner_agent_id": agent_id,
            "decided_at": datetime.now().isoformat(),
            "version": 1,
        }
        
        return self._append_record("decisions", record)
    
    # Portfolio methods
    def add_to_portfolio(
        self,
        startup_id: str,
        decision_id: str,
        key_risks: List[str],
        follow_up_triggers: List[str],
        agent_id: str = "execution_v1",
    ) -> str:
        """Add accepted company to portfolio."""
        portfolio_id = str(uuid4())
        
        record: PortfolioRecord = {
            "id": portfolio_id,
            "startup_id": startup_id,
            "decision_id": decision_id,
            "accepted_at": datetime.now().isoformat(),
            "status": "active",
            "key_risks": key_risks,
            "follow_up_triggers": follow_up_triggers,
            "execution_agent_id": agent_id,
            "version": 1,
            "metadata": {},
        }
        
        return self._append_record("portfolio", record)
    
    # Rejection methods
    def add_rejection(
        self,
        startup_id: str,
        decision_id: str,
        reason_code: str,
        rationale: str,
        key_risks: List[str],
        agent_id: str = "execution_v1",
    ) -> str:
        """Add rejected company."""
        rejection_id = str(uuid4())
        
        record: RejectionRecord = {
            "id": rejection_id,
            "startup_id": startup_id,
            "decision_id": decision_id,
            "rejected_at": datetime.now().isoformat(),
            "reason_code": reason_code,
            "rationale": rationale,
            "key_risks": key_risks,
            "execution_agent_id": agent_id,
            "version": 1,
        }
        
        return self._append_record("rejections", record)
    
    # Watchlist methods
    def add_to_watchlist(
        self,
        startup_id: str,
        decision_id: str,
        check_interval_days: int = 30,
        cached_summary: str = "",
        agent_id: str = "execution_v1",
    ) -> str:
        """Add company to watchlist."""
        watchlist_id = str(uuid4())
        now = datetime.now()
        
        from datetime import timedelta
        next_check = now + timedelta(days=check_interval_days)
        
        record: WatchlistRecord = {
            "id": watchlist_id,
            "startup_id": startup_id,
            "decision_id": decision_id,
            "added_at": now.isoformat(),
            "last_checked_at": None,
            "check_interval_days": check_interval_days,
            "next_check_at": next_check.isoformat(),
            "cached_summary": cached_summary,
            "execution_agent_id": agent_id,
            "version": 1,
        }
        
        return self._append_record("watchlist", record)
    
    def update_watchlist_check(
        self,
        watchlist_id: str,
        new_summary: str,
        signal_detected: Optional[Dict[str, Any]] = None,
    ):
        """Update watchlist entry after check."""
        records = self._read_file(self.files["watchlist"])
        
        for i, record in enumerate(records):
            if record.get("id") == watchlist_id:
                record["last_checked_at"] = datetime.now().isoformat()
                record["cached_summary"] = new_summary
                
                # Update next check time
                from datetime import timedelta
                interval = record.get("check_interval_days", 30)
                next_check = datetime.now() + timedelta(days=interval)
                record["next_check_at"] = next_check.isoformat()
                
                # Increment version
                record["version"] = record.get("version", 1) + 1
                
                records[i] = record
                self._write_file(self.files["watchlist"], records)
                return
        
        raise ValueError(f"Watchlist record {watchlist_id} not found")
    
    # Signal methods
    def add_signal(
        self,
        startup_id: str,
        signal_type: str,
        strength: float,
        description: str,
        affected_confidence: Optional[float] = None,
        agent_id: str = "signal_tracker_v1",
    ) -> str:
        """Add a signal update."""
        signal_id = str(uuid4())
        
        record: SignalRecord = {
            "id": signal_id,
            "startup_id": startup_id,
            "signal_type": signal_type,
            "strength": strength,
            "description": description,
            "detected_at": datetime.now().isoformat(),
            "affected_confidence": affected_confidence,
            "tracker_agent_id": agent_id,
            "version": 1,
        }
        
        return self._append_record("signals", record)
    
    # Agent metrics methods
    def add_agent_metric(
        self,
        agent_id: str,
        agent_type: str,
        metric_name: str,
        metric_value: float,
        period_start: str,
        period_end: str,
        sample_size: int,
    ) -> str:
        """Add agent performance metric."""
        metric_id = str(uuid4())
        
        record: AgentMetric = {
            "id": metric_id,
            "agent_id": agent_id,
            "agent_type": agent_type,
            "metric_name": metric_name,
            "metric_value": metric_value,
            "calculated_at": datetime.now().isoformat(),
            "period_start": period_start,
            "period_end": period_end,
            "sample_size": sample_size,
            "version": 1,
        }
        
        return self._append_record("agent_metrics", record)
    
    # Query methods
    def get_startup(self, startup_id: str) -> Optional[Dict[str, Any]]:
        """Get startup by ID."""
        records = self._read_file(self.files["startups"])
        for record in records:
            if record.get("id") == startup_id:
                return record
        return None
    
    def get_watchlist_due_for_check(self) -> List[Dict[str, Any]]:
        """Get watchlist entries due for check."""
        records = self._read_file(self.files["watchlist"])
        now = datetime.now()
        
        due = []
        for record in records:
            next_check_str = record.get("next_check_at")
            if next_check_str:
                next_check = datetime.fromisoformat(next_check_str)
                if next_check <= now:
                    due.append(record)
        
        return due
    
    def get_all_startups(self) -> List[Dict[str, Any]]:
        """Get all startups."""
        return self._read_file(self.files["startups"])
    
    def get_all_decisions(self) -> List[Dict[str, Any]]:
        """Get all decisions."""
        return self._read_file(self.files["decisions"])
    
    def get_all_portfolio(self) -> List[Dict[str, Any]]:
        """Get all portfolio companies."""
        return self._read_file(self.files["portfolio"])
    
    def get_all_rejections(self) -> List[Dict[str, Any]]:
        """Get all rejections."""
        return self._read_file(self.files["rejections"])
    
    def get_all_watchlist(self) -> List[Dict[str, Any]]:
        """Get all watchlist companies."""
        return self._read_file(self.files["watchlist"])
