"""
=============================================================
  SMART AI SURVEILLANCE SYSTEM
  File    : backend/app/alert_system.py
  Purpose : Centralized alert manager.

  ALL alert types funnel through here:
    AMBULANCE_DETECTED
    ACCIDENT_DETECTED
    FIRE_DETECTED      (Day 11)
    SMOKE_DETECTED     (Day 11)
    CROWD_DETECTED
    HEAVY_TRAFFIC
    CONGESTION
    LOITERING
    ZONE_ENTER
    ZONE_EXIT

  Features:
    - Per-type cooldown (ACCIDENT has no cooldown)
    - In-memory deque of last 200 alerts (for API)
    - Rotating log file  backend/logs/alerts.log
    - Severity levels: CRITICAL / HIGH / MEDIUM / INFO
    - Thread-safe
=============================================================
"""

import logging, threading, time, os, json
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum

logger = logging.getLogger("AlertSystem")

LOG_DIR  = "backend/logs"
LOG_PATH = os.path.join(LOG_DIR, "alerts.log")


class Severity(str, Enum):
    CRITICAL = "CRITICAL"   # fire, accident, ambulance
    HIGH     = "HIGH"       # crowd, loitering
    MEDIUM   = "MEDIUM"     # heavy traffic
    INFO     = "INFO"       # zone events


# Cooldown seconds per alert type (0 = no cooldown)
_COOLDOWNS: Dict[str, float] = {
    "ACCIDENT_DETECTED"  : 0,      # every accident fires
    "AMBULANCE_DETECTED" : 15.0,
    "FIRE_DETECTED"      : 0,
    "SMOKE_DETECTED"     : 5.0,
    "CROWD_DETECTED"     : 30.0,
    "HEAVY_TRAFFIC"      : 30.0,
    "CONGESTION"         : 30.0,
    "LOITERING"          : 60.0,
    "ZONE_ENTER"         : 5.0,
    "ZONE_EXIT"          : 5.0,
}

_SEVERITY: Dict[str, Severity] = {
    "ACCIDENT_DETECTED"  : Severity.CRITICAL,
    "AMBULANCE_DETECTED" : Severity.CRITICAL,
    "FIRE_DETECTED"      : Severity.CRITICAL,
    "SMOKE_DETECTED"     : Severity.HIGH,
    "CROWD_DETECTED"     : Severity.HIGH,
    "HEAVY_TRAFFIC"      : Severity.MEDIUM,
    "CONGESTION"         : Severity.MEDIUM,
    "LOITERING"          : Severity.HIGH,
    "ZONE_ENTER"         : Severity.INFO,
    "ZONE_EXIT"          : Severity.INFO,
}


@dataclass
class Alert:
    alert_id   : int
    type       : str
    severity   : Severity
    camera_id  : int
    timestamp  : float
    message    : str
    metadata   : dict = field(default_factory=dict)
    acknowledged: bool = False

    def to_dict(self) -> dict:
        return {
            "alert_id"    : self.alert_id,
            "type"        : self.type,
            "severity"    : self.severity.value,
            "camera_id"   : self.camera_id,
            "timestamp"   : self.timestamp,
            "message"     : self.message,
            "metadata"    : self.metadata,
            "acknowledged": self.acknowledged,
        }


class AlertSystem:
    """
    Singleton alert manager. Import ALERT_SYSTEM everywhere.
    """
    _instance  = None
    _init_lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    o = super().__new__(cls)
                    o._setup()
                    cls._instance = o
        return cls._instance

    def _setup(self):
        os.makedirs(LOG_DIR, exist_ok=True)
        self._alerts   : deque    = deque(maxlen=200)
        self._cooldowns: Dict[str,float] = {}
        self._counter  : int      = 0
        self._lock     = threading.Lock()
        # File logger
        fh = logging.FileHandler(LOG_PATH)
        fh.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        logging.getLogger("AlertFile").addHandler(fh)
        self._flog = logging.getLogger("AlertFile")
        logger.info("[AlertSystem] Ready.")

    def fire(
        self,
        alert_type : str,
        camera_id  : int,
        message    : str,
        metadata   : dict = None,
    ) -> Optional[Alert]:
        """
        Fire an alert. Returns Alert if it passed cooldown, else None.
        """
        cooldown = _COOLDOWNS.get(alert_type, 10.0)
        now      = time.time()
        cd_key   = f"{alert_type}::{camera_id}"

        with self._lock:
            last = self._cooldowns.get(cd_key, 0.0)
            if cooldown > 0 and (now - last) < cooldown:
                return None   # still in cooldown

            self._cooldowns[cd_key] = now
            self._counter += 1
            sev = _SEVERITY.get(alert_type, Severity.INFO)

            alert = Alert(
                alert_id  = self._counter,
                type      = alert_type,
                severity  = sev,
                camera_id = camera_id,
                timestamp = now,
                message   = message,
                metadata  = metadata or {},
            )
            self._alerts.append(alert)

        # Log to console + file
        prefix = f"[{sev.value}] [{alert_type}] Cam{camera_id}"
        logger.warning(f"{prefix} — {message}")
        self._flog.warning(json.dumps(alert.to_dict()))

        return alert

    def acknowledge(self, alert_id: int) -> bool:
        with self._lock:
            for a in self._alerts:
                if a.alert_id == alert_id:
                    a.acknowledged = True
                    return True
        return False

    def get_recent(
        self,
        limit      : int = 50,
        since      : float = 0.0,
        alert_type : str = "",
        camera_id  : int = -1,
    ) -> List[dict]:
        with self._lock:
            results = []
            for a in reversed(self._alerts):
                if a.timestamp < since: continue
                if alert_type and a.type != alert_type: continue
                if camera_id >= 0 and a.camera_id != camera_id: continue
                results.append(a.to_dict())
                if len(results) >= limit: break
        return results

    def unacknowledged_count(self) -> int:
        with self._lock:
            return sum(1 for a in self._alerts if not a.acknowledged)


# Singleton
ALERT_SYSTEM = AlertSystem()