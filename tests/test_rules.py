from __future__ import annotations

import pytest

from cloudops_inspector.rules import RuleSet, expected_status, threshold_status
from cloudops_inspector.models import Status


def test_threshold_status():
    rule = {"warn": 80, "crit": 90}
    assert threshold_status(50, rule) == Status.OK
    assert threshold_status(80, rule) == Status.WARN
    assert threshold_status(95, rule) == Status.CRIT


def test_threshold_lower_is_worse():
    rule = {"warn": 90, "crit": 50}
    assert threshold_status(95, rule, higher_is_worse=False) == Status.OK
    assert threshold_status(90, rule, higher_is_worse=False) == Status.WARN
    assert threshold_status(40, rule, higher_is_worse=False) == Status.CRIT


def test_expected_status_severity():
    assert expected_status("no", "no") == Status.OK
    assert expected_status("yes", "no") == Status.WARN
    assert expected_status("yes", "no", {"severity": "crit"}) == Status.CRIT


def test_rule_set_load(rules):
    assert rules.enabled("disk_usage")
    assert rules.get("disk_usage")["crit"] == 90
    assert "cpu_usage" in rules.enabled_ids()


def test_rule_can_disable(tmp_path):
    path = tmp_path / "rules.yml"
    path.write_text("checks:\n  uptime:\n    enabled: false\n", encoding="utf-8")
    rules = RuleSet.load(path)
    assert rules.enabled("uptime") is False
