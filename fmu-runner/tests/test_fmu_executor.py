"""Tests for fmu_executor.py - unit tests for pure functions and integration tests using real FMUs.

Tests all 25 Reference FMUs across FMI 1.0 (CS + ME), 2.0, and 3.0.
"""
import numpy as np
import pytest

from fmu_executor import (
    should_process,
    read_fmu_metadata,
    build_input_array,
    run_fmu_simulation,
    format_output,
    get_fmu_type_name,
    convert_output_value,
)


# ===========================================================================
# Pure function tests (no FMU files needed)
# ===========================================================================


class TestShouldProcess:
    def test_fmu_extension(self):
        assert should_process("model.fmu") is True

    def test_fmu_extension_uppercase(self):
        assert should_process("model.FMU") is True

    def test_fmu_extension_mixed_case(self):
        assert should_process("model.Fmu") is True

    def test_non_fmu_slx(self):
        assert should_process("model.slx") is False

    def test_non_fmu_py(self):
        assert should_process("model.py") is False

    def test_no_extension(self):
        assert should_process("model") is False

    def test_empty_string(self):
        assert should_process("") is False

    def test_none(self):
        assert should_process(None) is False

    def test_dotfile_named_fmu(self):
        assert should_process(".fmu") is False

    def test_path_with_directory(self):
        assert should_process("path/to/model.fmu") is True

    def test_fmu_in_basename_not_extension(self):
        assert should_process("fmu_model.txt") is False


class TestGetFmuTypeName:
    def test_none_returns_real(self):
        assert get_fmu_type_name(None) == "Real"

    def test_string_real(self):
        assert get_fmu_type_name("Real") == "Real"

    def test_string_integer_current_behavior(self):
        assert get_fmu_type_name("Integer") == "Real"

    def test_string_boolean_current_behavior(self):
        assert get_fmu_type_name("Boolean") == "Real"

    def test_string_string_current_behavior(self):
        assert get_fmu_type_name("String") == "Real"

    def test_string_enumeration(self):
        assert get_fmu_type_name("Enumeration") == "Real"

    @pytest.mark.xfail(reason="get_fmu_type_name uses type().__name__ which is 'str' for string type values")
    def test_integer_correct_behavior(self):
        assert get_fmu_type_name("Integer") == "Integer"

    @pytest.mark.xfail(reason="get_fmu_type_name uses type().__name__ which is 'str' for string type values")
    def test_boolean_correct_behavior(self):
        assert get_fmu_type_name("Boolean") == "Boolean"

    @pytest.mark.xfail(reason="get_fmu_type_name uses type().__name__ which is 'str' for string type values")
    def test_string_correct_behavior(self):
        assert get_fmu_type_name("String") == "String"


class TestConvertOutputValue:
    def test_real_from_float64(self):
        result = convert_output_value(np.float64(3.14), "Real")
        assert result == pytest.approx(3.14)
        assert isinstance(result, float)

    def test_integer_from_float64(self):
        result = convert_output_value(np.float64(5.0), "Integer")
        assert result == 5
        assert isinstance(result, int)

    def test_boolean_true(self):
        result = convert_output_value(np.float64(1.0), "Boolean")
        assert result is True

    def test_boolean_false(self):
        result = convert_output_value(np.float64(0.0), "Boolean")
        assert result is False

    def test_string_type(self):
        result = convert_output_value("hello", "String")
        assert result == "hello"
        assert isinstance(result, str)

    def test_none_value(self):
        assert convert_output_value(None, "Real") is None
        assert convert_output_value(None, "Integer") is None

    def test_unknown_type_treated_as_real(self):
        result = convert_output_value(np.float64(2.71), "Enumeration")
        assert result == pytest.approx(2.71)
        assert isinstance(result, float)

    def test_numpy_int64(self):
        result = convert_output_value(np.int64(42), "Real")
        assert result == 42.0
        assert isinstance(result, float)


