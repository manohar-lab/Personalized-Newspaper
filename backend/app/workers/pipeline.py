"""pipeline.py — Autonomous Pipeline Orchestrator."""
import logging
from typing import Any, Dict
from app.workers.jobs import (
    job_fetch_feeds,
    job_extract_pending,
    job_analyze_pending,
    job_generate_daily_editions,
    job_cleanup_old_data,
    job_full_pipeline,
)

logger = logging.getLogger(__name__)

__all__ = [
    "job_fetch_feeds",
    "job_extract_pending",
    "job_analyze_pending",
    "job_generate_daily_editions",
    "job_cleanup_old_data",
    "job_full_pipeline",
]
