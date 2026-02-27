"""Discovery scheduler jobs with manual start/stop control.

Manages two periodic jobs:
1. discovery_scan — discover new source candidates
2. discovery_validate — validate pending candidates

Both can be started/stopped independently via the API.
"""

import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config.settings import settings

logger = logging.getLogger(__name__)

# Module-level state
_discovery_state: dict = {
    "running": False,
    "last_scan_at": None,
    "last_validate_at": None,
    "scan_in_progress": False,
    "validate_in_progress": False,
    "total_scans": 0,
    "total_validations": 0,
    "last_scan_result": None,
    "last_validate_result": None,
}


def get_discovery_status() -> dict:
    """Return current discovery system status."""
    return {**_discovery_state}


async def run_discovery_scan():
    """Periodic job: discover new source candidates."""
    if _discovery_state["scan_in_progress"]:
        logger.info("Discovery scan already in progress, skipping")
        return

    _discovery_state["scan_in_progress"] = True
    try:
        from discovery.engine import DiscoveryEngine

        async with DiscoveryEngine() as engine:
            result = await engine.run()

        _discovery_state["last_scan_at"] = datetime.utcnow().isoformat()
        _discovery_state["total_scans"] += 1
        _discovery_state["last_scan_result"] = {
            "candidates_found": len(result),
            "timestamp": _discovery_state["last_scan_at"],
        }
        logger.info(f"Discovery scan complete: {len(result)} new candidates")
    except Exception as e:
        logger.error(f"Discovery scan failed: {e}", exc_info=True)
        _discovery_state["last_scan_result"] = {
            "error": str(e)[:500],
            "timestamp": datetime.utcnow().isoformat(),
        }
    finally:
        _discovery_state["scan_in_progress"] = False


async def run_discovery_validate():
    """Periodic job: validate pending candidates."""
    if _discovery_state["validate_in_progress"]:
        logger.info("Discovery validation already in progress, skipping")
        return

    _discovery_state["validate_in_progress"] = True
    try:
        from discovery.validator import SourceValidator

        async with SourceValidator() as validator:
            result = await validator.validate_batch(limit=10)

        _discovery_state["last_validate_at"] = datetime.utcnow().isoformat()
        _discovery_state["total_validations"] += 1
        _discovery_state["last_validate_result"] = {
            **result,
            "timestamp": _discovery_state["last_validate_at"],
        }
        logger.info(f"Discovery validation complete: {result}")
    except Exception as e:
        logger.error(f"Discovery validation failed: {e}", exc_info=True)
        _discovery_state["last_validate_result"] = {
            "error": str(e)[:500],
            "timestamp": datetime.utcnow().isoformat(),
        }
    finally:
        _discovery_state["validate_in_progress"] = False


def register_discovery_jobs(scheduler: AsyncIOScheduler):
    """Register discovery jobs on the scheduler (paused by default)."""
    interval_hours = settings.discovery_interval_hours

    scheduler.add_job(
        run_discovery_scan,
        trigger="interval",
        hours=interval_hours,
        id="discovery_scan",
        max_instances=1,
        misfire_grace_time=600,
        replace_existing=True,
    )

    # Validation runs more frequently — every 2 hours
    scheduler.add_job(
        run_discovery_validate,
        trigger="interval",
        hours=max(1, interval_hours // 12),
        id="discovery_validate",
        max_instances=1,
        misfire_grace_time=600,
        replace_existing=True,
    )

    # Pause both if discovery is not enabled
    if not settings.discovery_enabled:
        scheduler.pause_job("discovery_scan")
        scheduler.pause_job("discovery_validate")
        logger.info("Discovery jobs registered (paused — discovery_enabled=false)")
    else:
        _discovery_state["running"] = True
        logger.info(
            f"Discovery jobs registered and running (scan every {interval_hours}h)"
        )


def start_discovery(scheduler: AsyncIOScheduler):
    """Resume discovery jobs."""
    try:
        scheduler.resume_job("discovery_scan")
        scheduler.resume_job("discovery_validate")
        _discovery_state["running"] = True
        logger.info("Discovery started")
    except Exception as e:
        logger.error(f"Failed to start discovery: {e}")
        raise


def stop_discovery(scheduler: AsyncIOScheduler):
    """Pause discovery jobs."""
    try:
        scheduler.pause_job("discovery_scan")
        scheduler.pause_job("discovery_validate")
        _discovery_state["running"] = False
        logger.info("Discovery stopped")
    except Exception as e:
        logger.error(f"Failed to stop discovery: {e}")
        raise
