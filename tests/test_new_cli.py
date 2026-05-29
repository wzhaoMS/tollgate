"""Tests for the new CLI commands."""
from __future__ import annotations

from src import cli


def test_cmd_seed_all(tmpdb):
    code = cli.cmd_seed_all([])
    assert code == 0


def test_cmd_capacity_builtin(tmpdb):
    code = cli.cmd_capacity(["--builtin"])
    assert code == 0


def test_cmd_capacity_lifecycle(tmpdb):
    from src import capacity_tracker
    capacity_tracker.import_builtin_capacity()
    code = cli.cmd_capacity(["--ticker", "AXTI"])
    assert code == 0


def test_cmd_governance_builtin(tmpdb):
    code = cli.cmd_governance(["--builtin"])
    assert code == 0


def test_cmd_supplier_pages_builtin(tmpdb):
    code = cli.cmd_supplier_pages(["--builtin"])
    assert code == 0


def test_cmd_alerts_empty(tmpdb):
    code = cli.cmd_alerts([])
    assert code == 0


def test_cmd_lifecycle_no_data(tmpdb):
    code = cli.cmd_lifecycle([])
    assert code == 0


def test_cmd_lifecycle_with_data(tmpdb):
    from src import capacity_tracker
    capacity_tracker.import_builtin_capacity()
    code = cli.cmd_lifecycle(["--ticker", "AXTI"])
    assert code == 0
