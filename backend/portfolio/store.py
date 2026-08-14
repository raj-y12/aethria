"""
Portfolio Store - Authoritative Memory Layer.

Append-only, versioned storage for all portfolio data.
Uses Supabase when ``USE_SUPABASE_STORAGE=1`` and local JSON files only in
explicit local/dev mode. Remote failures are surfaced to the caller.
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from utils.timeutil import utcnow, ensure_aware
from uuid import uuid4
import fcntl
import os

from tenant_context import require_user_id
from batch2.context import get_state as get_batch2_state
from batch1.context import get_state as get_batch1_state
from batch2.repository import Batch2State
from batch2.store import metric_append, metrics_get_all
from batch3.context import get_state as get_batch3_state
from batch3.repository import Batch3State
from batch3.store import list_get_all as batch3_list_get_all, list_replace as batch3_list_replace, list_upsert as batch3_list_upsert
import env_config
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
from portfolio.canonical_projection import canonical_startup_record


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
    
    def __init__(
        self,
        data_dir: str = "data/portfolio",
        user_id: Optional[str] = None,
        batch2_state: Optional[Batch2State] = None,
        canonical_startups: Optional[List[Dict[str, Any]]] = None,
        legacy_startup_aliases: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize portfolio store.

        Args:
            data_dir: Directory for portfolio JSON fallback files
            user_id: Tenant user id for Supabase-backed operations.
        """
        self.data_dir = Path(data_dir)
        self.logger = logging.getLogger("portfolio.store")
        explicit_uid = user_id.strip() if user_id and user_id.strip() else None
        postgres_configured = bool(
            explicit_uid and (get_batch1_state() is not None or env_config.is_production_env())
        )
        if not env_config.local_fallback_allowed() and not postgres_configured:
            raise RuntimeError(
                "PortfolioStore: local_storage_disabled_in_production; "
                "configure the shared PostgreSQL repository or explicitly use a non-production environment"
            )
        self._tenant_user_id = explicit_uid
        self._canonical_startups = {
            str(row.get("startup_id")): canonical_startup_record(row)
            for row in (canonical_startups or [])
            if isinstance(row, dict) and row.get("startup_id")
        } if canonical_startups is not None else None
        self._legacy_startup_aliases = {
            str(legacy): str(canonical)
            for legacy, canonical in (legacy_startup_aliases or {}).items()
            if str(legacy).strip() and str(canonical).strip()
        }
        self.batch2_state = batch2_state or get_batch2_state()
        self.batch3_state = get_batch3_state()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # File paths (fallback mode only)
        self.files = {
            "startups": self.data_dir / "startups.json",
            "decisions": self.data_dir / "decisions.json",
            "portfolio": self.data_dir / "portfolio.json",
            "rejections": self.data_dir / "rejections.json",
            "watchlist": self.data_dir / "watchlist.json",
            "signals": self.data_dir / "signals.json",
            "agent_metrics": self.data_dir / "agent_metrics.json",
        }
        self._supabase_tables: Dict[str, str] = {}

        # Initialize local files only in explicit local/dev mode.
        if env_config.local_fallback_allowed():
            for p in self.files.values():
                if not p.exists():
                    self._write_local_file(p, [])

    def _using_postgres(self) -> bool:
        return (
            get_batch1_state() is not None or env_config.is_production_env()
        ) and bool(self._tenant_user_id)

    # Compatibility name for isolated tests and old imports.
    def _using_supabase(self) -> bool:
        return self._using_postgres()

    def _supabase_uid(self) -> str:
        return require_user_id(self._tenant_user_id, context="PortfolioStore")

    def _file_key_for_path(self, file_path: Path) -> Optional[str]:
        for k, p in self.files.items():
            if p == file_path:
                return k
        return None

    def _read_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Read from Supabase (preferred) or JSON fallback."""
        file_key = self._file_key_for_path(file_path)
        if file_key == "agent_metrics" and self.batch2_state is not None:
            return metrics_get_all(user_id=self._supabase_uid(), state=self.batch2_state)
        if file_key in {"decisions", "portfolio", "rejections", "watchlist", "signals"} and self.batch3_state is not None:
            table = {"decisions": "portfolio_decisions", "portfolio": "portfolio_positions", "rejections": "portfolio_rejections", "watchlist": "portfolio_watchlist", "signals": "portfolio_signals"}[file_key]
            return batch3_list_get_all(table, user_id=self._supabase_uid(), state=self.batch3_state)
        if file_key == "startups" and self._using_postgres():
            raise RuntimeError("PortfolioStore: canonical_startup_snapshot_unavailable")
        if not env_config.local_fallback_allowed():
            raise RuntimeError(
                "PortfolioStore: local_storage_disabled; remote storage is required"
            )
        return self._read_local_file(file_path)

    def _read_local_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Read JSON file fallback."""
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
        """
        Write complete collection.
        In Supabase mode, upserts by id for mapped list tables and startups.
        """
        file_key = self._file_key_for_path(file_path)
        if file_key == "agent_metrics" and self.batch2_state is not None:
            self.batch2_state.replace_metrics(data)
            return
        if file_key in {"decisions", "portfolio", "rejections", "watchlist", "signals"} and self.batch3_state is not None:
            table = {"decisions": "portfolio_decisions", "portfolio": "portfolio_positions", "rejections": "portfolio_rejections", "watchlist": "portfolio_watchlist", "signals": "portfolio_signals"}[file_key]
            batch3_list_replace(table, data, user_id=self._supabase_uid(), state=self.batch3_state)
            return
        if file_key == "startups":
            raise RuntimeError("PortfolioStore: startup_persistence_owned_by_StartupRepository")
        self._write_local_file(file_path, data)

    def _write_local_file(self, file_path: Path, data: List[Dict[str, Any]]):
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
                    except Exception as e:
                        self.logger.debug("Temp file cleanup failed: %s", e)
    
    def _append_record(self, file_key: str, record: Dict[str, Any]) -> str:
        """
        Append or update a record (Supabase or file).
        """
        record_id = record.get("id") or str(uuid4())
        record = dict(record)
        record["id"] = record_id

        table = self._supabase_tables.get(file_key)
        if file_key in {"decisions", "portfolio", "rejections", "watchlist", "signals"} and self.batch3_state is not None:
            table = {"decisions": "portfolio_decisions", "portfolio": "portfolio_positions", "rejections": "portfolio_rejections", "watchlist": "portfolio_watchlist", "signals": "portfolio_signals"}[file_key]
            return batch3_list_upsert(table, record, user_id=self._supabase_uid(), state=self.batch3_state)
        if file_key == "agent_metrics" and self.batch2_state is not None:
            return metric_append(record, user_id=self._supabase_uid(), state=self.batch2_state)
        if file_key == "startups":
            raise RuntimeError("PortfolioStore: startup_persistence_owned_by_StartupRepository")
        if not env_config.local_fallback_allowed():
            raise RuntimeError(
                "PortfolioStore: local_storage_disabled; remote storage is required"
            )
        file_path = self.files[file_key]
        records = self._read_file(file_path)
        existing_idx = next((i for i, r in enumerate(records) if r.get("id") == record_id), None)
        if existing_idx is not None:
            record["version"] = records[existing_idx].get("version", 0) + 1
            records[existing_idx] = record
            self.logger.info(f"Updated {file_key} record {record_id} to version {record['version']}")
        else:
            record["version"] = 1
            records.append(record)
            self.logger.info(f"Added new {file_key} record {record_id}")
        self._write_local_file(file_path, records)
        return record_id
    
    # Startup methods
    def add_startup(self, scout_output: Dict[str, Any], agent_id: str = "scout_v1") -> str:
        """Compatibility no-op; canonical startup creation belongs to StartupRepository."""
        del agent_id
        startup_id = str(scout_output.get("startup_id") or scout_output.get("id") or "").strip()
        return self._legacy_startup_aliases.get(startup_id, startup_id)
    
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
            # PartnerOutput already uses canonical YES/NO/MAYBE. Default to NO for safety.
            "decision": partner_output.get("decision", "NO"),
            "confidence": partner_output.get("confidence", 0),
            "rationale": partner_output.get("rationale", ""),
            "next_action": partner_output.get("next_action", ""),
            "human_review_required": partner_output.get("human_review_required", False),
            "partner_agent_id": agent_id,
            "decided_at": utcnow().isoformat(),
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
            "accepted_at": utcnow().isoformat(),
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
            "rejected_at": utcnow().isoformat(),
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
        now = utcnow()
        
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
                record["last_checked_at"] = utcnow().isoformat()
                record["cached_summary"] = new_summary
                from datetime import timedelta
                interval = record.get("check_interval_days", 30)
                next_check = utcnow() + timedelta(days=interval)
                record["next_check_at"] = next_check.isoformat()
                record["version"] = record.get("version", 1) + 1
                if self.batch3_state is not None:
                    batch3_list_upsert(
                        "portfolio_watchlist", record,
                        user_id=self._supabase_uid(), state=self.batch3_state,
                    )
                else:
                    records[i] = record
                    self._write_local_file(self.files["watchlist"], records)
                return
        raise ValueError(f"Watchlist record {watchlist_id} not found")

    def update_watchlist_fields(self, watchlist_id: str, patch: Dict[str, Any]) -> bool:
        """Update one watchlist record only when the requested fields changed."""
        records = self.get_all_watchlist()
        for index, record in enumerate(records):
            if record.get("id") != watchlist_id:
                continue
            if all(record.get(key) == value for key, value in patch.items()):
                return False
            updated = dict(record)
            updated.update(patch)
            updated["version"] = int(record.get("version") or 0) + 1
            if self.batch3_state is not None:
                batch3_list_upsert(
                    "portfolio_watchlist", updated,
                    user_id=self._supabase_uid(), state=self.batch3_state,
                )
            else:
                records[index] = updated
                self._write_local_file(self.files["watchlist"], records)
            return True
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
            "detected_at": utcnow().isoformat(),
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
            "calculated_at": utcnow().isoformat(),
            "period_start": period_start,
            "period_end": period_end,
            "sample_size": sample_size,
            "version": 1,
        }
        
        return self._append_record("agent_metrics", record)
    
    # Query methods
    def get_startup(self, startup_id: str) -> Optional[Dict[str, Any]]:
        """Get startup by ID."""
        requested = str(startup_id or "").strip()
        if self._canonical_startups is not None:
            canonical_id = self._legacy_startup_aliases.get(requested, requested)
            record = self._canonical_startups.get(canonical_id)
            return dict(record) if record is not None else None
        records = self._read_file(self.files["startups"])
        for record in records:
            if record.get("id") == startup_id:
                return record
        return None
    
    def get_watchlist_due_for_check(self) -> List[Dict[str, Any]]:
        """Get watchlist entries due for check."""
        records = self._read_file(self.files["watchlist"])
        now = utcnow()
        
        due = []
        for record in records:
            next_check_str = record.get("next_check_at")
            if next_check_str:
                next_check = ensure_aware(datetime.fromisoformat(next_check_str))
                if next_check <= now:
                    due.append(record)
        
        return due
    
    def get_all_startups(self) -> List[Dict[str, Any]]:
        """Get all startups."""
        if self._canonical_startups is not None:
            return [dict(record) for record in self._canonical_startups.values()]
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

    def get_all_signals(self) -> List[Dict[str, Any]]:
        """Get all signal records through the configured storage backend."""
        return self._read_file(self.files["signals"])
