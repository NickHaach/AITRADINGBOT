"""In-process autopilot: scheduled trading cycles with quiet hours + kill switch."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional

from ai_trading_shared.utils.logging import get_logger
from pydantic import BaseModel, Field

logger = get_logger(__name__)

RunCycleFn = Callable[[], Awaitable[dict]]


class AutopilotConfig(BaseModel):
    enabled: bool = False
    interval_minutes: int = Field(15, ge=1, le=240)
    quiet_start_hour: int = Field(22, ge=0, le=23)  # UTC
    quiet_end_hour: int = Field(6, ge=0, le=23)  # UTC
    kill_switch: bool = False
    tickers: Optional[str] = None  # comma-separated; None = default universe


class AutopilotStatus(BaseModel):
    enabled: bool
    interval_minutes: int
    quiet_start_hour: int
    quiet_end_hour: int
    kill_switch: bool
    tickers: Optional[str] = None
    in_quiet_hours: bool = False
    last_run_at: Optional[str] = None
    next_run_at: Optional[str] = None
    last_error: Optional[str] = None
    last_result: Optional[dict] = None
    runs: int = 0


class AutopilotController:
    """Owns a single asyncio loop that calls the portfolio cycle runner."""

    def __init__(self, run_cycle: RunCycleFn, set_kill_switch: Callable[[bool], None]) -> None:
        self._run_cycle = run_cycle
        self._set_kill_switch = set_kill_switch
        self.config = AutopilotConfig()
        self.last_run_at: Optional[datetime] = None
        self.next_run_at: Optional[datetime] = None
        self.last_error: Optional[str] = None
        self.last_result: Optional[dict] = None
        self.runs = 0
        self._task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()

    def in_quiet_hours(self, now: Optional[datetime] = None) -> bool:
        now = now or datetime.now(timezone.utc)
        hour = now.hour
        start = self.config.quiet_start_hour
        end = self.config.quiet_end_hour
        if start == end:
            return False
        if start < end:
            return start <= hour < end
        # wraps midnight (e.g. 22 → 6)
        return hour >= start or hour < end

    def status(self) -> AutopilotStatus:
        now = datetime.now(timezone.utc)
        return AutopilotStatus(
            enabled=self.config.enabled,
            interval_minutes=self.config.interval_minutes,
            quiet_start_hour=self.config.quiet_start_hour,
            quiet_end_hour=self.config.quiet_end_hour,
            kill_switch=self.config.kill_switch,
            tickers=self.config.tickers,
            in_quiet_hours=self.in_quiet_hours(now),
            last_run_at=self.last_run_at.isoformat() if self.last_run_at else None,
            next_run_at=self.next_run_at.isoformat() if self.next_run_at else None,
            last_error=self.last_error,
            last_result=self.last_result,
            runs=self.runs,
        )

    def apply_config(self, patch: AutopilotConfig) -> AutopilotStatus:
        was_enabled = self.config.enabled
        self.config = patch
        self._set_kill_switch(patch.kill_switch)
        if patch.enabled and not was_enabled:
            self.start()
        elif not patch.enabled and was_enabled:
            self.stop()
        elif patch.enabled and self._task is None:
            self.start()
        return self.status()

    def start(self) -> AutopilotStatus:
        self.config.enabled = True
        self._stop.clear()
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop(), name="portfolio-autopilot")
            logger.info(
                "autopilot_started",
                interval=self.config.interval_minutes,
                quiet=f"{self.config.quiet_start_hour}-{self.config.quiet_end_hour}",
            )
        return self.status()

    def stop(self) -> AutopilotStatus:
        self.config.enabled = False
        self._stop.set()
        self.next_run_at = None
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = None
        logger.info("autopilot_stopped")
        return self.status()

    async def shutdown(self) -> None:
        self.stop()

    async def _loop(self) -> None:
        # Short initial delay so boot seed finishes first
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=5.0)
            return
        except asyncio.TimeoutError:
            pass

        while self.config.enabled and not self._stop.is_set():
            now = datetime.now(timezone.utc)
            if self.config.kill_switch:
                self.last_error = "Kill switch armed — cycles paused"
                self.next_run_at = None
            elif self.in_quiet_hours(now):
                self.last_error = None
                self.next_run_at = None
                logger.debug("autopilot_quiet_hours")
            else:
                try:
                    result = await self._run_cycle()
                    self.last_run_at = datetime.now(timezone.utc)
                    self.last_result = {
                        "approved_trades": result.get("approved_trades"),
                        "rejected_trades": result.get("rejected_trades"),
                        "signals": result.get("signals"),
                        "closed_outcomes": result.get("closed_outcomes"),
                        "equity": result.get("equity"),
                    }
                    self.last_error = None
                    self.runs += 1
                    logger.info("autopilot_cycle_ok", runs=self.runs)
                except Exception as exc:  # noqa: BLE001
                    self.last_error = str(exc)[:300]
                    logger.exception("autopilot_cycle_failed")

            interval = max(60, int(self.config.interval_minutes) * 60)
            from datetime import timedelta

            self.next_run_at = datetime.now(timezone.utc) + timedelta(seconds=interval)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=float(interval))
                break
            except asyncio.TimeoutError:
                continue