class TestBuildInputArray:
    def test_basic_two_inputs(self):
        data = [
            {"time": 0.0, "a": 1.0, "b": 2.0},
            {"time": 1.0, "a": 3.0, "b": 4.0},
        ]
        result = build_input_array(data, ["a", "b"])
        assert result is not None
        assert result.dtype.names == ("time", "a", "b")
        assert len(result) == 2
        assert result["time"][0] == 0.0
        assert result["a"][1] == 3.0
        assert result["b"][0] == 2.0

    def test_missing_column_defaults_to_zero(self):
        data = [{"time": 0.0, "a": 5.0}]
        result = build_input_array(data, ["a", "b"])
        assert result["b"][0] == 0.0

    def test_extra_columns_ignored(self):
        data = [{"time": 0.0, "a": 1.0, "extra": 99.0}]
        result = build_input_array(data, ["a"])
        assert result.dtype.names == ("time", "a")

    def test_missing_time_defaults_to_zero(self):
        data = [{"a": 5.0}]
        result = build_input_array(data, ["a"])
        assert result["time"][0] == 0.0

    def test_empty_data_returns_none(self):
        assert build_input_array([], ["a"]) is None

    def test_empty_names_returns_none(self):
        assert build_input_array([{"time": 0}], []) is None

    def test_none_data_returns_none(self):
        assert build_input_array(None, ["a"]) is None

    def test_none_names_returns_none(self):
        assert build_input_array([{"time": 0}], None) is None

    def test_single_row(self):
        data = [{"time": 0.0, "x": 1.5}]
        result = build_input_array(data, ["x"])
        assert len(result) == 1
        assert result.dtype.names == ("time", "x")

    def test_all_dtypes_are_float64(self):
        data = [{"time": 0, "a": 1, "b": 2}]
        result = build_input_array(data, ["a", "b"])
        for name in result.dtype.names:
            assert result.dtype[name] == np.float64

    def test_string_value_raises(self):
        data = [{"time": 0.0, "a": "hello"}]
        with pytest.raises(ValueError):
            build_input_array(data, ["a"])


class TestFormatOutput:
    def test_basic_conversion(self):
        dtype = np.dtype([("time", "f8"), ("h", "f8"), ("v", "f8")])
        result = np.array([(0.0, 1.0, 0.0), (0.01, 0.99, -0.0981)], dtype=dtype)
        metadata = {"outputs": [{"name": "h", "type": "Real"}, {"name": "v", "type": "Real"}]}
        output = format_output(result, ["h", "v"], metadata)
        assert len(output) == 2
        assert output[0]["time"] == 0.0
        assert output[0]["h"] == 1.0
        assert output[0]["v"] == 0.0

    def test_position_mapping_h(self):
        dtype = np.dtype([("time", "f8"), ("h", "f8")])
        result = np.array([(0.0, 5.0)], dtype=dtype)
        metadata = {"outputs": [{"name": "h", "type": "Real"}]}
        output = format_output(result, ["h"], metadata)
        assert output[0]["position"] == 5.0

    def test_position_mapping_x(self):
        dtype = np.dtype([("time", "f8"), ("x", "f8")])
        result = np.array([(0.0, 3.0)], dtype=dtype)
        metadata = {"outputs": [{"name": "x", "type": "Real"}]}
        output = format_output(result, ["x"], metadata)
        assert output[0]["position"] == 3.0

    def test_position_fallback_first_numeric(self):
        dtype = np.dtype([("time", "f8"), ("foo", "f8"), ("bar", "f8")])
        result = np.array([(0.0, 7.0, 8.0)], dtype=dtype)
        metadata = {"outputs": [{"name": "foo", "type": "Real"}, {"name": "bar", "type": "Real"}]}
        output = format_output(result, ["foo", "bar"], metadata)
        assert output[0]["position"] == 7.0

    def test_no_outputs_no_position(self):
        dtype = np.dtype([("time", "f8")])
        result = np.array([(0.0,)], dtype=dtype)
        metadata = {"outputs": []}
        output = format_output(result, [], metadata)
        assert len(output) == 1
        assert "position" not in output[0]

    def test_native_python_types(self):
        dtype = np.dtype([("time", "f8"), ("val", "f8")])
        result = np.array([(0.0, 42.0)], dtype=dtype)
        metadata = {"outputs": [{"name": "val", "type": "Real"}]}
        output = format_output(result, ["val"], metadata)
        assert isinstance(output[0]["time"], float)
        assert isinstance(output[0]["val"], float)

    def test_position_candidate_priority(self):
        dtype = np.dtype([("time", "f8"), ("x", "f8"), ("h", "f8")])
        result = np.array([(0.0, 10.0, 20.0)], dtype=dtype)
        metadata = {"outputs": [{"name": "x", "type": "Real"}, {"name": "h", "type": "Real"}]}
        output = format_output(result, ["x", "h"], metadata)
        assert output[0]["position"] == 20.0  # h has higher priority than x


# ===========================================================================
# Helpers for integration tests
# ===========================================================================

def _assert_simulation_ok(fmu_path, stop_time=1.0):
    """Run a simulation and assert it completes with output rows."""
    result = run_fmu_simulation(fmu_path, [], {"start_time": 0.0, "stop_time": stop_time})
    assert result["status"] == "completed", f"Simulation failed: {result.get('error_message')}"
    assert result["error_message"] is None
    assert len(result["input_data"]) > 0
    return result


