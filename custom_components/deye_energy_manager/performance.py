"""Private, aggregate runtime performance diagnostics for Deye Energy Manager.

The collector deliberately has no Home Assistant entity, Store or event
listener of its own. It keeps only small in-memory counters and emits one
aggregate log record per reporting window.
"""

from __future__ import annotations

from collections import Counter
import json
import logging
import time
from typing import Any, Callable


_LOGGER = logging.getLogger("custom_components.deye_energy_manager.performance")


def run_core_with_timings(
    core_fn: Callable[[dict[str, Any], str], dict[str, Any]],
    payload: dict[str, Any],
    strategy: str,
    queued_clock: float,
) -> tuple[dict[str, Any], dict[str, float]]:
    """Run pure optimizer Core and return worker-side wall/CPU timings."""
    worker_started = time.perf_counter()
    cpu_started = time.thread_time()
    result = core_fn(payload, strategy)
    cpu_ms = (time.thread_time() - cpu_started) * 1000.0
    wall_ms = (time.perf_counter() - worker_started) * 1000.0
    return result, {
        "queue_wait_ms": max(0.0, (worker_started - queued_clock) * 1000.0),
        "wall_ms": max(0.0, wall_ms),
        "thread_cpu_ms": max(0.0, cpu_ms),
    }


