"""
In-memory store for local development - replaces QuixLake queries.

This module provides a thread-safe in-memory storage for simulation results
and timeseries data when running locally without QuixLake.
"""
import logging
import threading
from collections import defaultdict
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class LocalStore:
    """Thread-safe in-memory store for simulation results."""

    def __init__(self):
        self._results: Dict[str, dict] = {}  # message_key -> result
        self._timeseries: Dict[str, List[dict]] = defaultdict(list)  # message_key -> [points]
        self._lock = threading.RLock()

    def add_result(self, message_key: str, result: dict):
        """
        Store a validation result and extract timeseries data.

        Args:
            message_key: Unique identifier for the run
            result: Full validation result payload from Kafka
        """
        with self._lock:
            # Flatten config for compatibility with QuixLake schema
            flattened = self._flatten_result(result)
            self._results[message_key] = flattened

            # Extract timeseries from input_data
            self._timeseries[message_key] = []  # Clear existing
            for point in result.get("input_data", []):
                self._timeseries[message_key].append({
                    "message_key": message_key,
                    **point
                })

            logger.info(f"LocalStore: added result for {message_key} "
                       f"({len(self._timeseries[message_key])} timeseries points)")

    def _flatten_result(self, result: dict) -> dict:
        """
        Flatten nested config into top-level keys for QuixLake compatibility.

        QuixLake stores nested objects as flattened columns like:
        config_success_criteria_field_name, config_success_criteria_target_value
        """
        flat = {}

        for key, value in result.items():
            if key == "config" and isinstance(value, dict):
                # Flatten config
                for ck, cv in value.items():
                    if isinstance(cv, dict):
                        for ck2, cv2 in cv.items():
                            flat[f"config_{ck}_{ck2}"] = cv2
                    else:
                        flat[f"config_{ck}"] = cv
                # Also keep original config for API response
                flat["config"] = value
            elif key == "validation" and isinstance(value, dict):
                # Flatten validation results
                for vk, vv in value.items():
                    flat[f"validation_{vk}"] = vv
            else:
                flat[key] = value

        return flat

    def get_result_by_message_key(self, message_key: str) -> Optional[dict]:
        """Fetch a single result record by message_key."""
        with self._lock:
            result = self._results.get(message_key)
            if result:
                logger.debug(f"LocalStore: found result for {message_key}")
            else:
                logger.warning(f"LocalStore: no result for {message_key}")
            return result

    def get_timeseries_by_message_key(self, message_key: str) -> List[dict]:
        """Fetch timeseries data for a simulation run."""
        with self._lock:
            data = list(self._timeseries.get(message_key, []))
            logger.debug(f"LocalStore: {len(data)} timeseries points for {message_key}")
            return data

    def get_related_runs(self, message_key: str) -> List[dict]:
        """
        Get all runs related to a message_key (parent + variants).

        Finds runs where message_key matches or starts with base_key_gen_.
        """
        # Determine the base key (remove _gen_N suffix if present)
        base_key = message_key.rsplit("_gen_", 1)[0] if "_gen_" in message_key else message_key

        with self._lock:
            related = [
                r for k, r in self._results.items()
                if k == base_key or k.startswith(f"{base_key}_gen_")
            ]
            # Sort by message_key for consistent ordering
            related.sort(key=lambda r: r.get("message_key", ""))
            logger.debug(f"LocalStore: {len(related)} related runs for {message_key}")
            return related

    def get_all_results(self) -> List[dict]:
        """Get all stored results (for debugging/run history)."""
        with self._lock:
            return list(self._results.values())

    def clear(self):
        """Clear all stored data (for testing)."""
        with self._lock:
            self._results.clear()
            self._timeseries.clear()
            logger.info("LocalStore: cleared all data")