def _assert_native_types(result):
    """Assert all values in output rows are native Python types."""
    for row in result["input_data"]:
        for key, val in row.items():
            assert isinstance(val, (float, int, bool, str, list)), (
                f"Non-native type for '{key}': {type(val)}"
            )


# ===========================================================================
# FMI 2.0 - Integration tests (primary target version)
# ===========================================================================


class TestFmi20ReadMetadata:
    def test_bouncing_ball(self, fmi20_bouncing_ball):
        meta = read_fmu_metadata(fmi20_bouncing_ball)
        assert meta["model_name"] == "BouncingBall"
        assert meta["fmi_version"] == "2.0"
        assert len(meta["inputs"]) == 0
        assert len(meta["outputs"]) == 2
        assert len(meta["parameters"]) == 2
        output_names = [v["name"] for v in meta["outputs"]]
        assert "h" in output_names
        assert "v" in output_names

    def test_bouncing_ball_parameters(self, fmi20_bouncing_ball):
        meta = read_fmu_metadata(fmi20_bouncing_ball)
        params = {v["name"]: v for v in meta["parameters"]}
        assert params["g"]["start"] == "-9.81"
        assert params["e"]["start"] == "0.7"

    def test_dahlquist(self, fmi20_dahlquist):
        meta = read_fmu_metadata(fmi20_dahlquist)
        assert meta["model_name"] == "Dahlquist"
        assert meta["fmi_version"] == "2.0"
        assert len(meta["inputs"]) == 0
        assert len(meta["outputs"]) == 1
        assert len(meta["parameters"]) == 1
        assert meta["outputs"][0]["name"] == "x"
        assert meta["parameters"][0]["name"] == "k"

    def test_feedthrough(self, fmi20_feedthrough):
        meta = read_fmu_metadata(fmi20_feedthrough)
        assert meta["model_name"] == "Feedthrough"
        assert len(meta["inputs"]) == 6
        assert len(meta["outputs"]) == 6
        assert len(meta["parameters"]) == 2

    def test_feedthrough_input_types(self, fmi20_feedthrough):
        meta = read_fmu_metadata(fmi20_feedthrough)
        input_types = {v["name"]: v["type"] for v in meta["inputs"]}
        assert input_types["Float64_continuous_input"] == "Real"
        assert input_types["Int32_input"] == "Integer"
        assert input_types["Boolean_input"] == "Boolean"
        assert input_types["String_input"] == "String"

    def test_resource(self, fmi20_resource):
        meta = read_fmu_metadata(fmi20_resource)
        assert meta["model_name"] == "Resource"
        assert len(meta["inputs"]) == 0
        assert len(meta["outputs"]) == 1
        assert meta["outputs"][0]["name"] == "y"

    def test_stair(self, fmi20_stair):
        meta = read_fmu_metadata(fmi20_stair)
        assert meta["model_name"] == "Stair"
        assert len(meta["inputs"]) == 0
        assert len(meta["outputs"]) == 1
        assert meta["outputs"][0]["name"] == "counter"

    def test_vanderpol(self, fmi20_vanderpol):
        meta = read_fmu_metadata(fmi20_vanderpol)
        assert len(meta["outputs"]) == 2
        output_names = [v["name"] for v in meta["outputs"]]
        assert "x0" in output_names
        assert "x1" in output_names
        assert len(meta["parameters"]) == 1
        assert meta["parameters"][0]["name"] == "mu"

    def test_var_info_has_standard_keys(self, fmi20_bouncing_ball):
        meta = read_fmu_metadata(fmi20_bouncing_ball)
        expected_keys = {"name", "valueReference", "description", "type", "start", "causality", "variability"}
        for v in meta["outputs"] + meta["parameters"]:
            assert set(v.keys()) == expected_keys

    def test_nonexistent_file_raises(self):
        with pytest.raises(Exception):
            read_fmu_metadata("nonexistent.fmu")


