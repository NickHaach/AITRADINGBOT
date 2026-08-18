"""Autopilot quiet hours + start/stop."""

from __future__ import annotations

from datetime import datetime, timezone

from portfolio.autopilot import AutopilotConfig, AutopilotController


async def _noop() -> dict:
    return {}


def test_quiet_hours_wraps_midnight() -> None:
    ctrl = AutopilotController(run_cycle=_noop, set_kill_switch=lambda _: None)
    ctrl.config = AutopilotConfig(quiet_start_hour=22, quiet_end_hour=6)
    night = datetime(2026, 8, 5, 23, 0, tzinfo=timezone.utc)
    morning = datetime(2026, 8, 6, 3, 0, tzinfo=timezone.utc)
    midday = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)
    assert ctrl.in_quiet_hours(night) is True
    assert ctrl.in_quiet_hours(morning) is True
    assert ctrl.in_quiet_hours(midday) is False


def test_apply_config_sets_kill_switch() -> None:
    armed: list[bool] = []
    ctrl = AutopilotController(run_cycle=_noop, set_kill_switch=armed.append)
    status = ctrl.apply_config(
        AutopilotConfig(enabled=False, interval_minutes=5, kill_switch=True)
    )
    assert status.kill_switch is True
    assert armed[-1] is True
