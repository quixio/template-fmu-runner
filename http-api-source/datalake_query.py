"""
Data Lake Query Helper - Query QuixLake data lake API or local in-memory store.

For local development, set USE_LOCAL_STORE=true to use an in-memory store
instead of QuixLake. This enables the API to work without QuixLake connectivity.
"""
import os
import math
import logging
import time
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# Check if we should use local in-memory store instead of QuixLake
USE_LOCAL_STORE = os.environ.get("USE_LOCAL_STORE", "").lower() == "true"

# Local store instance (initialized lazily if USE_LOCAL_STORE is True)
_local_store = None

if USE_LOCAL_STORE:
    logger.info("DataLakeQuery: USE_LOCAL_STORE=true, using in-memory store")
    from local_store import LocalStore
    from kafka_consumer import start_background_consumer

    _local_store = LocalStore()
    start_background_consumer(_local_store)
else:
    # Only import QuixLake if we're using it
    from quixlake import QuixLakeClient

MAX_RETRIES = 3
RETRY_DELAY = 1.0  # seconds
CACHE_TTL = 300  # 5 minutes - cache successful results to work around catalog inconsistency

# Simple TTL cache for query results
_cache: Dict[str, tuple] = {}  # key -> (timestamp, data)

# Configuration from environment variables (only needed for QuixLake mode)
QUIXLAKE_API_URL = os.environ.get("QUIXLAKE_API_URL", "")
QUIXLAKE_TOKEN = os.environ.get("QUIXLAKE_TOKEN", os.environ.get("Quix__Sdk__Token", ""))

if not USE_LOCAL_STORE:
    # Log configuration at module load
    logger.info(f"DataLakeQuery config: API_URL={QUIXLAKE_API_URL[:50] if QUIXLAKE_API_URL else 'NOT SET'}...")
    logger.info(f"DataLakeQuery config: TOKEN={'SET (' + str(len(QUIXLAKE_TOKEN)) + ' chars)' if QUIXLAKE_TOKEN else 'NOT SET'}")


def _escape_sql_string(value: str) -> str:
    """Escape single quotes in SQL string values."""
    return value.replace("'", "''")


def _clean_nan(value: Any) -> Any:
    """Convert NaN/Inf values to None for JSON serialization."""
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def _clean_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    """Clean all NaN values in a dictionary."""
    return {k: _clean_nan(v) for k, v in d.items()}