class TestFmi20BouncingBall:
    def test_completes(self, fmi20_bouncing_ball):
        _assert_simulation_ok(fmi20_bouncing_ball, stop_time=3.0)

    def test_initial_conditions(self, fmi20_bouncing_ball):
        result = _assert_simulation_ok(fmi20_bouncing_ball)
        first = result["input_data"][0]
        assert first["time"] == 0.0
        assert first["h"] == 1.0
        assert first["v"] == 0.0

    def test_position_mapped_from_h(self, fmi20_bouncing_ball):
        result = _assert_simulation_ok(fmi20_bouncing_ball)
        first = result["input_data"][0]
        assert "position" in first
        assert first["position"] == first["h"]

    def test_height_decreases_initially(self, fmi20_bouncing_ball):
        result = _assert_simulation_ok(fmi20_bouncing_ball)
        rows = result["input_data"]
        assert rows[1]["h"] < rows[0]["h"]

    def test_height_nonnegative(self, fmi20_bouncing_ball):
        result = _assert_simulation_ok(fmi20_bouncing_ball, stop_time=5.0)
        for row in result["input_data"]:
            assert row["h"] >= 0.0

    def test_output_keys(self, fmi20_bouncing_ball):
        result = _assert_simulation_ok(fmi20_bouncing_ball)
        assert set(result["input_data"][0].keys()) == {"time", "h", "v", "position"}

    def test_native_python_types(self, fmi20_bouncing_ball):
        result = _assert_simulation_ok(fmi20_bouncing_ball)
        _assert_native_types(result)

    def test_parameter_override_e(self, fmi20_bouncing_ball):
        result = run_fmu_simulation(fmi20_bouncing_ball, [], {
            "start_time": 0.0, "stop_time": 3.0, "parameters": {"e": 0.5},
        })
        assert result["status"] == "completed"

    def test_invalid_parameter_ignored(self, fmi20_bouncing_ball):
        result = run_fmu_simulation(fmi20_bouncing_ball, [], {
            "start_time": 0.0, "stop_time": 1.0, "parameters": {"nonexistent": 42},
        })
        assert result["status"] == "completed"


class TestFmi20Dahlquist:
    def test_initial_value(self, fmi20_dahlquist):
        result = _assert_simulation_ok(fmi20_dahlquist)
        assert result["input_data"][0]["x"] == 1.0

    def test_exponential_decay(self, fmi20_dahlquist):
        result = _assert_simulation_ok(fmi20_dahlquist, stop_time=3.0)
        rows = result["input_data"]
        for i in range(1, len(rows)):
            assert rows[i]["x"] < rows[i - 1]["x"]
        assert 0 < rows[-1]["x"] < 0.1  # exp(-3) ~ 0.0498

    def test_position_maps_to_x(self, fmi20_dahlquist):
        result = _assert_simulation_ok(fmi20_dahlquist)
        assert result["input_data"][0]["position"] == result["input_data"][0]["x"]

    def test_k_override_faster_decay(self, fmi20_dahlquist):
        r1 = _assert_simulation_ok(fmi20_dahlquist)
        r2 = run_fmu_simulation(fmi20_dahlquist, [], {
            "start_time": 0.0, "stop_time": 1.0, "parameters": {"k": 2.0},
        })
        assert r2["status"] == "completed"
        assert r2["input_data"][-1]["x"] < r1["input_data"][-1]["x"]


class TestFmi20Feedthrough:
    def test_no_inputs_completes(self, fmi20_feedthrough):
        _assert_simulation_ok(fmi20_feedthrough, stop_time=0.01)

    def test_string_output_excluded(self, fmi20_feedthrough):
        result = _assert_simulation_ok(fmi20_feedthrough, stop_time=0.01)
        assert "String_output" not in result["input_data"][0]

    def test_has_enumeration_output(self, fmi20_feedthrough):
        result = _assert_simulation_ok(fmi20_feedthrough, stop_time=0.01)
        assert "Enumeration_output" in result["input_data"][0]

    def test_position_maps_to_first_numeric(self, fmi20_feedthrough):
        result = _assert_simulation_ok(fmi20_feedthrough, stop_time=0.01)
        first = result["input_data"][0]
        assert first["position"] == first["Float64_continuous_output"]

    def test_native_types(self, fmi20_feedthrough):
        result = _assert_simulation_ok(fmi20_feedthrough, stop_time=0.01)
        _assert_native_types(result)


class TestFmi20Resource:
    def test_completes(self, fmi20_resource):
        _assert_simulation_ok(fmi20_resource)

    def test_output_y_exists(self, fmi20_resource):
        result = _assert_simulation_ok(fmi20_resource)
        assert "y" in result["input_data"][0]

    def test_output_is_constant(self, fmi20_resource):
        result = _assert_simulation_ok(fmi20_resource)
        y_vals = [row["y"] for row in result["input_data"]]
        assert all(v == y_vals[0] for v in y_vals)

    def test_native_types(self, fmi20_resource):
        result = _assert_simulation_ok(fmi20_resource)
        _assert_native_types(result)


class TestFmi20Stair:
    def test_completes(self, fmi20_stair):
        _assert_simulation_ok(fmi20_stair)

    def test_counter_starts_at_one(self, fmi20_stair):
        result = _assert_simulation_ok(fmi20_stair)
        assert result["input_data"][0]["counter"] == 1.0

    def test_counter_increases(self, fmi20_stair):
        result = _assert_simulation_ok(fmi20_stair, stop_time=3.0)
        counters = [row["counter"] for row in result["input_data"]]
        assert counters[-1] > counters[0]

    def test_counter_is_monotonic(self, fmi20_stair):
        result = _assert_simulation_ok(fmi20_stair, stop_time=3.0)
        counters = [row["counter"] for row in result["input_data"]]
        for i in range(1, len(counters)):
            assert counters[i] >= counters[i - 1]

    def test_native_types(self, fmi20_stair):
        result = _assert_simulation_ok(fmi20_stair)
        _assert_native_types(result)


