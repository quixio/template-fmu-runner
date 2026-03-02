import os
import sys

import pytest

# Ensure fmu-runner root is on sys.path so bare imports work
RUNNER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RUNNER_DIR not in sys.path:
    sys.path.insert(0, RUNNER_DIR)

FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def _fmu_path(version: str, name: str) -> str:
    path = os.path.join(FIXTURES_DIR, version, name)
    assert os.path.exists(path), f"Test fixture not found: {path}"
    return path


# ---- FMI 1.0 CoSimulation ----

@pytest.fixture
def fmi10_cs_bouncing_ball():
    return _fmu_path("1.0/cs", "BouncingBall.fmu")

@pytest.fixture
def fmi10_cs_dahlquist():
    return _fmu_path("1.0/cs", "Dahlquist.fmu")

@pytest.fixture
def fmi10_cs_feedthrough():
    return _fmu_path("1.0/cs", "Feedthrough.fmu")

@pytest.fixture
def fmi10_cs_resource():
    return _fmu_path("1.0/cs", "Resource.fmu")

@pytest.fixture
def fmi10_cs_stair():
    return _fmu_path("1.0/cs", "Stair.fmu")

@pytest.fixture
def fmi10_cs_vanderpol():
    return _fmu_path("1.0/cs", "VanDerPol.fmu")


# ---- FMI 1.0 ModelExchange ----

@pytest.fixture
def fmi10_me_bouncing_ball():
    return _fmu_path("1.0/me", "BouncingBall.fmu")

@pytest.fixture
def fmi10_me_dahlquist():
    return _fmu_path("1.0/me", "Dahlquist.fmu")

@pytest.fixture
def fmi10_me_feedthrough():
    return _fmu_path("1.0/me", "Feedthrough.fmu")

@pytest.fixture
def fmi10_me_stair():
    return _fmu_path("1.0/me", "Stair.fmu")

@pytest.fixture
def fmi10_me_vanderpol():
    return _fmu_path("1.0/me", "VanDerPol.fmu")


# ---- FMI 2.0 ----

@pytest.fixture
def fmi20_bouncing_ball():
    return _fmu_path("2.0", "BouncingBall.fmu")

@pytest.fixture
def fmi20_dahlquist():
    return _fmu_path("2.0", "Dahlquist.fmu")

@pytest.fixture
def fmi20_feedthrough():
    return _fmu_path("2.0", "Feedthrough.fmu")

@pytest.fixture
def fmi20_resource():
    return _fmu_path("2.0", "Resource.fmu")

@pytest.fixture
def fmi20_stair():
    return _fmu_path("2.0", "Stair.fmu")

@pytest.fixture
def fmi20_vanderpol():
    return _fmu_path("2.0", "VanDerPol.fmu")


# ---- FMI 3.0 ----

@pytest.fixture
def fmi30_bouncing_ball():
    return _fmu_path("3.0", "BouncingBall.fmu")

@pytest.fixture
def fmi30_clocks():
    return _fmu_path("3.0", "Clocks.fmu")

@pytest.fixture
def fmi30_dahlquist():
    return _fmu_path("3.0", "Dahlquist.fmu")

@pytest.fixture
def fmi30_feedthrough():
    return _fmu_path("3.0", "Feedthrough.fmu")

@pytest.fixture
def fmi30_resource():
    return _fmu_path("3.0", "Resource.fmu")

@pytest.fixture
def fmi30_stair():
    return _fmu_path("3.0", "Stair.fmu")

@pytest.fixture
def fmi30_statespace():
    return _fmu_path("3.0", "StateSpace.fmu")

@pytest.fixture
def fmi30_vanderpol():
    return _fmu_path("3.0", "VanDerPol.fmu")