class RuntimePerformanceMonitor:
    """Low-overhead private counters reset after each aggregate report."""

    REPORT_SECONDS = 60
    LAG_SECONDS = 1
    _MAX_SIZE_SAMPLES = 16

    def __init__(self) -> None:
        self._active = False
        self._window_started = 0.0
        self._next_lag_clock: float | None = None
        self._counters: dict[str, float] = {}
        self._maps: dict[str, Counter[str]] = {}
        self._reports_emitted = 0

    @property
    def active(self) -> bool:
        return self._active

    @property
    def reports_emitted(self) -> int:
        return self._reports_emitted

    def start(self, now: float | None = None) -> None:
        clock = time.perf_counter() if now is None else now
        self._active = True
        self._reset_window(clock)
        self._next_lag_clock = clock + self.LAG_SECONDS

    def stop(self) -> None:
        self._active = False
        self._next_lag_clock = None
        self._counters.clear()
        self._maps.clear()

    def inc(self, name: str, amount: int | float = 1) -> None:
        if not self._active:
            return
        self._counters[name] = self._counters.get(name, 0.0) + amount

    def set_value(self, name: str, value: int | float) -> None:
        if self._active:
            self._counters[name] = float(value)

    def inc_map(self, group: str, key: Any, amount: int = 1) -> None:
        if not self._active:
            return
        normalized = str(key or "unknown")
        self._maps.setdefault(group, Counter())[normalized] += amount

    def observe_ms(self, name: str, elapsed_ms: float) -> None:
        if not self._active:
            return
        value = max(0.0, float(elapsed_ms))
        self.inc(f"{name}_count")
        self.inc(f"{name}_total_ms", value)
        self._counters[f"{name}_max_ms"] = max(
            self._counters.get(f"{name}_max_ms", 0.0), value
        )

    def counter(self, name: str) -> float:
        """Expose a read-only scalar for focused tests, never HA state."""
        return self._counters.get(name, 0.0)

    def mapped(self, group: str) -> dict[str, int]:
        """Expose a copied map for focused tests, never HA state."""
        return dict(self._maps.get(group, {}))

    def record_optimizer_request(self, reasons: set[str]) -> None:
        self.inc("optimizer_request_total")
        for reason in reasons:
            self.inc_map("optimizer_request_by_reason", reason)

    def record_input_event(
        self, entity_id: str, *, accepted: bool, coalesced: bool
    ) -> None:
        self.inc("optimizer_input_events_total")
        self.inc_map("optimizer_input_events_by_entity", entity_id)
        if accepted:
            self.inc("optimizer_input_events_accepted_for_debounce")
        if coalesced:
            self.inc("optimizer_input_events_coalesced_debounced")

    def record_proxy_event(self, entity_id: str) -> None:
        self.inc("proxy_source_events_total")
        self.inc_map("proxy_source_events_by_entity", entity_id)

    def record_entity_write(
        self,
        entity_key: str,
        reason: str,
        *,
        channel: str | None = None,
    ) -> None:
        key = str(entity_key or "unknown")
        channel = channel or self._publication_channel(key)
        self.inc("attempted_entity_writes_total")
        self.inc_map("attempted_entity_writes_by_channel", channel)
        self.inc_map("attempted_entity_writes_by_reason", reason)
        self.inc(f"{channel}_write_calls")
        if channel == "proxy":
            self.inc("proxy_output_writes_total")

    def record_lag_tick(self, now: float | None = None) -> None:
        if not self._active:
            return
        clock = time.perf_counter() if now is None else now
        expected = self._next_lag_clock
        if expected is None:
            self._next_lag_clock = clock + self.LAG_SECONDS
            return
        lag_ms = max(0.0, (clock - expected) * 1000.0)
        self.inc("event_loop_lag_samples")
        self.inc("event_loop_lag_total_ms", lag_ms)
        self._counters["event_loop_lag_max_ms"] = max(
            self._counters.get("event_loop_lag_max_ms", 0.0), lag_ms
        )
        for threshold in (50, 100, 250, 500, 1000):
            if lag_ms >= threshold:
                self.inc(f"event_loop_lag_ge_{threshold}ms")
        # A single long stall must produce one observation, not repeated debt.
        self._next_lag_clock = clock + self.LAG_SECONDS

    def emit_report(self, runtime: Any, now: float | None = None) -> str | None:
        """Emit exactly one aggregate record and reset the reporting window."""
        if not self._active:
            return None
        clock = time.perf_counter() if now is None else now
        self._measure_payload_sizes(runtime)
        elapsed_s = max(0.0, clock - self._window_started)
        message = self._format_report(runtime, elapsed_s)
        _LOGGER.warning(message)
        self._reports_emitted += 1
        self._reset_window(clock)
        self._next_lag_clock = clock + self.LAG_SECONDS
        return message

    def _reset_window(self, now: float) -> None:
        self._window_started = now
        self._counters = {}
        self._maps = {}

    @staticmethod
    def _publication_channel(key: str) -> str:
        lowered = key.lower()
        if lowered.startswith("proxy_"):
            return "proxy"
        if lowered in {"ai_state", "ai_plan_48h", "ai_suggestion", "ai_status"}:
            return "ai_state"
        if "diagnostic" in lowered:
            return "diagnostics"
        if "solcast" in lowered and ("accuracy" in lowered or "history" in lowered):
            return "historical_solcast_accuracy"
        if "control" in lowered or "action" in lowered:
            return "control_status"
        if "tou" in lowered:
            return "tou"
        if "slot" in lowered or "schedule" in lowered:
            return "schedule"
        return "other"

    def _measure_payload_sizes(self, runtime: Any) -> None:
        started = time.perf_counter()
        solcast_payload = {
            "history": getattr(runtime, "solcast_history", []),
            "tracking": getattr(runtime, "solcast_tracking", {}),
        }
        energy_payload = {
            "samples": getattr(runtime, "energy_samples", []),
            "daily_archive": getattr(runtime, "daily_archive", []),
            "monthly_archive": getattr(runtime, "monthly_archive", []),
            "counter_state": getattr(runtime, "energy_counter_state", {}),
        }
        diagnostics = (
            runtime.diagnostics_public_snapshot()
            if callable(getattr(runtime, "diagnostics_public_snapshot", None))
            else getattr(runtime, "_diagnostics_snapshot", {})
        )
        payloads = {
            "ai_state_payload_bytes": getattr(runtime, "_ai_state_snapshot", {}),
            "diagnostics_payload_bytes": diagnostics,
            "historical_solcast_attrs_bytes": solcast_payload,
            "learning_summary_payload_bytes": getattr(runtime, "_learning_summary_cache", {}),
            "energy_store_payload_bytes": energy_payload,
        }
        self.set_value("energy_sample_count", len(getattr(runtime, "energy_samples", [])))
        for name, payload in payloads.items():
            self._counters[name] = float(self._estimate_json_bytes(payload))
        self.observe_ms(
            "payload_size_measure",
            (time.perf_counter() - started) * 1000.0,
        )

    @classmethod
    def _estimate_json_bytes(
        cls,
        value: Any,
        *,
        depth: int = 0,
        seen: set[int] | None = None,
    ) -> int:
        """Estimate JSON UTF-8 bytes using bounded samples for large sequences."""
        if depth > 12:
            return len(json.dumps(str(value), ensure_ascii=False).encode("utf-8"))
        if value is None or isinstance(value, (bool, int, float, str)):
            return len(
                json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            )
        if seen is None:
            seen = set()
        if isinstance(value, (dict, list, tuple, set)):
            identity = id(value)
            if identity in seen:
                return 4
            seen = {*seen, identity}
        if isinstance(value, dict):
            total = 2 + max(0, len(value) - 1)
            for key, item in value.items():
                total += len(
                    json.dumps(str(key), ensure_ascii=False, separators=(",", ":")).encode(
                        "utf-8"
                    )
                ) + 1
                total += cls._estimate_json_bytes(item, depth=depth + 1, seen=seen)
            return total
        if isinstance(value, (list, tuple, set)):
            sequence = value if isinstance(value, (list, tuple)) else tuple(value)
            length = len(sequence)
            if not length:
                return 2
            if length <= cls._MAX_SIZE_SAMPLES:
                sampled = sequence
            else:
                sampled = [
                    sequence[round(index * (length - 1) / (cls._MAX_SIZE_SAMPLES - 1))]
                    for index in range(cls._MAX_SIZE_SAMPLES)
                ]
            sample_bytes = sum(
                cls._estimate_json_bytes(item, depth=depth + 1, seen=seen)
                for item in sampled
            )
            estimated_items = round(sample_bytes / len(sampled) * length)
            return 2 + max(0, length - 1) + estimated_items
        return len(
            json.dumps(value, default=str, ensure_ascii=False, separators=(",", ":")).encode(
                "utf-8"
            )
        )

    def _format_report(self, runtime: Any, elapsed_s: float) -> str:
        get = self._counters.get

        def average(total: str, count: str) -> float:
            amount = get(count, 0.0)
            return get(total, 0.0) / amount if amount else 0.0

        def top(group: str, limit: int = 10) -> str:
            values = self._maps.get(group, Counter()).most_common(limit)
            return ",".join(f"{key}:{value}" for key, value in values) or "none"

        lines = [
            f"DEM PERF 60s window={elapsed_s:.1f}s control_enabled={bool(getattr(runtime, 'control_enabled', False))}",
            "event_loop_lag "
            f"samples={int(get('event_loop_lag_samples', 0))} "
            f"avg_ms={average('event_loop_lag_total_ms', 'event_loop_lag_samples'):.2f} "
            f"max_ms={get('event_loop_lag_max_ms', 0):.2f} "
            f"ge50={int(get('event_loop_lag_ge_50ms', 0))} "
            f"ge100={int(get('event_loop_lag_ge_100ms', 0))} "
            f"ge250={int(get('event_loop_lag_ge_250ms', 0))} "
            f"ge500={int(get('event_loop_lag_ge_500ms', 0))} "
            f"ge1000={int(get('event_loop_lag_ge_1000ms', 0))}",
            "optimizer "
            f"requests={int(get('optimizer_request_total', 0))} "
            f"started={int(get('optimizer_started', 0))} "
            f"same={int(get('optimizer_skipped_same_snapshot', 0))} "
            f"busy={int(get('optimizer_skipped_busy', 0))} "
            f"pending={int(get('optimizer_pending_set', 0))} "
            f"followup={int(get('optimizer_followup_started', 0))} "
            f"completed={int(get('optimizer_completed', 0))} "
            f"failed={int(get('optimizer_failed', 0))} "
            f"reasons=[{top('optimizer_request_by_reason')}]",
            "optimizer_timing "
            f"prepare_count={int(get('optimizer_prepare_count', 0))} "
            f"prepare_total_ms={get('optimizer_prepare_total_ms', 0):.2f} "
            f"prepare_max_ms={get('optimizer_prepare_max_ms', 0):.2f} "
            f"queue_total_ms={get('optimizer_executor_queue_wait_total_ms', 0):.2f} "
            f"queue_max_ms={get('optimizer_executor_queue_wait_max_ms', 0):.2f} "
            f"core_wall_total_ms={get('optimizer_core_wall_total_ms', 0):.2f} "
            f"core_wall_max_ms={get('optimizer_core_wall_max_ms', 0):.2f} "
            f"core_thread_cpu_total_ms={get('optimizer_core_thread_cpu_total_ms', 0):.2f} "
            f"core_thread_cpu_max_ms={get('optimizer_core_thread_cpu_max_ms', 0):.2f} "
            f"apply_total_ms={get('optimizer_apply_result_total_ms', 0):.2f} "
            f"apply_max_ms={get('optimizer_apply_result_max_ms', 0):.2f}",
            "snapshots "
            f"ai_builds={int(get('ai_snapshot_build_count', 0))} "
            f"ai_total_ms={get('ai_snapshot_build_total_ms', 0):.2f} "
            f"ai_max_ms={get('ai_snapshot_build_max_ms', 0):.2f} "
            f"diagnostics_builds={int(get('diagnostics_build_count', 0))} "
            f"diagnostics_total_ms={get('diagnostics_build_total_ms', 0):.2f} "
            f"diagnostics_max_ms={get('diagnostics_build_max_ms', 0):.2f}",
            "publish "
            f"full_calls={int(get('notify_update_full_calls', 0))} "
            f"granular_calls={int(get('notify_granular_calls', 0))} "
            f"writes={int(get('attempted_entity_writes_total', 0))} "
            f"full_total_ms={get('full_publish_total_ms', 0):.2f} "
            f"full_max_ms={get('full_publish_max_ms', 0):.2f} "
            f"reasons=[{top('notify_update_full_by_reason')}] "
            f"channels=[{top('attempted_entity_writes_by_channel')}] "
            f"write_reasons=[{top('attempted_entity_writes_by_reason')}]",
            "proxy "
            f"source_events={int(get('proxy_source_events_total', 0))} "
            f"output_writes={int(get('proxy_output_writes_total', 0))} "
            f"top=[{top('proxy_source_events_by_entity')}]",
            "optimizer_inputs "
            f"events={int(get('optimizer_input_events_total', 0))} "
            f"accepted={int(get('optimizer_input_events_accepted_for_debounce', 0))} "
            f"coalesced={int(get('optimizer_input_events_coalesced_debounced', 0))} "
            f"semantic_changed={int(get('optimizer_semantic_snapshot_changed', 0))} "
            f"semantic_same={int(get('optimizer_semantic_snapshot_same', 0))} "
            f"top=[{top('optimizer_input_events_by_entity')}]",
            "learning "
            f"wrapper_calls={int(get('learning_summary_wrapper_calls', 0))} "
            f"cache_hits={int(get('learning_summary_cache_hits', 0))} "
            f"build_calls={int(get('learning_summary_build_count', 0))} "
            f"build_total_ms={get('learning_summary_build_total_ms', 0):.2f} "
            f"build_max_ms={get('learning_summary_build_max_ms', 0):.2f}",
            "energy "
            f"collect_calls={int(get('energy_collect_count', 0))} "
            f"collect_total_ms={get('energy_collect_total_ms', 0):.2f} "
            f"collect_max_ms={get('energy_collect_max_ms', 0):.2f} "
            f"sample_count={int(get('energy_sample_count', 0))}",
            "stores "
            f"ai_saves={int(get('ai_store_save_count', 0))}/{get('ai_store_save_total_ms', 0):.2f}ms "
            f"ai_prep={int(get('ai_store_prepare_count', 0))}/{get('ai_store_prepare_total_ms', 0):.2f}ms "
            f"learning_saves={int(get('learning_store_save_count', 0))}/{get('learning_store_save_total_ms', 0):.2f}ms "
            f"learning_prep={int(get('learning_store_prepare_count', 0))}/{get('learning_store_prepare_total_ms', 0):.2f}ms "
            f"energy_saves={int(get('energy_store_save_count', 0))}/{get('energy_store_save_total_ms', 0):.2f}ms "
            f"energy_prep={int(get('energy_store_prepare_count', 0))}/{get('energy_store_prepare_total_ms', 0):.2f}ms",
            "control "
            f"requested={int(get('inverter_write_requested', 0))} "
            f"executed={int(get('inverter_write_executed', 0))} "
            f"same={int(get('inverter_write_skipped_same_value', 0))} "
            f"readback={int(get('inverter_readback', 0))} "
            f"confirm_start={int(get('inverter_confirmation_started', 0))} "
            f"confirm_done={int(get('inverter_confirmation_completed', 0))} "
            f"confirm_timeout={int(get('inverter_confirmation_timeout', 0))} "
            f"rollback={int(get('inverter_rollback', 0))} "
            f"tou_executed={int(get('tou_write_executed', 0))}",
            "payload_bytes "
            f"ai={int(get('ai_state_payload_bytes', 0))} "
            f"diagnostics={int(get('diagnostics_payload_bytes', 0))} "
            f"solcast={int(get('historical_solcast_attrs_bytes', 0))} "
            f"learning={int(get('learning_summary_payload_bytes', 0))} "
            f"energy_store={int(get('energy_store_payload_bytes', 0))} "
            f"measure_ms={get('payload_size_measure_total_ms', 0):.2f}",
        ]
        return "\n".join(lines)