class TestFmi20VanDerPol:
    def test_initial_conditions(self, fmi20_vanderpol):
        result = _assert_simulation_ok(fmi20_vanderpol)
        first = result["input_data"][0]
        assert first["x0"] == 2.0
        assert first["x1"] == 0.0

    def test_oscillates(self, fmi20_vanderpol):
        result = _assert_simulation_ok(fmi20_vanderpol, stop_time=20.0)
        x0_vals = [row["x0"] for row in result["input_data"]]
        assert any(v > 0 for v in x0_vals)
        assert any(v < 0 for v in x0_vals)

    def test_position_maps_to_first_output(self, fmi20_vanderpol):
        result = _assert_simulation_ok(fmi20_vanderpol)
        assert result["input_data"][0]["position"] == result["input_data"][0]["x0"]

    def test_output_keys(self, fmi20_vanderpol):
        result = _assert_simulation_ok(fmi20_vanderpol)
        assert set(result["input_data"][0].keys()) == {"time", "x0", "x1", "position"}

    def test_native_types(self, fmi20_vanderpol):
        result = _assert_simulation_ok(fmi20_vanderpol)
        _assert_native_types(result)


# ===========================================================================
# FMI 1.0 CoSimulation - Integration tests
# ===========================================================================


class TestFmi10CsBouncingBall:
    def test_completes(self, fmi10_cs_bouncing_ball):
        _assert_simulation_ok(fmi10_cs_bouncing_ball, stop_time=3.0)

    def test_initial_conditions(self, fmi10_cs_bouncing_ball):
        result = _assert_simulation_ok(fmi10_cs_bouncing_ball)
        first = result["input_data"][0]
        assert first["h"] == 1.0
        assert first["v"] == 0.0

    def test_height_decreases_initially(self, fmi10_cs_bouncing_ball):
        result = _assert_simulation_ok(fmi10_cs_bouncing_ball)
        rows = result["input_data"]
        assert rows[1]["h"] < rows[0]["h"]

    def test_height_nonnegative(self, fmi10_cs_bouncing_ball):
        result = _assert_simulation_ok(fmi10_cs_bouncing_ball, stop_time=5.0)
        for row in result["input_data"]:
            assert row["h"] >= -0.01  # small tolerance for 1.0 solver

    def test_position_mapped_from_h(self, fmi10_cs_bouncing_ball):
        result = _assert_simulation_ok(fmi10_cs_bouncing_ball)
        assert result["input_data"][0]["position"] == result["input_data"][0]["h"]

    def test_native_types(self, fmi10_cs_bouncing_ball):
        _assert_native_types(_assert_simulation_ok(fmi10_cs_bouncing_ball))


class TestFmi10CsDahlquist:
    def test_completes(self, fmi10_cs_dahlquist):
        _assert_simulation_ok(fmi10_cs_dahlquist)

    def test_initial_value(self, fmi10_cs_dahlquist):
        result = _assert_simulation_ok(fmi10_cs_dahlquist)
        assert result["input_data"][0]["x"] == 1.0

    def test_decays(self, fmi10_cs_dahlquist):
        result = _assert_simulation_ok(fmi10_cs_dahlquist, stop_time=3.0)
        rows = result["input_data"]
        assert rows[-1]["x"] < rows[0]["x"]
        assert rows[-1]["x"] > 0

    def test_native_types(self, fmi10_cs_dahlquist):
        _assert_native_types(_assert_simulation_ok(fmi10_cs_dahlquist))


class TestFmi10CsFeedthrough:
    def test_completes(self, fmi10_cs_feedthrough):
        _assert_simulation_ok(fmi10_cs_feedthrough, stop_time=0.01)

    def test_string_output_excluded(self, fmi10_cs_feedthrough):
        result = _assert_simulation_ok(fmi10_cs_feedthrough, stop_time=0.01)
        assert "String_output" not in result["input_data"][0]

    def test_has_numeric_outputs(self, fmi10_cs_feedthrough):
        result = _assert_simulation_ok(fmi10_cs_feedthrough, stop_time=0.01)
        assert "Float64_continuous_output" in result["input_data"][0]

    def test_native_types(self, fmi10_cs_feedthrough):
        _assert_native_types(_assert_simulation_ok(fmi10_cs_feedthrough, stop_time=0.01))


