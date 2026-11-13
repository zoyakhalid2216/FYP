import pytest

from src.automation.safety import SafetyLimitError, SafetyPolicy


def test_safety_action_limit():
    policy = SafetyPolicy(max_actions=2)
    policy.check_actions(2)
    with pytest.raises(SafetyLimitError):
        policy.check_actions(3)


def test_safety_time_limit():
    policy = SafetyPolicy(max_seconds=5)
    policy.check_time(4.9)
    with pytest.raises(SafetyLimitError):
        policy.check_time(5.1)


def test_safety_from_config_strings():
    policy = SafetyPolicy.from_config(
        {"automation": {"max_actions": 10}},
        {"max_actions": "12", "max_retries": "2", "verify_actions": "1"},
    )
    assert policy.max_actions == 12
    assert policy.max_retries == 2
    assert policy.verify_change is True
