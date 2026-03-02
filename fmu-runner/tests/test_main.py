"""Tests for main.py - get_fmu_path and process_message end-to-end tests."""
import os
import pytest

from main import get_fmu_path, process_message, FMU_DIR


# ---------------------------------------------------------------------------
# get_fmu_path
# ---------------------------------------------------------------------------
class TestGetFmuPath:
    def test_existing_fmu_returns_path(self):
        path = get_fmu_path("BouncingBall.fmu")
        assert os.path.exists(path)
        assert path.endswith("BouncingBall.fmu")

    def test_nonexistent_fmu_raises(self):
        with pytest.raises(FileNotFoundError, match="FMU file not found"):
            get_fmu_path("nonexistent.fmu")

    def test_returns_path_under_fmu_dir(self):
        path = get_fmu_path("BouncingBall.fmu")
        assert os.path.dirname(path) == FMU_DIR


# ---------------------------------------------------------------------------
# process_message - end-to-end tests
# ---------------------------------------------------------------------------
class TestProcessMessage:
    def test_valid_request_completes(self):
        row = {
            "message_key": "test-1",
            "model_filename": "BouncingBall.fmu",
            "config": {"start_time": 0.0, "stop_time": 2.0},
            "input_data": [],
        }
        result = process_message(row)
        assert result is not None
        assert result["status"] == "completed"
        assert result["message_key"] == "test-1"
        assert result["model_filename"] == "BouncingBall.fmu"

    def test_output_has_envelope_keys(self):
        row = {
            "message_key": "envelope-test",
            "model_filename": "BouncingBall.fmu",
            "config": {"start_time": 0.0, "stop_time": 1.0},
            "input_data": [],
        }
        result = process_message(row)
        required_keys = {
            "message_key", "submitted_at", "started_at", "completed_at",
            "processing_time_ms", "model_filename", "config", "status",
            "error_message", "input_data",
        }
        assert set(result.keys()) == required_keys

    def test_timestamps_are_utc_iso(self):
        row = {
            "message_key": "ts-test",
            "model_filename": "BouncingBall.fmu",
            "config": {},
            "input_data": [],
        }
        result = process_message(row)
        assert result["started_at"].endswith("Z")
        assert result["completed_at"].endswith("Z")

    def test_processing_time_is_positive(self):
        row = {
            "message_key": "time-test",
            "model_filename": "BouncingBall.fmu",
            "config": {"start_time": 0.0, "stop_time": 1.0},
            "input_data": [],
        }
        result = process_message(row)
        assert result["processing_time_ms"] > 0

    def test_non_fmu_file_returns_none(self):
        row = {"message_key": "skip", "model_filename": "model.slx"}
        assert process_message(row) is None

    def test_empty_filename_returns_none(self):
        row = {"message_key": "skip", "model_filename": ""}
        assert process_message(row) is None

    def test_missing_filename_returns_none(self):
        row = {"message_key": "skip"}
        assert process_message(row) is None

    def test_nonexistent_fmu_returns_error(self):
        row = {
            "message_key": "err-test",
            "model_filename": "nonexistent.fmu",
            "config": {},
            "input_data": [],
        }
        result = process_message(row)
        assert result["status"] == "error"
        assert "FMU file not found" in result["error_message"]
        assert result["input_data"] == []

    def test_error_response_has_envelope_keys(self):
        row = {
            "message_key": "err-envelope",
            "model_filename": "nonexistent.fmu",
        }
        result = process_message(row)
        required_keys = {
            "message_key", "submitted_at", "started_at", "completed_at",
            "processing_time_ms", "model_filename", "config", "status",
            "error_message", "input_data",
        }
        assert set(result.keys()) == required_keys

    def test_submitted_at_passed_through(self):
        row = {
            "message_key": "passthrough",
            "submitted_at": "2025-01-15T10:00:00Z",
            "model_filename": "BouncingBall.fmu",
            "config": {},
            "input_data": [],
        }
        result = process_message(row)
        assert result["submitted_at"] == "2025-01-15T10:00:00Z"

    def test_config_defaults_applied(self):
        row = {
            "message_key": "defaults",
            "model_filename": "BouncingBall.fmu",
            "config": {},
            "input_data": [],
        }
        result = process_message(row)
        assert result["config"]["start_time"] == 0.0
        assert result["config"]["stop_time"] == 10.0

    def test_simulation_output_data_not_empty(self):
        row = {
            "message_key": "data-test",
            "model_filename": "BouncingBall.fmu",
            "config": {"start_time": 0.0, "stop_time": 1.0},
            "input_data": [],
        }
        result = process_message(row)
        assert len(result["input_data"]) > 0
        first = result["input_data"][0]
        assert "time" in first
        assert "h" in first
        assert "v" in first
        assert "position" in first
