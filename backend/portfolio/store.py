"""
Portfolio Store - Authoritative Memory Layer.

Append-only, versioned storage for all portfolio data.
Uses Supabase when configured (including startups via portfolio_startups);
falls back to local JSON files only when Supabase is unavailable.
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
from supabase_doc_store import list_get_all, list_get_by_id, list_upsert
from supabase_client import get_service_client
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
    
    def __init__(self, data_dir: str = "data/portfolio", user_id: Optional[str] = None):
        """
        Initialize portfolio store.

        Args:
            data_dir: Directory for portfolio JSON fallback files
            user_id: Tenant user id for Supabase-backed operations.
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger("portfolio.store")
        explicit_uid = user_id.strip() if user_id and user_id.strip() else None
        env_uid = os.getenv("AETHRIA_AGENT_USER_ID", "").strip() or None
        # Prefer explicit user_id; fall back to process-level tenant id for agent workers.
        self._tenant_user_id = explicit_uid or env_uid
        
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
        self._supabase_tables = {
            "startups": "portfolio_startups",
            "decisions": "portfolio_decisions",
            "portfolio": "portfolio_positions",
            "rejections": "portfolio_rejections",
            "watchlist": "portfolio_watchlist",
            "signals": "portfolio_signals",
            "agent_metrics": "portfolio_agent_metrics",
        }

        # Initialize fallback files only when needed.
        for p in self.files.values():
            if not p.exists():
                self._write_local_file(p, [])

    def _is_supabase_configured(self) -> bool:
        return bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

    def _using_supabase(self) -> bool:
        # Supabase-first behavior; fallback only when credentials or tenant are missing.
        return self._is_supabase_configured() and bool(self._tenant_user_id)

    def _supabase_uid(self) -> str:
        return require_user_id(self._tenant_user_id, context="PortfolioStore")

    def _supabase_client(self):
        return get_service_client()

    def _file_key_for_path(self, file_path: Path) -> Optional[str]:
        for k, p in self.files.items():
            if p == file_path:
                return k
        return None

    def _row_to_startup_record(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize portfolio_startups row into StartupRecord shape used by portfolio layer."""
        return {
            "id": row.get("id") or row.get("startup_id") or "",
            "startup_id": row.get("startup_id") or row.get("id") or "",
            "name": row.get("name") or "",
            "one_line": row.get("one_line") or "",
            "sector": row.get("sector") or "",
            "problem": row.get("problem") or "",
            "solution": row.get("solution") or "",
            "target_users": row.get("target_users") or "",
            "why_now": row.get("why_now") or "",
            "scout_type": row.get("scout_type") or "",
            "scout_confidence": row.get("scout_confidence") or 0.0,
            "discovered_at": row.get("discovered_at") or "",
            "version": row.get("version") or 1,
            "metadata": row.get("metadata") if isinstance(row.get("metadata"), dict) else {},
        }

    def _startup_record_to_row(self, record: Dict[str, Any]) -> Dict[str, Any]:
        rid = record.get("id") or record.get("startup_id") or str(uuid4())
        return {
            "id": rid,
            "user_id": self._supabase_uid(),
            "startup_id": record.get("startup_id") or rid,
            "name": record.get("name", ""),
            "one_line": record.get("one_line", ""),
            "sector": record.get("sector", ""),
            "problem": record.get("problem", ""),
            "solution": record.get("solution", ""),
            "target_users": record.get("target_users", ""),
            "why_now": record.get("why_now", ""),
            "scout_type": record.get("scout_type", ""),
            "scout_confidence": record.get("scout_confidence", 0.0),
            "discovered_at": record.get("discovered_at") or utcnow().isoformat(),
            "version": int(record.get("version") or 1),
            "metadata": record.get("metadata") if isinstance(record.get("metadata"), dict) else {},
        }

    def _get_startups_supabase(self) -> List[Dict[str, Any]]:
        try:
            uid = self._supabase_uid()
            r = (
                self._supabase_client()
                .table(self._supabase_tables["startups"])
                .select("*")
                .eq("user_id", uid)
                .order("discovered_at")
                .execute()
            )
            rows = (r.data or []) if hasattr(r, "data") else []
            return [self._row_to_startup_record(row) for row in rows if isinstance(row, dict)]
        except Exception as e:
            self.logger.warning("Supabase startups read failed; using local fallback: %s", e)
            return self._read_local_file(self.files["startups"])

    def _duplicate_startup_id_supabase(self, name: str) -> Optional[str]:
        """Return the id of an existing portfolio startup with the same (case-insensitive)
        name, or None. Targeted query — does NOT download the whole table (the old
        name-dedup re-fetched every row on every insert, an O(n) egress hit per add).
        """
        new_name = (name or "").strip()
        if not new_name:
            return None
        try:
            uid = self._supabase_uid()
            # ILIKE does the case-insensitive match; escape LIKE metacharacters so a
            # name containing % or _ matches literally, then confirm exact equality.
            pattern = new_name.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            r = (
                self._supabase_client()
                .table(self._supabase_tables["startups"])
                .select("id,name")
                .eq("user_id", uid)
                .ilike("name", pattern)
                .limit(5)
                .execute()
            )
            rows = (r.data or []) if hasattr(r, "data") else []
            target = new_name.lower()
            for row in rows:
                if isinstance(row, dict) and (row.get("name") or "").strip().lower() == target:
                    return row.get("id")
        except Exception as e:
            self.logger.warning("Supabase duplicate-name check failed; allowing add: %s", e)
        return None

    def _upsert_startup_supabase(self, record: Dict[str, Any]) -> str:
        uid = self._supabase_uid()
        row = self._startup_record_to_row(record)
        rid = row["id"]
        existing = (
            self._supabase_client()
            .table(self._supabase_tables["startups"])
            .select("id,version")
            .eq("user_id", uid)
            .eq("id", rid)
            .limit(1)
            .execute()
        )
        existing_rows = (existing.data or []) if hasattr(existing, "data") else []
        if existing_rows:
            row["version"] = int(existing_rows[0].get("version") or 1) + 1
            self.logger.info("Updated startups record %s to version %s", rid, row["version"])
        else:
            row["version"] = int(record.get("version") or 1)
            self.logger.info("Added new startups record %s", rid)

        self._supabase_client().table(self._supabase_tables["startups"]).upsert(
            row,
            on_conflict="id",
        ).execute()
        return rid

    def _read_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Read from Supabase (preferred) or JSON fallback."""
        file_key = self._file_key_for_path(file_path)
        table = self._supabase_tables.get(file_key) if file_key else None
        if table and self._using_supabase():
            if file_key == "startups":
                return self._get_startups_supabase()
            return list_get_all(table, user_id=self._supabase_uid())
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
        table = self._supabase_tables.get(file_key) if file_key else None
        if table and self._using_supabase():
            if file_key == "startups":
                for rec in data:
                    self._upsert_startup_supabase(rec)
                return
            uid = self._supabase_uid()
            for rec in data:
                list_upsert(table, rec, user_id=uid)
            return
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
        if table and self._using_supabase():
            if file_key == "startups":
                return self._upsert_startup_supabase(record)
            uid = self._supabase_uid()
            existing = list_get_by_id(table, record_id, user_id=uid)
            if existing is not None:
                record["version"] = existing.get("version", 0) + 1
                self.logger.info(f"Updated {file_key} record {record_id} to version {record['version']}")
            else:
                record["version"] = 1
                self.logger.info(f"Added new {file_key} record {record_id}")
            list_upsert(table, record, user_id=uid)
            return record_id

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
            "discovered_at": utcnow().isoformat(),
            "version": 1,
            "metadata": {
                "agent_id": agent_id,
                "source": "scout",
            },
        }
        
        if self._using_supabase():
            # Legacy duplicate protection for name-based duplicates — targeted query,
            # not a full-table scan.
            dup_id = self._duplicate_startup_id_supabase(record.get("name") or "")
            if dup_id:
                self.logger.info("Duplicate company name detected in Supabase; skipping add: %s", record.get("name"))
                return dup_id or startup_id
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
                if self._using_supabase() and self._supabase_tables.get("watchlist"):
                    list_upsert(
                        self._supabase_tables["watchlist"],
                        record,
                        user_id=self._supabase_uid(),
                    )
                else:
                    records[i] = record
                    self._write_local_file(self.files["watchlist"], records)
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