class DataLakeQuery:
    """Query helper for QuixLake data lake API or local in-memory store."""

    def __init__(self):
        self.api_url = QUIXLAKE_API_URL
        self.token = QUIXLAKE_TOKEN

    def _get_client(self):
        """Create a QuixLake client instance."""
        if USE_LOCAL_STORE:
            raise RuntimeError("QuixLake client not available in local store mode")
        return QuixLakeClient(base_url=self.api_url, token=self.token)

    def get_result_by_message_key(self, message_key: str) -> Optional[Dict[str, Any]]:
        """Fetch a single result record by message_key."""
        # Use local store if enabled
        if USE_LOCAL_STORE:
            return _local_store.get_result_by_message_key(message_key)

        escaped_key = _escape_sql_string(message_key)
        last_error = None

        for attempt in range(MAX_RETRIES + 1):
            try:
                logger.debug(f"Querying result for: {message_key} (attempt {attempt + 1})")
                with self._get_client() as client:
                    df = client.query(f"""
                        SELECT * FROM results
                        WHERE message_key = '{escaped_key}'
                        LIMIT 1
                    """)

                    if not df.empty:
                        logger.debug(f"Found result for: {message_key}")
                        return _clean_dict(df.iloc[0].to_dict())
                    logger.warning(f"No result found for: {message_key}")
                    return None
            except Exception as e:
                last_error = e
                logger.warning(f"Attempt {attempt + 1} failed for {message_key}: {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)

        logger.error(f"All retries failed for {message_key}: {last_error}", exc_info=True)
        return None

    def get_timeseries_by_message_key(self, message_key: str) -> List[Dict[str, Any]]:
        """Fetch timeseries data for a simulation run."""
        # Use local store if enabled
        if USE_LOCAL_STORE:
            return _local_store.get_timeseries_by_message_key(message_key)

        escaped_key = _escape_sql_string(message_key)
        last_error = None

        for attempt in range(MAX_RETRIES + 1):
            try:
                with self._get_client() as client:
                    df = client.query(f"""
                        SELECT *
                        FROM timeseries
                        WHERE message_key = '{escaped_key}'
                        ORDER BY time ASC
                    """)

                    if not df.empty:
                        return [_clean_dict(row) for row in df.to_dict(orient='records')]
                    return []
            except Exception as e:
                last_error = e
                logger.warning(f"Attempt {attempt + 1} failed for timeseries {message_key}: {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)

        logger.error(f"All retries failed for timeseries {message_key}: {last_error}", exc_info=True)
        return []

    def get_related_runs(self, message_key: str) -> List[Dict[str, Any]]:
        """
        Fetch all runs related to a message_key.
        Uses caching to work around QuixLake catalog inconsistency.
        """
        # Use local store if enabled
        if USE_LOCAL_STORE:
            return _local_store.get_related_runs(message_key)

        # Determine the base key (parent) - remove _gen_N suffix if present
        base_key = message_key
        if "_gen_" in message_key:
            base_key = message_key.rsplit("_gen_", 1)[0]

        cache_key = f"related:{base_key}"

        # Check cache first
        if cache_key in _cache:
            cached_time, cached_data = _cache[cache_key]
            if time.time() - cached_time < CACHE_TTL:
                logger.debug(f"Cache hit for related runs: {base_key}")
                return cached_data

        escaped_base_key = _escape_sql_string(base_key)
        last_error = None

        for attempt in range(MAX_RETRIES + 1):
            try:
                query = f"""
                    SELECT * FROM results
                    WHERE message_key = '{escaped_base_key}'
                       OR (starts_with(message_key, '{escaped_base_key}_gen_'))
                    ORDER BY message_key ASC
                """
                logger.info(f"Related runs query (attempt {attempt + 1})")
                with self._get_client() as client:
                    df = client.query(query)

                    if not df.empty:
                        result = [_clean_dict(row) for row in df.to_dict(orient='records')]
                        logger.debug(f"Found {len(result)} related runs for: {message_key}")
                        # Cache successful results
                        _cache[cache_key] = (time.time(), result)
                        return result
                    logger.warning(f"No related runs found for: {message_key} (attempt {attempt + 1})")
            except Exception as e:
                last_error = e
                logger.warning(f"Attempt {attempt + 1} failed for related runs {message_key}: {e}")

            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)

        logger.error(f"All retries failed for related runs {message_key}: {last_error}", exc_info=True)
        return []

    def get_family_result(self, message_key: str) -> Optional[Dict[str, Any]]:
        """
        Get the aggregated result for a run family.
        If the original run failed but a variant passed, returns the best passing variant.
        """
        related_runs = self.get_related_runs(message_key)
        if not related_runs:
            return None

        # Find passing runs
        passing_runs = [r for r in related_runs if r.get('validation_passed') is True]

        # If any passed, return the best one (highest max height)
        if passing_runs:
            best_run = max(passing_runs, key=lambda r: r.get('validation_calculated_value', 0) or 0)
            return {
                **best_run,
                '_family_passed': True,
                '_family_total_runs': len(related_runs),
                '_family_passed_count': len(passing_runs),
                '_is_variant': '_gen_' in best_run.get('message_key', '')
            }

        # Otherwise return the original run (first one without _gen_)
        original = next((r for r in related_runs if '_gen_' not in r.get('message_key', '')), related_runs[0])
        return {
            **original,
            '_family_passed': False,
            '_family_total_runs': len(related_runs),
            '_family_passed_count': 0,
            '_is_variant': False
        }

    def compute_statistics(self, timeseries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compute statistics from timeseries data."""
        if not timeseries:
            return {}

        positions = [t.get('position', 0) for t in timeseries if t.get('position') is not None]
        velocities = [t.get('velocity', 0) for t in timeseries if t.get('velocity') is not None]
        times = [t.get('time', 0) for t in timeseries if t.get('time') is not None]

        stats = {
            "data_points": len(timeseries),
        }

        if positions:
            stats["max_position"] = max(positions)
            stats["min_position"] = min(positions)

        if velocities:
            stats["max_velocity"] = max(velocities)
            stats["min_velocity"] = min(velocities)

        if len(times) > 1:
            stats["duration"] = max(times) - min(times)

        return stats