class TestFmi10CsResource:
    def test_completes(self, fmi10_cs_resource):
        _assert_simulation_ok(fmi10_cs_resource)

    def test_output_y_is_constant(self, fmi10_cs_resource):
        result = _assert_simulation_ok(fmi10_cs_resource)
        y_vals = [row["y"] for row in result["input_data"]]
        assert all(v == y_vals[0] for v in y_vals)

    def test_native_types(self, fmi10_cs_resource):
        _assert_native_types(_assert_simulation_ok(fmi10_cs_resource))


class TestFmi10CsStair:
    def test_completes(self, fmi10_cs_stair):
        _assert_simulation_ok(fmi10_cs_stair)

    def test_counter_starts_at_one(self, fmi10_cs_stair):
        result = _assert_simulation_ok(fmi10_cs_stair)
        assert result["input_data"][0]["counter"] == 1.0

    def test_counter_monotonic(self, fmi10_cs_stair):
        result = _assert_simulation_ok(fmi10_cs_stair, stop_time=3.0)
        counters = [row["counter"] for row in result["input_data"]]
        for i in range(1, len(counters)):
            assert counters[i] >= counters[i - 1]

    def test_native_types(self, fmi10_cs_stair):
        _assert_native_types(_assert_simulation_ok(fmi10_cs_stair))


class TestFmi10CsVanDerPol:
    def test_completes(self, fmi10_cs_vanderpol):
        _assert_simulation_ok(fmi10_cs_vanderpol)

    def test_initial_conditions(self, fmi10_cs_vanderpol):
        result = _assert_simulation_ok(fmi10_cs_vanderpol)
        first = result["input_data"][0]
        assert first["x0"] == 2.0
        assert first["x1"] == 0.0

    def test_oscillates(self, fmi10_cs_vanderpol):
        result = _assert_simulation_ok(fmi10_cs_vanderpol, stop_time=20.0)
        x0_vals = [row["x0"] for row in result["input_data"]]
        assert any(v > 0 for v in x0_vals)
        assert any(v < 0 for v in x0_vals)

    def test_native_types(self, fmi10_cs_vanderpol):
        _assert_native_types(_assert_simulation_ok(fmi10_cs_vanderpol))


# ===========================================================================
# FMI 1.0 ModelExchange - Integration tests
# ===========================================================================


class TestFmi10MeBouncingBall:
    def test_completes(self, fmi10_me_bouncing_ball):
        _assert_simulation_ok(fmi10_me_bouncing_ball, stop_time=3.0)

    def test_initial_conditions(self, fmi10_me_bouncing_ball):
        result = _assert_simulation_ok(fmi10_me_bouncing_ball)
        first = result["input_data"][0]
        assert first["h"] == 1.0
        assert first["v"] == 0.0

    def test_height_decreases_initially(self, fmi10_me_bouncing_ball):
        result = _assert_simulation_ok(fmi10_me_bouncing_ball)
        rows = result["input_data"]
        assert rows[1]["h"] < rows[0]["h"]

    def test_produces_multiple_rows(self, fmi10_me_bouncing_ball):
        """ME solver produces more integration steps than CS; verify we get data."""
        result = _assert_simulation_ok(fmi10_me_bouncing_ball, stop_time=5.0)
        assert len(result["input_data"]) > 100

    def test_native_types(self, fmi10_me_bouncing_ball):
        _assert_native_types(_assert_simulation_ok(fmi10_me_bouncing_ball))


class TestFmi10MeDahlquist:
    def test_completes(self, fmi10_me_dahlquist):
        _assert_simulation_ok(fmi10_me_dahlquist)

    def test_initial_value(self, fmi10_me_dahlquist):
        result = _assert_simulation_ok(fmi10_me_dahlquist)
        assert result["input_data"][0]["x"] == 1.0

    def test_decays(self, fmi10_me_dahlquist):
        result = _assert_simulation_ok(fmi10_me_dahlquist, stop_time=3.0)
        rows = result["input_data"]
        assert rows[-1]["x"] < rows[0]["x"]
        assert rows[-1]["x"] > 0

    def test_native_types(self, fmi10_me_dahlquist):
        _assert_native_types(_assert_simulation_ok(fmi10_me_dahlquist))


class TestFmi10MeFeedthrough:
    def test_completes(self, fmi10_me_feedthrough):
        _assert_simulation_ok(fmi10_me_feedthrough, stop_time=0.01)

    def test_string_output_excluded(self, fmi10_me_feedthrough):
        result = _assert_simulation_ok(fmi10_me_feedthrough, stop_time=0.01)
        assert "String_output" not in result["input_data"][0]

    def test_has_numeric_outputs(self, fmi10_me_feedthrough):
        result = _assert_simulation_ok(fmi10_me_feedthrough, stop_time=0.01)
        assert "Float64_continuous_output" in result["input_data"][0]

    def test_native_types(self, fmi10_me_feedthrough):
        _assert_native_types(_assert_simulation_ok(fmi10_me_feedthrough, stop_time=0.01))


