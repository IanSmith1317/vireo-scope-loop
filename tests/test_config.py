"""Tests for config.py — verifies all expected config values are defined."""

import config


def test_api_key_defined():
    assert hasattr(config, "API_KEY")


def test_model_strings():
    assert isinstance(config.MODEL_LOW, str)
    assert isinstance(config.MODEL_HIGH, str)
    assert "sonnet" in config.MODEL_LOW or "claude" in config.MODEL_LOW
    assert "opus" in config.MODEL_HIGH or "claude" in config.MODEL_HIGH


def test_max_tokens():
    assert isinstance(config.MAX_TOKENS, int)
    assert config.MAX_TOKENS > 0


def test_threshold_config():
    assert isinstance(config.FREQUENCY_THRESHOLD, int)
    assert isinstance(config.ROLE_THRESHOLD, int)
    assert config.FREQUENCY_THRESHOLD >= 1
    assert config.ROLE_THRESHOLD >= 1


def test_workflow_config():
    assert isinstance(config.WORKFLOWS_PER_CALL, int)
    assert isinstance(config.ITERATIONS_PER_ROLE, int)
    assert config.WORKFLOWS_PER_CALL >= 1
    assert config.ITERATIONS_PER_ROLE >= 1


def test_roles():
    assert isinstance(config.ROLES, list)
    assert len(config.ROLES) > 0
    for role_name, weight in config.ROLES:
        assert isinstance(role_name, str)
        assert isinstance(weight, float)
        assert 0 < weight <= 1.0
