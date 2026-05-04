"""Performance timing utilities for anxwritter build profiling."""
from __future__ import annotations

import time
from contextlib import contextmanager
from typing import List, Optional, Tuple

from loguru import logger


class PhaseTimer:
    """Accumulates named phase timings for a build operation."""

    def __init__(self, scope: str):
        self.scope = scope
        self.phases: List[Tuple[str, float]] = []
        self._start: float = time.perf_counter()

    @contextmanager
    def phase(self, name: str):
        t0 = time.perf_counter()
        yield
        elapsed = time.perf_counter() - t0
        self.phases.append((name, elapsed))
        logger.debug("{scope} | {name}: {elapsed:.4f}s",
                     scope=self.scope, name=name, elapsed=elapsed)

    def record(self, name: str, elapsed: float):
        self.phases.append((name, elapsed))
        logger.debug("{scope} | {name}: {elapsed:.4f}s",
                     scope=self.scope, name=name, elapsed=elapsed)

    @property
    def total(self) -> float:
        return time.perf_counter() - self._start

    def summary(self, extra: str = "",
                sub_timings: Optional[List[Tuple[str, PhaseTimer]]] = None):
        total = self.total
        lines = [f"[{self.scope}] Total: {total:.3f}s"
                 + (f" | {extra}" if extra else "")]
        for name, elapsed in self.phases:
            pct = (elapsed / total * 100) if total > 0 else 0
            lines.append(f"  {name:<30s} {elapsed:>8.4f}s {pct:>5.1f}%")
            if sub_timings:
                for parent_name, sub_timer in sub_timings:
                    if parent_name == name and sub_timer is not None:
                        sub_total = sum(e for _, e in sub_timer.phases)
                        for sn, se in sub_timer.phases:
                            sp = (se / sub_total * 100) if sub_total > 0 else 0
                            lines.append(
                                f"    {sn:<28s} {se:>8.4f}s {sp:>5.1f}%")
        logger.debug("\n" + "\n".join(lines))