class TestFmi10MeStair:
    def test_completes(self, fmi10_me_stair):
        _assert_simulation_ok(fmi10_me_stair)

    def test_counter_starts_at_one(self, fmi10_me_stair):
        result = _assert_simulation_ok(fmi10_me_stair)
        assert result["input_data"][0]["counter"] == 1.0

    def test_counter_monotonic(self, fmi10_me_stair):
        result = _assert_simulation_ok(fmi10_me_stair, stop_time=3.0)
        counters = [row["counter"] for row in result["input_data"]]
        for i in range(1, len(counters)):
            assert counters[i] >= counters[i - 1]

    def test_native_types(self, fmi10_me_stair):
        _assert_native_types(_assert_simulation_ok(fmi10_me_stair))


class TestFmi10MeVanDerPol:
    def test_completes(self, fmi10_me_vanderpol):
        _assert_simulation_ok(fmi10_me_vanderpol)

    def test_initial_conditions(self, fmi10_me_vanderpol):
        result = _assert_simulation_ok(fmi10_me_vanderpol)
        first = result["input_data"][0]
        assert first["x0"] == 2.0
        assert first["x1"] == 0.0

    def test_oscillates(self, fmi10_me_vanderpol):
        result = _assert_simulation_ok(fmi10_me_vanderpol, stop_time=20.0)
        x0_vals = [row["x0"] for row in result["input_data"]]
        assert any(v > 0 for v in x0_vals)
        assert any(v < 0 for v in x0_vals)

    def test_native_types(self, fmi10_me_vanderpol):
        _assert_native_types(_assert_simulation_ok(fmi10_me_vanderpol))


# ===========================================================================
# FMI 3.0 - Integration tests
# ===========================================================================


class TestFmi30BouncingBall:
    def test_completes(self, fmi30_bouncing_ball):
        _assert_simulation_ok(fmi30_bouncing_ball, stop_time=3.0)

    def test_initial_conditions(self, fmi30_bouncing_ball):
        result = _assert_simulation_ok(fmi30_bouncing_ball)
        first = result["input_data"][0]
        assert first["h"] == 1.0
        assert first["v"] == 0.0

    def test_has_h_ft_output(self, fmi30_bouncing_ball):
        """FMI 3.0 BouncingBall adds h_ft (height in feet)."""
        meta = read_fmu_metadata(fmi30_bouncing_ball)
        output_names = [v["name"] for v in meta["outputs"]]
        assert "h_ft" in output_names

    def test_height_decreases_over_time(self, fmi30_bouncing_ball):
        result = _assert_simulation_ok(fmi30_bouncing_ball)
        rows = result["input_data"]
        # FMI 3.0 solver may have identical first rows; check later in the series
        assert rows[-1]["h"] < rows[0]["h"]

    def test_height_nonnegative(self, fmi30_bouncing_ball):
        result = _assert_simulation_ok(fmi30_bouncing_ball, stop_time=5.0)
        for row in result["input_data"]:
            assert row["h"] >= 0.0

    def test_native_types(self, fmi30_bouncing_ball):
        _assert_native_types(_assert_simulation_ok(fmi30_bouncing_ball))


class TestFmi30Clocks:
    def test_metadata_readable(self, fmi30_clocks):
        """Clocks.fmu metadata can be read even though simulation is unsupported."""
        meta = read_fmu_metadata(fmi30_clocks)
        assert meta["fmi_version"] == "3.0"

    def test_simulation_returns_error(self, fmi30_clocks):
        """Clocks.fmu uses ModelExchange-only features not supported by fmpy simulate."""
        result = run_fmu_simulation(fmi30_clocks, [], {"start_time": 0.0, "stop_time": 1.0})
        assert result["status"] == "error"
        assert result["error_message"] is not None
        assert result["input_data"] == []


class TestFmi30Dahlquist:
    def test_completes(self, fmi30_dahlquist):
        _assert_simulation_ok(fmi30_dahlquist)

    def test_initial_value(self, fmi30_dahlquist):
        result = _assert_simulation_ok(fmi30_dahlquist)
        assert result["input_data"][0]["x"] == 1.0

    def test_decays(self, fmi30_dahlquist):
        result = _assert_simulation_ok(fmi30_dahlquist, stop_time=3.0)
        rows = result["input_data"]
        assert rows[-1]["x"] < rows[0]["x"]
        assert rows[-1]["x"] > 0

    def test_fmi_version_is_30(self, fmi30_dahlquist):
        meta = read_fmu_metadata(fmi30_dahlquist)
        assert meta["fmi_version"] == "3.0"

    def test_native_types(self, fmi30_dahlquist):
        _assert_native_types(_assert_simulation_ok(fmi30_dahlquist))


class TestFmi30Feedthrough:
    def test_completes(self, fmi30_feedthrough):
        _assert_simulation_ok(fmi30_feedthrough, stop_time=0.01)

    def test_has_expanded_input_types(self, fmi30_feedthrough):
        """FMI 3.0 Feedthrough has more data types than 2.0."""
        meta = read_fmu_metadata(fmi30_feedthrough)
        assert len(meta["inputs"]) >= 12  # Float32, Int8, UInt8, etc.

    def test_string_output_excluded(self, fmi30_feedthrough):
        result = _assert_simulation_ok(fmi30_feedthrough, stop_time=0.01)
        assert "String_output" not in result["input_data"][0]

    def test_native_types(self, fmi30_feedthrough):
        _assert_native_types(_assert_simulation_ok(fmi30_feedthrough, stop_time=0.01))


class TestFmi30Resource:
    def test_completes(self, fmi30_resource):
        _assert_simulation_ok(fmi30_resource)

    def test_output_y_exists(self, fmi30_resource):
        result = _assert_simulation_ok(fmi30_resource)
        assert "y" in result["input_data"][0]

    def test_native_types(self, fmi30_resource):
        _assert_native_types(_assert_simulation_ok(fmi30_resource))


class TestFmi30Stair:
    def test_completes(self, fmi30_stair):
        _assert_simulation_ok(fmi30_stair)

    def test_counter_starts_at_one(self, fmi30_stair):
        result = _assert_simulation_ok(fmi30_stair)
        assert result["input_data"][0]["counter"] == 1.0

    def test_counter_monotonic(self, fmi30_stair):
        result = _assert_simulation_ok(fmi30_stair, stop_time=3.0)
        counters = [row["counter"] for row in result["input_data"]]
        for i in range(1, len(counters)):
            assert counters[i] >= counters[i - 1]

    def test_native_types(self, fmi30_stair):
        _assert_native_types(_assert_simulation_ok(fmi30_stair))


class TestFmi30StateSpace:
    def test_metadata_readable(self, fmi30_statespace):
        meta = read_fmu_metadata(fmi30_statespace)
        assert meta["fmi_version"] == "3.0"
        output_names = [v["name"] for v in meta["outputs"]]
        assert "y" in output_names

    def test_has_structural_parameters(self, fmi30_statespace):
        """StateSpace has array-valued structural parameters (A, B, C, D matrices)."""
        meta = read_fmu_metadata(fmi30_statespace)
        param_names = [v["name"] for v in meta["parameters"]]
        for name in ["A", "B", "C", "D", "x0"]:
            assert name in param_names

    def test_simulation_runs(self, fmi30_statespace):
        """StateSpace simulation may complete or error due to array parameters."""
        result = run_fmu_simulation(fmi30_statespace, [], {"start_time": 0.0, "stop_time": 1.0})
        # Accept either outcome - the important thing is no unhandled crash
        assert result["status"] in ("completed", "error")


class TestFmi30VanDerPol:
    def test_completes(self, fmi30_vanderpol):
        _assert_simulation_ok(fmi30_vanderpol)

    def test_initial_conditions(self, fmi30_vanderpol):
        result = _assert_simulation_ok(fmi30_vanderpol)
        first = result["input_data"][0]
        assert first["x0"] == 2.0
        assert first["x1"] == 0.0

    def test_oscillates(self, fmi30_vanderpol):
        result = _assert_simulation_ok(fmi30_vanderpol, stop_time=20.0)
        x0_vals = [row["x0"] for row in result["input_data"]]
        assert any(v > 0 for v in x0_vals)
        assert any(v < 0 for v in x0_vals)

    def test_fmi_version_is_30(self, fmi30_vanderpol):
        meta = read_fmu_metadata(fmi30_vanderpol)
        assert meta["fmi_version"] == "3.0"

    def test_native_types(self, fmi30_vanderpol):
        _assert_native_types(_assert_simulation_ok(fmi30_vanderpol))


# ===========================================================================
# Error handling
# ===========================================================================


class TestErrorHandling:
    def test_nonexistent_file_returns_error(self):
        result = run_fmu_simulation("nonexistent.fmu", [], {"start_time": 0, "stop_time": 1})
        assert result["status"] == "error"
        assert result["error_message"] is not None
        assert result["input_data"] == []

    def test_empty_config_uses_defaults(self, fmi20_bouncing_ball):
        result = run_fmu_simulation(fmi20_bouncing_ball, [], {})
        assert result["status"] == "completed"
