from __future__ import annotations

import asyncio
import contextvars
from contextlib import asynccontextmanager, contextmanager
from copy import deepcopy
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from functools import partial
import logging
import math
import time
from typing import Any, Callable
import uuid

_LOGGER = logging.getLogger(__name__)

_HOMEASSISTANT_STARTED_EVENT = "homeassistant_started"

# A daily forecast may legitimately be published only a few times per day.
# Thirty hours also covers the longest local DST day without accepting an
# entity that has not refreshed since the preceding local day.
_SOLCAST_DAILY_FORECAST_STALE_SECONDS = 30 * 60 * 60
_SOLCAST_TRACKING_STALE_SECONDS = 30 * 60

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import (
    async_track_point_in_time,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store
from homeassistant.util.dt import now as ha_now

from .const import (
    CONF_BATTERY_BMS_VOLTAGE_SENSOR,
    CONF_BATTERY_CURRENT_SENSOR,
    CONF_BATTERY_SOH_SENSOR,
    CONF_BATTERY_SOC_SENSOR,
    CONF_BATTERY_POSITIVE_IS_DISCHARGE,
    CONF_BATTERY_TEMPERATURE_SENSOR,
    CONF_BUY_PRICE_TODAY_SENSOR,
    CONF_BUY_PRICE_TOMORROW_SENSOR,
    CONF_BUY_SELLER_ID,
    CONF_BUY_SELLER_TARIFF_ID,
    CONF_CHARGE_CURRENT_NUMBER,
    CONF_DAILY_BATTERY_CHARGE_SENSOR,
    CONF_DAILY_BATTERY_DISCHARGE_SENSOR,
    CONF_DAILY_ENERGY_BOUGHT_SENSOR,
    CONF_DAILY_ENERGY_SOLD_SENSOR,
    CONF_DAILY_LOAD_CONSUMPTION_SENSOR,
    CONF_DAILY_PV_PRODUCTION_SENSOR,
    CONF_GRID_CHARGE_CURRENT_NUMBER,
    CONF_GRID_L1_POWER_SENSOR,
    CONF_GRID_L1_VOLTAGE_SENSOR,
    CONF_GRID_L2_POWER_SENSOR,
    CONF_GRID_L2_VOLTAGE_SENSOR,
    CONF_GRID_L3_POWER_SENSOR,
    CONF_GRID_L3_VOLTAGE_SENSOR,
    CONF_GRID_POWER_SENSOR,
    CONF_GRID_POSITIVE_IS_IMPORT,
    CONF_INVERTER_AC_TEMPERATURE_SENSOR,
    CONF_INVERTER_DEVICE_ID,
    CONF_INVERTER_MAX_POWER_W,
    CONF_INVERTER_PROVIDER,
    CONF_LOAD_FREQUENCY_SENSOR,
    CONF_LOAD_L1_POWER_SENSOR,
    CONF_LOAD_L2_POWER_SENSOR,
    CONF_LOAD_L3_POWER_SENSOR,
    CONF_LOAD_POWER_SENSOR,
    CONF_BATTERY_POWER_SENSOR,
    CONF_DISCHARGE_CURRENT_NUMBER,
    CONF_MAX_SELL_POWER_NUMBER,
    CONF_PV1_CURRENT_SENSOR,
    CONF_PV1_POWER_SENSOR,
    CONF_PV1_VOLTAGE_SENSOR,
    CONF_PV2_CURRENT_SENSOR,
    CONF_PV2_POWER_SENSOR,
    CONF_PV2_VOLTAGE_SENSOR,
    CONF_PV3_POWER_SENSOR,
    CONF_PV_POWER_SENSOR,
    CONF_PRICE_SENSOR,
    CONF_SELL_PRICE_TOMORROW_SENSOR,
    CONF_SOLCAST_CURRENT_POWER_SENSOR,
    CONF_SOLCAST_FORECAST_DAY_3_SENSOR,
    CONF_SOLCAST_FORECAST_DAY_4_SENSOR,
    CONF_SOLCAST_FORECAST_DAY_5_SENSOR,
    CONF_SOLCAST_FORECAST_DAY_6_SENSOR,
    CONF_SOLCAST_FORECAST_DAY_7_SENSOR,
    CONF_SOLCAST_FORECAST_TODAY_SENSOR,
    CONF_SOLCAST_FORECAST_TOMORROW_SENSOR,
    CONF_SOLCAST_PEAK_POWER_TODAY_SENSOR,
    CONF_SOLCAST_PEAK_TIME_TODAY_SENSOR,
    CONF_SOLCAST_REMAINING_TODAY_SENSOR,
    CONF_WORK_MODE_SELECT,
    CONF_WORK_MODE_AUX_ENTITY,
    CONF_WEATHER_ENTITY,
    CONF_PRICE_SOURCE,
    CONF_OSD_PROVIDER,
    CONF_TARIFF_PLAN,
    CONF_DISTRIBUTION_PEAK_RATE,
    CONF_DISTRIBUTION_OFFPEAK_RATE,
    CONF_CUSTOM_OFFPEAK_WINDOWS,
    CONF_TARIFF_MODE,
    CONF_PRICE_INCLUDES_DISTRIBUTION,
    CONF_BUY_PRICE_CONTRACT,
    CONF_SELL_PRICE_CONTRACT,
    CONF_TARIFF_CATALOG_URL,
    CONTROL_MODES,
    DOMAIN,
    MANAGER_MODES,
    MODE_SELLING_FIRST,
    MODE_CHARGE,
    MODE_NORMAL_OPERATION,
    MODE_ZERO_EXPORT,
    MODE_ZERO_EXPORT_CT,
    normalize_manager_mode,
    PHYSICAL_NORMAL_MODES,
    SCHEDULE_SCHEMA_VERSION,
    SLOTS,
    SLOT_MODES,
    WORK_MODES,
    DEFAULT_BATTERY_SOC,
    DEFAULT_BATTERY_BMS_VOLTAGE_SENSOR,
    DEFAULT_BATTERY_CURRENT_SENSOR,
    DEFAULT_BATTERY_SOH_SENSOR,
    DEFAULT_BATTERY_TEMPERATURE_SENSOR,
    DEFAULT_DAILY_BATTERY_CHARGE_SENSOR,
    DEFAULT_DAILY_BATTERY_DISCHARGE_SENSOR,
    DEFAULT_DAILY_ENERGY_BOUGHT_SENSOR,
    DEFAULT_DAILY_ENERGY_SOLD_SENSOR,
    DEFAULT_DAILY_LOAD_CONSUMPTION_SENSOR,
    DEFAULT_DAILY_PV_PRODUCTION_SENSOR,
    DEFAULT_GRID_CHARGE_CURRENT,
    DEFAULT_GRID_L1_POWER_SENSOR,
    DEFAULT_GRID_L1_VOLTAGE_SENSOR,
    DEFAULT_GRID_L2_POWER_SENSOR,
    DEFAULT_GRID_L2_VOLTAGE_SENSOR,
    DEFAULT_GRID_L3_POWER_SENSOR,
    DEFAULT_GRID_L3_VOLTAGE_SENSOR,
    DEFAULT_GRID_POWER_SENSOR,
    DEFAULT_INVERTER_AC_TEMPERATURE_SENSOR,
    DEFAULT_INVERTER_MAX_POWER_W,
    DEFAULT_INVERTER_PROVIDER,
    DEFAULT_LOAD_FREQUENCY_SENSOR,
    DEFAULT_LOAD_L1_POWER_SENSOR,
    DEFAULT_LOAD_L2_POWER_SENSOR,
    DEFAULT_LOAD_L3_POWER_SENSOR,
    DEFAULT_LOAD_POWER_SENSOR,
    DEFAULT_BATTERY_POWER_SENSOR,
    DEFAULT_PV1_CURRENT_SENSOR,
    DEFAULT_PV1_POWER_SENSOR,
    DEFAULT_PV1_VOLTAGE_SENSOR,
    DEFAULT_PV2_CURRENT_SENSOR,
    DEFAULT_PV2_POWER_SENSOR,
    DEFAULT_PV2_VOLTAGE_SENSOR,
    DEFAULT_PV3_POWER_SENSOR,
    DEFAULT_PV_POWER_SENSOR,
    DEFAULT_PRICE_SENSOR,
    DEFAULT_SOLCAST_CURRENT_POWER_SENSOR,
    DEFAULT_SOLCAST_FORECAST_DAY_3_SENSOR,
    DEFAULT_SOLCAST_FORECAST_DAY_4_SENSOR,
    DEFAULT_SOLCAST_FORECAST_DAY_5_SENSOR,
    DEFAULT_SOLCAST_FORECAST_DAY_6_SENSOR,
    DEFAULT_SOLCAST_FORECAST_DAY_7_SENSOR,
    DEFAULT_SOLCAST_FORECAST_TODAY_SENSOR,
    DEFAULT_SOLCAST_FORECAST_TOMORROW_SENSOR,
    DEFAULT_SOLCAST_PEAK_POWER_TODAY_SENSOR,
    DEFAULT_SOLCAST_PEAK_TIME_TODAY_SENSOR,
    DEFAULT_SOLCAST_REMAINING_TODAY_SENSOR,
    DEFAULT_WEATHER_ENTITY,
    DEFAULT_OSD_PROVIDER,
    DEFAULT_TARIFF_PLAN,
    DEFAULT_DISTRIBUTION_PEAK_RATE,
    DEFAULT_DISTRIBUTION_OFFPEAK_RATE,
    DEFAULT_CUSTOM_OFFPEAK_WINDOWS,
    DEFAULT_TARIFF_MODE,
    DEFAULT_PRICE_INCLUDES_DISTRIBUTION,
    DEFAULT_TARIFF_CATALOG_URL,
    DEFAULT_BUY_SELLER_ID,
    DEFAULT_BUY_SELLER_TARIFF_ID,
    DEFAULT_GRID_POSITIVE_IS_IMPORT,
    DEFAULT_BATTERY_POSITIVE_IS_DISCHARGE,
    DEFAULT_MAX_SELL_POWER,
    DEFAULT_DISCHARGE_CURRENT,
    DEFAULT_CHARGE_CURRENT,
    DEFAULT_GRID_CHARGE_CURRENT,
    DEFAULT_WORK_MODE_SELECT,
    PROVIDER_LEWA_REKA,
    PROVIDER_SOLARMAN,
    PROVIDER_SUNSYNK,
    conf_tou_entity,
)
from .price_sources import (
    SUPPORTED_ECONOMIC_ROLES,
    build_canonical_direction,
    canonical_maps,
    detect_source_adapter,
    effective_contract_for_day,
    price_mapping_fingerprint,
    rebuild_price_contract,
    resolve_contract_schemas,
)
from .inverter_provider import (
    boolean_state as provider_boolean_state,
    boolean_option as provider_boolean_option,
    convert_w_to_native_unit,
    detect_entity_max_power_w,
    format_time_option,
    logical_mode_matches,
    logical_mode_option,
    normal_profile_mode_metadata,
    number_entity_range,
    NumberEntityRange,
    operation_for_entity,
    profile as provider_profile,
    provider_tou_field_capabilities,
    provider_key,
    resolve_select_option,
    state_matches_boolean,
)
from .tariff_catalog import TariffCatalogManager
from .performance import RuntimePerformanceMonitor, run_core_with_timings
from .ai_planner import (
    ALGORITHM_VERSION,
    DEFAULT_MINIMUM_AUTO_SELL_POWER_W,
    DEFAULT_PRICE_EQUIVALENCE_BAND,
    PLAN_SCHEMA_VERSION,
    build_plan_bundle,
    quantize_power_w,
    simulate_alternative,
    snapshot_id,
)
from .ai_assistant import (
    build_private_payload,
    material_review_fingerprint,
    normalize_config as normalize_ai_api_config,
    redact_config as redact_ai_api_config,
    request_analysis as request_ai_analysis,
)
from .battery_model import (
    build_soc_timeline,
    effective_minimum,
    effective_power_limit,
    migrate_efficiencies,
    remaining_minutes_in_hour,
)
from .history import (
    ENERGY_COMPACT_FORMAT_VERSION,
    HISTORY_SCHEMA_VERSION,
    compact_energy_sample,
    default_user_profiles,
    energy_kwh,
    finite_float,
    migrate_ai_payload,
    migrate_energy_payload,
    migrate_learning_payload,
    migrate_solcast_payload,
    power_w,
    update_energy_counter,
)
from .learning import (
    corrected_pv_forecast,
    forecast_load,
    learning_maturity,
    learning_stage,
    load_profile_diagnostics,
    pv_profile_diagnostics,
    pv_quality_flags,
    update_load_profile,
    update_pv_profile,
)
from .telemetry import (
    channel_summary,
    energy_balance,
    new_channel,
    record_channel,
    split_directional_power,
)
from .tariffs import (
    available_tariffs,
    catalog_hourly_profile,
    get_tariff,
    hourly_tariff_profile,
    parse_windows,
    resolve_seller_tariff,
    seller_catalog_canonical_buy,
    seller_catalog_options,
    seller_support_entry,
    seller_tariff_options,
    tariff_availability,
    tariff_zone,
)


_CONTROL_TRANSACTION_ID: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "control_transaction_id", default=None
)

# Live PV/load noise is material to a rolling plan only after crossing a 25%
# forecast-deviation band. The 250 W denominator floor prevents tiny night/base
# forecasts from turning sensor jitter into repeated Core runs. Both constants
# are covered by the 5G.4D rolling-recalc tests.
LIVE_DEVIATION_BUCKET_RATIO = 0.25
LIVE_DEVIATION_REFERENCE_FLOOR_W = 250.0
FUTURE_PLAN_INTENT_SCHEMA_VERSION = 2
FUTURE_PLAN_LIFECYCLE_SCHEMA_VERSION = 1


class ControlDisabledError(Exception):
    """Raised when a physical write is attempted while control is disabled."""


class FuturePlanTransientError(RuntimeError):
    """A future slot is safe to retry while its hour is still active."""


class ExternalAIDailyLimitError(RuntimeError):
    """Raised before a provider call that would exceed the persisted daily cap."""


@dataclass
class SlotSettings:
    key: str
    label: str
    enabled: bool = False
    mode: str = MODE_NORMAL_OPERATION
    # Physical Deye work mode used only by logical Normal Operation slots.
    # It is intentionally independent from ``mode`` so no UI/logical label can
    # ever be sent to the inverter select entity.
    physical_work_mode: str | None = None
    sell_power: float = 0
    discharge_current: float = 0
    # Per-slot permission for physical Deye TOU Grid Charge.  It is meaningful
    # only while this slot uses MODE_CHARGE; a positive current alone never
    # grants permission to charge from the grid.
    charge_enabled: bool = False
    charge_current: float = 0
    grid_charge_current: float = 0
    # Manager safety threshold that stops Selling First when the battery SOC
    # reaches this value.  It is a logical guard only and must never be written
    # to the physical Deye Time Of Use SOC.
    minimum_sell_soc: float = 0
    # Physical Deye Time Of Use SOC for this logical slot.  It is deliberately
    # unknown until restored from the user's prior configuration or explicitly
    # confirmed by the user.  All logical modes (Normal, Charge, Selling First
    # and disabled) use this value as the physical SOC written to the inverter.
    tou_soc: float | None = None
    min_sell_price: float = 0
    # True only for a Selling slot materialised by Optimizer Core Apply Today.
    # Such a slot owns the sell power, never the inverter's global maximum
    # battery discharge current.  RestoreEntity persists this marker through
    # the slot-mode entity attributes.
    ai_sell_power_only: bool = False


@dataclass
class TouMappingSlot:
    """One physical Deye Time Of Use slot.

    The model intentionally holds only the fields the inverter can store per
    range: start/end time, SOC and the hourly Grid Charge permission.  Manager
    logical modes, sell power, currents, prices and physical work mode variants
    are runtime overlays and are never persisted here.
    """

    index: int
    start: int
    end: int
    soc: float
    grid_charge: bool
    source_hours: list[int] = field(default_factory=list)
    provider_fields: dict[str, Any] = field(default_factory=dict)


@dataclass
class TouMapping:
    """A complete 24-hour physical Deye TOU mapping."""

    slots: list[TouMappingSlot] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.slots)


@dataclass
class DeyeEnergyManagerRuntime:
    hass: HomeAssistant
    entry_id: str
    data: dict[str, Any]
    scheduler_enabled: bool = False
    soc_guard_enabled: bool = True
    price_guard_enabled: bool = False
    emergency_stop: bool = False
    control_mode: str = "Schedule"
    min_sell_soc: float = 30
    price_sell_threshold: float = 0
    manual_sell_power: float = 3000
    manual_discharge_current: float = 80
    manual_charge_current: float = 60
    default_work_mode: str = MODE_NORMAL_OPERATION
    default_physical_work_mode: str | None = None
    default_sell_power: float = 0
    default_discharge_current: float = 0
    default_charge_current: float = 0
    default_grid_charge_current: float = 0
    # Separate values used exclusively by planned Charge slots.  They are
    # independent from the full default/recovery state above.
    charge_profile_charge_current: float = 0
    charge_profile_discharge_current: float = 0
    charge_profile_grid_charge_current: float = 0
    charge_profile_target_soc: float = 100
    # The only permission to enable Deye Grid Charge for Charge slots.
    charge_profile_grid_enabled: bool = False
    # User-owned Normal Operation template.  The physical mode is mandatory
    # and accepts only the two zero-export variants supported by Deye.
    normal_profile_physical_work_mode: str | None = None
    normal_profile_sell_power: float = 0
    normal_profile_discharge_current: float = 0
    normal_profile_charge_current: float = 0
    normal_profile_grid_charge_current: float = 0
    normal_profile_tou_soc: float | None = None
    _normal_profile_loaded_from_store: bool = False
    schedule_schema_version: int = 0
    _restored_slot_mode_keys: set[str] = field(default_factory=set)
    # Track which per-slot helper entities have been restored so the 5A.1
    # migration can safely resolve a missing selling slot tou_soc.
    _restored_slot_tou_soc_keys: set[str] = field(default_factory=set)
    _restored_slot_minimum_sell_soc_keys: set[str] = field(default_factory=set)
    _tou_soc_migration_done: bool = False
    # Stage 5B: physical Deye Time Of Use transaction state.
    tou_write_pending: bool = False
    tou_operation_status: str = "idle"
    # Stable Stage 5C contract.  ``tou_operation_status`` is retained for
    # compatibility with the Stage 5B diagnostics and tests.
    tou_contract_status: str = "idle"
    tou_operation_started_at: datetime | None = None
    tou_last_error: str = ""
    tou_transaction_log: list[dict[str, Any]] = field(default_factory=list)
    reverse_sync_status: str = "idle"
    reverse_sync_last_error: str = ""
    reverse_sync_changed_hours: list[int] = field(default_factory=list)
    reverse_sync_round_trip_ok: bool | None = None
    _tou_transaction_lock_obj: asyncio.Lock | None = None
    _tou_pending_owner: object | None = None
    _tou_confirmation_event_obj: asyncio.Event | None = None
    _tou_confirmation_unsub: Callable[[], None] | None = None
    sold_energy_today: float = 0
    sold_value_today: float = 0
    sold_energy_current_hour: float = 0
    sold_value_current_hour: float = 0
    _energy_last_update: datetime | None = None
    _energy_day: str = ""
    _stats_store: Store | None = None
    _ai_store: Store | None = None
    _charge_profile_loaded_from_store: bool = False
    _solcast_store: Store | None = None
    _learning_store: Store | None = None
    _ai_save_task: Any = None
    _ai_save_dirty: bool = False
    _ai_last_saved_fingerprint: str = ""
    _learning_save_task: Any = None
    _learning_save_dirty: bool = False
    _learning_last_saved_fingerprint: str = ""
    _learning_summary_generation: int = 0
    _learning_summary_cache_key: str = ""
    _learning_summary_cache: dict[str, Any] = field(default_factory=dict)
    _energy_save_task: Any = None
    _energy_save_dirty: bool = False
    _energy_revision: int = 0
    _energy_saved_revision: int = -1
    _energy_recent_details: list[dict[str, Any]] = field(default_factory=list)
    _energy_legacy_payload_backup: dict[str, Any] | None = None
    _startup_in_progress: bool = False
    _platform_setup_in_progress: bool = False
    _platform_publish_pending: bool = False
    _initial_optimizer_pending: bool = False
    _initial_optimizer_started: bool = False
    _initial_optimizer_completed: bool = False
    _unsub_hass_started: Callable[[], None] | None = None
    _unloading: bool = False
    _samples_store: Store | None = None
    _tariff_catalog_manager: TariffCatalogManager | None = None
    _tariff_refresh_task: Any = None
    _price_adapter_cache: dict[str, dict[str, Any]] = field(default_factory=dict)
    _price_resolution_cache: dict[str, dict[str, Any]] = field(default_factory=dict)
    _canonical_price_snapshot: dict[str, Any] = field(default_factory=dict)
    _stats_dirty: bool = False
    sales_stats: dict[str, Any] = field(default_factory=dict)
    ai_settings: dict[str, Any] = field(default_factory=dict)
    ai_history: list[dict[str, Any]] = field(default_factory=list)
    optimizer_plan: dict[str, Any] = field(default_factory=dict)
    optimizer_plan_history: list[dict[str, Any]] = field(default_factory=list)
    plan_execution_archive: list[dict[str, Any]] = field(default_factory=list)
    _optimizer_input_snapshot_id: str = ""
    _optimizer_generation_reason: str = "startup"
    _optimizer_recalc_task: Any = None
    _optimizer_recalc_pending: bool = False
    _optimizer_pending_reasons: set[str] = field(default_factory=set)
    _optimizer_debounce_reasons: set[str] = field(default_factory=set)
    _optimizer_public_snapshot: dict[str, Any] = field(default_factory=dict)
    _optimizer_output_snapshot_id: str = ""
    _optimizer_last_plan_id: str = ""
    _optimizer_last_profile_execution_revision: int = -1
    _optimizer_active_recalc: int = 0
    _optimizer_budget_blocked_snapshot_id: str = ""
    _optimizer_budget_status: dict[str, Any] = field(default_factory=lambda: {
        "status": "idle",
        "reason": None,
        "limits": {},
        "usage": {},
    })
    _sensor_snapshot_task: Any = None
    _sensor_snapshot_pending: bool = False
    _sensor_snapshot_requested_keys: set[str] = field(default_factory=set)
    _ai_state_snapshot: dict[str, Any] = field(default_factory=dict)
    _diagnostics_snapshot: dict[str, Any] = field(default_factory=dict)
    _ai_state_snapshot_id: str = ""
    _diagnostics_snapshot_id: str = ""
    _optimizer_listener_entity_ids: tuple[str, ...] = ()
    _optimizer_input_reasons: dict[str, str] = field(default_factory=dict)
    runtime_metrics: dict[str, Any] = field(default_factory=lambda: {
        "optimizer_recalc_requested": 0,
        "optimizer_recalc_started": 0,
        "optimizer_recalc_completed": 0,
        "optimizer_recalc_followup": 0,
        "optimizer_recalc_skipped_same_snapshot": 0,
        "optimizer_recalc_reasons": {},
        "optimizer_recalc_last_started": None,
        "optimizer_recalc_last_finished": None,
        "optimizer_recalc_last_duration_s": None,
        "optimizer_recalc_max_active": 0,
        "optimizer_initial_requested": 0,
        "optimizer_initial_completed": 0,
        "optimizer_budget_exceeded": 0,
        "snapshot_publish_count": 0,
        "notify_update_count": 0,
        "self_entity_event_ignored": 0,
        "external_input_event_count": 0,
    })
    ai_api_config: dict[str, Any] = field(default_factory=dict)
    ai_api_status: dict[str, Any] = field(default_factory=lambda: {"status": "disabled"})
    ai_api_cache: dict[str, Any] = field(default_factory=dict)
    ai_api_limit_state: dict[str, Any] = field(default_factory=dict)
    ai_api_metrics: dict[str, Any] = field(default_factory=lambda: {
        "requested": 0,
        "executed": 0,
        "skipped_daily_limit": 0,
        "skipped_cooldown": 0,
        "skipped_same_input": 0,
        "skipped_fail_closed": 0,
        "completed": 0,
        "failed": 0,
        "retry": 0,
        "active": 0,
        "max_active": 0,
        "last_duration_ms": None,
    })
    _ai_api_last_call: datetime | None = None
    _ai_api_last_attempt: datetime | None = None
    _ai_api_running: bool = False
    _ai_api_task: Any = None
    _optimizer_last_inputs: dict[str, Any] = field(default_factory=dict)
    future_plan: dict[str, Any] = field(default_factory=dict)
    # Stage 5G.4J.8C: lightweight, persisted per-slot schedule generation and
    # ownership.  These fields deliberately do not duplicate the schedule.
    schedule_revision: int = 0
    schedule_slot_revisions: dict[str, int] = field(default_factory=dict)
    schedule_slot_ownership: dict[str, dict[str, Any]] = field(default_factory=dict)
    solcast_history: list[dict[str, Any]] = field(default_factory=list)
    solcast_tracking: dict[str, Any] = field(default_factory=dict)
    learning_history: list[dict[str, Any]] = field(default_factory=list)
    learning_tracking: dict[str, Any] = field(default_factory=dict)
    learning_revision: int = 0
    history_watermark: str = ""
    energy_samples: list[dict[str, Any]] = field(default_factory=list)
    daily_archive: list[dict[str, Any]] = field(default_factory=list)
    monthly_archive: list[dict[str, Any]] = field(default_factory=list)
    energy_counter_state: dict[str, dict[str, Any]] = field(default_factory=dict)
    user_profiles: dict[str, Any] = field(default_factory=default_user_profiles)
    data_quality: dict[str, Any] = field(default_factory=dict)
    load_profile_7x24: dict[str, Any] = field(default_factory=dict)
    pv_learning_profile: dict[str, Any] = field(default_factory=dict)
    profile_execution: list[dict[str, Any]] = field(default_factory=list)
    _profile_execution_revision: int = 0
    weather_forecast: list[dict[str, Any]] = field(default_factory=list)
    weather_daily_forecast: list[dict[str, Any]] = field(default_factory=list)
    weather_last_updated: str = ""
    weather_last_error: str = ""
    weather_forecast_timeout: float = 5.0
    _last_energy_sample_at: datetime | None = None
    slots: dict[str, SlotSettings] = field(default_factory=dict)
    last_action: str = "Idle"
    last_applied_at: str = ""
    last_saved_at: str = ""
    last_error: str = ""
    last_schedule_attempt: dict[str, Any] = field(default_factory=dict)
    control_confirmation_timeout: float = 30.0
    _pending_control_transaction: dict[str, Any] = field(default_factory=dict)
    unsub_confirmation_timer: Any = None
    unsub_confirmation_listener: Any = None
    unsub_confirmation_poll: Any = None
    unsub_input_listener: Any = None
    unsub_input_debounce: Any = None
    unsub_timer: Any = None
    unsub_performance_report: Any = None
    unsub_performance_lag: Any = None
    _performance: RuntimePerformanceMonitor = field(
        default_factory=RuntimePerformanceMonitor,
        repr=False,
    )
    _performance_publish_reason: str | None = None
    _entity_publish_signatures: dict[int, Any] = field(default_factory=dict)
    entities: list[Any] = field(default_factory=list)
    _last_tou_signature: str = ""
    # Stage 5D: the schedule signature remains a cache hint, while the physical
    # signature is rebuilt from normalized, confirmed 6/6 readback every cycle.
    _last_physical_tou_signature: str = ""
    _last_external_tou_mismatch_signature: str = ""
    tou_expected_signature: str = ""
    tou_physical_signature: str = ""
    tou_reconciliation_in_sync: bool = False
    tou_readback_complete: bool = False
    tou_last_external_mismatch_at: str = ""
    tou_mismatched_fields: list[str] = field(default_factory=list)
    tou_reconciliation_status: str = "waiting_readback"
    tou_last_reconciliation_error: str = ""
    # Tracks whether the latest TOU operation crossed the preflight boundary
    # and issued at least one physical Deye service call.  Validation failures
    # must not trigger a second transaction that restores defaults.
    _last_tou_write_started: bool = False
    _last_slot_failure_signature: str = ""
    _last_sell_block_signature: str = ""
    # Lightweight, non-persistent SOC freshness state. ``last_reported`` from
    # HA remains authoritative when available; this event timestamp is only a
    # compatibility fallback for older State/test-double implementations.
    _soc_observed_at: datetime | None = None
    _soc_observed_entity_id: str | None = None
    # Report evidence from verified sibling measurements.  These timestamps are
    # deliberately runtime-only: a restart must reconstruct health from real HA
    # state metadata instead of making an old SOC look fresh.
    _soc_source_observed_at: dict[str, datetime] = field(default_factory=dict)
    _soc_quality_signature: tuple[str, float | None] | None = None
    _operation_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _schedule_reconcile_task: Any = None
    _schedule_reconcile_requested: bool = False
    _rollback_task: Any = None

    # Master control switch state (persistent) and runtime status.
    control_enabled: bool = True
    control_status: str = "Aktywne"
    control_entity_id: str | None = None
    planned_manager_action: str = "Oczekiwanie na pierwszy cykl Managera"
    executed_manager_action: str = "Oczekiwanie na pierwszy cykl Managera"
    # Monotonic counter incremented only after a guarded physical inverter
    # service call succeeds.  Manager diagnostics use it to distinguish an
    # applied change from an idempotent cycle whose targets already matched.
    _physical_write_count: int = 0

    # Disable/enable lifecycle.
    _disable_generation: int = 0
    _active_control_operations: int = 0
    _control_cleanup_event: asyncio.Event = field(default_factory=asyncio.Event)
    _control_epoch: int = 0
    _active_control_transactions: dict[str, dict[str, Any]] = field(default_factory=dict)
    _disable_waiting_transactions: set[str] = field(default_factory=set)
    _control_disable_error: str = ""

    # Per-transaction guard data for rollback scope.
    _active_control_transaction_id: str | None = None
    _active_control_transaction_snapshot: dict[str, str] = field(default_factory=dict)
    _rollback_scope_transaction_id: str | None = None
    _rollback_scope_snapshot: dict[str, str] = field(default_factory=dict)

    # Cancellation signal for the active TOU transaction.
    _active_tou_cancel_event: asyncio.Event | None = None

    def __post_init__(self) -> None:
        self.slots = {key: SlotSettings(key=key, label=label) for key, label, *_ in SLOTS}
        raw_ai_api = self.data.get("ai_api") if isinstance(self.data.get("ai_api"), dict) else {}
        try:
            self.ai_api_config = normalize_ai_api_config(raw_ai_api)
        except ValueError:
            self.ai_api_config = normalize_ai_api_config({"enabled": False, "provider": "openrouter"})
        self.ai_api_status = {
            "status": "ready" if self.ai_api_config.get("enabled") else "disabled",
            "provider": self.ai_api_config.get("provider"),
            "model": self.ai_api_config.get("model"),
            "last_error": None,
        }

    def _control_is_active(self) -> bool:
        """Return whether new physical inverter writes may start."""
        return self.control_enabled and self.control_status == "Aktywne"

    def _control_block_message(self) -> str:
        if self.control_status == "Wyłączanie":
            return (
                "Trwa wyłączanie Sterowania Deye. Poczekaj na zakończenie "
                "aktywnej transakcji i spróbuj ponownie."
            )
        return (
            "Sterowanie Deye jest wyłączone. Włącz „Sterowanie Deye”, aby "
            "wysyłać polecenia do falownika."
        )

    def _ensure_control_active(self) -> None:
        if not self._control_is_active():
            raise ControlDisabledError(self._control_block_message())

    @asynccontextmanager
    async def _control_operation(self, name: str):
        """Register one physical-control operation and bind its task context."""
        existing_id = _CONTROL_TRANSACTION_ID.get()
        existing = self._active_control_transactions.get(existing_id or "")
        if existing is not None:
            yield existing_id
            return

        self._ensure_control_active()
        transaction_id = uuid.uuid4().hex
        meta = {
            "id": transaction_id,
            "name": name,
            "epoch": self._control_epoch,
            "started_at": ha_now().isoformat(timespec="seconds"),
            "snapshot": {},
            "rollback_snapshot": {},
            "rollback": False,
            "stale": False,
        }
        self._active_control_transactions[transaction_id] = meta
        self._active_control_operations = len(self._active_control_transactions)
        self._active_control_transaction_id = transaction_id
        token = _CONTROL_TRANSACTION_ID.set(transaction_id)
        try:
            yield transaction_id
        finally:
            _CONTROL_TRANSACTION_ID.reset(token)
            self._finish_control_operation(transaction_id)

    def _finish_control_operation(self, transaction_id: str) -> None:
        self._active_control_transactions.pop(transaction_id, None)
        self._disable_waiting_transactions.discard(transaction_id)
        self._active_control_operations = len(self._active_control_transactions)
        if self._active_control_transaction_id == transaction_id:
            self._active_control_transaction_id = None
            self._active_control_transaction_snapshot = {}
        if not self._disable_waiting_transactions:
            self._control_cleanup_event.set()

    def _set_control_transaction_snapshot(
        self, transaction_id: str | None, snapshot: dict[str, str]
    ) -> None:
        if not transaction_id:
            return
        meta = self._active_control_transactions.get(transaction_id)
        if meta is None:
            return
        normalized = {str(entity_id): str(value) for entity_id, value in snapshot.items()}
        meta["snapshot"] = normalized
        self._active_control_transaction_snapshot = dict(normalized)

    @contextmanager
    def _control_rollback_scope(
        self,
        transaction_id: str | None,
        snapshot: dict[str, str],
    ):
        """Allow only exact snapshot restoration for one known transaction."""
        if not transaction_id:
            yield
            return
        meta = self._active_control_transactions.get(transaction_id)
        if meta is None:
            raise ControlDisabledError("Brak aktywnej transakcji dla rollbacku")
        normalized = {str(entity_id): str(value) for entity_id, value in snapshot.items()}
        meta["rollback"] = True
        meta["rollback_snapshot"] = normalized
        self._rollback_scope_transaction_id = transaction_id
        self._rollback_scope_snapshot = dict(normalized)
        token = _CONTROL_TRANSACTION_ID.set(transaction_id)
        try:
            yield
        finally:
            _CONTROL_TRANSACTION_ID.reset(token)
            meta["rollback"] = False
            meta["rollback_snapshot"] = {}
            if self._rollback_scope_transaction_id == transaction_id:
                self._rollback_scope_transaction_id = None
                self._rollback_scope_snapshot = {}

    def _rollback_value_matches(
        self, entity_id: str, target_value: Any, snapshot_value: str
    ) -> bool:
        domain = entity_id.split(".", 1)[0]
        if domain == "number":
            actual = self.safe_float(target_value, float("nan"))
            expected = self.safe_float(snapshot_value, float("nan"))
            return (
                math.isfinite(actual)
                and math.isfinite(expected)
                and math.isclose(actual, expected, abs_tol=0.1)
            )
        if domain == "time":
            return self._time_to_minutes(target_value) == self._time_to_minutes(snapshot_value)
        if domain == "switch":
            if target_value in (True, "on"):
                normalized = "on"
            elif target_value in (False, "off"):
                normalized = "off"
            else:
                return False
            return normalized == snapshot_value
        if domain == "select":
            return str(target_value) == str(snapshot_value)
        return False

    def _guard_physical_write(self, entity_id: str, target_value: Any) -> None:
        """Enforce the master control state at the lowest write layer."""
        transaction_id = _CONTROL_TRANSACTION_ID.get()
        meta = self._active_control_transactions.get(transaction_id or "")

        if self._control_is_active():
            if meta is not None and (
                meta.get("stale") or int(meta.get("epoch", -1)) != self._control_epoch
            ):
                raise ControlDisabledError(
                    "Nieaktualna transakcja Sterowania Deye została zablokowana."
                )
            return

        if self.control_status == "Wyłączanie" and meta is not None and meta.get("rollback"):
            snapshot = meta.get("rollback_snapshot") or {}
            if (
                entity_id in snapshot
                and self._rollback_value_matches(entity_id, target_value, snapshot[entity_id])
            ):
                return
            raise ControlDisabledError(
                "Rollback Sterowania Deye wykracza poza snapshot transakcji."
            )

        raise ControlDisabledError(self._control_block_message())

    async def _async_physical_service_call(
        self,
        domain: str,
        service: str,
        data: dict[str, Any],
        *,
        target_value: Any,
    ) -> None:
        """Guard and execute one physical Home Assistant inverter service."""
        entity_id = str(data.get("entity_id") or "")
        if not entity_id:
            raise ValueError("Brak encji dla fizycznego zapisu Deye")
        self._performance.inc("inverter_write_requested")
        self._guard_physical_write(entity_id, target_value)
        await self.hass.services.async_call(domain, service, data, blocking=True)
        self._performance.inc("inverter_write_executed")
        lowered_entity_id = entity_id.lower()
        if "time_of_use" in lowered_entity_id or "_tou_" in lowered_entity_id:
            self._performance.inc("tou_write_executed")
        self._physical_write_count += 1

    def _control_result_is_current(self, transaction_id: str | None = None) -> bool:
        transaction_id = transaction_id or _CONTROL_TRANSACTION_ID.get()
        if not transaction_id:
            return self._control_is_active()
        meta = self._active_control_transactions.get(transaction_id)
        return bool(
            meta
            and not meta.get("stale")
            and int(meta.get("epoch", -1)) == self._control_epoch
            and self._control_is_active()
        )

    def _control_transaction_is_stale(self, transaction_id: str | None = None) -> bool:
        """Return whether a timed-out/invalidated operation may no longer publish results."""
        transaction_id = transaction_id or _CONTROL_TRANSACTION_ID.get()
        meta = self._active_control_transactions.get(transaction_id or "")
        return bool(meta and meta.get("stale"))

    async def _async_persist_control_enabled(self) -> None:
        await self.async_save_ai_data()

    async def async_disable_control(self) -> None:
        """Disable only the physical execution layer and await bounded cleanup."""
        if self.control_status == "Wyłączone":
            self.control_enabled = False
            return
        if self.control_status == "Wyłączanie":
            raise ControlDisabledError(self._control_block_message())

        self.control_enabled = False
        self.control_status = "Wyłączanie"
        self._disable_generation += 1
        self._control_epoch += 1
        generation = self._disable_generation
        self._control_cleanup_event = asyncio.Event()
        self._disable_waiting_transactions = {
            transaction_id
            for transaction_id, meta in self._active_control_transactions.items()
            if not meta.get("stale")
        }
        self._control_disable_error = ""
        self._clear_pending_control_transaction()
        self._schedule_reconcile_requested = False
        if self._active_tou_cancel_event is not None:
            self._active_tou_cancel_event.set()
        if not self._disable_waiting_transactions:
            self._control_cleanup_event.set()
        self.planned_manager_action = self._planned_manager_action_text()
        self.executed_manager_action = "Nie wykonano — sterowanie wyłączone"
        self.notify_update()

        await self._async_persist_control_enabled()
        try:
            await asyncio.wait_for(
                self._control_cleanup_event.wait(),
                timeout=self.control_confirmation_timeout,
            )
        except asyncio.TimeoutError:
            waiting = sorted(self._disable_waiting_transactions)
            for transaction_id in waiting:
                meta = self._active_control_transactions.get(transaction_id)
                if meta is not None:
                    meta["stale"] = True
            self._disable_waiting_transactions.clear()
            self._control_disable_error = (
                "Przekroczono 30 s oczekiwania na zakończenie Sterowania Deye. "
                "Stare operacje zostały unieważnione."
            )
            self.last_error = self._control_disable_error
            self._stop_tou_confirmation_listener()
            self.tou_write_pending = False
            self._clear_pending_control_transaction()
        finally:
            if generation == self._disable_generation and self.control_status == "Wyłączanie":
                self.control_status = "Wyłączone"
                self.executed_manager_action = "Nie wykonano — sterowanie wyłączone"
                self.notify_update()

    async def async_enable_control(self) -> None:
        """Enable future normal Manager cycles without writing immediately."""
        if self.control_status == "Wyłączanie":
            raise ControlDisabledError(self._control_block_message())
        if self._control_is_active():
            return
        self.control_enabled = True
        self.control_status = "Aktywne"
        self._control_epoch += 1
        self._control_disable_error = ""
        self.planned_manager_action = self._planned_manager_action_text()
        self.executed_manager_action = (
            "Nie wykonano — zatrzymanie awaryjne"
            if self.emergency_stop
            else "Oczekiwanie na kolejny cykl Managera"
        )
        await self._async_persist_control_enabled()
        self.notify_update()
        if not self.emergency_stop:
            # Reuse the normal Manager decision path.  The existing scheduler
            # coalesces rapid requests and acquires _operation_lock outside this
            # method, so enabling control cannot deadlock or duplicate writes.
            self._schedule_schedule_reconciliation()

    @staticmethod
    def normalize_schedule_mode(
        mode: Any,
        physical_work_mode: Any = None,
    ) -> tuple[str, str | None, bool]:
        """Normalize one legacy slot without guessing a physical Deye mode."""
        if mode in PHYSICAL_NORMAL_MODES:
            return MODE_NORMAL_OPERATION, str(mode), True
        if mode == MODE_NORMAL_OPERATION:
            physical = str(physical_work_mode) if physical_work_mode in PHYSICAL_NORMAL_MODES else None
            return MODE_NORMAL_OPERATION, physical, False
        if mode in (MODE_SELLING_FIRST, MODE_CHARGE):
            return str(mode), None, False
        raise ValueError(f"Nieobsługiwany tryb harmonogramu: {mode}")

    async def async_restore_slot_mode(
        self,
        slot_key: str,
        restored_mode: str,
        *,
        ai_sell_power_only: bool = False,
    ) -> None:
        """Restore and idempotently migrate one legacy slot entity state."""
        slot = self.slots[slot_key]
        stored_physical = slot.physical_work_mode
        logical, physical, migrated = self.normalize_schedule_mode(restored_mode, stored_physical)
        slot.mode = logical
        slot.physical_work_mode = physical
        slot.ai_sell_power_only = bool(
            ai_sell_power_only and logical == MODE_SELLING_FIRST
        )
        self._restored_slot_mode_keys.add(slot_key)

        # Persist the migration once all RestoreEntity slot states have been
        # observed.  No inverter service call or profile/default substitution
        # is performed here.
        all_restored = len(self._restored_slot_mode_keys) == len(self.slots)
        if migrated or (all_restored and self.schedule_schema_version < SCHEDULE_SCHEMA_VERSION):
            if all_restored:
                self.schedule_schema_version = SCHEDULE_SCHEMA_VERSION
            await self.async_save_ai_data()

    @property
    def work_mode_select(self) -> str | None:
        return self.data.get(CONF_WORK_MODE_SELECT)

    @property
    def inverter_provider(self) -> str:
        """Return the configured provider; old entries remain Lewa-Reka."""
        return provider_key(self.data)

    @property
    def work_mode_aux_entity(self) -> str | None:
        return self.data.get(CONF_WORK_MODE_AUX_ENTITY)

    @property
    def max_sell_power_number(self) -> str | None:
        return self.data.get(CONF_MAX_SELL_POWER_NUMBER)

    @property
    def configured_inverter_max_power_w(self) -> int:
        """User-configured inverter AC power limit (W)."""
        try:
            value = int(float(self.data.get(CONF_INVERTER_MAX_POWER_W, DEFAULT_INVERTER_MAX_POWER_W)))
        except (TypeError, ValueError):
            value = DEFAULT_INVERTER_MAX_POWER_W
        return max(1000, min(30000, value))

    @property
    def detected_entity_max_power_w(self) -> int | None:
        """Reliable maximum from the mapped Max Sell Power entity, if any."""
        entity_id = self.max_sell_power_number
        if not entity_id:
            return None
        return detect_entity_max_power_w(self.hass.states.get(entity_id))

    @property
    def effective_inverter_max_power_w(self) -> int:
        """Effective sell-power ceiling for this instance.

        The user-configured value is the source of truth. The detected entity
        maximum is only a proposal used to pre-fill the configuration step.
        """
        return self.configured_inverter_max_power_w

    @property
    def max_sell_power_range(self) -> NumberEntityRange:
        """Physical min/max/step of the mapped Max Sell Power number entity."""
        return number_entity_range(self.hass.states.get(self.max_sell_power_number))

    def validate_manual_sell_power_w(self, label: str, value_w: float) -> None:
        """Reject an invalid manual sell-power value before any write.

        Zero watts is always allowed because it represents "no selling" in the
        logical configuration. Physical min/max/step checks apply only to
        positive values that will actually be sent to the inverter.
        """
        if not math.isfinite(value_w) or value_w < 0:
            raise ValueError(f"{label}: moc sprzedaży musi być nieujemną liczbą")
        if value_w > self.effective_inverter_max_power_w:
            raise ValueError(
                f"{label}: moc sprzedaży {value_w} W przekracza efektywny limit "
                f"{self.effective_inverter_max_power_w} W"
            )
        if value_w == 0:
            return
        physical = self.max_sell_power_range
        if physical.maximum_w is not None and value_w > physical.maximum_w:
            raise ValueError(
                f"{label}: moc sprzedaży {value_w} W przekracza fizyczny limit encji "
                f"{physical.maximum_w} W"
            )
        if physical.minimum_w is not None and value_w < physical.minimum_w:
            raise ValueError(
                f"{label}: moc sprzedaży {value_w} W jest poniżej fizycznego minimum encji "
                f"{physical.minimum_w} W"
            )
        if (
            physical.step_w is not None
            and physical.step_w > 0
            and physical.minimum_w is not None
        ):
            steps = (value_w - physical.minimum_w) / physical.step_w
            if not math.isclose(steps, round(steps), abs_tol=1e-6):
                raise ValueError(
                    f"{label}: moc sprzedaży {value_w} W nie jest zgodna z fizycznym krokiem "
                    f"{physical.step_w} W"
                )

    def normalize_automatic_sell_power_w(self, value_w: float) -> float:
        """Return a sell-power value safe for automatic Deye writes.

        The returned value is:
        - capped to the effective inverter limit,
        - capped to the physical entity maximum,
        - rounded down to the physical entity step,
        - never rounded up.

        A positive value below the physical minimum is reduced to 0 W,
        consistent with the semantics of disabled selling.
        """
        physical = self.max_sell_power_range
        physical_maximum = physical.maximum_w
        maximum = float(self.effective_inverter_max_power_w)
        if physical_maximum is not None:
            maximum = min(maximum, physical_maximum)
        return quantize_power_w(
            value_w,
            step_w=physical.step_w if physical.step_w is not None else 1.0,
            minimum_w=physical.minimum_w if physical.minimum_w is not None else 0.0,
            maximum_w=maximum,
        )

    async def async_set_max_sell_power_number(self, value_w: float) -> float | None:
        """Write a sell-power value in watts, converting to the entity's native unit.

        Returns the native value that was written, or None when the value is 0 W
        and the physical entity does not accept 0 W (min > 0). In that case the
        caller must rely on the work mode to stop selling.
        """
        normalized_w = self.normalize_automatic_sell_power_w(value_w)
        physical = self.max_sell_power_range
        if normalized_w == 0 and physical.minimum_w is not None and physical.minimum_w > 0:
            return None
        native_value = convert_w_to_native_unit(normalized_w, physical.native_unit)
        await self.async_set_number(self.max_sell_power_number, native_value)
        return native_value

    async def async_set_max_sell_power_number_if_needed(
        self, value_w: float
    ) -> float | None:
        """Apply automatic sell power only when its native readback differs."""
        normalized_w = self.normalize_automatic_sell_power_w(value_w)
        physical = self.max_sell_power_range
        if normalized_w == 0 and physical.minimum_w is not None and physical.minimum_w > 0:
            return None
        native_value = convert_w_to_native_unit(normalized_w, physical.native_unit)
        state = self.hass.states.get(self.max_sell_power_number)
        current = None if state is None else self.safe_float(state.state, float("nan"))
        if current is not None and math.isfinite(current) and math.isclose(
            current, native_value, abs_tol=0.1
        ):
            self._performance.inc("inverter_write_skipped_same_value")
            return native_value
        return await self.async_set_max_sell_power_number(value_w)

    @property
    def discharge_current_number(self) -> str | None:
        return self.data.get(CONF_DISCHARGE_CURRENT_NUMBER)

    @property
    def charge_current_number(self) -> str | None:
        return self.data.get(CONF_CHARGE_CURRENT_NUMBER)

    @property
    def grid_charge_current_number(self) -> str | None:
        configured = self.data.get(CONF_GRID_CHARGE_CURRENT_NUMBER)
        if configured:
            return str(configured)
        return DEFAULT_GRID_CHARGE_CURRENT if self.inverter_provider == PROVIDER_LEWA_REKA else None

    @property
    def grid_power_sensor(self) -> str | None:
        configured = self.data.get(CONF_GRID_POWER_SENSOR)
        if configured and self.hass.states.get(configured) is not None:
            return configured
        if self.inverter_provider != PROVIDER_LEWA_REKA:
            return configured
        if self.hass.states.get(DEFAULT_GRID_POWER_SENSOR) is not None:
            return DEFAULT_GRID_POWER_SENSOR
        return configured

    @property
    def pv_power_sensor(self) -> str | None:
        return self.configured_sensor(CONF_PV_POWER_SENSOR, DEFAULT_PV_POWER_SENSOR)

    @property
    def load_power_sensor(self) -> str | None:
        return self.configured_sensor(CONF_LOAD_POWER_SENSOR, DEFAULT_LOAD_POWER_SENSOR)

    @property
    def battery_power_sensor(self) -> str | None:
        return self.configured_sensor(CONF_BATTERY_POWER_SENSOR, DEFAULT_BATTERY_POWER_SENSOR)

    @property
    def battery_soc_sensor(self) -> str | None:
        configured = self.data.get(CONF_BATTERY_SOC_SENSOR)
        if configured and self.hass.states.get(configured) is not None:
            return configured
        if self.inverter_provider != PROVIDER_LEWA_REKA:
            return configured
        if self.hass.states.get(DEFAULT_BATTERY_SOC) is not None:
            return DEFAULT_BATTERY_SOC
        return configured

    def configured_sensor(self, key: str, default_entity: str) -> str | None:
        configured = self.data.get(key)
        if configured and self.hass.states.get(configured) is not None:
            return configured
        if self.inverter_provider != PROVIDER_LEWA_REKA:
            return configured
        if self.hass.states.get(default_entity) is not None:
            return default_entity
        return configured or default_entity

    @property
    def price_sensor(self) -> str | None:
        return str(self.data.get(CONF_PRICE_SENSOR) or "") or None

    @property
    def sell_price_tomorrow_sensor(self) -> str | None:
        return str(self.data.get(CONF_SELL_PRICE_TOMORROW_SENSOR) or "") or None

    @property
    def buy_price_today_sensor(self) -> str | None:
        return str(self.data.get(CONF_BUY_PRICE_TODAY_SENSOR) or "") or None

    @property
    def buy_price_tomorrow_sensor(self) -> str | None:
        return str(self.data.get(CONF_BUY_PRICE_TOMORROW_SENSOR) or "") or None

    @property
    def buy_seller_id(self) -> str:
        return str(self.data.get(CONF_BUY_SELLER_ID, DEFAULT_BUY_SELLER_ID) or "")

    @property
    def buy_seller_tariff_id(self) -> str:
        return str(self.data.get(CONF_BUY_SELLER_TARIFF_ID, DEFAULT_BUY_SELLER_TARIFF_ID) or "")

    def _price_registry_entry(self, entity_id: str | None) -> Any:
        if not entity_id:
            return None
        try:
            from homeassistant.helpers import entity_registry as er

            registry = er.async_get(self.hass)
            if registry is None:
                return None
            return registry.async_get(entity_id) if hasattr(registry, "async_get") else getattr(registry, "entities", {}).get(entity_id)
        except (AttributeError, ImportError, KeyError, TypeError):
            return None

    def capture_price_binding(self, entity_id: str | None) -> dict[str, Any]:
        """Capture stable registry identity without selecting any other entity."""
        mapped = str(entity_id or "")
        entry = self._price_registry_entry(mapped)
        binding: dict[str, Any] = {"entity_id": mapped}
        if entry is None:
            return binding
        binding.update({
            "registry_entry_id": str(getattr(entry, "id", "") or ""),
            "platform": str(getattr(entry, "platform", "") or ""),
            "config_entry_id": str(getattr(entry, "config_entry_id", "") or ""),
            "unique_id": str(getattr(entry, "unique_id", "") or ""),
            "device_id": str(getattr(entry, "device_id", "") or ""),
        })
        return binding

    def resolve_price_binding(
        self,
        mapped_entity: str | None,
        binding: dict[str, Any] | None,
    ) -> tuple[str, str, str]:
        """Resolve a rename by stable identity, never by provider defaults."""
        mapped = str(mapped_entity or "")
        saved = dict(binding or {}) if isinstance(binding, dict) else {}
        if not mapped:
            return "", "unmapped", "user_unmapped"
        saved_registry_id = str(saved.get("registry_entry_id") or "")
        cache_key = repr((mapped, sorted(saved.items())))
        cached = self._price_resolution_cache.get(cache_key)
        if cached and self.hass.states.get(str(cached.get("resolved") or "")) is not None:
            cached_entry = self._price_registry_entry(str(cached.get("resolved") or ""))
            if (
                not saved_registry_id
                or cached_entry is None
                or str(getattr(cached_entry, "id", "") or "") == saved_registry_id
            ):
                return str(cached["resolved"]), str(cached["status"]), str(cached.get("reason") or "")
        if mapped and self.hass.states.get(mapped) is not None:
            mapped_entry = self._price_registry_entry(mapped)
            if (
                not saved_registry_id
                or (
                    mapped_entry is not None
                    and str(getattr(mapped_entry, "id", "") or "") == saved_registry_id
                )
            ):
                result = (mapped, "mapped_entity", "")
                self._price_resolution_cache[cache_key] = {"resolved": result[0], "status": result[1], "reason": result[2]}
                return result
        candidates: list[Any] = []
        try:
            from homeassistant.helpers import entity_registry as er

            registry = er.async_get(self.hass)
            entries = list(getattr(registry, "entities", {}).values()) if registry is not None else []
            if saved_registry_id:
                candidates = [entry for entry in entries if str(getattr(entry, "id", "") or "") == saved_registry_id]
            if not candidates and saved.get("unique_id") and saved.get("platform"):
                candidates = [
                    entry for entry in entries
                    if str(getattr(entry, "unique_id", "") or "") == str(saved.get("unique_id"))
                    and str(getattr(entry, "platform", "") or "") == str(saved.get("platform"))
                    and (
                        not saved.get("config_entry_id")
                        or str(getattr(entry, "config_entry_id", "") or "") == str(saved.get("config_entry_id"))
                    )
                ]
        except (AttributeError, ImportError, KeyError, TypeError):
            candidates = []
        if len(candidates) == 1:
            resolved = str(getattr(candidates[0], "entity_id", "") or "")
            if resolved:
                status = "renamed_resolved" if resolved != mapped else "mapped_entity"
                reason = "resolved_by_stable_identity" if status == "renamed_resolved" else ""
                self._price_resolution_cache[cache_key] = {"resolved": resolved, "status": status, "reason": reason}
                return resolved, status, reason
        reason = "ambiguous_stable_identity" if len(candidates) > 1 else "mapped_entity_missing"
        return mapped, "mapped_entity_missing", reason

    def _price_source_metadata(self, entity_id: str | None) -> dict[str, str | None]:
        """Return cached registry/config-entry metadata for adapter detection."""
        key = str(entity_id or "")
        if not key:
            return {"platform": None, "config_entry_domain": None, "device_metadata": None}
        if key in self._price_adapter_cache:
            return self._price_adapter_cache[key]
        platform: str | None = None
        config_entry_domain: str | None = None
        device_metadata: str | None = None
        try:
            from homeassistant.helpers import entity_registry as er

            registry = er.async_get(self.hass)
            entry = registry.async_get(key) if registry is not None and hasattr(registry, "async_get") else None
            if entry is None and registry is not None:
                entry = getattr(registry, "entities", {}).get(key)
            platform = str(getattr(entry, "platform", "") or "") or None
            config_entry_id = getattr(entry, "config_entry_id", None)
            config_entries = getattr(self.hass, "config_entries", None)
            source_entry = (
                config_entries.async_get_entry(config_entry_id)
                if config_entry_id and config_entries is not None and hasattr(config_entries, "async_get_entry")
                else None
            )
            config_entry_domain = str(getattr(source_entry, "domain", "") or "") or None
            device_id = getattr(entry, "device_id", None)
            if device_id:
                from homeassistant.helpers import device_registry as dr

                device_registry = dr.async_get(self.hass)
                device = device_registry.async_get(device_id) if device_registry is not None else None
                if device is not None:
                    identifiers = " ".join(
                        f"{domain} {identifier}"
                        for domain, identifier in (getattr(device, "identifiers", set()) or set())
                    )
                    device_metadata = " ".join(
                        str(value or "")
                        for value in (
                            getattr(device, "manufacturer", None),
                            getattr(device, "model", None),
                            getattr(device, "name", None),
                            identifiers,
                        )
                    ).strip() or None
        except (AttributeError, KeyError, TypeError):
            pass
        metadata = {
            "platform": platform,
            "config_entry_domain": config_entry_domain,
            "device_metadata": device_metadata,
        }
        self._price_adapter_cache[key] = metadata
        return metadata

    def price_contract(self, direction: str) -> dict[str, Any]:
        """Resolve one independent, versioned BUY or SELL source contract."""
        is_sell = direction == "sell"
        legacy_today_key = CONF_PRICE_SENSOR if is_sell else CONF_BUY_PRICE_TODAY_SENSOR
        legacy_tomorrow_key = CONF_SELL_PRICE_TOMORROW_SENSOR if is_sell else CONF_BUY_PRICE_TOMORROW_SENSOR
        key = CONF_SELL_PRICE_CONTRACT if is_sell else CONF_BUY_PRICE_CONTRACT
        explicit_contract = self.data.get(key) if isinstance(self.data.get(key), dict) else {}
        # Minor 23 guarantees presence-aware central mappings. Runtime never
        # consults provider defaults or price_source; those remain migration-only.
        today_entity = str(self.data.get(legacy_today_key) or "")
        tomorrow_entity = str(self.data.get(legacy_tomorrow_key) or "")
        slot_identity_matches: dict[str, bool] = {}
        bindings: dict[str, dict[str, Any]] = {}
        for day_name, entity_id in (("today", today_entity), ("tomorrow", tomorrow_entity)):
            saved_binding = explicit_contract.get(f"{day_name}_binding")
            saved_binding = dict(saved_binding) if isinstance(saved_binding, dict) else {}
            captured = self.capture_price_binding(entity_id) if entity_id else {}
            saved_entity = str(explicit_contract.get(f"{day_name}_entity") or saved_binding.get("entity_id") or "")
            saved_registry_id = str(saved_binding.get("registry_entry_id") or "")
            captured_registry_id = str(captured.get("registry_entry_id") or "")
            same_identity = bool(
                saved_entity == entity_id
                or (
                    entity_id
                    and saved_registry_id
                    and captured_registry_id
                    and saved_registry_id == captured_registry_id
                )
            )
            slot_identity_matches[day_name] = same_identity
            bindings[day_name] = saved_binding if same_identity and saved_binding else captured
        today_binding = bindings["today"]
        tomorrow_binding = bindings["tomorrow"]
        resolved_today, today_status, today_reason = self.resolve_price_binding(today_entity, today_binding)
        resolved_tomorrow, tomorrow_status, tomorrow_reason = self.resolve_price_binding(tomorrow_entity, tomorrow_binding)
        reusable_contract = dict(explicit_contract)
        if all(slot_identity_matches.values()):
            # A registry-backed rename is the same source. Move its fingerprint
            # forward so custom metadata and stable schema may be retained.
            reusable_contract.update({
                "today_entity": today_entity,
                "tomorrow_entity": tomorrow_entity,
                "mapping_fingerprint": price_mapping_fingerprint(today_entity, tomorrow_entity),
            })
        adapters: dict[str, str] = {}
        for day_name, entity_id, resolved in (
            ("today", today_entity, resolved_today),
            ("tomorrow", tomorrow_entity, resolved_tomorrow),
        ):
            metadata = self._price_source_metadata(resolved or entity_id)
            saved_adapter = str(
                explicit_contract.get(f"resolved_adapter_{day_name}")
                or explicit_contract.get("source_adapter")
                or ""
            )
            detected_adapter = detect_source_adapter(
                resolved or entity_id,
                platform=metadata.get("platform"),
                config_entry_domain=metadata.get("config_entry_domain"),
                device_metadata=metadata.get("device_metadata"),
            )
            adapters[day_name] = (
                saved_adapter
                if detected_adapter == "generic"
                and slot_identity_matches[day_name]
                and saved_adapter in ("pstryk", "rce_pse", "generic", "custom")
                else detected_adapter
            )
        contract = rebuild_price_contract(
            reusable_contract,
            "sell" if is_sell else "buy",
            today_entity,
            tomorrow_entity,
            adapters["today"],
            adapters["tomorrow"],
        )
        contract.update({
            "today_entity": today_entity,
            "tomorrow_entity": tomorrow_entity,
            "resolved_today_entity": resolved_today,
            "resolved_tomorrow_entity": resolved_tomorrow,
            "today_binding": today_binding,
            "tomorrow_binding": tomorrow_binding,
            "stable_identity_today_status": today_status,
            "stable_identity_tomorrow_status": tomorrow_status,
            "stable_identity_today_reason": today_reason,
            "stable_identity_tomorrow_reason": tomorrow_reason,
        })
        if not today_entity:
            contract["today_binding"] = {}
            contract["resolved_schema_today"] = {}
        if not tomorrow_entity:
            contract["tomorrow_binding"] = {}
            contract["resolved_schema_tomorrow"] = {}
        contract, _schema_diagnostics = resolve_contract_schemas(
            contract,
            self.hass.states.get(resolved_today) if resolved_today else None,
            self.hass.states.get(resolved_tomorrow) if resolved_tomorrow else None,
        )
        # Runtime cache is stored on the contract itself. It is persisted on the
        # next settings save and avoids rediscovery during normal operation.
        self.data[key] = contract
        return contract

    @property
    def solcast_current_power_sensor(self) -> str | None:
        return self.configured_sensor(CONF_SOLCAST_CURRENT_POWER_SENSOR, DEFAULT_SOLCAST_CURRENT_POWER_SENSOR)

    @property
    def solcast_forecast_today_sensor(self) -> str | None:
        return self.configured_sensor(CONF_SOLCAST_FORECAST_TODAY_SENSOR, DEFAULT_SOLCAST_FORECAST_TODAY_SENSOR)

    @property
    def daily_pv_production_sensor(self) -> str | None:
        return self.configured_sensor(CONF_DAILY_PV_PRODUCTION_SENSOR, DEFAULT_DAILY_PV_PRODUCTION_SENSOR)

    # Status panel detail sensors
    @property
    def pv1_power_sensor(self) -> str | None:
        return self.configured_sensor(CONF_PV1_POWER_SENSOR, DEFAULT_PV1_POWER_SENSOR)

    @property
    def pv1_voltage_sensor(self) -> str | None:
        return self.configured_sensor(CONF_PV1_VOLTAGE_SENSOR, DEFAULT_PV1_VOLTAGE_SENSOR)

    @property
    def pv1_current_sensor(self) -> str | None:
        return self.configured_sensor(CONF_PV1_CURRENT_SENSOR, DEFAULT_PV1_CURRENT_SENSOR)

    @property
    def pv2_power_sensor(self) -> str | None:
        return self.configured_sensor(CONF_PV2_POWER_SENSOR, DEFAULT_PV2_POWER_SENSOR)

    @property
    def pv2_voltage_sensor(self) -> str | None:
        return self.configured_sensor(CONF_PV2_VOLTAGE_SENSOR, DEFAULT_PV2_VOLTAGE_SENSOR)

    @property
    def pv2_current_sensor(self) -> str | None:
        return self.configured_sensor(CONF_PV2_CURRENT_SENSOR, DEFAULT_PV2_CURRENT_SENSOR)

    @property
    def pv3_power_sensor(self) -> str | None:
        return self.configured_sensor(CONF_PV3_POWER_SENSOR, DEFAULT_PV3_POWER_SENSOR)

    @property
    def battery_bms_voltage_sensor(self) -> str | None:
        return self.configured_sensor(CONF_BATTERY_BMS_VOLTAGE_SENSOR, DEFAULT_BATTERY_BMS_VOLTAGE_SENSOR)

    @property
    def battery_current_sensor(self) -> str | None:
        return self.configured_sensor(CONF_BATTERY_CURRENT_SENSOR, DEFAULT_BATTERY_CURRENT_SENSOR)

    @property
    def battery_temperature_sensor(self) -> str | None:
        return self.configured_sensor(CONF_BATTERY_TEMPERATURE_SENSOR, DEFAULT_BATTERY_TEMPERATURE_SENSOR)

    @property
    def battery_soh_sensor(self) -> str | None:
        return self.configured_sensor(CONF_BATTERY_SOH_SENSOR, DEFAULT_BATTERY_SOH_SENSOR)

    @property
    def daily_battery_charge_sensor(self) -> str | None:
        return self.configured_sensor(CONF_DAILY_BATTERY_CHARGE_SENSOR, DEFAULT_DAILY_BATTERY_CHARGE_SENSOR)

    @property
    def daily_battery_discharge_sensor(self) -> str | None:
        return self.configured_sensor(CONF_DAILY_BATTERY_DISCHARGE_SENSOR, DEFAULT_DAILY_BATTERY_DISCHARGE_SENSOR)

    @property
    def daily_energy_bought_sensor(self) -> str | None:
        return self.configured_sensor(CONF_DAILY_ENERGY_BOUGHT_SENSOR, DEFAULT_DAILY_ENERGY_BOUGHT_SENSOR)

    @property
    def daily_energy_sold_sensor(self) -> str | None:
        return self.configured_sensor(CONF_DAILY_ENERGY_SOLD_SENSOR, DEFAULT_DAILY_ENERGY_SOLD_SENSOR)

    @property
    def grid_l1_power_sensor(self) -> str | None:
        return self.configured_sensor(CONF_GRID_L1_POWER_SENSOR, DEFAULT_GRID_L1_POWER_SENSOR)

    @property
    def grid_l1_voltage_sensor(self) -> str | None:
        return self.configured_sensor(CONF_GRID_L1_VOLTAGE_SENSOR, DEFAULT_GRID_L1_VOLTAGE_SENSOR)

    @property
    def grid_l2_power_sensor(self) -> str | None:
        return self.configured_sensor(CONF_GRID_L2_POWER_SENSOR, DEFAULT_GRID_L2_POWER_SENSOR)

    @property
    def grid_l2_voltage_sensor(self) -> str | None:
        return self.configured_sensor(CONF_GRID_L2_VOLTAGE_SENSOR, DEFAULT_GRID_L2_VOLTAGE_SENSOR)

    @property
    def grid_l3_power_sensor(self) -> str | None:
        return self.configured_sensor(CONF_GRID_L3_POWER_SENSOR, DEFAULT_GRID_L3_POWER_SENSOR)

    @property
    def grid_l3_voltage_sensor(self) -> str | None:
        return self.configured_sensor(CONF_GRID_L3_VOLTAGE_SENSOR, DEFAULT_GRID_L3_VOLTAGE_SENSOR)

    @property
    def load_frequency_sensor(self) -> str | None:
        return self.configured_sensor(CONF_LOAD_FREQUENCY_SENSOR, DEFAULT_LOAD_FREQUENCY_SENSOR)

    @property
    def daily_load_consumption_sensor(self) -> str | None:
        return self.configured_sensor(CONF_DAILY_LOAD_CONSUMPTION_SENSOR, DEFAULT_DAILY_LOAD_CONSUMPTION_SENSOR)

    @property
    def load_l1_power_sensor(self) -> str | None:
        return self.configured_sensor(CONF_LOAD_L1_POWER_SENSOR, DEFAULT_LOAD_L1_POWER_SENSOR)

    @property
    def load_l2_power_sensor(self) -> str | None:
        return self.configured_sensor(CONF_LOAD_L2_POWER_SENSOR, DEFAULT_LOAD_L2_POWER_SENSOR)

    @property
    def load_l3_power_sensor(self) -> str | None:
        return self.configured_sensor(CONF_LOAD_L3_POWER_SENSOR, DEFAULT_LOAD_L3_POWER_SENSOR)

    @property
    def inverter_ac_temperature_sensor(self) -> str | None:
        return self.configured_sensor(CONF_INVERTER_AC_TEMPERATURE_SENSOR, DEFAULT_INVERTER_AC_TEMPERATURE_SENSOR)

    @property
    def solcast_forecast_tomorrow_sensor(self) -> str | None:
        return self.configured_sensor(CONF_SOLCAST_FORECAST_TOMORROW_SENSOR, DEFAULT_SOLCAST_FORECAST_TOMORROW_SENSOR)

    @property
    def solcast_forecast_day_3_sensor(self) -> str | None:
        return self.configured_sensor(CONF_SOLCAST_FORECAST_DAY_3_SENSOR, DEFAULT_SOLCAST_FORECAST_DAY_3_SENSOR)

    @property
    def solcast_forecast_day_4_sensor(self) -> str | None:
        return self.configured_sensor(CONF_SOLCAST_FORECAST_DAY_4_SENSOR, DEFAULT_SOLCAST_FORECAST_DAY_4_SENSOR)

    @property
    def solcast_forecast_day_5_sensor(self) -> str | None:
        return self.configured_sensor(CONF_SOLCAST_FORECAST_DAY_5_SENSOR, DEFAULT_SOLCAST_FORECAST_DAY_5_SENSOR)

    @property
    def solcast_forecast_day_6_sensor(self) -> str | None:
        return self.configured_sensor(CONF_SOLCAST_FORECAST_DAY_6_SENSOR, DEFAULT_SOLCAST_FORECAST_DAY_6_SENSOR)

    @property
    def solcast_forecast_day_7_sensor(self) -> str | None:
        return self.configured_sensor(CONF_SOLCAST_FORECAST_DAY_7_SENSOR, DEFAULT_SOLCAST_FORECAST_DAY_7_SENSOR)

    @property
    def solcast_remaining_today_sensor(self) -> str | None:
        return self.configured_sensor(CONF_SOLCAST_REMAINING_TODAY_SENSOR, DEFAULT_SOLCAST_REMAINING_TODAY_SENSOR)

    @property
    def solcast_peak_power_today_sensor(self) -> str | None:
        return self.configured_sensor(CONF_SOLCAST_PEAK_POWER_TODAY_SENSOR, DEFAULT_SOLCAST_PEAK_POWER_TODAY_SENSOR)

    @property
    def solcast_peak_time_today_sensor(self) -> str | None:
        return self.configured_sensor(CONF_SOLCAST_PEAK_TIME_TODAY_SENSOR, DEFAULT_SOLCAST_PEAK_TIME_TODAY_SENSOR)

    @property
    def weather_entity(self) -> str | None:
        return self.data.get(CONF_WEATHER_ENTITY) or DEFAULT_WEATHER_ENTITY

    @property
    def osd_provider(self) -> str:
        return str(self.data.get(CONF_OSD_PROVIDER, DEFAULT_OSD_PROVIDER)).lower()

    @property
    def tariff_plan(self) -> str:
        return str(self.data.get(CONF_TARIFF_PLAN, DEFAULT_TARIFF_PLAN)).lower()

    @property
    def distribution_peak_rate(self) -> float:
        return max(0.0, self.safe_float(self.data.get(CONF_DISTRIBUTION_PEAK_RATE), DEFAULT_DISTRIBUTION_PEAK_RATE))

    @property
    def distribution_offpeak_rate(self) -> float:
        return max(0.0, self.safe_float(self.data.get(CONF_DISTRIBUTION_OFFPEAK_RATE), DEFAULT_DISTRIBUTION_OFFPEAK_RATE))

    @property
    def custom_offpeak_windows(self) -> str:
        return str(self.data.get(CONF_CUSTOM_OFFPEAK_WINDOWS, DEFAULT_CUSTOM_OFFPEAK_WINDOWS))

    @property
    def tariff_mode(self) -> str:
        value = str(self.data.get(CONF_TARIFF_MODE, DEFAULT_TARIFF_MODE)).lower()
        return value if value in ("automatic", "manual") else DEFAULT_TARIFF_MODE

    @property
    def price_includes_distribution(self) -> bool:
        return bool(self.data.get(CONF_PRICE_INCLUDES_DISTRIBUTION, DEFAULT_PRICE_INCLUDES_DISTRIBUTION))

    @property
    def tariff_catalog(self) -> dict[str, Any]:
        if self._tariff_catalog_manager is not None:
            return self._tariff_catalog_manager.catalog
        return {}

    def normalized_grid_power(self) -> float:
        value = self.grid_power_reading().get("value")
        return float(value) if value is not None else 0.0

    def normalized_battery_power(self) -> float:
        value = self.battery_power_reading().get("value")
        return float(value) if value is not None else 0.0

    def tariff_context(self, moment: datetime | None = None) -> dict[str, Any]:
        current = moment or ha_now()
        catalog = self.tariff_catalog
        tariff = get_tariff(catalog, self.osd_provider, self.tariff_plan)
        tariff_available, tariff_error = tariff_availability(tariff, current.date()) if tariff else (False, "brak taryfy w katalogu")
        automatic = self.tariff_mode == "automatic" and tariff is not None and tariff_available
        if automatic:
            profile = catalog_hourly_profile(current, catalog, self.osd_provider, self.tariff_plan, 48)
        elif self.tariff_mode == "manual":
            today = hourly_tariff_profile(
                current,
                "custom",
                self.distribution_peak_rate,
                self.distribution_offpeak_rate,
                self.custom_offpeak_windows,
                "other",
            )
            tomorrow = hourly_tariff_profile(
                current + timedelta(days=1),
                "custom",
                self.distribution_peak_rate,
                self.distribution_offpeak_rate,
                self.custom_offpeak_windows,
                "other",
            )
            profile = [*today, *tomorrow]
        else:
            profile = []
        current_row = next(
            (row for row in profile if row.get("date") == current.date().isoformat() and row.get("hour") == current.hour),
            profile[current.hour] if len(profile) > current.hour else {},
        )
        catalog_rates = tariff.get("rates", {}) if automatic and tariff else {}
        numeric_rates = [float(value) for value in catalog_rates.values() if isinstance(value, (int, float))]
        display_peak_rate = max(numeric_rates) if numeric_rates else self.distribution_peak_rate
        display_offpeak_rate = min(numeric_rates) if numeric_rates else self.distribution_offpeak_rate
        providers = [
            {
                "id": key,
                "name": str(value.get("name") or key),
                "tariffs": available_tariffs(catalog, key),
            }
            for key, value in catalog.get("providers", {}).items()
        ]
        buy_contract = self.price_contract("buy")
        sell_contract = self.price_contract("sell")
        buy_entities_empty = not str(buy_contract.get("today_entity") or "") and not str(
            buy_contract.get("tomorrow_entity") or ""
        )
        support = seller_support_entry(catalog, self.osd_provider, self.tariff_plan)
        seller_options = seller_catalog_options(catalog)
        selected_seller = self.buy_seller_id
        selected_tariff = self.buy_seller_tariff_id
        compatible_tariffs = (
            seller_tariff_options(
                catalog,
                selected_seller,
                self.osd_provider,
                self.tariff_plan,
                current.date(),
            )
            if selected_seller
            else []
        )
        seller_tariff_options_by_scope: dict[str, list[dict[str, str]]] = {}
        for provider_id, provider_item in catalog.get("providers", {}).items():
            for plan_id in provider_item.get("tariffs", {}):
                for seller_item in seller_options:
                    scope_key = f"{provider_id}/{plan_id}/{seller_item['id']}"
                    scoped_options = seller_tariff_options(
                        catalog,
                        seller_item["id"],
                        provider_id,
                        plan_id,
                        current.date(),
                    )
                    if scoped_options:
                        seller_tariff_options_by_scope[scope_key] = scoped_options
        automatic_tariff_id = compatible_tariffs[0]["id"] if len(compatible_tariffs) == 1 else ""
        if not buy_entities_empty:
            fallback_status = "ignored_explicit_buy_mapping"
            fallback_reason = "Jawne mapowanie BUY ma pierwszeństwo przed katalogiem sprzedawcy."
        elif not selected_seller:
            fallback_status = "seller_not_selected"
            fallback_reason = "Wybierz sprzedawcę energii, aby utworzyć standardowe ceny BUY."
        elif compatible_tariffs:
            fallback_status = "ready" if automatic_tariff_id or selected_tariff else "tariff_selection_required"
            fallback_reason = "" if fallback_status == "ready" else "Wybierz właściwą taryfę sprzedawcy."
        else:
            fallback_status = str(support.get("status") or "no_valid_standard_tariff")
            fallback_reason = str(support.get("reason") or "Brak ważnej, zgodnej taryfy sprzedawcy.")
        context = {
            "provider": self.osd_provider,
            "provider_name": str(
                catalog.get("providers", {}).get(self.osd_provider, {}).get("name")
                or self.osd_provider
            ),
            "plan": self.tariff_plan,
            "plan_name": str(tariff.get("name")) if tariff else self.tariff_plan.upper(),
            "mode": self.tariff_mode,
            "configured": automatic or self.tariff_mode == "manual",
            "tariff_error": "" if automatic or self.tariff_mode == "manual" else tariff_error,
            "zone": current_row.get("zone"),
            "season": current_row.get("season"),
            "day_type": current_row.get("day_type"),
            "distribution_rate": current_row.get("rate", 0),
            "common_rate": current_row.get("common_rate", 0),
            "total_distribution_rate": current_row.get("total_distribution_rate", current_row.get("rate", 0)),
            "peak_rate": round(display_peak_rate, 5),
            "offpeak_rate": round(display_offpeak_rate, 5),
            "custom_offpeak_windows": self.custom_offpeak_windows,
            "price_includes_distribution": buy_contract.get("includes_distribution_variable") is True,
            "price_contracts": {"buy": buy_contract, "sell": sell_contract},
            "seller_fallback": {
                "show": buy_entities_empty,
                "enabled": buy_entities_empty,
                "selected_seller_id": selected_seller,
                "selected_seller_tariff_id": selected_tariff,
                "automatic_seller_tariff_id": automatic_tariff_id,
                "suggested_seller_id": str(support.get("suggested_seller_id") or ""),
                "support_status": str(support.get("status") or "UNKNOWN_REQUIRES_RESEARCH"),
                "support_reason": str(support.get("reason") or ""),
                "status": fallback_status,
                "reason": fallback_reason,
                "seller_options": seller_options,
                "tariff_options": compatible_tariffs,
                "tariff_options_by_scope": seller_tariff_options_by_scope,
                "support_matrix": deepcopy(catalog.get("seller_support_matrix", {})),
                "tariff_selector_required": len(compatible_tariffs) > 1,
            },
            "price_diagnostics": deepcopy(self._canonical_price_snapshot),
            "grid_positive_is_import": bool(self.data.get(CONF_GRID_POSITIVE_IS_IMPORT, DEFAULT_GRID_POSITIVE_IS_IMPORT)),
            "battery_positive_is_discharge": bool(self.data.get(CONF_BATTERY_POSITIVE_IS_DISCHARGE, DEFAULT_BATTERY_POSITIVE_IS_DISCHARGE)),
            "providers": providers,
            "tariffs": available_tariffs(catalog, self.osd_provider),
            "hourly_profile": profile,
        }
        if self._tariff_catalog_manager is not None:
            context.update(self._tariff_catalog_manager.status())
        return context

    def validate_and_bind_price_contract(
        self,
        contract: dict[str, Any],
        *,
        strict: bool = True,
    ) -> dict[str, Any]:
        """Validate mapped entities/schema and attach stable registry bindings."""
        prepared = dict(contract)
        states: list[Any] = []
        for day_name in ("today", "tomorrow"):
            mapped = str(prepared.get(f"{day_name}_entity") or "")
            saved_binding = prepared.get(f"{day_name}_binding")
            if not isinstance(saved_binding, dict) or str(saved_binding.get("entity_id") or "") != mapped:
                saved_binding = self.capture_price_binding(mapped)
            resolved, status, reason = self.resolve_price_binding(mapped, saved_binding)
            prepared[f"{day_name}_binding"] = saved_binding
            prepared[f"resolved_{day_name}_entity"] = resolved
            prepared[f"stable_identity_{day_name}_status"] = status
            prepared[f"stable_identity_{day_name}_reason"] = reason
            if not mapped:
                prepared[f"{day_name}_binding"] = {}
                prepared[f"resolved_schema_{day_name}"] = {}
            state = self.hass.states.get(resolved) if resolved else None
            states.append(state)
            if strict and mapped and state is None:
                raise ValueError(f"{day_name.upper()}: mapped_entity_missing ({mapped})")
        prepared, schema_diagnostics = resolve_contract_schemas(prepared, states[0], states[1])
        for day_name, state in zip(("today", "tomorrow"), states):
            if state is None:
                continue
            status = str(schema_diagnostics.get(day_name, {}).get("status") or "")
            if strict and status == "unsupported_price_schema":
                raise ValueError(f"{day_name.upper()}: unsupported_price_schema")
        return prepared

    def validate_tariff_settings(self, settings: dict[str, Any]) -> dict[str, Any]:
        """Return a safe, normalized tariff configuration from the card."""
        if not isinstance(settings, dict):
            raise ValueError("Ustawienia taryfy muszą być obiektem")
        mode = str(settings.get(CONF_TARIFF_MODE, self.tariff_mode)).lower()
        if mode not in ("automatic", "manual"):
            raise ValueError("Nieznany tryb taryfy")
        provider = str(settings.get(CONF_OSD_PROVIDER, self.osd_provider)).lower()
        plan = str(settings.get(CONF_TARIFF_PLAN, self.tariff_plan)).lower()
        selected_tariff = get_tariff(self.tariff_catalog, provider, plan)
        if mode == "automatic" and selected_tariff is None:
            raise ValueError("Wybrana taryfa nie występuje w katalogu operatora")
        if mode == "automatic" and selected_tariff is not None:
            available, unavailable_reason = tariff_availability(selected_tariff, ha_now().date())
            if not available:
                raise ValueError(f"Wybrana taryfa nie może być jeszcze użyta: {unavailable_reason}")
        if provider not in self.tariff_catalog.get("providers", {}):
            raise ValueError("Nieznany operator OSD")
        peak = self.safe_float(settings.get(CONF_DISTRIBUTION_PEAK_RATE), self.distribution_peak_rate)
        offpeak = self.safe_float(settings.get(CONF_DISTRIBUTION_OFFPEAK_RATE), self.distribution_offpeak_rate)
        if not 0 <= peak <= 10 or not 0 <= offpeak <= 10:
            raise ValueError("Stawka dystrybucyjna musi mieścić się w zakresie 0–10 PLN/kWh")
        windows = str(settings.get(CONF_CUSTOM_OFFPEAK_WINDOWS, self.custom_offpeak_windows)).strip()
        if mode == "manual" and not parse_windows(windows):
            raise ValueError("Profil ręczny wymaga poprawnych przedziałów godzin")
        buy_input = settings.get(CONF_BUY_PRICE_CONTRACT)
        sell_input = settings.get(CONF_SELL_PRICE_CONTRACT)
        if buy_input is not None and not isinstance(buy_input, dict):
            raise ValueError("Kontrakt BUY musi być obiektem")
        if sell_input is not None and not isinstance(sell_input, dict):
            raise ValueError("Kontrakt SELL musi być obiektem")
        custom_fields = {
            "source_adapter", "economic_role", "semantic_scope", "includes_distribution_variable",
            "price_basis", "includes_excise", "includes_service_margin", "unit",
            "granularity", "current_price_only", "list_attribute",
            "today_list_attribute", "tomorrow_list_attribute", "value_field",
            "start_field", "end_field", "period_field", "timestamp_field",
            "timestamp_role", "business_date_field", "vat_rate",
        }

        def editable_contract(direction: str, submitted: dict[str, Any] | None) -> dict[str, Any]:
            current = self.price_contract(direction)
            if not isinstance(submitted, dict):
                return current
            current_adapters = {
                str(current.get(f"resolved_adapter_{day_name}") or "unmapped")
                for day_name in ("today", "tomorrow")
                if str(current.get(f"{day_name}_entity") or "")
            }
            requested_adapter = str(submitted.get("source_adapter") or current.get("source_adapter") or "")
            # Known integrations own their schema and semantics.  The tariff
            # editor may only author a Custom contract for generic/custom
            # mappings; mapped entity fields always come from Options Flow.
            if requested_adapter != "custom" or any(
                adapter in {"pstryk", "rce_pse"} for adapter in current_adapters
            ):
                return current
            candidate = dict(current)
            for field in custom_fields:
                if field in submitted:
                    candidate[field] = submitted[field]
            candidate.update({
                "source_adapter": "custom",
                "today_entity": str(current.get("today_entity") or ""),
                "tomorrow_entity": str(current.get("tomorrow_entity") or ""),
                "mapping_fingerprint": price_mapping_fingerprint(
                    current.get("today_entity"), current.get("tomorrow_entity")
                ),
            })
            return rebuild_price_contract(
                candidate,
                direction,
                candidate["today_entity"],
                candidate["tomorrow_entity"],
                "custom",
                "custom",
            )

        buy_contract = editable_contract("buy", buy_input)
        sell_contract = editable_contract("sell", sell_input)
        for direction, contract in (("BUY", buy_contract), ("SELL", sell_contract)):
            if (
                contract.get("source_adapter") == "custom"
                and contract.get("economic_role") not in SUPPORTED_ECONOMIC_ROLES
            ):
                raise ValueError(f"{direction}: wybierz rolę ekonomiczną własnego źródła")
        buy_contract = self.validate_and_bind_price_contract(
            buy_contract, strict=isinstance(buy_input, dict) and buy_contract.get("source_adapter") == "custom"
        )
        sell_contract = self.validate_and_bind_price_contract(
            sell_contract, strict=isinstance(sell_input, dict) and sell_contract.get("source_adapter") == "custom"
        )
        seller_id = str(settings.get(CONF_BUY_SELLER_ID, self.buy_seller_id) or "")
        seller_tariff_id = str(
            settings.get(CONF_BUY_SELLER_TARIFF_ID, self.buy_seller_tariff_id) or ""
        )
        buy_entities_empty = not str(buy_contract.get("today_entity") or "") and not str(
            buy_contract.get("tomorrow_entity") or ""
        )
        if seller_id and seller_id not in self.tariff_catalog.get("seller_tariffs", {}):
            raise ValueError("Nieznany sprzedawca energii")
        if buy_entities_empty and seller_tariff_id:
            for target_day in (ha_now().date(), ha_now().date() + timedelta(days=1)):
                _resolved_id, entry, reason = resolve_seller_tariff(
                    self.tariff_catalog,
                    seller_id,
                    seller_tariff_id,
                    provider,
                    plan,
                    target_day,
                )
                if entry is None:
                    raise ValueError(f"Taryfa sprzedawcy nie jest ważna dla {target_day.isoformat()}: {reason}")
        mapped_adapters = {
            str(contract.get(f"resolved_adapter_{day_name}") or "")
            for contract in (buy_contract, sell_contract)
            for day_name in ("today", "tomorrow")
            if str(contract.get(f"{day_name}_entity") or "")
        }
        price_source = (
            "none" if not mapped_adapters
            else "pstryk" if mapped_adapters == {"pstryk"}
            else "pse_rce" if mapped_adapters == {"rce_pse"}
            else "other"
        )
        return {
            CONF_TARIFF_MODE: mode,
            CONF_OSD_PROVIDER: provider,
            CONF_TARIFF_PLAN: plan,
            CONF_DISTRIBUTION_PEAK_RATE: round(peak, 5),
            CONF_DISTRIBUTION_OFFPEAK_RATE: round(offpeak, 5),
            CONF_CUSTOM_OFFPEAK_WINDOWS: windows,
            CONF_PRICE_SOURCE: price_source,
            CONF_PRICE_INCLUDES_DISTRIBUTION: buy_contract.get("includes_distribution_variable") is True,
            CONF_BUY_PRICE_CONTRACT: buy_contract,
            CONF_SELL_PRICE_CONTRACT: sell_contract,
            CONF_BUY_SELLER_ID: seller_id,
            CONF_BUY_SELLER_TARIFF_ID: seller_tariff_id,
            CONF_BUY_PRICE_TODAY_SENSOR: buy_contract.get("today_entity") or "",
            CONF_BUY_PRICE_TOMORROW_SENSOR: buy_contract.get("tomorrow_entity") or "",
            CONF_PRICE_SENSOR: sell_contract.get("today_entity") or "",
            CONF_SELL_PRICE_TOMORROW_SENSOR: sell_contract.get("tomorrow_entity") or "",
            CONF_GRID_POSITIVE_IS_IMPORT: bool(settings.get(CONF_GRID_POSITIVE_IS_IMPORT, self.data.get(CONF_GRID_POSITIVE_IS_IMPORT, DEFAULT_GRID_POSITIVE_IS_IMPORT))),
            CONF_BATTERY_POSITIVE_IS_DISCHARGE: bool(settings.get(CONF_BATTERY_POSITIVE_IS_DISCHARGE, self.data.get(CONF_BATTERY_POSITIVE_IS_DISCHARGE, DEFAULT_BATTERY_POSITIVE_IS_DISCHARGE))),
        }

    async def async_update_tariff_settings(self, settings: dict[str, Any]) -> dict[str, Any]:
        normalized = self.validate_tariff_settings(settings)
        previous = self.tariff_context()
        self.data.update(normalized)
        self._sanitize_cached_price_plans()
        self.request_optimizer_recalc("tariff")
        self.request_sensor_snapshot_refresh({"ai_state", "diagnostics"})
        self.learning_tracking["tariff_changed_at"] = ha_now().isoformat(timespec="seconds")
        await self.async_add_ai_analysis({
            "type": "tariff_configuration",
            "status": "saved",
            "previous": {"provider": previous.get("provider"), "plan": previous.get("plan"), "catalog_version": previous.get("catalog_version")},
            "current": {"provider": self.osd_provider, "plan": self.tariff_plan, "catalog_version": self.tariff_context().get("catalog_version")},
        })
        self.mark_config_saved()
        return normalized

    async def async_refresh_tariff_catalog(self) -> bool:
        if self._tariff_catalog_manager is None:
            return False
        changed = await self._tariff_catalog_manager.async_refresh(force=True)
        self._notify_update_for("tariff")
        return changed

    def weather_context(self) -> dict[str, Any]:
        state = self.hass.states.get(self.weather_entity) if self.weather_entity else None
        attrs = dict(state.attributes) if state is not None else {}
        cloud = self.safe_float(attrs.get("cloud_coverage"), 0)
        precipitation = self.safe_float(attrs.get("precipitation_probability"), 0)
        # Weather is a conservative auxiliary signal. Solcast remains the primary forecast.
        risk_factor = max(0.75, min(1.0, 1.0 - cloud * 0.0015 - precipitation * 0.001))
        return {
            "entity_id": self.weather_entity,
            "available": state is not None and state.state not in ("unknown", "unavailable"),
            "condition": state.state if state is not None else "unavailable",
            "temperature": attrs.get("temperature"),
            "temperature_unit": attrs.get("temperature_unit"),
            "pressure": attrs.get("pressure"),
            "pressure_unit": attrs.get("pressure_unit"),
            "humidity": attrs.get("humidity"),
            "wind_speed": attrs.get("wind_speed"),
            "wind_speed_unit": attrs.get("wind_speed_unit"),
            "wind_bearing": attrs.get("wind_bearing"),
            "wind_gust_speed": attrs.get("wind_gust_speed"),
            "visibility": attrs.get("visibility"),
            "visibility_unit": attrs.get("visibility_unit"),
            "cloud_coverage": attrs.get("cloud_coverage"),
            "precipitation_probability": attrs.get("precipitation_probability"),
            "precipitation_unit": attrs.get("precipitation_unit"),
            "risk_factor": round(risk_factor, 3),
            "forecast": self.weather_forecast[:48],
            "daily_forecast": self.weather_daily_forecast[:7],
            "hourly_count": len(self.weather_forecast[:48]),
            "daily_count": len(self.weather_daily_forecast[:7]),
            "last_updated": self.weather_last_updated,
            "last_error": self.weather_last_error,
        }

    @staticmethod
    def _price_from_object(item: Any) -> float | None:
        if not isinstance(item, dict):
            return None
        for key in (
            "price", "value", "state", "amount", "total", "net_price", "gross_price",
            "energy_price", "unit_price", "price_with_tax", "pln_kwh", "pln_per_kwh",
            "sell_price", "buy_price", "sprzedaz", "zakup", "cena", "pln", "rce",
        ):
            if key not in item:
                continue
            try:
                value = float(item[key])
            except (TypeError, ValueError):
                continue
            if math.isfinite(value):
                return value
        return None

    def _price_slot_from_value(
        self,
        value: Any,
        fallback: int | None = None,
    ) -> tuple[date | None, int | None]:
        """Return local calendar date/hour for a provider price label.

        Offset-aware ISO values are converted to Home Assistant's local
        timezone before either field is read. Naive ISO values retain their
        existing local-wall-time meaning. Plain hourly labels remain undated.
        """
        if isinstance(value, (int, float)) and 0 <= int(value) <= 23:
            return None, int(value)
        text = str(value or "")
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo is not None and parsed.utcoffset() is not None:
                local_tz = ha_now().tzinfo
                if local_tz is not None:
                    parsed = parsed.astimezone(local_tz)
            return parsed.date(), parsed.hour
        except (TypeError, ValueError):
            pass
        import re

        match = re.search(r"(?:^|\D)(\d{1,2})(?::\d{2})?", text)
        if match and 0 <= int(match.group(1)) <= 23:
            return None, int(match.group(1))
        return (
            None,
            fallback if fallback is not None and 0 <= fallback <= 23 else None,
        )

    def _hour_from_value(self, value: Any, fallback: int | None = None) -> int | None:
        """Compatibility wrapper returning only the localized hour."""
        return self._price_slot_from_value(value, fallback)[1]

    def _price_entries(
        self,
        entity_id: str | None,
        allow_state_fallback: bool = True,
    ) -> list[tuple[date | None, int, float]]:
        """Read ordered, localized price entries without losing their date."""
        state = self.hass.states.get(entity_id) if entity_id else None
        if state is None:
            return []
        result: list[tuple[date | None, int, float]] = []

        def add(item: Any, fallback: int | None = None) -> None:
            local_date: date | None = None
            hour: int | None = fallback
            value: float | None = None
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                local_date, hour = self._price_slot_from_value(item[0], fallback)
                try:
                    value = float(item[1])
                except (TypeError, ValueError):
                    value = None
            elif isinstance(item, dict):
                for key in (
                    "hour", "start", "from", "time", "date", "datetime", "timestamp",
                    "period", "label", "name", "start_time", "starts_at", "valid_from", "begin", "od",
                ):
                    if key in item:
                        local_date, hour = self._price_slot_from_value(item[key], fallback)
                        break
                value = self._price_from_object(item)
            else:
                try:
                    value = float(item)
                except (TypeError, ValueError):
                    value = None
            if hour is not None and value is not None and math.isfinite(value):
                result.append((local_date, hour, value))

        def parse(source: Any) -> None:
            if isinstance(source, list):
                for index, item in enumerate(source):
                    add(item, index if index < 24 else None)
            elif isinstance(source, dict):
                for index, (key, value) in enumerate(source.items()):
                    if isinstance(value, dict):
                        add({**value, "hour": value.get("hour", key)}, index if index < 24 else None)
                    else:
                        add([key, value], index if index < 24 else None)

        attrs = dict(state.attributes)
        for key in (
            "prices", "price", "today", "tomorrow", "hourly", "hours", "data", "values",
            "items", "entries", "forecast", "raw_today", "raw_tomorrow", "source", "price_list",
            "hourly_prices", "prices_today", "prices_tomorrow", "today_prices", "tomorrow_prices",
            "sell_prices", "buy_prices", "ceny", "ceny_godzinowe", "energy_prices",
        ):
            parse(attrs.get(key))
        if not result and allow_state_fallback:
            for key, value in attrs.items():
                if self._hour_from_value(key) is not None or isinstance(value, (list, dict)):
                    parse({key: value})
        if not result and allow_state_fallback:
            value = self.state_float_or_none(entity_id)
            if value is not None and math.isfinite(value):
                current = ha_now()
                result.append((current.date(), current.hour, value))
        return result

    def price_map(self, entity_id: str | None, allow_state_fallback: bool = True) -> dict[int, float]:
        """Read common hourly-price attribute layouts used by Polish integrations."""
        result: dict[int, float] = {}
        for _local_date, hour, value in self._price_entries(entity_id, allow_state_fallback):
            result.setdefault(hour, value)
        return result

    def price_maps(
        self,
        today_entity_id: str | None,
        tomorrow_entity_id: str | None,
        *,
        current: datetime | None = None,
    ) -> list[dict[int, float]]:
        """Bucket localized entries into DEM Today/Tomorrow maps."""
        reference = current or ha_now()
        maps: list[dict[int, float]] = [{}, {}]
        for source_day, (entity_id, allow_fallback) in enumerate((
            (today_entity_id, True),
            (tomorrow_entity_id, False),
        )):
            for local_date, hour, value in self._price_entries(entity_id, allow_fallback):
                day_offset = (
                    source_day
                    if local_date is None
                    else (local_date - reference.date()).days
                )
                if day_offset in (0, 1):
                    maps[day_offset].setdefault(hour, value)
        return maps

    @staticmethod
    def _canonical_price_day_signature(contract: dict[str, Any], day_name: str) -> tuple[Any, ...]:
        """Return the source identity and economics owned by one mapping slot."""
        binding = contract.get(f"{day_name}_binding")
        binding = binding if isinstance(binding, dict) else {}
        entity_id = str(contract.get(f"{day_name}_entity") or "")
        identity = str(binding.get("registry_entry_id") or entity_id)
        effective = effective_contract_for_day(contract, 0 if day_name == "today" else 1)
        return (
            identity,
            str(contract.get(f"resolved_adapter_{day_name}") or effective.get("source_adapter") or ""),
            str(effective.get("semantic_scope") or ""),
            str(effective.get("economic_role") or ""),
            effective.get("includes_distribution_variable"),
            effective.get("includes_excise"),
            effective.get("includes_service_margin"),
            str(effective.get("price_basis") or ""),
            str(effective.get("unit") or ""),
            str(effective.get("value_field") or ""),
            str(effective.get("list_attribute") or ""),
            str(effective.get("today_list_attribute") or ""),
            str(effective.get("tomorrow_list_attribute") or ""),
            str(effective.get("granularity") or ""),
        )

    def _sanitize_canonical_price_snapshot(self, snapshot: Any) -> bool:
        """Drop only cached direction/day rows that no longer match mappings.

        Persisted optimizer output is presentation/cache state, never source
        authority. This one-shot guard runs on load or an explicit tariff save;
        it does not add polling, listeners or Core executions.
        """
        if not isinstance(snapshot, dict) or snapshot.get("schema_version") != 1:
            return False
        changed = False
        for direction in ("buy", "sell"):
            current = self.price_contract(direction)
            branch = snapshot.get(direction)
            if not isinstance(branch, dict):
                continue
            cached_contract = branch.get("contract")
            cached_contract = cached_contract if isinstance(cached_contract, dict) else {}
            rows = [row for row in branch.get("rows", []) if isinstance(row, dict)]
            diagnostics = branch.get("diagnostics")
            diagnostics = dict(diagnostics) if isinstance(diagnostics, dict) else {}
            day_status = dict(diagnostics.get("day_status") or {})
            resolver = dict(diagnostics.get("resolver") or {})
            branch_changed = False
            for day_name in ("today", "tomorrow"):
                mapped = str(current.get(f"{day_name}_entity") or "")
                current_signature = self._canonical_price_day_signature(current, day_name)
                cached_signature = self._canonical_price_day_signature(cached_contract, day_name)
                effective = effective_contract_for_day(current, 0 if day_name == "today" else 1)
                current_adapter = str(
                    current.get(f"resolved_adapter_{day_name}")
                    or effective.get("source_adapter")
                    or "unmapped"
                )
                incompatible_row = any(
                    row.get("day") == day_name
                    and (
                        str(row.get("source_adapter") or "") != current_adapter
                        or str(row.get("source_semantic_scope") or "")
                        != str(effective.get("semantic_scope") or "")
                        or str(row.get("source_economic_role") or "")
                        != str(effective.get("economic_role") or "")
                    )
                    for row in rows
                )
                invalidate = not mapped or current_signature != cached_signature or incompatible_row
                if not invalidate:
                    continue
                before = len(rows)
                rows = [row for row in rows if row.get("day") != day_name]
                branch_changed = branch_changed or len(rows) != before or current_signature != cached_signature
                diagnostics[f"coverage_{day_name}"] = 0
                day_status[day_name] = "unmapped" if not mapped else "waiting_data"
                current_resolver = {
                    "mapped_entity": mapped,
                    "resolved_entity": str(current.get(f"resolved_{day_name}_entity") or mapped),
                    "stable_identity_status": str(current.get(f"stable_identity_{day_name}_status") or ("unmapped" if not mapped else "unbound")),
                    "detected_adapter": current_adapter,
                    "resolved_schema": "unknown" if mapped else "brak",
                    "coverage_hours": 0,
                    "status": "waiting_data" if mapped else "unmapped",
                    "reason": "cache_invalidated" if mapped else "user_unmapped",
                }
                if mapped:
                    current_resolver.update({
                        "unit": effective.get("unit"),
                        "economic_role": effective.get("economic_role"),
                        "semantic_scope": effective.get("semantic_scope"),
                    })
                resolver[day_name] = current_resolver
            branch["rows"] = rows
            branch["contract"] = deepcopy(current)
            diagnostics["day_status"] = day_status
            diagnostics["resolver"] = resolver
            if not str(current.get("today_entity") or "") and not str(current.get("tomorrow_entity") or ""):
                diagnostics["status"] = "price_source_not_configured"
            elif branch_changed and not rows:
                diagnostics["status"] = "waiting_data"
            branch["diagnostics"] = diagnostics
            snapshot[direction] = branch
            changed = changed or branch_changed
        return changed

    def _sanitize_cached_price_plans(self) -> bool:
        """Sanitize every live/persisted canonical cache without touching history."""
        changed = False
        for plan in (self.optimizer_plan, self._optimizer_public_snapshot):
            canonical = plan.get("canonical_prices") if isinstance(plan, dict) else None
            changed = self._sanitize_canonical_price_snapshot(canonical) or changed
        changed = self._sanitize_canonical_price_snapshot(self._canonical_price_snapshot) or changed
        planner = self._ai_state_snapshot.get("planner_48h") if isinstance(self._ai_state_snapshot, dict) else None
        canonical = planner.get("canonical_prices") if isinstance(planner, dict) else None
        changed = self._sanitize_canonical_price_snapshot(canonical) or changed
        if changed:
            self._optimizer_input_snapshot_id = ""
            self._optimizer_generation_reason = "price_mapping_cache_invalidated"
        return changed

    def canonical_price_context(
        self,
        current: datetime,
        tariff_rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Build the single backend price truth consumed by Core and the card."""
        distribution_by_slot: dict[tuple[date, int], float] = {}
        for row in tariff_rows:
            if not isinstance(row, dict) or row.get("available", True) is False:
                continue
            try:
                row_date = date.fromisoformat(str(row.get("date") or ""))
                row_hour = int(row.get("hour"))
            except (TypeError, ValueError):
                continue
            if 0 <= row_hour <= 23:
                distribution_by_slot[(row_date, row_hour)] = self.safe_float(
                    row.get("total_distribution_rate", row.get("rate")), 0
                )
        results: dict[str, Any] = {"schema_version": 1}
        for direction in ("buy", "sell"):
            contract = self.price_contract(direction)
            today_entity = str(contract.get("resolved_today_entity") or contract.get("today_entity") or "")
            tomorrow_entity = str(contract.get("resolved_tomorrow_entity") or contract.get("tomorrow_entity") or "")
            today_state = self.hass.states.get(today_entity) if today_entity else None
            tomorrow_state = self.hass.states.get(tomorrow_entity) if tomorrow_entity else None
            use_seller_catalog = (
                direction == "buy"
                and not str(contract.get("today_entity") or "")
                and not str(contract.get("tomorrow_entity") or "")
                and bool(self.buy_seller_id)
            )
            result = (
                seller_catalog_canonical_buy(
                    current,
                    self.tariff_catalog,
                    self.buy_seller_id,
                    self.buy_seller_tariff_id,
                    self.osd_provider,
                    self.tariff_plan,
                    distribution_by_slot,
                )
                if use_seller_catalog
                else build_canonical_direction(
                    contract,
                    today_state,
                    tomorrow_state,
                    current,
                    distribution_by_slot,
                )
            )
            resolver = result.setdefault("diagnostics", {}).setdefault("resolver", {})
            if use_seller_catalog:
                results[direction] = result
                continue
            for day_name in ("today", "tomorrow"):
                mapped = str(contract.get(f"{day_name}_entity") or "")
                resolved = str(contract.get(f"resolved_{day_name}_entity") or mapped)
                stable_status = str(contract.get(f"stable_identity_{day_name}_status") or "unbound")
                stable_reason = str(contract.get(f"stable_identity_{day_name}_reason") or "")
                branch = resolver.setdefault(day_name, {})
                schema = branch.get("resolved_schema") if isinstance(branch.get("resolved_schema"), dict) else {}
                day_contract = effective_contract_for_day(contract, 0 if day_name == "today" else 1)
                branch.update({
                    "mapped_entity": mapped,
                    "resolved_entity": resolved,
                    "stable_identity_status": stable_status,
                    "detected_adapter": contract.get(f"resolved_adapter_{day_name}") or day_contract.get("source_adapter"),
                    "resolved_schema": schema.get("schema_id") or "unknown",
                    "list_attribute": schema.get("list_attribute") or "",
                    "value_field": schema.get("value_field") or "",
                    "unit": day_contract.get("unit"),
                    "economic_role": day_contract.get("economic_role"),
                    "semantic_scope": day_contract.get("semantic_scope"),
                    "coverage_hours": sum(
                        1 for row in result.get("rows", []) if row.get("day") == day_name
                    ),
                    "reason": stable_reason or branch.get("status") or "",
                })
                if stable_status == "mapped_entity_missing":
                    branch["status"] = "mapped_entity_missing"
                elif stable_status == "unmapped":
                    branch["status"] = "unmapped"
                    branch["reason"] = "user_unmapped"
                    result.setdefault("diagnostics", {}).setdefault("day_status", {})[day_name] = "unmapped"
            if all(
                str(contract.get(f"stable_identity_{day_name}_status") or "") == "unmapped"
                for day_name in ("today", "tomorrow")
            ):
                result["diagnostics"]["status"] = "price_source_not_configured"
            results[direction] = result
        self._canonical_price_snapshot = deepcopy(results)
        return results

    def _weather_factors_48h(self) -> list[float | None]:
        factors: list[float | None] = [None] * 48
        current = ha_now()
        for fallback_index, row in enumerate(self.weather_forecast[:48]):
            if not isinstance(row, dict):
                continue
            index: int | None = None
            raw_time = row.get("datetime", row.get("time"))
            if raw_time:
                try:
                    stamp = datetime.fromisoformat(str(raw_time).replace("Z", "+00:00"))
                    if current.tzinfo is not None and stamp.tzinfo is not None:
                        stamp = stamp.astimezone(current.tzinfo)
                    day_offset = (stamp.date() - current.date()).days
                    if 0 <= day_offset <= 1:
                        index = day_offset * 24 + stamp.hour
                except (TypeError, ValueError):
                    index = None
            if index is None:
                stamp = current + timedelta(hours=fallback_index)
                day_offset = (stamp.date() - current.date()).days
                if 0 <= day_offset <= 1:
                    index = day_offset * 24 + stamp.hour
            if index is None or not 0 <= index < 48:
                continue
            cloud = self.safe_float(row.get("cloud_coverage"), 0)
            precipitation = self.safe_float(row.get("precipitation_probability"), 0)
            factors[index] = round(max(0.65, min(1.05, 1 - cloud * 0.002 - precipitation * 0.001)), 3)
        return factors

    def battery_model_context(self) -> dict[str, Any]:
        """Return explicit SOC, efficiency and power-limit semantics."""
        settings = self.ai_settings
        capacity = max(0.1, self.safe_float(settings.get("batteryCapacityKwh"), 10))
        legacy_efficiency = self.safe_float(settings.get("batteryEfficiency"), 90)
        legacy_efficiency = legacy_efficiency / 100 if legacy_efficiency > 1 else legacy_efficiency
        migrated = migrate_efficiencies(legacy_efficiency)

        def directional(key: str, fallback: float) -> float:
            value = self.safe_float(settings.get(key), fallback)
            value = value / 100 if value > 1 else value
            return max(0.5, min(1.0, value))

        charge_efficiency = directional("chargeEfficiency", migrated["charge_efficiency"])
        discharge_efficiency = directional("dischargeEfficiency", migrated["discharge_efficiency"])
        minimum = effective_minimum(
            hard_min_soc_pct=self.safe_float(settings.get("minSoc"), 20),
            reserve_kwh=self.safe_float(settings.get("reserveKwh"), 0),
            capacity_kwh=capacity,
            reserve_mode=str(settings.get("reserveMode") or "additional"),
        )
        voltage = self.state_float_or_none(self.battery_bms_voltage_sensor)
        if voltage is None:
            voltage = finite_float(settings.get("nominalBatteryVoltage"))
        plan_limit_w = min(
            self.safe_float(settings.get("maxSellPower"), 5000),
            self.effective_inverter_max_power_w,
        )
        inverter_limit_w = finite_float(settings.get("inverterPowerW"))
        if inverter_limit_w is None:
            inverter_limit_w = self.effective_inverter_max_power_w
        else:
            inverter_limit_w = min(inverter_limit_w, self.effective_inverter_max_power_w)
        entity_limit_w = self.state_float_or_none(self.max_sell_power_number)
        if entity_limit_w is None:
            entity_limit_w = self.effective_inverter_max_power_w
        else:
            entity_limit_w = min(entity_limit_w, self.effective_inverter_max_power_w)
        power = effective_power_limit(
            plan_limit_w=plan_limit_w,
            export_limit_w=finite_float(settings.get("exportLimitW")),
            inverter_limit_w=inverter_limit_w,
            current_limit_a=self.safe_float(settings.get("maxBatteryCurrentA"), self.manual_discharge_current or 120),
            battery_voltage_v=voltage,
            entity_limit_w=entity_limit_w,
        )
        charge_current = self.safe_float(
            settings.get("maxBatteryChargeCurrentA"),
            self.manual_charge_current or 60,
        )
        charge_power_from_current = charge_current * voltage if voltage and voltage > 0 else None
        charge_limit_w = power["effective_limit_w"]
        if charge_power_from_current is not None and charge_power_from_current > 0:
            charge_limit_w = min(charge_limit_w, charge_power_from_current)
        return {
            "capacity_kwh": capacity,
            "battery_voltage_v": voltage,
            "charge_efficiency": charge_efficiency,
            "discharge_efficiency": discharge_efficiency,
            "round_trip_efficiency": round(charge_efficiency * discharge_efficiency, 6),
            "efficiency_migration": migrated["migration"],
            "minimum": minimum,
            "target_max_soc_pct": max(
                minimum["effective_min_soc_pct"],
                min(100.0, self.safe_float(settings.get("targetSoc"), 100)),
            ),
            "power_limit": power,
            "directional_power_limits": {
                "battery_charge_limit_w": round(max(0.0, charge_limit_w), 3),
                "battery_discharge_limit_w": power["effective_limit_w"],
                "charge_current_a": charge_current,
            },
            "current_hour_remaining_minutes": remaining_minutes_in_hour(ha_now()),
        }

    def optimizer_baseline_schedule(self) -> list[dict[str, Any]]:
        """Snapshot the existing user schedule without changing a slot."""
        voltage = self.state_float_or_none(self.battery_bms_voltage_sensor)
        result: list[dict[str, Any]] = []
        for index in range(48):
            hour = index % 24
            slot = next(
                (
                    self.slots[key]
                    for key, _label, start, end in SLOTS
                    if start <= hour < end
                ),
                None,
            )
            if slot is None:
                result.append({
                    "enabled": False,
                    "mode": MODE_NORMAL_OPERATION,
                    "sell_power_w": 0.0,
                    "charge_enabled": False,
                    "charge_power_w": 0.0,
                })
                continue
            charge_current = min(
                value
                for value in (
                    max(0.0, slot.charge_current),
                    max(0.0, slot.grid_charge_current),
                )
                if value > 0
            ) if slot.charge_current > 0 and slot.grid_charge_current > 0 else max(
                0.0,
                slot.charge_current,
                slot.grid_charge_current,
            )
            result.append({
                "slot_key": slot.key,
                "enabled": bool(slot.enabled),
                "mode": slot.mode,
                "physical_work_mode": slot.physical_work_mode,
                "sell_power_w": max(0.0, slot.sell_power),
                "discharge_current_a": max(0.0, slot.discharge_current),
                "charge_enabled": bool(slot.charge_enabled),
                "charge_current_a": max(0.0, slot.charge_current),
                "grid_charge_current_a": max(0.0, slot.grid_charge_current),
                "charge_power_w": (
                    round(charge_current * voltage, 3)
                    if voltage is not None and charge_current > 0
                    else 0.0
                ),
                "tou_soc": slot.tou_soc,
                "minimum_sell_soc": slot.minimum_sell_soc,
                "min_sell_price": slot.min_sell_price,
            })
        return result

    def _learning_profile_stats(self, profile: dict[str, Any]) -> dict[str, int]:
        """Read counters from current and legacy learned-profile structures."""
        if not isinstance(profile, dict):
            return {
                "accepted_samples": 0,
                "rejected_samples": 0,
                "covered_cells": 0,
            }
        nested_cells = profile.get("cells")
        if isinstance(nested_cells, dict):
            cells = nested_cells
            accepted = int(max(0.0, self.safe_float(
                profile.get("accepted_samples"),
                sum(
                    self.safe_float(cell.get("samples"), 0)
                    for cell in cells.values()
                    if isinstance(cell, dict)
                ),
            )))
            rejected = int(max(0.0, self.safe_float(
                profile.get("rejected_samples"),
                0,
            )))
        else:
            cells = {
                key: cell
                for key, cell in profile.items()
                if isinstance(cell, dict) and "samples" in cell
            }
            accepted = int(sum(
                max(0.0, self.safe_float(cell.get("samples"), 0))
                for cell in cells.values()
            ))
            rejected = 0
        covered = sum(
            1
            for cell in cells.values()
            if isinstance(cell, dict)
            and self.safe_float(cell.get("samples"), 0) > 0
        )
        return {
            "accepted_samples": accepted,
            "rejected_samples": rejected,
            "covered_cells": covered,
        }

    def optimizer_core_inputs(
        self,
        settings: dict[str, Any] | None = None,
        battery_model: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return the subset of Optimizer Core inputs that limit power flows.

        This helper is public so tests can verify the exact limits passed to the
        planner without running the full 48-hour optimization.
        """
        if settings is None:
            settings = self.ai_settings
        if battery_model is None:
            battery_model = self.battery_model_context()
        model_discharge_limit = self.safe_float(
            battery_model["power_limit"].get("effective_limit_w"),
            0,
        )
        explicit_discharge_limit = finite_float(settings.get("batteryDischargeLimitW"))
        discharge_candidates = [
            value
            for value in (model_discharge_limit, explicit_discharge_limit)
            if value is not None and value > 0
        ]
        effective_discharge_limit = min(discharge_candidates) if discharge_candidates else 0.0
        source_limits = dict(battery_model["power_limit"].get("limits_w") or {})
        if explicit_discharge_limit is not None and explicit_discharge_limit > 0:
            source_limits["configured_battery_discharge"] = explicit_discharge_limit
        physical_sell_power = self.max_sell_power_range
        return {
            "max_sell_power_w": min(
                self.safe_float(settings.get("maxSellPower"), 5000),
                self.effective_inverter_max_power_w,
            ),
            "effective_power_limit_w": battery_model["power_limit"]["effective_limit_w"],
            "battery_charge_limit_w": self.safe_float(
                settings.get("batteryChargeLimitW"),
                battery_model["directional_power_limits"]["battery_charge_limit_w"],
            ),
            # The explicit setting is an additional safety cap.  It may lower,
            # but never raise, the physical/model limit.
            "battery_discharge_limit_w": effective_discharge_limit,
            "sell_power_limits_w": source_limits,
            "sell_power_minimum_w": (
                physical_sell_power.minimum_w
                if physical_sell_power.minimum_w is not None
                else 0.0
            ),
            "sell_power_maximum_w": physical_sell_power.maximum_w,
            "sell_power_step_w": (
                physical_sell_power.step_w
                if physical_sell_power.step_w is not None
                else 1.0
            ),
            "price_equivalence_band": max(
                0.0,
                self.safe_float(
                    settings.get("priceEquivalenceBand"),
                    DEFAULT_PRICE_EQUIVALENCE_BAND,
                ),
            ),
            "minimum_auto_sell_power_w": max(
                0.0,
                self.safe_float(
                    settings.get("minimumAutoSellPowerW"),
                    DEFAULT_MINIMUM_AUTO_SELL_POWER_W,
                ),
            ),
            "battery_discharge_limit_reason": battery_model["power_limit"].get("limit_reason"),
            "grid_import_limit_w": self.safe_float(
                settings.get("gridImportLimitW"),
                settings.get("inverterPowerW") or 100000,
            ),
            "grid_export_limit_w": self.safe_float(settings.get("exportLimitW"), 100000),
            "inverter_ac_limit_w": min(
                self.safe_float(settings.get("inverterPowerW"), 100000),
                self.effective_inverter_max_power_w,
            ),
        }

    def _prepare_ai_plan_48h(self) -> dict[str, Any]:
        """Capture every HA/runtime input before pure Core work leaves MainThread."""
        settings = self.ai_settings
        battery_model = self.battery_model_context()
        learning = self.learning_summary()
        profile = learning.get("hourly_profile") if isinstance(learning.get("hourly_profile"), list) else []
        by_hour = {int(str(row.get("hour", "0"))[:2]): row for row in profile if isinstance(row, dict)}
        tariff = self.tariff_context()
        tariff_rows = [
            row for row in tariff.get("hourly_profile", [])[:48]
            if isinstance(row, dict)
        ]
        buy_contract = self.price_contract("buy")
        sell_contract = self.price_contract("sell")
        distribution = [
            self.safe_float(row.get("total_distribution_rate", row.get("rate")), 0)
            for row in tariff_rows
        ]
        distribution.extend([0.0] * (48 - len(distribution)))
        osd_data_complete = bool(tariff.get("configured")) and len(tariff_rows) == 48 and all(
            row.get("available", True) is not False
            and row.get("total_distribution_rate", row.get("rate")) is not None
            for row in tariff_rows
        )
        osd_available_hours = (
            48
            if buy_contract.get("includes_distribution_variable") is True
            else 0
            if not bool(tariff.get("configured"))
            else sum(
                1
                for row in tariff_rows
                if row.get("available", True) is not False
                and row.get("total_distribution_rate", row.get("rate")) is not None
            )
        )
        load_profile_stats = self._learning_profile_stats(self.load_profile_7x24)
        pv_profile_stats = self._learning_profile_stats(self.pv_learning_profile)
        today_forecast_reading = self.solcast_forecast_today_reading()
        today_forecast = (
            max(0, self.safe_float(today_forecast_reading.get("value"), 0))
            if today_forecast_reading.get("status") in ("ok", "derived_actual_plus_remaining")
            else 0
        )
        today_actual = max(0, self.state_float(self.daily_pv_production_sensor, 0))
        remaining_reading = self._measurement(
            self.solcast_remaining_today_sensor,
            kind="energy",
            stale_after_seconds=_SOLCAST_TRACKING_STALE_SECONDS,
        )
        remaining = max(0, self.safe_float(remaining_reading.get("value"), 0))
        if remaining <= 0:
            remaining = max(0, today_forecast - today_actual)
        tomorrow_reading = self._measurement(
            self.solcast_forecast_tomorrow_sensor,
            kind="energy",
            stale_after_seconds=_SOLCAST_DAILY_FORECAST_STALE_SECONDS,
        )
        tomorrow_forecast = max(
            0,
            self.safe_float(tomorrow_reading.get("value"), 0),
        )
        selected_strategy = str(settings.get("strategy") or "balanced")
        if selected_strategy == "autoconsumption":
            selected_strategy = "safe"
        current = ha_now()
        canonical_prices = self.canonical_price_context(current, tariff_rows)
        sell_prices = canonical_maps(canonical_prices["sell"])
        buy_prices = canonical_maps(canonical_prices["buy"])
        load_forecasts = [
            forecast_load(self.load_profile_7x24, current.replace(minute=0, second=0, microsecond=0) + timedelta(hours=index))
            for index in range(48)
        ]
        live_state = self.live_state_context()
        current_load_forecast, _load_source, _load_samples = forecast_load(
            self.load_profile_7x24,
            current.replace(minute=0, second=0, microsecond=0),
        )
        current_pv_forecast = finite_float(by_hour.get(current.hour, {}).get("pv_kwh"))
        live_state["pv_forecast_deviation"] = self._material_deviation_bucket(
            live_state.get("pv_power_w"),
            current_pv_forecast,
        )
        live_state["load_forecast_deviation"] = self._material_deviation_bucket(
            live_state.get("home_power_w"),
            current_load_forecast,
        )
        current_hour_partial = self.current_hour_partial_context()
        historical_hours = [
            {
                key: row.get(key)
                for key in (
                    "hour", "local_date", "local_hour", "pv_kwh", "load_kwh",
                    "grid_import_kwh", "grid_export_kwh", "battery_charge_kwh",
                    "battery_discharge_kwh", "soc_start", "soc_end", "soc_min",
                    "soc_max", "soc_avg", "sell_price_avg", "buy_price_avg",
                    "action", "control", "channel_quality", "energy_balance",
                    "solcast_accuracy_percent", "weather_forecast", "weather_actual",
                )
            }
            for row in self.learning_history[:168]
            if isinstance(row, dict)
        ]
        source_quality = self.source_quality_context()
        source_quality["channel_diagnostics"] = learning.get("channel_diagnostics", {})
        source_quality["usable_history_hours"] = learning.get("usable_hours", 0)
        source_quality["history_first_hour"] = learning.get("history_first_hour")
        source_quality["history_last_hour"] = learning.get("history_last_hour")
        payload = {
            "date": current.date().isoformat(),
            "generated_at": current.isoformat(timespec="seconds"),
            "timezone": str(
                getattr(getattr(self.hass, "config", None), "time_zone", None)
                or current.tzinfo
                or "UTC"
            ),
            "current_hour": current.hour,
            "soc": (
                round(value, 1)
                if (value := self.current_soc_or_none()) is not None
                else None
            ),
            "battery_capacity_kwh": self.safe_float(settings.get("batteryCapacityKwh"), 10),
            "battery_efficiency": battery_model["round_trip_efficiency"],
            "charge_efficiency": battery_model["charge_efficiency"],
            "discharge_efficiency": battery_model["discharge_efficiency"],
            "min_soc": self.safe_float(settings.get("minSoc"), 20),
            "effective_min_soc": battery_model["minimum"]["effective_min_soc_pct"],
            "target_soc": self.safe_float(settings.get("targetSoc"), 100),
            "reserve_kwh": self.safe_float(settings.get("reserveKwh"), 0),
            **self.optimizer_core_inputs(settings, battery_model),
            "current_hour_remaining_minutes": battery_model["current_hour_remaining_minutes"],
            "charge_kwh_per_hour": max(0.25, self.safe_float(settings.get("batteryCapacityKwh"), 10) * 0.25),
            "min_sell_price": self.safe_float(settings.get("minSellPrice"), 0),
            "max_buy_price": self.safe_float(settings.get("maxBuyPrice"), 999),
            "allow_battery_sell": bool(settings.get("allowBatterySell", True)),
            "allow_grid_charge": bool(settings.get("allowGridCharge", True)),
            "sell_prices": sell_prices,
            "buy_prices": buy_prices,
            "distribution": distribution,
            "price_includes_distribution": buy_contract.get("includes_distribution_variable") is True,
            "price_contracts": {"buy": buy_contract, "sell": sell_contract},
            "price_diagnostics": deepcopy(canonical_prices),
            "canonical_prices": deepcopy(canonical_prices),
            "osd_data_complete": osd_data_complete,
            "osd_available_hours": osd_available_hours,
            "tariff_context": {
                key: tariff.get(key)
                for key in (
                    "provider", "provider_name", "plan", "plan_name", "mode",
                    "configured", "tariff_error",
                    "price_includes_distribution", "hourly_profile",
                )
            },
            "buy_price_source": self.buy_price_today_sensor,
            # Core consumes energy forecasts in kWh.  The first array contains
            # energy still available from now, while ``pv_forecast_full`` keeps
            # the full-day denominator.  Neither field is a realization rate.
            "pv_forecast": [remaining, tomorrow_forecast],
            "pv_forecast_full": [today_forecast, tomorrow_forecast],
            "pv_forecast_available": [
                today_forecast_reading.get("status") in ("ok", "derived_actual_plus_remaining"),
                tomorrow_reading.get("status") == "ok",
            ],
            "forecast_correction": self.safe_float(learning.get("solcast_correction_factor"), 1),
            # Historical completed-day accuracy is used only for uncertainty;
            # current-day realization is intentionally absent from Core input.
            "forecast_accuracy": learning.get("solcast_accuracy_avg"),
            "pv_profile": [self.safe_float(by_hour.get(hour, {}).get("pv_kwh"), 0) for hour in range(24)],
            "load_profile": [self.safe_float(by_hour.get(hour, {}).get("load_kwh"), 0) for hour in range(24)],
            # Preserve a missing forecast as None. Optimizer Core may use only
            # evidence-based fallbacks and must never turn missing load into
            # additional sellable energy by coercing it to zero.
            "load_profile_48h": [value for value, _source, _samples in load_forecasts],
            "load_profile_sources_48h": [
                {"source": source, "samples": samples}
                for _value, source, samples in load_forecasts
            ],
            "weather_factors": self._weather_factors_48h(),
            "apply_weather_correction": bool(settings.get("applyWeatherCorrection", False)),
            "recorded_days": learning.get("recorded_days", 0),
            "load_profile_sample_count": load_profile_stats["accepted_samples"],
            "load_profile_rejected_count": load_profile_stats["rejected_samples"],
            "load_profile_covered_cells": load_profile_stats["covered_cells"],
            "load_profile_total_cells": 168,
            "pv_profile_sample_count": pv_profile_stats["accepted_samples"],
            "pv_profile_rejected_count": pv_profile_stats["rejected_samples"],
            "pv_profile_covered_cells": pv_profile_stats["covered_cells"],
            "pv_profile_total_cells": 288,
            "learning_stage": learning.get("learning_stage", {}),
            "learning_maturity": learning.get("learning_maturity", {}),
            "user_profiles": deepcopy(self.user_profiles),
            "profile_execution": deepcopy(self.profile_execution),
            "data_quality": source_quality,
            "soc_diagnostics": self.soc_diagnostics(),
            "live_state": live_state,
            "current_hour_partial": current_hour_partial,
            "historical_hours": historical_hours,
            "history_revision": (
                f"{learning.get('history_last_hour') or 'none'}:"
                f"{learning.get('recorded_hours', 0)}:"
                f"{learning.get('usable_hours', 0)}"
            ),
            "history_schema_version": HISTORY_SCHEMA_VERSION,
            "generation_reason": self._optimizer_generation_reason,
            "previous_plan_id": self.optimizer_plan.get("plan_id"),
            "baseline_schedule": self.optimizer_baseline_schedule(),
            "battery_cycle_cost_per_kwh": self.safe_float(settings.get("batteryCycleCostPerKwh"), 0),
            "terminal_energy_value_per_kwh": self.safe_float(settings.get("terminalEnergyValuePerKwh"), 0),
            "battery_voltage_v": battery_model.get("battery_voltage_v"),
        }
        current_snapshot_id = snapshot_id({
            "semantic_inputs": self._semantic_optimizer_inputs(payload)
        })
        # Every mutable runtime collection included above is copied, so this
        # owned payload can safely cross into the executor without HA access.
        self._optimizer_last_inputs = payload
        return {
            "payload": payload,
            "selected_strategy": selected_strategy,
            "snapshot_id": current_snapshot_id,
            "current": current,
            "battery_model": battery_model,
        }

    @classmethod
    def _semantic_optimizer_inputs(
        cls,
        value: Any,
        _path: tuple[str, ...] = (),
    ) -> Any:
        """Drop reporting metadata while retaining freshness state transitions."""
        if isinstance(value, dict):
            status = str(value.get("status") or "")
            result = {
                str(key): cls._semantic_optimizer_inputs(
                    item,
                    (*_path, str(key)),
                )
                for key, item in value.items()
                if key not in {
                    "generated_at",
                    "generation_reason",
                    "previous_plan_id",
                    "last_updated",
                    "last_reported",
                    "reported_at",
                    "soc_reported_at",
                    "soc_report_age_seconds",
                    "observed_at",
                    "value_changed_at",
                    "freshness_source",
                    "source_health_source",
                    "source_health_at",
                    "source_health_age_seconds",
                    "effective_soc_freshness_at",
                    "effective_soc_age_seconds",
                    "freshness_reason",
                    "effective_threshold_seconds",
                    "age_seconds",
                }
                and not (
                    _path == ("live_state",)
                    and (
                        key == "timestamp"
                        or (
                            key == "pv_power_w"
                            and "pv_forecast_deviation" in value
                        )
                        or (
                            key == "home_power_w"
                            and "load_forecast_deviation" in value
                        )
                    )
                )
                and not (
                    _path == ()
                    and key in {"current_hour_partial", "current_hour_remaining_minutes"}
                )
            }
            if status == "stale" and "reason" in result:
                result["reason"] = "stale"
            return result
        if isinstance(value, (list, tuple)):
            return [
                cls._semantic_optimizer_inputs(item, (*_path, str(index)))
                for index, item in enumerate(value)
            ]
        return value

    def _optimizer_plan_is_current(self, prepared: dict[str, Any]) -> bool:
        if prepared["snapshot_id"] == self._optimizer_budget_blocked_snapshot_id:
            return True
        return bool(
            self.optimizer_plan
            and prepared["snapshot_id"] == self._optimizer_input_snapshot_id
            and self.optimizer_plan.get("algorithm_version") == ALGORITHM_VERSION
            and self.optimizer_plan.get("plan_schema_version") == PLAN_SCHEMA_VERSION
        )

    @staticmethod
    def _compact_optimizer_history_entry(plan: Any) -> dict[str, Any]:
        """Keep one useful plan audit record without another complete 48 h plan."""
        source = plan if isinstance(plan, dict) else {}
        quality = source.get("data_quality") if isinstance(source.get("data_quality"), dict) else {}
        return {
            key: source.get(key)
            for key in (
                "plan_id",
                "generated_at",
                "horizon_start",
                "horizon_end",
                "generation_reason",
                "algorithm_version",
                "plan_schema_version",
                "history_schema_version",
                "input_snapshot_id",
                "selected_variant",
                "learning_status",
                "plan_status",
                "previous_plan_id",
                "superseded_by_plan_id",
                "baseline_result",
                "optimized_result",
                "benefit",
                "neutrality_threshold",
                "comparison",
                "recommended_write",
            )
            if key in source
        } | {
            "data_quality": {
                key: quality.get(key)
                for key in (
                    "fail_closed",
                    "fail_closed_reason",
                    "learning_apply_allowed",
                    "recorded_days",
                    "usable_history_hours",
                )
                if key in quality
            }
        }

    def _apply_prepared_ai_plan(
        self,
        prepared: dict[str, Any],
        core_result: dict[str, Any] | None,
    ) -> tuple[dict[str, Any], bool]:
        """Apply a pure Core result on MainThread and report semantic output change."""
        current = prepared["current"]
        battery_model = prepared["battery_model"]
        current_snapshot_id = prepared["snapshot_id"]
        if core_result is None:
            result = dict(self.optimizer_plan)
        else:
            result = dict(core_result)
            self._optimizer_budget_blocked_snapshot_id = ""
            self._optimizer_budget_status = {
                "status": "ok",
                "reason": None,
                "limits": deepcopy(core_result.get("core_budget", {}).get("limits", {})),
                "usage": deepcopy(core_result.get("core_budget", {}).get("usage", {})),
            }
            previous = (
                self._compact_optimizer_history_entry(self.optimizer_plan)
                if self.optimizer_plan
                else None
            )
            if previous:
                previous["superseded_by_plan_id"] = result.get("plan_id")
                self.optimizer_plan_history = [previous, *self.optimizer_plan_history][:30]
            self.optimizer_plan = core_result
            self._sync_profile_execution_from_plan(result, current)
            self._optimizer_input_snapshot_id = current_snapshot_id
            self._optimizer_generation_reason = "cached_until_input_change"
            # Core refreshes are high-frequency derived state. Mark them for a
            # controlled final flush instead of writing both Stores per cycle.
            self._ai_save_dirty = True
            self._learning_save_dirty = True
        archive_changed = self._sync_plan_execution_archive(result, current)
        if archive_changed:
            self._ai_save_dirty = True
        forecast_hours = [
            {
                "timestamp": f"{row.get('date')}T{int(row.get('hour', 0)):02d}:00:00{current.strftime('%z')[:3]}:{current.strftime('%z')[3:]}",
                "soc_end_pct": row.get("soc_end_pct", row.get("soc_after")),
            }
            for row in result.get("rows", [])
            if isinstance(row, dict)
        ]
        result["battery_model"] = battery_model
        # A shallow list snapshot preserves every established public row while
        # avoiding deep-copying up to two years of immutable-by-convention data.
        result["profile_execution"] = list(self.profile_execution)
        result["soc_timeline"] = build_soc_timeline(
            now=current,
            historical_hours=self.learning_history,
            current_soc_pct=self.current_soc_or_none(),
            forecast_hours=forecast_hours,
        )
        plan_id = str(result.get("plan_id") or "")
        output_changed = bool(
            plan_id != self._optimizer_last_plan_id
            or self._profile_execution_revision
            != self._optimizer_last_profile_execution_revision
            or not self._optimizer_public_snapshot
        )
        if output_changed or not self._optimizer_public_snapshot:
            self._optimizer_public_snapshot = result
            self._optimizer_last_plan_id = plan_id
            self._optimizer_last_profile_execution_revision = (
                self._profile_execution_revision
            )
            self._optimizer_output_snapshot_id = plan_id
        return result, output_changed

    def ai_plan_48h(self) -> dict[str, Any]:
        """Synchronous compatibility wrapper used outside the HA runtime worker."""
        prepared = self._prepare_ai_plan_48h()
        core_result = None
        if not self._optimizer_plan_is_current(prepared):
            core_result = build_plan_bundle(
                prepared["payload"],
                prepared["selected_strategy"],
            )
        result, _changed = self._apply_prepared_ai_plan(prepared, core_result)
        return result

    def register_entity(self, entity: Any) -> None:
        if entity not in self.entities:
            self.entities.append(entity)

    def unregister_entity(self, entity: Any) -> None:
        if entity in self.entities:
            self.entities.remove(entity)
        self._entity_publish_signatures.pop(id(entity), None)

    def _entity_public_signature(self, entity: Any) -> Any:
        """Build the same public state/attribute signature HA would publish."""
        try:
            if hasattr(type(entity), "is_on"):
                public_state = getattr(entity, "is_on")
            elif hasattr(type(entity), "native_value"):
                public_state = getattr(entity, "native_value")
            elif hasattr(type(entity), "current_option"):
                public_state = getattr(entity, "current_option")
            else:
                public_state = getattr(entity, "state", None)
            attributes_factory = getattr(entity, "_async_generate_attributes", None)
            entity_key = str(getattr(entity, "_deye_manager_key", ""))
            if entity_key == "ai_state":
                return (
                    "ai_state",
                    getattr(entity, "available", True),
                    public_state,
                    self._ai_state_snapshot_id,
                )
            if entity_key == "diagnostics":
                # Diagnostics is already a granular channel. Avoid hashing its
                # growing metrics on every unrelated full publication.
                return None
            attributes = (
                attributes_factory()
                if callable(attributes_factory)
                else getattr(entity, "extra_state_attributes", None)
            )
            try:
                attributes_identity = snapshot_id(attributes)
            except (TypeError, ValueError):
                attributes_identity = repr(attributes)
            return (
                getattr(entity, "available", True),
                public_state,
                attributes_identity,
            )
        except Exception:
            # A custom entity getter must never be allowed to suppress a write.
            return None

    @callback
    def _notify_update_for(self, reason: str) -> None:
        """Tag one legacy no-argument publication without changing its contract."""
        previous = self._performance_publish_reason
        self._performance_publish_reason = reason
        try:
            self.notify_update()
        finally:
            self._performance_publish_reason = previous

    @callback
    def notify_update(self, reason: str | None = None) -> None:
        reason = reason or self._performance_publish_reason or "other"
        self.runtime_metrics["notify_update_count"] += 1
        if self._platform_setup_in_progress:
            self._platform_publish_pending = True
            self._sensor_snapshot_requested_keys.update({"ai_state", "diagnostics"})
            self._sensor_snapshot_pending = True
            return
        self._performance.inc("notify_update_full_calls")
        self._performance.inc_map("notify_update_full_by_reason", reason)
        self.request_sensor_snapshot_refresh()
        publish_started = time.perf_counter()
        self._notify_entities_from_cache(reason=reason)
        self._performance.observe_ms(
            "full_publish",
            (time.perf_counter() - publish_started) * 1000.0,
        )

    @callback
    def _notify_entities_from_cache(
        self,
        entity_keys: set[str] | None = None,
        *,
        reason: str = "granular",
    ) -> int:
        if entity_keys is not None:
            self._performance.inc("notify_granular_calls")
        published = 0
        for entity in list(self.entities):
            if (
                getattr(entity, "hass", None) is not None
                and (
                    entity_keys is None
                    or getattr(entity, "_deye_manager_key", None) in entity_keys
                )
            ):
                identity = id(entity)
                signature = self._entity_public_signature(entity)
                if (
                    entity_keys is None
                    and signature is not None
                    and self._entity_publish_signatures.get(identity) == signature
                ):
                    continue
                self._performance.record_entity_write(
                    getattr(entity, "_deye_manager_key", "unknown"),
                    reason,
                    channel=("proxy" if getattr(entity, "source_fn", None) is not None else None),
                )
                entity.async_write_ha_state()
                if signature is not None:
                    self._entity_publish_signatures[identity] = signature
                published += 1
        return published

    def request_sensor_snapshot_refresh(
        self,
        entity_keys: set[str] | None = None,
    ) -> Any:
        """Coalesce expensive publication snapshot rebuilds outside getters."""
        self._sensor_snapshot_requested_keys.update(
            entity_keys or {"ai_state", "diagnostics"}
        )
        self._sensor_snapshot_pending = True
        task = self._sensor_snapshot_task
        if (
            self._startup_in_progress
            or self._platform_setup_in_progress
            or (self._initial_optimizer_pending and not self._initial_optimizer_started)
            or self._unloading
            or (task is not None and not task.done())
        ):
            return task
        task = self.hass.async_create_task(self.async_refresh_sensor_snapshots())
        self._sensor_snapshot_task = task
        return task

    def build_ai_state_snapshot(self) -> dict[str, Any]:
        """Build the expensive AI sensor payload outside entity getters."""
        learning = self.learning_summary()
        return {
            "settings": self.ai_settings,
            "user_profiles": self.user_profiles,
            "optimizer_plan_history": self.optimizer_plan_history[:30],
            "optimizer_plan_history_format": "compact-v1",
            "optimizer_plan_history_schema_version": HISTORY_SCHEMA_VERSION,
            "api_assistant": self.ai_api_public_context(),
            "history": self.ai_history,
            "history_count": len(self.ai_history),
            "learning_summary": learning,
            "solcast_current_day": self.solcast_current_day_metrics(
                historical_accuracy_pct=learning.get("solcast_accuracy_avg"),
            ),
            "learning_recent": self.learning_history[:24],
            "learning_current_hour": self._finalize_learning_hour(
                self.learning_tracking,
                update_models=False,
            ) if self.learning_tracking else {},
            "current_hour_partial": self.current_hour_partial_context(),
            "live_state": self.live_state_context(),
            "daily_summary": self.history_daily_summary(),
            "monthly_summary": self.history_monthly_summary(),
            "solcast_history": self.solcast_history,
            # Preserve the established detailed UI contract for the latest
            # 288 minutes while older persisted rows stay compact.
            "energy_samples": (
                self._energy_recent_details[-288:]
                if self._energy_recent_details
                else self.energy_samples[-288:]
            ),
            "weather": self.weather_context(),
            "tariff": self.tariff_context(),
            "planner_48h": self._optimizer_public_snapshot or self.optimizer_plan,
            "future_plan": self.future_plan,
            "plan_execution_index": self.plan_execution_index(),
            "plan_execution_today": self.plan_execution_day(),
        }

    def diagnostics_public_snapshot(self) -> dict[str, Any]:
        """Merge small live lifecycle counters into the cached heavy diagnostics."""
        snapshot = dict(self._diagnostics_snapshot)
        snapshot["optimizer_runtime"] = {
            **deepcopy(self.runtime_metrics),
            "pending": self._optimizer_recalc_pending,
            "pending_reasons": sorted(self._optimizer_pending_reasons),
            "active_recalc": self._optimizer_active_recalc,
            "listener_entities": list(self._optimizer_listener_entity_ids),
        }
        return snapshot

    async def async_refresh_sensor_snapshots(self) -> None:
        """Build AI and diagnostics snapshots single-flight, never in a getter."""
        if self._unloading:
            return
        current = asyncio.current_task()
        active = self._sensor_snapshot_task
        if active is not None and active is not current and not active.done():
            self._sensor_snapshot_pending = True
            await asyncio.shield(active)
            return
        if active is None or active.done():
            self._sensor_snapshot_task = current
        follow_up_used = False
        changed_keys: set[str] = set()
        try:
            while True:
                self._sensor_snapshot_pending = False
                requested_keys = set(self._sensor_snapshot_requested_keys)
                self._sensor_snapshot_requested_keys.clear()
                await asyncio.sleep(0)
                if "ai_state" in requested_keys:
                    snapshot_started = time.perf_counter()
                    ai_snapshot = self.build_ai_state_snapshot()
                    self._performance.observe_ms(
                        "ai_snapshot_build",
                        (time.perf_counter() - snapshot_started) * 1000.0,
                    )
                    ai_snapshot_id = snapshot_id(ai_snapshot)
                    if ai_snapshot_id != self._ai_state_snapshot_id:
                        self._ai_state_snapshot = ai_snapshot
                        self._ai_state_snapshot_id = ai_snapshot_id
                        changed_keys.add("ai_state")
                if "diagnostics" in requested_keys:
                    diagnostics_started = time.perf_counter()
                    diagnostics_snapshot = self.diagnostics()
                    self._performance.observe_ms(
                        "diagnostics_build",
                        (time.perf_counter() - diagnostics_started) * 1000.0,
                    )
                    diagnostics_semantic = {
                        key: value
                        for key, value in diagnostics_snapshot.items()
                        if key != "optimizer_runtime"
                    }
                    diagnostics_snapshot_id = snapshot_id(diagnostics_semantic)
                    if diagnostics_snapshot_id != self._diagnostics_snapshot_id:
                        self._diagnostics_snapshot = diagnostics_snapshot
                        self._diagnostics_snapshot_id = diagnostics_snapshot_id
                        changed_keys.add("diagnostics")
                if self._sensor_snapshot_pending and not follow_up_used:
                    follow_up_used = True
                    continue
                break
        finally:
            if self._sensor_snapshot_task is current:
                self._sensor_snapshot_task = None
        if changed_keys:
            self.runtime_metrics["snapshot_publish_count"] += 1
            self._notify_entities_from_cache(
                changed_keys,
                reason="sensor_snapshot",
            )
        if self._sensor_snapshot_pending and not self._unloading:
            self.request_sensor_snapshot_refresh()

    def request_optimizer_recalc(self, reason: str | set[str] | list[str] | tuple[str, ...] = "manual") -> Any:
        """Coalesce material 5G input changes into one optimizer task."""
        requested_reasons = (
            {str(item or "manual") for item in reason}
            if isinstance(reason, (set, list, tuple))
            else {str(reason or "manual")}
        )
        self._performance.record_optimizer_request(requested_reasons)
        self._performance.inc("optimizer_pending_set")
        self.runtime_metrics["optimizer_recalc_requested"] += 1
        reason_counts = self.runtime_metrics["optimizer_recalc_reasons"]
        for normalized_reason in requested_reasons:
            reason_counts[normalized_reason] = int(reason_counts.get(normalized_reason, 0)) + 1
            metric_key = f"optimizer_recalc_reason_{normalized_reason}"
            self.runtime_metrics[metric_key] = int(self.runtime_metrics.get(metric_key, 0)) + 1
        self._optimizer_pending_reasons.update(requested_reasons)
        self._optimizer_recalc_pending = True
        task = self._optimizer_recalc_task
        if task is not None and not task.done():
            self._performance.inc("optimizer_skipped_busy")
        if (
            self._startup_in_progress
            or self._platform_setup_in_progress
            or (self._initial_optimizer_pending and not self._initial_optimizer_started)
            or self._unloading
            or (task is not None and not task.done())
        ):
            return task
        task = self.hass.async_create_task(self.async_refresh_optimizer_plan())
        self._optimizer_recalc_task = task
        return task

    async def async_refresh_optimizer_plan(self) -> None:
        """Run pure Core off-loop, with semantic dedup and one follow-up."""
        if self._unloading:
            return
        current = asyncio.current_task()
        active = self._optimizer_recalc_task
        if active is not None and active is not current and not active.done():
            self._optimizer_recalc_pending = True
            await asyncio.shield(active)
            return
        if active is None or active.done():
            self._optimizer_recalc_task = current
        self._optimizer_active_recalc += 1
        self.runtime_metrics["optimizer_recalc_max_active"] = max(
            int(self.runtime_metrics["optimizer_recalc_max_active"]),
            self._optimizer_active_recalc,
        )
        follow_up_used = False
        output_changed = False
        try:
            while True:
                self._optimizer_recalc_pending = False
                reasons = sorted(self._optimizer_pending_reasons)
                self._optimizer_pending_reasons.clear()
                await asyncio.sleep(0)
                prepare_started = time.perf_counter()
                try:
                    prepared = self._prepare_ai_plan_48h()
                except Exception:
                    self._performance.inc("optimizer_failed")
                    raise
                self._performance.observe_ms(
                    "optimizer_prepare",
                    (time.perf_counter() - prepare_started) * 1000.0,
                )
                if self._optimizer_plan_is_current(prepared):
                    self._performance.inc("optimizer_skipped_same_snapshot")
                    self._performance.inc("optimizer_semantic_snapshot_same")
                    self.runtime_metrics["optimizer_recalc_skipped_same_snapshot"] += 1
                else:
                    self._performance.inc("optimizer_semantic_snapshot_changed")
                    loop = asyncio.get_running_loop()
                    started_at = ha_now()
                    started_clock = loop.time()
                    self._performance.inc("optimizer_started")
                    self.runtime_metrics["optimizer_recalc_started"] += 1
                    self.runtime_metrics["optimizer_recalc_last_started"] = started_at.isoformat()
                    self.runtime_metrics["optimizer_recalc_last_reasons"] = reasons
                    executor = getattr(self.hass, "async_add_executor_job", None)
                    queued_clock = time.perf_counter()
                    if self._performance.active:
                        core_callable = partial(
                            run_core_with_timings,
                            build_plan_bundle,
                            queued_clock=queued_clock,
                        )
                    else:
                        core_callable = build_plan_bundle
                    args = (
                        core_callable,
                        prepared["payload"],
                        prepared["selected_strategy"],
                    )
                    try:
                        timed_result = (
                            await executor(*args)
                            if callable(executor)
                            else await asyncio.to_thread(*args)
                        )
                    except Exception:
                        self._performance.inc("optimizer_failed")
                        raise
                    if (
                        isinstance(timed_result, tuple)
                        and len(timed_result) == 2
                        and isinstance(timed_result[1], dict)
                    ):
                        core_result, worker_timings = timed_result
                        self._performance.observe_ms(
                            "optimizer_executor_queue_wait",
                            worker_timings["queue_wait_ms"],
                        )
                        self._performance.observe_ms(
                            "optimizer_core_wall",
                            worker_timings["wall_ms"],
                        )
                        self._performance.observe_ms(
                            "optimizer_core_thread_cpu",
                            worker_timings["thread_cpu_ms"],
                        )
                    else:
                        # Compatibility with lightweight HA/test executor shims
                        # that return the Core result without calling the worker.
                        core_result = timed_result
                    if self._unloading:
                        return
                    if isinstance(core_result, dict) and core_result.get("budget_exceeded"):
                        self._optimizer_budget_blocked_snapshot_id = prepared["snapshot_id"]
                        self._optimizer_budget_status = {
                            "status": "budget_exceeded",
                            "reason": str(core_result.get("failure_reason") or "operation_budget_exceeded"),
                            "limits": deepcopy(core_result.get("core_budget", {}).get("limits", {})),
                            "usage": deepcopy(core_result.get("core_budget", {}).get("usage", {})),
                        }
                        self._optimizer_generation_reason = "core_budget_exceeded"
                        self.runtime_metrics["optimizer_budget_exceeded"] += 1
                        self._performance.inc("optimizer_budget_exceeded")
                    else:
                        apply_started = time.perf_counter()
                        try:
                            _result, changed = self._apply_prepared_ai_plan(prepared, core_result)
                        except Exception:
                            self._performance.inc("optimizer_failed")
                            raise
                        self._performance.observe_ms(
                            "optimizer_apply_result",
                            (time.perf_counter() - apply_started) * 1000.0,
                        )
                        output_changed = output_changed or changed
                    self._performance.inc("optimizer_completed")
                    self.runtime_metrics["optimizer_recalc_completed"] += 1
                    self.runtime_metrics["optimizer_recalc_last_finished"] = ha_now().isoformat()
                    self.runtime_metrics["optimizer_recalc_last_duration_s"] = round(
                        loop.time() - started_clock,
                        4,
                    )
                if self._optimizer_recalc_pending and not follow_up_used:
                    follow_up_used = True
                    self._performance.inc("optimizer_followup_started")
                    self.runtime_metrics["optimizer_recalc_followup"] += 1
                    continue
                break
        finally:
            self._optimizer_active_recalc = max(0, self._optimizer_active_recalc - 1)
            if self._optimizer_recalc_task is current:
                self._optimizer_recalc_task = None
        if output_changed:
            self.request_sensor_snapshot_refresh({"ai_state"})
        self._notify_entities_from_cache(
            {"diagnostics"},
            reason="optimizer_diagnostics",
        )
        # Do not create an automatic recovery chain after the single controlled
        # follow-up.  A later independent debounce/tick may consume the retained
        # dirty bit and reasons in a fresh bounded cycle.

    def active_slot_key(self) -> str:
        hour = ha_now().hour
        for key, _label, start, end in SLOTS:
            if start <= hour < end:
                return key
        return "23_00"

    @property
    def active_slot(self) -> SlotSettings:
        return self.slots[self.active_slot_key()]

    def state_float(self, entity_id: str | None, default: float = 0) -> float:
        value = self.state_float_or_none(entity_id)
        return default if value is None else value

    def state_float_or_none(self, entity_id: str | None) -> float | None:
        """Return a finite numeric state or None when the source is not trustworthy."""
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable", "none", ""):
            return None
        try:
            value = float(state.state)
        except (TypeError, ValueError):
            return None
        return value if math.isfinite(value) else None

    @staticmethod
    def _timestamp_age_seconds(moment: Any) -> float | None:
        """Return a timezone-safe non-negative age for one HA report timestamp."""
        if not isinstance(moment, datetime):
            return None
        try:
            return max(0.0, (ha_now() - moment).total_seconds())
        except TypeError:
            return None

    @staticmethod
    def _source_health_threshold_seconds(state: Any, fallback: int = 900) -> int:
        """Derive a bounded health TTL from provider metadata when it exists."""
        attributes = getattr(state, "attributes", {}) if state is not None else {}
        for key in (
            "update_interval_seconds",
            "scan_interval_seconds",
            "poll_interval_seconds",
            "update_interval",
            "scan_interval",
        ):
            raw = attributes.get(key) if isinstance(attributes, dict) else None
            if isinstance(raw, timedelta):
                interval = raw.total_seconds()
            else:
                interval = finite_float(raw)
            if interval is not None and interval > 0:
                # Four missed reports is a conservative communication boundary;
                # keep it bounded so bad metadata cannot retain SOC indefinitely.
                return int(max(60, min(3600, interval * 4)))
        return int(fallback)

    def _entity_source_identity(self, entity_id: str | None) -> tuple[str, str] | None:
        """Return a registry-backed source identity, never an entity-name guess."""
        if not entity_id:
            return None
        try:
            from homeassistant.helpers import entity_registry as er  # local HA runtime

            entry = er.async_get(self.hass).async_get(entity_id)
        except (ImportError, AttributeError, KeyError, TypeError):
            entry = None
        if entry is None:
            return None
        device_id = getattr(entry, "device_id", None)
        if device_id:
            return ("device", str(device_id))
        config_entry_id = getattr(entry, "config_entry_id", None)
        if config_entry_id:
            return ("config_entry", str(config_entry_id))
        config_entry_ids = getattr(entry, "config_entry_ids", None)
        if config_entry_ids:
            normalized = ",".join(sorted(str(item) for item in config_entry_ids))
            if normalized:
                return ("config_entries", normalized)
        return None

    def _soc_sibling_entity_ids(self) -> tuple[str, ...]:
        """Return the provider-agnostic measurement cohort eligible for health."""
        return tuple(dict.fromkeys(
            entity_id
            for entity_id in (
                self.battery_bms_voltage_sensor,
                self.battery_current_sensor,
                self.battery_power_sensor,
                self.grid_power_sensor,
                self.pv_power_sensor,
                self.load_power_sensor,
            )
            if entity_id and entity_id != self.battery_soc_sensor
        ))

    def _verified_soc_sibling(self, entity_id: str | None) -> bool:
        """Accept health only from the exact SOC device/config-entry identity."""
        soc_identity = self._entity_source_identity(self.battery_soc_sensor)
        sibling_identity = self._entity_source_identity(entity_id)
        return soc_identity is not None and sibling_identity == soc_identity

    def _soc_sibling_health(self) -> dict[str, Any] | None:
        """Return the newest verified sibling report, independent of its value."""
        candidates: list[dict[str, Any]] = []
        for entity_id in self._soc_sibling_entity_ids():
            if not self._verified_soc_sibling(entity_id):
                continue
            state = self.hass.states.get(entity_id)
            if state is None or str(state.state).strip().lower() in {
                "unknown", "unavailable", "none", "",
            }:
                continue
            reported = getattr(state, "last_reported", None)
            observed = self._soc_source_observed_at.get(entity_id)
            updated = getattr(state, "last_updated", None)
            timestamps = [
                item for item in (reported, observed, updated) if isinstance(item, datetime)
            ]
            if not timestamps:
                continue
            moment = max(timestamps)
            candidates.append({
                "entity_id": entity_id,
                "at": moment,
                "age_seconds": self._timestamp_age_seconds(moment),
                "threshold_seconds": self._source_health_threshold_seconds(state),
            })
        return max(candidates, key=lambda item: item["at"]) if candidates else None

    def _observe_soc_sibling_event(self, event: Any) -> bool:
        """Record one verified sibling report and detect a SOC quality transition."""
        event_data = getattr(event, "data", event if isinstance(event, dict) else {})
        entity_id = str(event_data.get("entity_id") or "")
        if not self._verified_soc_sibling(entity_id):
            return False
        state = event_data.get("new_state") or self.hass.states.get(entity_id)
        moment = getattr(state, "last_reported", None) if state is not None else None
        if not isinstance(moment, datetime):
            moment = getattr(event, "time_fired", None)
        if not isinstance(moment, datetime):
            moment = ha_now()
        self._soc_source_observed_at[entity_id] = moment
        return self._refresh_soc_quality_signature()

    def soc_diagnostics(self, stale_after_seconds: int = 900) -> dict[str, Any]:
        """Return SOC value plus independent, provider-agnostic source health."""
        entity_id = self.battery_soc_sensor
        state = self.hass.states.get(entity_id) if entity_id else None
        raw_value = state.state if state is not None else None
        updated = getattr(state, "last_updated", None) if state is not None else None
        reported = getattr(state, "last_reported", None) if state is not None else None
        changed = getattr(state, "last_changed", None) if state is not None else None
        observed = (
            self._soc_observed_at
            if entity_id and self._soc_observed_entity_id == entity_id
            else None
        )
        reported_age = self._timestamp_age_seconds(reported)
        own_threshold = self._source_health_threshold_seconds(state, stale_after_seconds)
        sibling = self._soc_sibling_health()
        compatibility_at = observed if isinstance(observed, datetime) else updated
        compatibility_age = self._timestamp_age_seconds(compatibility_at)

        health_at: datetime | None = None
        health_source = "unavailable"
        freshness_reason = "no_fresh_source_health"
        effective_threshold = own_threshold
        if reported_age is not None and reported_age <= own_threshold:
            health_at = reported
            health_source = "own_soc_report"
            freshness_reason = "own_soc_report"
        elif sibling is not None and sibling.get("age_seconds") is not None and (
            sibling["age_seconds"] <= sibling["threshold_seconds"]
        ):
            health_at = sibling["at"]
            health_source = f"sibling_health:{sibling['entity_id']}"
            freshness_reason = "sibling_health"
            effective_threshold = int(sibling["threshold_seconds"])
        elif compatibility_age is not None and compatibility_age <= stale_after_seconds:
            health_at = compatibility_at
            health_source = (
                "event_observed_at" if isinstance(observed, datetime) else "last_updated_fallback"
            )
            freshness_reason = "compatibility_fallback"
            effective_threshold = int(stale_after_seconds)
        else:
            stale_candidates: list[tuple[datetime, str, int]] = []
            if isinstance(reported, datetime):
                stale_candidates.append((reported, "own_soc_report", own_threshold))
            if sibling is not None and isinstance(sibling.get("at"), datetime):
                stale_candidates.append((
                    sibling["at"],
                    f"sibling_health:{sibling['entity_id']}",
                    int(sibling["threshold_seconds"]),
                ))
            if isinstance(compatibility_at, datetime):
                stale_candidates.append((compatibility_at, "compatibility_fallback", stale_after_seconds))
            if stale_candidates:
                health_at, health_source, effective_threshold = max(
                    stale_candidates, key=lambda item: item[0]
                )

        age_seconds = self._timestamp_age_seconds(health_at)

        normalized: float | None = None
        reason: str | None = None
        if not entity_id:
            status, reason = "not_configured", "Nie skonfigurowano encji SOC"
        elif state is None:
            status, reason = "unavailable", "Encja SOC nie istnieje w bieżącym stanie HA"
        elif str(raw_value).strip().lower() in {"", "unknown", "unavailable", "none"}:
            status = str(raw_value).strip().lower() or "unknown"
            reason = f"Encja SOC ma stan {status}"
        else:
            try:
                value = float(raw_value)
            except (TypeError, ValueError):
                value = float("nan")
            if not math.isfinite(value):
                status, reason = "invalid", "SOC nie jest skończoną liczbą"
            elif not 0.0 <= value <= 100.0:
                status, reason = "out_of_range", "SOC musi mieścić się w zakresie 0–100%"
            elif health_at is None or age_seconds is None or age_seconds > effective_threshold:
                status = "stale"
                reason = (
                    "Brak świeżego, wiarygodnego health źródła SOC"
                    if age_seconds is None
                    else f"Health źródła SOC jest starszy niż {effective_threshold} s "
                    f"({round(age_seconds)} s)"
                )
            else:
                status = "valid"
                normalized = value

        valid = status == "valid"
        return {
            "source_entity": entity_id,
            "entity_id": entity_id,
            "raw_value": raw_value,
            "normalized_value": normalized,
            "value": normalized,
            "unit": str(state.attributes.get("unit_of_measurement") or "") if state else None,
            "status": status,
            "valid": valid,
            "reason": reason,
            "last_updated": updated.isoformat() if isinstance(updated, datetime) else None,
            "last_reported": reported.isoformat() if isinstance(reported, datetime) else None,
            "reported_at": reported.isoformat() if isinstance(reported, datetime) else None,
            "soc_reported_at": reported.isoformat() if isinstance(reported, datetime) else None,
            "soc_report_age_seconds": round(reported_age, 1) if reported_age is not None else None,
            "observed_at": observed.isoformat() if isinstance(observed, datetime) else None,
            "value_changed_at": (
                changed.isoformat()
                if isinstance(changed, datetime)
                else updated.isoformat() if isinstance(updated, datetime) else None
            ),
            # Preserve the 5G.4F public field while exposing the richer 5G.4I
            # source class separately.
            "freshness_source": (
                "last_reported"
                if freshness_reason == "own_soc_report"
                else "event_observed_at"
                if health_source == "event_observed_at"
                else "last_updated_fallback"
                if health_source == "last_updated_fallback"
                else health_source
            ),
            "source_health_source": health_source,
            "source_health_at": health_at.isoformat() if isinstance(health_at, datetime) else None,
            "source_health_age_seconds": round(age_seconds, 1) if age_seconds is not None else None,
            "effective_soc_freshness_at": health_at.isoformat() if isinstance(health_at, datetime) else None,
            "effective_soc_age_seconds": round(age_seconds, 1) if age_seconds is not None else None,
            "freshness_reason": freshness_reason,
            "age_seconds": round(age_seconds, 1) if age_seconds is not None else None,
            "stale_after_seconds": effective_threshold,
            "effective_threshold_seconds": effective_threshold,
            "quality": "good" if valid else "degraded" if status == "stale" else "unavailable",
            "source": "primary" if valid else "unavailable",
        }

    def current_soc_or_none(self) -> float | None:
        """Return a fresh, finite SOC in the physical 0–100% range."""
        return self.soc_diagnostics().get("normalized_value")

    @staticmethod
    def _soc_semantic_signature(diagnostics: dict[str, Any]) -> tuple[str, float | None]:
        """Return only material SOC state, never a report timestamp."""
        value = finite_float(diagnostics.get("normalized_value"))
        return (
            str(diagnostics.get("status") or "unknown"),
            round(value, 6) if value is not None else None,
        )

    def _refresh_soc_quality_signature(self) -> bool:
        """Remember SOC quality and report whether its semantics changed."""
        current = self._soc_semantic_signature(self.soc_diagnostics())
        previous = self._soc_quality_signature
        self._soc_quality_signature = current
        return previous is not None and previous != current

    def _observe_soc_source_event(self, event: Any) -> bool:
        """Record one real SOC source event without making it a Core input."""
        event_data = getattr(event, "data", event if isinstance(event, dict) else {})
        entity_id = str(event_data.get("entity_id") or self.battery_soc_sensor or "")
        state = event_data.get("new_state") or (
            self.hass.states.get(entity_id) if entity_id else None
        )
        event_time = getattr(state, "last_reported", None) if state is not None else None
        if not isinstance(event_time, datetime):
            event_time = getattr(event, "time_fired", None)
        if not isinstance(event_time, datetime):
            # Reaching this callback is itself evidence of a real source event.
            event_time = ha_now()
        self._soc_observed_entity_id = entity_id or None
        self._soc_observed_at = event_time
        return self._refresh_soc_quality_signature()

    @staticmethod
    def _state_event_is_report_only(event_data: dict[str, Any]) -> bool:
        """Return true when a complete HA event carries no value/attribute change."""
        old_state = event_data.get("old_state")
        new_state = event_data.get("new_state")
        return bool(
            old_state is not None
            and new_state is not None
            and getattr(old_state, "state", None) == getattr(new_state, "state", None)
            and getattr(old_state, "attributes", {}) == getattr(new_state, "attributes", {})
        )

    def _measurement(
        self,
        entity_id: str | None,
        *,
        kind: str = "power",
        stale_after_seconds: int = 900,
    ) -> dict[str, Any]:
        """Describe one source, normalized to W or kWh, without a zero fallback."""
        state = self.hass.states.get(entity_id) if entity_id else None
        unit = str(state.attributes.get("unit_of_measurement") or "") if state is not None else ""
        assumed_unit = unit or ("W" if kind == "power" else "kWh" if kind == "energy" else "")
        value = (
            power_w(state.state, assumed_unit)
            if state is not None and kind == "power"
            else energy_kwh(state.state, assumed_unit)
            if state is not None and kind == "energy"
            else finite_float(state.state) if state is not None else None
        )
        updated = getattr(state, "last_updated", None) if state is not None else None
        stale = False
        if isinstance(updated, datetime):
            try:
                stale = (ha_now() - updated).total_seconds() > stale_after_seconds
            except TypeError:
                stale = False
        status = "not_configured" if not entity_id else "missing" if state is None else "invalid_unit" if value is None and state.state not in ("unknown", "unavailable", "none", "") else "unavailable" if value is None else "stale" if stale else "ok"
        return {
            "entity_id": entity_id,
            "value": value,
            "unit": unit or (assumed_unit if state is not None else None),
            "unit_assumed": bool(state is not None and not unit and assumed_unit),
            "last_updated": updated.isoformat() if isinstance(updated, datetime) else None,
            "status": status,
            "quality": "good" if status == "ok" else "unavailable" if status in ("not_configured", "missing", "unavailable") else "degraded",
            "source": "primary",
        }

    def load_power_reading(self) -> dict[str, Any]:
        """Resolve total LOAD once, keeping phase measurements as details only."""
        primary = self._measurement(self.load_power_sensor)
        phases = [
            self._measurement(self.load_l1_power_sensor),
            self._measurement(self.load_l2_power_sensor),
            self._measurement(self.load_l3_power_sensor),
        ]
        phase_values = [item.get("value") for item in phases]
        complete_phases = all(value is not None for value in phase_values)
        phase_sum = sum(float(value) for value in phase_values) if complete_phases else None

        if primary["value"] is not None and primary["status"] != "stale":
            result = dict(primary)
            if phase_sum is not None:
                denominator = max(100.0, abs(float(primary["value"])), abs(phase_sum))
                mismatch = abs(float(primary["value"]) - phase_sum) / denominator
                result["phase_sum_w"] = round(phase_sum, 3)
                result["phase_mismatch_percent"] = round(mismatch * 100, 1)
                if mismatch > 0.15:
                    result.update(status="inconsistent", quality="degraded")
            result["phases"] = phases
            self.data_quality["load_power"] = result
            return result

        if complete_phases:
            result = {
                "entity_id": " + ".join(item.get("entity_id") or "?" for item in phases),
                "value": phase_sum,
                "unit": "W",
                "last_updated": max((item.get("last_updated") or "" for item in phases), default="") or None,
                "status": "fallback",
                "quality": "degraded",
                "source": "load_phases",
                "fallback_reason": f"Load Power: {primary['status']}",
                "phases": phases,
                "phase_sum_w": round(phase_sum, 3),
            }
            self.data_quality["load_power"] = result
            return result

        # Emergency balance uses the same sign conventions as the planner:
        # load = PV + grid import + battery discharge.
        pv = self._measurement(self.pv_power_sensor)
        grid_value = self.normalized_grid_power() if self.entity_available(self.grid_power_sensor) else None
        battery_value = self.battery_power_reading().get("value")
        if pv["value"] is not None and grid_value is not None and battery_value is not None:
            result = {
                "entity_id": None,
                "value": max(0.0, float(pv["value"]) + float(grid_value) + float(battery_value)),
                "unit": "W",
                "last_updated": None,
                "status": "emergency_fallback",
                "quality": "low",
                "source": "energy_balance",
                "fallback_reason": f"Load Power: {primary['status']}; niepełne fazy",
                "phases": phases,
            }
            self.data_quality["load_power"] = result
            return result

        result = {
            **primary,
            "value": None,
            "source": "unavailable",
            "quality": "unavailable",
            "phases": phases,
        }
        self.data_quality["load_power"] = result
        return result

    def battery_power_reading(self) -> dict[str, Any]:
        """Prefer direct battery power; use V×A only as a marked fallback."""
        direct = self._measurement(self.battery_power_sensor)
        if direct["value"] is not None and direct["status"] != "stale":
            value = float(direct["value"])
            if not bool(self.data.get(CONF_BATTERY_POSITIVE_IS_DISCHARGE, DEFAULT_BATTERY_POSITIVE_IS_DISCHARGE)):
                value = -value
            result = {**direct, "value": value}
            self.data_quality["battery_power"] = result
            return result
        voltage = self._measurement(self.battery_bms_voltage_sensor, kind="raw")
        current = self._measurement(self.battery_current_sensor, kind="raw")
        if voltage["value"] is not None and current["value"] is not None:
            value = float(voltage["value"]) * float(current["value"])
            if not bool(self.data.get(CONF_BATTERY_POSITIVE_IS_DISCHARGE, DEFAULT_BATTERY_POSITIVE_IS_DISCHARGE)):
                value = -value
            result = {
                "entity_id": f"{self.battery_bms_voltage_sensor} × {self.battery_current_sensor}",
                "value": value,
                "unit": "W",
                "last_updated": None,
                "status": "fallback",
                "quality": "degraded",
                "source": "voltage_times_current",
                "fallback_reason": f"Battery Power: {direct['status']}",
            }
            self.data_quality["battery_power"] = result
            return result
        result = {**direct, "value": None, "source": "unavailable", "quality": "unavailable"}
        self.data_quality["battery_power"] = result
        return result

    def grid_power_reading(self) -> dict[str, Any]:
        """Resolve signed grid power and reject a misleading Solarman total."""
        positive_is_import = bool(
            self.data.get(CONF_GRID_POSITIVE_IS_IMPORT, DEFAULT_GRID_POSITIVE_IS_IMPORT)
        )

        def signed(reading: dict[str, Any]) -> dict[str, Any]:
            result = dict(reading)
            if result.get("value") is not None:
                value = float(result["value"])
                result["value"] = value if positive_is_import else -value
            return result

        primary = signed(self._measurement(self.grid_power_sensor))
        phases = [
            signed(self._measurement(self.grid_l1_power_sensor)),
            signed(self._measurement(self.grid_l2_power_sensor)),
            signed(self._measurement(self.grid_l3_power_sensor)),
        ]
        phase_values = [item.get("value") for item in phases]
        complete_phases = all(value is not None for value in phase_values)
        phase_sum = sum(float(value) for value in phase_values) if complete_phases else None

        if primary.get("value") is not None and primary.get("status") != "stale":
            result = dict(primary)
            result["phases"] = phases
            if phase_sum is not None:
                denominator = max(100.0, abs(float(primary["value"])), abs(phase_sum))
                mismatch = abs(float(primary["value"]) - phase_sum) / denominator
                result["phase_sum_w"] = round(phase_sum, 3)
                result["phase_mismatch_percent"] = round(mismatch * 100, 1)
                if self.inverter_provider == PROVIDER_SOLARMAN and mismatch > 0.15:
                    result.update(
                        value=phase_sum,
                        source="grid_phases",
                        status="fallback",
                        quality="degraded",
                        fallback_reason="Solarman: całkowita moc sieci nie zgadza się z sumą L1-L3",
                    )
                elif mismatch > 0.15:
                    result.update(status="inconsistent", quality="degraded")
            self.data_quality["grid_power"] = result
            return result

        if complete_phases:
            result = {
                "entity_id": " + ".join(item.get("entity_id") or "?" for item in phases),
                "value": phase_sum,
                "unit": "W",
                "last_updated": max((item.get("last_updated") or "" for item in phases), default="") or None,
                "status": "fallback",
                "quality": "degraded",
                "source": "grid_phases",
                "fallback_reason": f"Grid Power: {primary.get('status')}",
                "phases": phases,
                "phase_sum_w": round(float(phase_sum), 3),
            }
            self.data_quality["grid_power"] = result
            return result

        result = {
            **primary,
            "value": None,
            "source": "unavailable",
            "quality": "unavailable",
            "phases": phases,
        }
        self.data_quality["grid_power"] = result
        return result

    def daily_energy_value(self, entity_id: str | None) -> float:
        """Return an energy entity in kWh, including Wh/MWh source units."""
        value = self._measurement(entity_id, kind="energy").get("value")
        return max(0.0, float(value)) if value is not None else 0.0

    def source_quality_context(self) -> dict[str, Any]:
        """Return the exact source/fallback status consumed by learning."""
        load = self.load_power_reading()
        battery = self.battery_power_reading()
        sources = {
            "load_power": load,
            "battery_power": battery,
            "pv_power": self._measurement(self.pv_power_sensor),
            "grid_power": self.grid_power_reading(),
            "battery_soc": self.soc_diagnostics(),
        }
        score_map = {"good": 100, "degraded": 70, "low": 40, "unavailable": 0}
        quality_values = [score_map.get(str(item.get("quality")), 0) for item in sources.values()]
        return {
            "schema_version": HISTORY_SCHEMA_VERSION,
            "score": round(sum(quality_values) / len(quality_values)) if quality_values else 0,
            "sources": sources,
            "fallback_in_use": any(item.get("source") not in ("primary", "unavailable") for item in sources.values()),
        }

    def _telemetry_readings(self) -> dict[str, dict[str, Any]]:
        """Return independent live channels without replacing missing values by zero."""
        load = self.load_power_reading()
        battery = self.battery_power_reading()
        grid = self.grid_power_reading()
        return {
            "pv": self._measurement(self.pv_power_sensor),
            "load": load,
            "load_l1": self._measurement(self.load_l1_power_sensor),
            "load_l2": self._measurement(self.load_l2_power_sensor),
            "load_l3": self._measurement(self.load_l3_power_sensor),
            "grid": grid,
            "battery": battery,
            "soc": self.soc_diagnostics(),
            "sell_price": self._measurement(self.price_sensor, kind="raw"),
            "buy_price": self._measurement(self.buy_price_today_sensor, kind="raw"),
        }

    def live_state_context(
        self,
        readings: dict[str, dict[str, Any]] | None = None,
        moment: datetime | None = None,
    ) -> dict[str, Any]:
        """Build the current measured state consumed by Optimizer Core."""
        current = moment or ha_now()
        values = readings or self._telemetry_readings()

        def value(name: str) -> float | None:
            item = values.get(name, {})
            raw = item.get("value") if isinstance(item, dict) else None
            return float(raw) if raw is not None else None

        grid = value("grid")
        battery = value("battery")
        slot = self.active_slot
        return {
            "timestamp": current.isoformat(timespec="seconds"),
            "soc_pct": value("soc"),
            "pv_power_w": value("pv"),
            "home_power_w": value("load"),
            "grid_power_w": grid,
            "grid_direction": (
                "import" if grid is not None and grid > 0
                else "export" if grid is not None and grid < 0
                else "idle" if grid is not None
                else "unknown"
            ),
            "battery_power_w": battery,
            "battery_direction": (
                "discharge" if battery is not None and battery > 0
                else "charge" if battery is not None and battery < 0
                else "idle" if battery is not None
                else "unknown"
            ),
            "sell_price": value("sell_price"),
            "buy_price": value("buy_price"),
            "active_mode": slot.mode if slot.enabled else MODE_NORMAL_OPERATION,
            "active_power_w": max(0.0, float(slot.sell_power or 0.0)),
            "slot_key": slot.key,
            "channels": {
                name: {
                    "status": item.get("status"),
                    "quality": item.get("quality"),
                    "source": item.get("source"),
                    "last_updated": item.get("last_updated"),
                    "usable": item.get("value") is not None,
                }
                for name, item in values.items()
                if isinstance(item, dict)
            },
        }

    @staticmethod
    def _material_deviation_bucket(
        actual_power_w: Any,
        expected_kwh: Any,
    ) -> float | None:
        """Quantize live-vs-hourly forecast deviation for semantic recalc."""

        actual = finite_float(actual_power_w)
        expected = finite_float(expected_kwh)
        if actual is None or expected is None:
            return None
        reference_w = max(LIVE_DEVIATION_REFERENCE_FLOOR_W, abs(expected) * 1000.0)
        ratio = (actual - expected * 1000.0) / reference_w
        if abs(ratio) < LIVE_DEVIATION_BUCKET_RATIO:
            return 0.0
        bucket = round(ratio / LIVE_DEVIATION_BUCKET_RATIO) * LIVE_DEVIATION_BUCKET_RATIO
        return round(max(-4.0, min(4.0, bucket)), 2)

    def current_hour_partial_context(self) -> dict[str, Any]:
        """Return energy already observed in the open hour plus its quality."""
        tracking = self.learning_tracking if isinstance(self.learning_tracking, dict) else {}
        now = ha_now()
        elapsed_minutes = max(0, min(60, now.minute))
        channels = tracking.get("channels") if isinstance(tracking.get("channels"), dict) else {}
        summaries = {
            name: channel_summary(item, expected_seconds=max(60.0, elapsed_minutes * 60.0))
            for name, item in channels.items()
            if isinstance(item, dict)
        }

        def observed(field: str, channel: str) -> float | None:
            if int(summaries.get(channel, {}).get("valid_samples", 0)) <= 0:
                return None
            return round(self.safe_float(tracking.get(field), 0), 5)

        return {
            "hour": tracking.get("hour"),
            "elapsed_minutes": elapsed_minutes,
            "remaining_minutes": max(0, 60 - elapsed_minutes),
            "pv_kwh": observed("pv_kwh", "pv"),
            "load_kwh": observed("load_kwh", "load"),
            "grid_import_kwh": observed("grid_import_kwh", "grid"),
            "grid_export_kwh": observed("grid_export_kwh", "grid"),
            "battery_charge_kwh": observed("battery_charge_kwh", "battery"),
            "battery_discharge_kwh": observed("battery_discharge_kwh", "battery"),
            "soc_start_pct": tracking.get("soc_start"),
            "soc_current_pct": (
                tracking.get("soc_last", tracking.get("soc_start"))
                if int(summaries.get("soc", {}).get("valid_samples", 0)) > 0
                else None
            ),
            "channels": summaries,
        }

    def entity_available(self, entity_id: str | None) -> bool:
        if not entity_id:
            return False
        state = self.hass.states.get(entity_id)
        return state is not None and state.state not in ("unknown", "unavailable", "none", "")

    def state_text(self, entity_id: str | None) -> str:
        if not entity_id:
            return "unknown"
        state = self.hass.states.get(entity_id)
        return state.state if state is not None else "unknown"

    @property
    def data_available(self) -> bool:
        """Check only entities required to write a complete Deye control plan.

        SOC and price are conditions of Selling First, not a global data
        interlock.  A Zero Export slot must therefore remain executable when
        price data is absent.
        """
        if not provider_profile(self.data).basic_control:
            return False
        required = [
            self.work_mode_select,
            self.max_sell_power_number,
            self.discharge_current_number,
            self.charge_current_number,
            self.grid_charge_current_number,
        ]
        if provider_profile(self.data).needs_aux_export_switch:
            required.append(self.work_mode_aux_entity)
        return all(self.entity_available(entity_id) for entity_id in required)

    @property
    def required_entities_complete(self) -> bool:
        """Check that all entities required for full integration mapping are available.

        Unlike ``data_available`` this includes the battery SOC sensor, which is
        mandatory for complete operation and safe Selling First guards even
        though Zero Export slots can execute without it.
        """
        if not provider_profile(self.data).basic_control:
            return False
        required = [
            self.work_mode_select,
            self.max_sell_power_number,
            self.discharge_current_number,
            self.charge_current_number,
            self.grid_charge_current_number,
            self.battery_soc_sensor,
        ]
        if provider_profile(self.data).needs_aux_export_switch:
            required.append(self.work_mode_aux_entity)
        return all(self.entity_available(entity_id) for entity_id in required)

    @property
    def mapping_error(self) -> bool:
        return len(self._tou_mapping) > 6

    @property
    def next_active_slot(self) -> str:
        keys = [key for key, *_rest in SLOTS]
        current_index = keys.index(self.active_slot_key())
        for offset in range(1, len(keys) + 1):
            key, label, *_rest = SLOTS[(current_index + offset) % len(SLOTS)]
            if self.slots[key].enabled:
                return label
        return "NONE"

    @property
    def decision_reason(self) -> str:
        status = self.manager_status
        if status == "BŁĄD MAPOWANIA":
            return f"Mapowanie wymaga {len(self._tou_mapping)} zakresów; Deye obsługuje 6"
        if status == "BRAK DANYCH":
            return "Brak wymaganych danych lub encji sterujących falownikiem"
        if status == "SPRZEDAŻ ZABLOKOWANA":
            issue = self._selling_slot_guard_issue()
            return issue[1] if issue else "Sprzedaż wstrzymana przez warunek aktywnego slotu"
        if status == "CENA ZA NISKA":
            price = self.state_float(self.price_sensor, 0)
            return f"Cena {price:.2f} PLN/kWh jest niższa od progu {self.active_min_sell_price:.2f} PLN/kWh"
        if status == "SOC ZA NISKIE":
            soc = self.state_float(self.battery_soc_sensor, 0)
            return f"SOC {soc:.0f}% osiągnął lub jest niższy od limitu {self.active_min_sell_soc:.0f}%"
        reasons = {
            "SLOT WYŁĄCZONY": "Bieżący slot jest wyłączony; obowiązują ustawienia domyślne",
            "HARMONOGRAM WYŁĄCZONY": "Harmonogram jest wyłączony; manager oczekuje",
            "WSTRZYMANA SPRZEDAŻ": "Sterowanie zatrzymane; obowiązują ustawienia domyślne",
            "ZATRZYMANIE AWARYJNE": "Aktywne zatrzymanie awaryjne",
            "OCHRONA BATERII": "Aktywna ochrona baterii",
            "SPRZEDAŻ RĘCZNA": "Aktywny ręczny tryb sprzedaży",
            "ŁADOWANIE BATERII": "Aktywne ręczne ładowanie baterii",
            "ŁADOWANIE Z SIECI": "Ładowanie z sieci według harmonogramu",
            "ŁADOWANIE Z PV": "Ładowanie z PV według harmonogramu",
            "SPRZEDAŻ AKTYWNA": "Warunki sprzedaży są spełnione",
            "NORMALNA PRACA (CT)": "Aktywny tryb Normalna Praca — Deye: Zero Export To CT",
            "NORMALNA PRACA (LOAD)": "Aktywny tryb Normalna Praca — Deye: Zero Export To Load",
            "OCZEKIWANIE": "Manager oczekuje na zmianę warunków lub kolejny slot",
        }
        return reasons.get(status, status)

    def mark_settings_applied(self) -> None:
        self.last_applied_at = ha_now().isoformat(timespec="seconds")

    def mark_config_saved(self) -> None:
        self.last_saved_at = ha_now().isoformat(timespec="seconds")
        if self._ai_store is not None:
            self.request_ai_save()
        self.notify_update()

    def _tou_entities(self) -> list[tuple[str, str]]:
        entities: list[tuple[str, str]] = []
        for idx in range(1, 7):
            entities.extend([
                (f"TOU {idx} — start", self._tou_entity(idx, "start")),
                (f"TOU {idx} — minimalny SOC", self._tou_entity(idx, "soc")),
                (f"TOU {idx} — ładowanie z sieci", self._tou_entity(idx, "grid")),
            ])
        return entities

    def tou_mapping_diagnostics(self) -> dict[str, Any]:
        entities = [
            {"label": label, "entity_id": entity_id, "ok": self.entity_available(entity_id)}
            for label, entity_id in self._tou_entities()
        ]
        missing = [item["entity_id"] for item in entities if not item["ok"]]
        item = provider_profile(self.data)
        return {
            "ok": bool(item.native_tou and not missing),
            "supported": item.native_tou,
            "provider": self.inverter_provider,
            "provider_label": item.label,
            "native_tou": item.native_tou,
            "note": item.notes,
            "missing": missing,
            "entities": entities,
        }

    def _tou_field_actual_value(self, entity_id: str | None, field_name: str) -> Any:
        """Return a normalized TOU value without losing the raw HA state."""
        if not self.entity_available(entity_id):
            return None
        raw = self.state_text(entity_id)
        if field_name in ("start", "end"):
            minutes = self._time_to_minutes(raw)
            return None if minutes is None else f"{minutes // 60:02d}:{minutes % 60:02d}"
        if field_name == "soc":
            value = self.safe_float(raw, float("nan"))
            return value if math.isfinite(value) else None
        if field_name == "grid_charge":
            return provider_boolean_state(self.data, "grid", raw)
        return raw

    def _tou_field_capability(
        self,
        slot_index: int,
        field_name: str,
        entity_id: str | None,
    ) -> dict[str, Any]:
        """Build one runtime capability entry for a physical TOU field."""
        declared = provider_tou_field_capabilities(self.inverter_provider).get(
            field_name, {"supported": False, "domains": (), "per_slot": False}
        )
        domain = str(entity_id or "").split(".", 1)[0] if entity_id else ""
        allowed_domains = tuple(declared.get("domains", ()))
        configured = bool(entity_id)
        domain_supported = bool(domain and domain in allowed_domains)
        state = self.hass.states.get(entity_id) if entity_id else None
        current_available = bool(
            state is not None
            and str(state.state).strip().casefold()
            not in ("unknown", "unavailable", "none", "")
        )
        supported = bool(declared.get("supported") and configured and domain_supported)
        read_only = bool(declared.get("read_only", False))
        readable = bool(supported and current_available)
        writable = bool(supported and current_available and not read_only)
        blocked_by_master = not self._control_is_active()
        blocked_by_pending = bool(self.tou_write_pending)
        return {
            "slot_index": slot_index,
            "field": field_name,
            "entity_id": entity_id or None,
            "domain": domain or None,
            "supported": supported,
            "configured": configured,
            "domain_supported": domain_supported,
            "readable": readable,
            "writable": writable,
            "current_available": current_available,
            "read_only": read_only,
            "service_kind": operation_for_entity(entity_id, field_name),
            "write_method": operation_for_entity(entity_id, field_name),
            "blocked_by_master_control": blocked_by_master,
            "blocked_by_tou_pending": blocked_by_pending,
            "control_writable": bool(
                writable and not blocked_by_master and not blocked_by_pending
            ),
            "actual": self._tou_field_actual_value(entity_id, field_name),
            "raw_actual": None if state is None else str(state.state),
        }

    def tou_slot_capabilities(self) -> list[dict[str, Any]]:
        """Return the authoritative per-slot physical TOU capability matrix."""
        profile = provider_profile(self.data)
        rows: list[dict[str, Any]] = []
        for slot_index in range(1, 7):
            next_slot = 1 if slot_index == 6 else slot_index + 1
            entity_ids = {
                "start": self._tou_entity(slot_index, "start"),
                "end": self._tou_entity(next_slot, "start"),
                "soc": self._tou_entity(slot_index, "soc"),
                "grid_charge": self._tou_entity(slot_index, "grid"),
                "out_power": None,
                "charge_current": None,
                "discharge_current": None,
            }
            fields = {
                field_name: self._tou_field_capability(
                    slot_index, field_name, entity_id
                )
                for field_name, entity_id in entity_ids.items()
            }
            rows.append(
                {
                    "slot_index": slot_index,
                    "provider": self.inverter_provider,
                    "provider_label": profile.label,
                    "read_only": not profile.native_tou,
                    "supports_start": fields["start"]["supported"],
                    "supports_end_as_next_start": fields["end"]["supported"],
                    "supports_soc": fields["soc"]["supported"],
                    "supports_grid_charge": fields["grid_charge"]["supported"],
                    "supports_out_power": False,
                    "supports_charge_current": False,
                    "supports_discharge_current": False,
                    "blocked_by_master_control": not self._control_is_active(),
                    "control_writable": bool(
                        self._control_is_active()
                        and not self.tou_write_pending
                        and any(field["writable"] for field in fields.values())
                    ),
                    "fields": fields,
                }
            )
        return rows

    def provider_capabilities(self) -> dict[str, Any]:
        """Return an explicit, read-only capability matrix for this mapping."""
        item = provider_profile(self.data)
        entities = {
            "work_mode": self.work_mode_select,
            "sell_power": self.max_sell_power_number,
            "discharge_current": self.discharge_current_number,
            "charge_current": self.charge_current_number,
            "grid_charge_current": self.grid_charge_current_number,
            "soc": self.battery_soc_sensor,
            "grid_power": self.grid_power_sensor,
            "pv_power": self.pv_power_sensor,
            "load_power": self.load_power_sensor,
            "battery_power": self.battery_power_sensor,
            "sell_price": self.price_sensor,
            "solcast_today": self.solcast_forecast_today_sensor,
        }
        for idx in range(1, 7):
            for kind in ("start", "soc", "grid"):
                entities[f"tou_{idx}_{kind}"] = self._tou_entity(idx, kind)

        groups: dict[str, tuple[str, ...]] = {
            "readings": ("soc", "grid_power", "pv_power", "load_power", "battery_power"),
            "basic_control": ("work_mode", "sell_power", "discharge_current", "charge_current", "grid_charge_current"),
            "selling": ("work_mode", "sell_power", "discharge_current", "soc"),
            "charging": ("work_mode", "charge_current", "grid_charge_current", "soc"),
            "full_tou": tuple(
                f"tou_{idx}_{kind}" for idx in range(1, 7) for kind in ("start", "soc", "grid")
            ),
            "core_ai": ("soc", "grid_power", "pv_power", "load_power", "battery_power", "sell_price", "solcast_today"),
        }
        result: dict[str, Any] = {}
        for name, keys in groups.items():
            supported = item.basic_control if name in ("basic_control", "selling", "charging") else True
            if name == "full_tou":
                supported = item.native_tou
            missing = [key for key in keys if not self.entity_available(entities.get(key))]
            result[name] = {
                "ok": bool(supported and not missing),
                "supported": supported,
                "missing": missing,
            }
        result["provider"] = {
            "key": self.inverter_provider,
            "label": item.label,
            "note": item.notes,
        }
        result["operations"] = {
            key: {
                "entity_id": entity_id or "not_configured",
                "operation": operation_for_entity(entity_id, key),
            }
            for key, entity_id in entities.items()
        }
        result["physical_tou_slots"] = self.tou_slot_capabilities()
        return result

    def control_values_snapshot(self) -> dict[str, str]:
        ids = {
            "System Work Mode": self.work_mode_select,
            "Max Sell Power": self.max_sell_power_number,
            "Prąd rozładowania": self.discharge_current_number,
            "Prąd ładowania baterii": self.charge_current_number,
            "Prąd ładowania z sieci": self.grid_charge_current_number,
        }
        return {label: self.state_text(entity_id) if entity_id else "nie skonfigurowano" for label, entity_id in ids.items()}

    def physical_tou_snapshot(self) -> list[dict[str, Any]]:
        """Describe expected and actually reported values of all six Deye ranges."""
        mapping = self._tou_mapping
        segments = mapping.slots
        current_hour = ha_now().hour
        rows: list[dict[str, Any]] = []
        capability_rows = self.tou_slot_capabilities()

        def minute_of_day(value: str) -> int | None:
            try:
                hour, minute = str(value)[:5].split(":", 1)
                return int(hour) * 60 + int(minute)
            except (TypeError, ValueError):
                return None

        current_minute = ha_now().hour * 60 + ha_now().minute
        for idx in range(1, 7):
            segment = segments[idx - 1] if idx <= len(segments) else None
            expected_start = (
                f"{int(segment.start):02d}:00" if segment is not None else None
            )
            expected_end = None
            active = False
            if segment is not None:
                end_hour = 24 if int(segment.end) == 0 else int(segment.end)
                expected_end = f"{end_hour % 24:02d}:00"
                active = int(segment.start) <= current_hour < end_hour
            capabilities = capability_rows[idx - 1]
            field_caps = capabilities["fields"]
            actual_start = field_caps["start"]["actual"]
            actual_end = field_caps["end"]["actual"]
            start_minute = minute_of_day(actual_start)
            end_minute = minute_of_day(actual_end)
            actual_active = False
            if start_minute is not None and end_minute is not None:
                actual_active = (
                    start_minute <= current_minute < end_minute
                    if start_minute < end_minute
                    else current_minute >= start_minute or current_minute < end_minute
                )
            soc_state = field_caps["soc"]["raw_actual"]
            grid_state = field_caps["grid_charge"]["raw_actual"]
            readable = bool(
                actual_start is not None
                and actual_end is not None
                and field_caps["soc"]["readable"]
                and field_caps["grid_charge"]["readable"]
            )
            expected_values = {
                "start": expected_start,
                "end": expected_end,
                "soc": segment.soc if segment is not None else None,
                "grid_charge": bool(segment and segment.grid_charge),
            }
            fields: dict[str, dict[str, Any]] = {}
            for field_name, expected in expected_values.items():
                capability = field_caps[field_name]
                transaction_field = "grid" if field_name == "grid_charge" else field_name
                transaction_item = next(
                    (
                        item
                        for item in reversed(self.tou_transaction_log)
                        if item.get("slot_index") == idx
                        and item.get("field") == transaction_field
                    ),
                    None,
                )
                operation_expected = (
                    transaction_item.get("expected")
                    if transaction_item is not None
                    else expected
                )
                actual = capability["actual"]
                if transaction_item is not None:
                    status = str(transaction_item.get("status") or "unavailable")
                elif not capability["readable"] or actual is None:
                    status = "unavailable"
                elif operation_expected is None:
                    status = "unchanged"
                else:
                    match_field = "grid" if field_name == "grid_charge" else field_name
                    status = (
                        "confirmed"
                        if self._tou_field_matches(
                            capability["entity_id"], match_field, operation_expected
                        )
                        else "mismatch"
                    )
                fields[field_name] = {
                    "entity_id": capability["entity_id"],
                    "actual": actual,
                    "raw_actual": capability["raw_actual"],
                    "expected": operation_expected,
                    "status": status,
                    "writable": capability["writable"],
                    "capability": capability,
                }
            rows.append({
                "range": idx,
                "active": active,
                "actual_active": actual_active,
                "expected_start": expected_start,
                "expected_end": expected_end,
                "expected_soc": segment.soc if segment is not None else None,
                "actual_start": actual_start,
                "actual_end": actual_end,
                "actual_soc": soc_state if readable else None,
                "expected_grid_charge": bool(segment and segment.grid_charge),
                "actual_grid_charge": grid_state,
                "actual_grid_charge_enabled": field_caps["grid_charge"]["actual"],
                "readable": readable,
                "writable": any(field["writable"] for field in field_caps.values()),
                "read_only": capabilities["read_only"],
                "blocked_by_master_control": capabilities["blocked_by_master_control"],
                "control_writable": capabilities["control_writable"],
                "capabilities": capabilities,
                "fields": fields,
            })
        return rows

    def active_slot_control_diagnostics(self) -> dict[str, Any]:
        """Keep logical sale guards separate from physical TOU/control values."""
        slot = self.active_slot
        charge_slot = bool(slot.enabled and slot.mode == MODE_CHARGE)
        effective_soc = self._physical_tou_soc_for_slot(slot)
        physical_tou = self.physical_tou_snapshot()
        active_range = next((row for row in physical_tou if row["active"]), None)
        expected_grid_current = (
            slot.grid_charge_current
            if charge_slot
            else self.default_grid_charge_current
        )
        raw_sell_power = self.target_sell_power
        applied_sell_power = self.applied_sell_power
        manager_status = self.manager_status
        sale_blocked_by_soc = (
            manager_status == "SPRZEDAŻ ZABLOKOWANA" and "SOC" in self.decision_reason
        )
        result: dict[str, Any] = {
            "slot": slot.key,
            "mode": slot.mode if slot.enabled else "Wyłączony",
            "minimum_sell_soc": slot.minimum_sell_soc,
            "tou_soc": slot.tou_soc,
            "charge_profile_target_soc": self.charge_profile_target_soc,
            "effective_tou_soc": effective_soc,
            "physical_range": active_range.get("range") if active_range else None,
            "physical_soc_actual": active_range.get("actual_soc") if active_range else "brak",
            "grid_charge_expected": bool(slot.charge_enabled),
            "grid_charge_actual": active_range.get("actual_grid_charge") if active_range else "brak",
            "sale_blocked_by_soc": sale_blocked_by_soc,
            "default_discharge_current_after_stop": self.default_discharge_current,
            "manager_does_not_force_zero_a": True,
            "currents": {
                "charge_expected": self.target_charge_current,
                "charge_actual": self.state_text(self.charge_current_number),
                "discharge_expected": self.target_discharge_current,
                "discharge_actual": self.state_text(self.discharge_current_number),
                "grid_charge_expected": expected_grid_current,
                "grid_charge_actual": self.state_text(self.grid_charge_current_number),
            },
            "power_limits": {
                "configured_inverter_max_power_w": self.configured_inverter_max_power_w,
                "detected_entity_max_power_w": self.detected_entity_max_power_w,
                "effective_inverter_max_power_w": self.effective_inverter_max_power_w,
                "target_sell_power_w": raw_sell_power,
                "applied_sell_power_w": applied_sell_power,
                "capped": applied_sell_power < raw_sell_power,
            },
        }
        return result

    def record_schedule_attempt(self, status: str, stage: str, expected: dict[str, Any], message: str = "") -> None:
        self.last_schedule_attempt = {
            "status": status,
            "at": ha_now().isoformat(timespec="seconds"),
            "slot": self.active_slot_key(),
            "stage": stage,
            "expected": expected,
            "actual": self.control_values_snapshot(),
            "message": message,
        }

    def diagnostics(self) -> dict[str, Any]:
        configured = {
            self.data.get(CONF_WORK_MODE_SELECT): DEFAULT_WORK_MODE_SELECT,
            self.data.get(CONF_MAX_SELL_POWER_NUMBER): DEFAULT_MAX_SELL_POWER,
            self.data.get(CONF_DISCHARGE_CURRENT_NUMBER): DEFAULT_DISCHARGE_CURRENT,
            self.data.get(CONF_CHARGE_CURRENT_NUMBER): DEFAULT_CHARGE_CURRENT,
            self.data.get(CONF_GRID_CHARGE_CURRENT_NUMBER): DEFAULT_GRID_CHARGE_CURRENT,
            self.data.get(CONF_BATTERY_SOC_SENSOR): DEFAULT_BATTERY_SOC,
            self.data.get(CONF_PRICE_SENSOR): DEFAULT_PRICE_SENSOR,
            self.data.get(CONF_GRID_POWER_SENSOR): DEFAULT_GRID_POWER_SENSOR,
            self.data.get(CONF_PV_POWER_SENSOR): DEFAULT_PV_POWER_SENSOR,
            self.data.get(CONF_LOAD_POWER_SENSOR): DEFAULT_LOAD_POWER_SENSOR,
            self.data.get(CONF_BATTERY_POWER_SENSOR): DEFAULT_BATTERY_POWER_SENSOR,
            self.data.get(CONF_WEATHER_ENTITY): DEFAULT_WEATHER_ENTITY,
        }
        entity_ids = [self.work_mode_select, self.max_sell_power_number, self.discharge_current_number,
                      self.charge_current_number, self.grid_charge_current_number, self.battery_soc_sensor,
                      self.price_sensor, self.grid_power_sensor, self.pv_power_sensor, self.load_power_sensor,
                      self.battery_power_sensor, self.weather_entity]
        entities = []
        for entity_id in entity_ids:
            state = self.hass.states.get(entity_id) if entity_id else None
            is_configured = entity_id in configured and entity_id != configured.get(entity_id)
            entities.append({
                "entity_id": entity_id or "not_configured",
                "state": state.state if state is not None else "missing",
                "ok": state is not None and state.state not in ("unknown", "unavailable"),
                "configured": is_configured,
                "default": entity_id == configured.get(entity_id) if entity_id else False,
            })
        optional_ids = {
            "load_l1_power": self.load_l1_power_sensor,
            "load_l2_power": self.load_l2_power_sensor,
            "load_l3_power": self.load_l3_power_sensor,
            "pv1_power": self.pv1_power_sensor,
            "pv2_power": self.pv2_power_sensor,
            "pv3_power": self.pv3_power_sensor,
            "battery_voltage": self.battery_bms_voltage_sensor,
            "battery_current": self.battery_current_sensor,
            "battery_temperature": self.battery_temperature_sensor,
            "battery_soh": self.battery_soh_sensor,
            "daily_energy_bought": self.daily_energy_bought_sensor,
            "daily_energy_sold": self.daily_energy_sold_sensor,
            "daily_battery_charge": self.daily_battery_charge_sensor,
            "daily_battery_discharge": self.daily_battery_discharge_sensor,
        }
        optional_entities = [
            {
                "name": name,
                **self._measurement(
                    entity_id,
                    kind="energy" if name.startswith("daily_") else "raw" if name.startswith("battery_") and name != "battery_power" else "power",
                ),
                "optional": True,
            }
            for name, entity_id in optional_ids.items()
        ]
        quality_context = self.source_quality_context()
        tou = self.tou_mapping_diagnostics()
        mapping_status = (
            "ERROR"
            if self.mapping_error
            else "OGRANICZONE"
            if not tou["supported"]
            else "TOU ERROR"
            if not tou["ok"]
            else "OK"
        )
        return {"integration_version": "0.8.0", "connected": self.data_available, "required_entities_complete": self.required_entities_complete, "entities": entities,
                "inverter_provider": self.inverter_provider,
                "inverter_device_id": self.data.get(CONF_INVERTER_DEVICE_ID),
                "inverter_provider_label": provider_profile(self.data).label,
                "provider_native_tou": provider_profile(self.data).native_tou,
                "last_saved_at": self.last_saved_at or "never", "last_applied_at": self.last_applied_at or "never",
                 "last_error": self.last_error or "none", "last_schedule_attempt": self.last_schedule_attempt,
                 "manager_status": self.manager_status, "mapping_status": mapping_status,
                 "optimizer_core_budget": deepcopy(self._optimizer_budget_status),
                 "optimizer_startup": {
                     "pending": self._initial_optimizer_pending,
                     "started": self._initial_optimizer_started,
                     "completed": self._initial_optimizer_completed,
                 },
                 "control": {
                     "entity_id": self.control_entity_id,
                     "enabled": self.control_enabled,
                     "status": self.control_status,
                     "control_enabled": self.control_enabled,
                     "control_status": self.control_status,
                     "control_epoch": self._control_epoch,
                     "disable_generation": self._disable_generation,
                     "active_control_operations": self._active_control_operations,
                     "active_transaction_ids": sorted(self._active_control_transactions),
                     "disable_waiting_transaction_ids": sorted(self._disable_waiting_transactions),
                     "disable_error": self._control_disable_error or "none",
                     "planned_manager_action": self.planned_manager_action,
                     "executed_manager_action": self.executed_manager_action,
                 },
                 "capabilities": self.provider_capabilities(),
                 "mapping_segments": len(self._tou_mapping),
                 "mapping_plan": self.schedule_mapping_snapshot(),
                 "power_limits": {
                     "configured_inverter_max_power_w": self.configured_inverter_max_power_w,
                     "detected_entity_max_power_w": self.detected_entity_max_power_w,
                     "effective_inverter_max_power_w": self.effective_inverter_max_power_w,
                 },
                 "tou": tou,
                "tou_transaction": {
                    "tou_write_pending": self.tou_write_pending,
                    "tou_operation_status": self.tou_operation_status,
                    "operation_status": self.tou_contract_status,
                    "tou_operation_started_at": self.tou_operation_started_at.isoformat() if self.tou_operation_started_at else None,
                    "tou_last_error": self.tou_last_error or "none",
                    "tou_transaction_log": self.tou_transaction_log,
                },
                "tou_reverse_sync": {
                    "reverse_sync_status": self.reverse_sync_status,
                    "reverse_sync_last_error": self.reverse_sync_last_error or "none",
                    "reverse_sync_changed_hours": list(self.reverse_sync_changed_hours),
                    "reverse_sync_round_trip_ok": self.reverse_sync_round_trip_ok,
                },
                "tou_reconciliation": self.tou_reconciliation_diagnostics(),
                "tou_capabilities": self.tou_slot_capabilities(),
                "physical_tou": self.physical_tou_snapshot(),
                "active_slot_control": self.active_slot_control_diagnostics(),
                "soc_semantics": {
                    "minimum_sell_soc": "logiczny próg zatrzymania sprzedaży dla slotów Sprzedaż; nie jest fizycznym SOC Deye TOU",
                    "tou_soc": "fizyczny SOC Deye TOU dla wszystkich trybów (Normalna, Ładowanie, Sprzedaż, Wyłączony)",
                    "charge_profile_target_soc": "fizyczny SOC Deye TOU dla slotów Ładowanie",
                },
                "charge_profile": {
                    "grid_charge_enabled": self.charge_profile_grid_enabled,
                    "charge_current": self.charge_profile_charge_current,
                    "discharge_current": self.charge_profile_discharge_current,
                    "grid_charge_current": self.charge_profile_grid_charge_current,
                    "target_soc": self.charge_profile_target_soc,
                },
                "default_settings": {
                    "mode": self.default_work_mode,
                    "physical_work_mode": self.default_normal_physical_work_mode(),
                    "sell_power": self.default_sell_power,
                    "discharge_current": self.default_discharge_current,
                    "charge_current": self.default_charge_current,
                    "grid_charge_current": self.default_grid_charge_current,
                },
                "normal_profile_options": normal_profile_mode_metadata(self.data),
                "normal_profile": {
                    "physical_work_mode": self.normal_profile_physical_work_mode,
                    "sell_power": self.normal_profile_sell_power,
                    "discharge_current": self.normal_profile_discharge_current,
                    "charge_current": self.normal_profile_charge_current,
                    "grid_charge_current": self.normal_profile_grid_charge_current,
                    "tou_soc": self.normal_profile_tou_soc,
                },
                "active_slot": self.active_slot_key(), "next_active_slot": self.next_active_slot,
                "history_schema_version": HISTORY_SCHEMA_VERSION,
                "optional_entities": optional_entities,
                "data_quality": quality_context,
                "energy_counters": self.data_quality.get("energy_counters", {}),
                "energy_samples": len(self.energy_samples), "weather": self.weather_context(), "tariff": self.tariff_context(),
                "optimizer_runtime": {
                    **deepcopy(self.runtime_metrics),
                    "pending": self._optimizer_recalc_pending,
                    "pending_reasons": sorted(self._optimizer_pending_reasons),
                    "active_recalc": self._optimizer_active_recalc,
                    "listener_entities": list(self._optimizer_listener_entity_ids),
                },
                "ai_api": self.ai_api_public_context()}

    def empty_hourly_stats(self) -> dict[str, dict[str, float]]:
        return {f"{hour:02d}": {"kwh": 0.0, "value": 0.0} for hour in range(24)}

    def empty_sales_stats(self) -> dict[str, Any]:
        return {
            "current_day": ha_now().date().isoformat(),
            "hourly": self.empty_hourly_stats(),
            "daily": {},
            "last_update": None,
        }

    def normalize_sales_stats(self, raw: dict[str, Any] | None) -> dict[str, Any]:
        stats = self.empty_sales_stats()
        if isinstance(raw, dict):
            stats.update(raw)
        hourly = stats.get("hourly")
        if not isinstance(hourly, dict):
            hourly = {}
        normalized_hourly = self.empty_hourly_stats()
        for hour, values in hourly.items():
            key = f"{int(hour):02d}" if str(hour).isdigit() else str(hour).zfill(2)
            if key not in normalized_hourly or not isinstance(values, dict):
                continue
            normalized_hourly[key]["kwh"] = self.safe_float(values.get("kwh"), 0)
            normalized_hourly[key]["value"] = self.safe_float(values.get("value"), 0)
        stats["hourly"] = normalized_hourly
        daily = stats.get("daily")
        stats["daily"] = daily if isinstance(daily, dict) else {}
        return stats

    async def async_load_sales_stats(self) -> None:
        self._stats_store = Store(self.hass, 1, f"{DOMAIN}_{self.entry_id}_sales_stats")
        self.sales_stats = self.normalize_sales_stats(await self._stats_store.async_load())
        last_update = self.sales_stats.get("last_update")
        if last_update:
            try:
                self._energy_last_update = datetime.fromisoformat(last_update)
            except (TypeError, ValueError):
                self._energy_last_update = None
        self._energy_day = str(self.sales_stats.get("current_day") or ha_now().date().isoformat())
        self.refresh_sales_totals()

    async def async_save_sales_stats(self) -> None:
        if self._stats_store is None or not self._stats_dirty:
            return
        self.sales_stats["last_update"] = self._energy_last_update.isoformat() if self._energy_last_update else None
        await self._stats_store.async_save(self.sales_stats)
        self._stats_dirty = False

    async def async_load_ai_data(self) -> None:
        self._ai_store = Store(self.hass, 1, f"{DOMAIN}_{self.entry_id}_ai_data")
        raw = await self._ai_store.async_load()
        data, migrated = migrate_ai_payload(raw)
        settings = data.get("settings")
        history = data.get("history")
        self.ai_settings = settings if isinstance(settings, dict) else {}
        self.ai_history = history[:365] if isinstance(history, list) else []
        self.control_enabled = bool(data.get("control_enabled", True))
        self.control_status = "Aktywne" if self.control_enabled else "Wyłączone"
        if not self.control_enabled:
            self.executed_manager_action = "Nie wykonano — sterowanie wyłączone"
        self.user_profiles = data.get("user_profiles") if isinstance(data.get("user_profiles"), dict) else default_user_profiles()
        optimizer_plan = data.get("optimizer_plan")
        optimizer_history = data.get("optimizer_plan_history")
        self.optimizer_plan = optimizer_plan if isinstance(optimizer_plan, dict) else {}
        source_optimizer_history = optimizer_history[:30] if isinstance(optimizer_history, list) else []
        self.optimizer_plan_history = [
            self._compact_optimizer_history_entry(row)
            for row in source_optimizer_history
            if isinstance(row, dict)
        ]
        if self.optimizer_plan_history != source_optimizer_history:
            migrated = True
        plan_execution_archive = data.get("plan_execution_archive")
        self.plan_execution_archive = (
            plan_execution_archive[:2160]
            if isinstance(plan_execution_archive, list)
            else []
        )
        self._optimizer_input_snapshot_id = str(data.get("optimizer_input_snapshot_id") or "")
        if self._sanitize_cached_price_plans():
            migrated = True
        self._optimizer_generation_reason = "startup_or_restored_state"
        self.schedule_revision = max(
            0, int(self.safe_float(data.get("schedule_revision"), 0))
        )
        raw_slot_revisions = data.get("schedule_slot_revisions")
        self.schedule_slot_revisions = {
            str(key): max(0, int(self.safe_float(value, 0)))
            for key, value in (
                raw_slot_revisions.items()
                if isinstance(raw_slot_revisions, dict)
                else []
            )
            if str(key) in self.slots
        }
        raw_slot_ownership = data.get("schedule_slot_ownership")
        self.schedule_slot_ownership = {
            str(key): deepcopy(value)
            for key, value in (
                raw_slot_ownership.items()
                if isinstance(raw_slot_ownership, dict)
                else []
            )
            if str(key) in self.slots and isinstance(value, dict)
        }
        future_plan = data.get("future_plan")
        self.future_plan, future_plan_migrated = self._normalize_stored_future_plan(
            future_plan
        )
        migrated = migrated or future_plan_migrated
        self.last_saved_at = str(data.get("last_saved_at") or "")
        self.schedule_schema_version = max(0, int(self.safe_float(data.get("schedule_schema_version"), 0)))
        raw_ai_limit = data.get("ai_api_limit")
        self.ai_api_limit_state = (
            dict(raw_ai_limit) if isinstance(raw_ai_limit, dict) else {}
        )
        self._normalize_ai_api_limit_state(ha_now())
        raw_ai_cache = data.get("ai_api_cache")
        self.ai_api_cache = dict(raw_ai_cache) if isinstance(raw_ai_cache, dict) else {}
        stored_default_physical_mode = data.get("default_physical_work_mode")
        if stored_default_physical_mode in PHYSICAL_NORMAL_MODES:
            self.default_physical_work_mode = str(stored_default_physical_mode)

        stored_physical_modes = data.get("slot_physical_modes")
        if isinstance(stored_physical_modes, dict):
            for slot_key, physical_mode in stored_physical_modes.items():
                if slot_key in self.slots and physical_mode in PHYSICAL_NORMAL_MODES:
                    self.slots[slot_key].physical_work_mode = str(physical_mode)

        # The Charge template is one atomic user-owned record.  Loading all
        # fields together prevents individual RestoreEntity callbacks from
        # rebuilding a mixed profile after a restart.
        raw_profile = data.get("charge_profile")
        if isinstance(raw_profile, dict):
            numeric = {
                "charge_profile_charge_current": self.safe_float(raw_profile.get("charge_current"), float("nan")),
                "charge_profile_discharge_current": self.safe_float(raw_profile.get("discharge_current"), float("nan")),
                "charge_profile_grid_charge_current": self.safe_float(raw_profile.get("grid_charge_current"), float("nan")),
                "charge_profile_target_soc": self.safe_float(raw_profile.get("target_soc"), float("nan")),
            }
            grid_enabled = raw_profile.get("grid_charge_enabled")
            currents_ok = all(
                math.isfinite(value) and 0 <= value <= 240
                for key, value in numeric.items()
                if key != "charge_profile_target_soc"
            )
            soc_ok = math.isfinite(numeric["charge_profile_target_soc"]) and 0 <= numeric["charge_profile_target_soc"] <= 100
            if currents_ok and soc_ok and isinstance(grid_enabled, bool):
                for key, value in numeric.items():
                    setattr(self, key, value)
                self.charge_profile_grid_enabled = grid_enabled
                self._charge_profile_loaded_from_store = True

        raw_normal_profile = data.get("normal_profile")
        if isinstance(raw_normal_profile, dict):
            physical_mode = raw_normal_profile.get("physical_work_mode")
            numeric = {
                "normal_profile_sell_power": self.safe_float(raw_normal_profile.get("sell_power"), float("nan")),
                "normal_profile_discharge_current": self.safe_float(raw_normal_profile.get("discharge_current"), float("nan")),
                "normal_profile_charge_current": self.safe_float(raw_normal_profile.get("charge_current"), float("nan")),
                "normal_profile_grid_charge_current": self.safe_float(raw_normal_profile.get("grid_charge_current"), float("nan")),
                "normal_profile_tou_soc": self.safe_float(raw_normal_profile.get("tou_soc"), float("nan")),
            }
            profile_ok = (
                physical_mode in PHYSICAL_NORMAL_MODES
                and math.isfinite(numeric["normal_profile_sell_power"])
                and 0 <= numeric["normal_profile_sell_power"] <= self.effective_inverter_max_power_w
                and all(
                    math.isfinite(numeric[key]) and 0 <= numeric[key] <= 240
                    for key in (
                        "normal_profile_discharge_current",
                        "normal_profile_charge_current",
                        "normal_profile_grid_charge_current",
                    )
                )
                and math.isfinite(numeric["normal_profile_tou_soc"])
                and 0 <= numeric["normal_profile_tou_soc"] <= 100
            )
            if profile_ok:
                self.normal_profile_physical_work_mode = str(physical_mode)
                for key, value in numeric.items():
                    setattr(self, key, value)
                self._normal_profile_loaded_from_store = True
        if migrated:
            await self.async_save_ai_data()
        else:
            self._ai_last_saved_fingerprint = snapshot_id(
                self._ai_store_fingerprint_payload()
            )

    def _ai_store_payload(self) -> dict[str, Any]:
        """Build the latest canonical AI Store payload only on a save path."""
        return {
            "schema_version": HISTORY_SCHEMA_VERSION,
            "settings": self.ai_settings,
            "history": self.ai_history[:365],
            "user_profiles": self.user_profiles,
            "optimizer_plan": self.optimizer_plan,
            "optimizer_plan_history": self.optimizer_plan_history[:30],
            "plan_execution_archive": self.plan_execution_archive[:2160],
            "optimizer_input_snapshot_id": self._optimizer_input_snapshot_id,
            "future_plan": self.future_plan,
            "schedule_revision": self.schedule_revision,
            "schedule_slot_revisions": self.schedule_slot_revisions,
            "schedule_slot_ownership": self.schedule_slot_ownership,
            "last_saved_at": self.last_saved_at,
            "schedule_schema_version": self.schedule_schema_version,
            "control_enabled": self.control_enabled,
            "default_physical_work_mode": self.default_physical_work_mode,
            "slot_physical_modes": {
                slot_key: slot.physical_work_mode
                for slot_key, slot in self.slots.items()
                if slot.physical_work_mode in PHYSICAL_NORMAL_MODES
            },
            "charge_profile": {
                "charge_current": self.charge_profile_charge_current,
                "discharge_current": self.charge_profile_discharge_current,
                "grid_charge_current": self.charge_profile_grid_charge_current,
                "target_soc": self.charge_profile_target_soc,
                "grid_charge_enabled": self.charge_profile_grid_enabled,
            },
            "normal_profile": {
                "physical_work_mode": self.normal_profile_physical_work_mode,
                "sell_power": self.normal_profile_sell_power,
                "discharge_current": self.normal_profile_discharge_current,
                "charge_current": self.normal_profile_charge_current,
                "grid_charge_current": self.normal_profile_grid_charge_current,
                "tou_soc": self.normal_profile_tou_soc,
            },
            "ai_api_limit": self.ai_api_limit_state,
            # Strict response validation bounds this cache to one small advisory
            # result. Persisting it keeps a successful fingerprint meaningful
            # after restart without restoring historical plan payloads.
            "ai_api_cache": self.ai_api_cache,
        }

    def _ai_store_fingerprint_payload(self) -> dict[str, Any]:
        """Return a bounded canonical identity for the complete AI Store state."""
        plan = self.optimizer_plan if isinstance(self.optimizer_plan, dict) else {}
        return {
            "settings": self.ai_settings,
            "history": self.ai_history[:365],
            "user_profiles": self.user_profiles,
            "optimizer": {
                "plan_id": plan.get("plan_id"),
                "input_snapshot_id": plan.get("input_snapshot_id"),
                "algorithm_version": plan.get("algorithm_version"),
                "plan_schema_version": plan.get("plan_schema_version"),
            },
            "optimizer_plan_history": self.optimizer_plan_history[:30],
            "plan_execution_archive": self.plan_execution_archive[:2160],
            "optimizer_input_snapshot_id": self._optimizer_input_snapshot_id,
            "future_plan": self.future_plan,
            "schedule_revision": self.schedule_revision,
            "schedule_slot_revisions": self.schedule_slot_revisions,
            "schedule_slot_ownership": self.schedule_slot_ownership,
            "last_saved_at": self.last_saved_at,
            "schedule_schema_version": self.schedule_schema_version,
            "control_enabled": self.control_enabled,
            "default_physical_work_mode": self.default_physical_work_mode,
            "slot_physical_modes": {
                key: slot.physical_work_mode for key, slot in self.slots.items()
            },
            "charge_profile": [
                self.charge_profile_charge_current,
                self.charge_profile_discharge_current,
                self.charge_profile_grid_charge_current,
                self.charge_profile_target_soc,
                self.charge_profile_grid_enabled,
            ],
            "normal_profile": [
                self.normal_profile_physical_work_mode,
                self.normal_profile_sell_power,
                self.normal_profile_discharge_current,
                self.normal_profile_charge_current,
                self.normal_profile_grid_charge_current,
                self.normal_profile_tou_soc,
            ],
            "ai_api_limit": self.ai_api_limit_state,
            "ai_api_cache": {
                "at": self.ai_api_cache.get("at"),
                "plan_id": self.ai_api_cache.get("plan_id"),
                "input_snapshot_id": self.ai_api_cache.get("input_snapshot_id"),
                "material_fingerprint": self.ai_api_cache.get("material_fingerprint"),
                "analysis": self.ai_api_cache.get("analysis"),
                "candidate": self.ai_api_cache.get("candidate"),
                "usage": self.ai_api_cache.get("usage"),
            },
        }

    def request_ai_save(self) -> Any:
        """Coalesce background AI Store requests into one tracked task."""
        self._ai_save_dirty = True
        task = self._ai_save_task
        if (
            self._ai_store is None
            or self._startup_in_progress
            or self._unloading
            or (task is not None and not task.done())
        ):
            return task
        task = self.hass.async_create_task(self.async_save_ai_data())
        self._ai_save_task = task
        return task

    async def async_save_ai_data(self, *, force: bool = False) -> None:
        """Persist AI state single-flight, with one coalesced latest follow-up."""
        if self._ai_store is None or (self._unloading and not force):
            return
        self._ai_save_dirty = True
        if self._startup_in_progress:
            return
        current = asyncio.current_task()
        active = self._ai_save_task
        if active is not None and active is not current and not active.done():
            await asyncio.shield(active)
            return
        if active is None or active.done():
            self._ai_save_task = current
        follow_up_used = False
        try:
            while True:
                self._ai_save_dirty = False
                prepare_started = time.perf_counter()
                payload = self._ai_store_payload()
                fingerprint = snapshot_id(self._ai_store_fingerprint_payload())
                self._performance.observe_ms(
                    "ai_store_prepare",
                    (time.perf_counter() - prepare_started) * 1000.0,
                )
                if fingerprint != self._ai_last_saved_fingerprint:
                    store_started = time.perf_counter()
                    await self._ai_store.async_save(payload)
                    self._performance.observe_ms(
                        "ai_store_save",
                        (time.perf_counter() - store_started) * 1000.0,
                    )
                    self._ai_last_saved_fingerprint = fingerprint
                if self._ai_save_dirty and not follow_up_used:
                    follow_up_used = True
                    continue
                break
        finally:
            if self._ai_save_task is current:
                self._ai_save_task = None
        if self._ai_save_dirty and not self._unloading:
            self.request_ai_save()

    async def async_set_ai_settings(self, settings: dict[str, Any]) -> None:
        self.ai_settings = dict(settings)
        self._optimizer_generation_reason = "settings_changed"
        await self.async_save_ai_data()
        self.request_optimizer_recalc("profile")
        self.notify_update()

    @staticmethod
    def validate_user_profiles(
        payload: dict[str, Any],
        *,
        max_power_w: int = DEFAULT_INVERTER_MAX_POWER_W,
    ) -> dict[str, Any]:
        """Validate all optimizer profiles atomically without touching Deye."""
        source = payload.get("profiles") if isinstance(payload.get("profiles"), dict) else payload
        if not isinstance(source, dict):
            raise ValueError("Profile użytkownika muszą być obiektem JSON")
        normalized = default_user_profiles()
        allowed_days = {
            "0", "1", "2", "3", "4", "5", "6",
            "pon", "wt", "śr", "czw", "pt", "sob", "niedz",
            "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
        }
        for profile_id in ("morning_sale", "evening_sale", "charging"):
            raw = source.get(profile_id)
            if raw is None:
                continue
            if not isinstance(raw, dict):
                raise ValueError(f"Profil {profile_id} musi być obiektem")
            target = normalized["profiles"][profile_id]
            target.update(raw)
            for key in ("start", "end"):
                value = str(target.get(key) or "")
                try:
                    hour_text, minute_text = value.split(":", 1)
                    hour, minute = int(hour_text), int(minute_text)
                except (ValueError, TypeError) as err:
                    raise ValueError(f"Nieprawidłowa godzina {key} w profilu {profile_id}") from err
                if not 0 <= hour <= 23 or not 0 <= minute <= 59:
                    raise ValueError(f"Godzina {key} poza zakresem w profilu {profile_id}")
                target[key] = f"{hour:02d}:{minute:02d}"
            if target["start"] == target["end"]:
                raise ValueError(f"Profil {profile_id} ma pusty przedział czasu")
            target["enabled"] = bool(target.get("enabled"))
            target["allow_partial"] = bool(target.get("allow_partial", True))
            target["goal_character"] = str(target.get("goal_character") or "preferred")
            days = target.get("active_days")
            if not isinstance(days, list):
                raise ValueError(f"Aktywne dni profilu {profile_id} muszą być listą")
            normalized_days = [str(day).strip().lower() for day in days]
            if any(day not in allowed_days for day in normalized_days):
                raise ValueError(f"Profil {profile_id} zawiera nieprawidłowy dzień tygodnia")
            target["active_days"] = normalized_days
            if str(target.get("priority")) not in ("low", "normal", "high"):
                raise ValueError(f"Nieprawidłowy priorytet profilu {profile_id}")
            if str(target.get("goal_character")) not in ("preferred", "required"):
                raise ValueError(f"Nieprawidłowy charakter celu profilu {profile_id}")
            note = str(target.get("note") or "")
            if len(note) > 500:
                raise ValueError(f"Notatka profilu {profile_id} jest za długa")
            target["note"] = note
            confidence = finite_float(target.get("minimum_confidence"))
            if confidence is None or not 0 <= confidence <= 100:
                raise ValueError(f"Pewność profilu {profile_id} musi mieścić się w zakresie 0–100%")
            target["minimum_confidence"] = confidence
            if profile_id != "charging":
                for key, maximum in (
                    ("target_energy_kwh", 200.0),
                    ("min_price", 20.0),
                    ("min_soc_after", 100.0),
                    ("min_net_result", 10000.0),
                ):
                    value = finite_float(target.get(key))
                    if value is None or not 0 <= value <= maximum:
                        raise ValueError(f"Nieprawidłowa wartość {key} w profilu {profile_id}")
                    target[key] = value
                power = finite_float(target.get("preferred_power_w"))
                if power is not None and not 0 < power <= max_power_w:
                    raise ValueError(
                        f"Moc profilu {profile_id} musi być w zakresie 1–{max_power_w} W"
                    )
                target["preferred_power_w"] = power
                target["allow_earlier_grid_charge"] = bool(
                    target.get("allow_earlier_grid_charge", False)
                )
                if target.get("target_basis") not in ("battery_to_grid", "total_export"):
                    raise ValueError(f"Nieprawidłowy sposób liczenia celu profilu {profile_id}")
                if target.get("distribution_method") not in ("best_hours", "even", "constant_power"):
                    raise ValueError(f"Nieprawidłowy sposób rozłożenia profilu {profile_id}")
            else:
                if target.get("source") not in ("auto", "pv", "grid", "pv_and_grid"):
                    raise ValueError("Nieprawidłowe źródło profilu ładowania")
                if target.get("target_type") not in ("soc", "energy"):
                    raise ValueError("Nieprawidłowy typ celu profilu ładowania")
                deadline = str(target.get("deadline") or "")
                try:
                    deadline_hour_text, deadline_minute_text = deadline.split(":", 1)
                    deadline_hour = int(deadline_hour_text)
                    deadline_minute = int(deadline_minute_text)
                except (ValueError, TypeError) as err:
                    raise ValueError("Nieprawidłowy termin profilu ładowania") from err
                if not 0 <= deadline_hour <= 23 or not 0 <= deadline_minute <= 59:
                    raise ValueError("Termin profilu ładowania jest poza zakresem")
                target["deadline"] = f"{deadline_hour:02d}:{deadline_minute:02d}"
                target_value = finite_float(target.get("target_value"))
                maximum = 100.0 if target.get("target_type") == "soc" else 200.0
                if target_value is None or not 0 < target_value <= maximum:
                    raise ValueError("Nieprawidłowy cel profilu ładowania")
                target["target_value"] = target_value
                max_price = finite_float(target.get("max_effective_price"))
                if max_price is None or not 0 <= max_price <= 20:
                    raise ValueError("Nieprawidłowa maksymalna cena ładowania")
                target["max_effective_price"] = max_price
                max_grid = finite_float(target.get("max_grid_energy_kwh"))
                if max_grid is not None and not 0 <= max_grid <= 200:
                    raise ValueError("Nieprawidłowy limit energii z sieci")
                target["max_grid_energy_kwh"] = max_grid
                power = finite_float(target.get("preferred_power_w"))
                if power is not None and not 0 < power <= max_power_w:
                    raise ValueError(
                        f"Moc profilu ładowania musi być w zakresie 1–{max_power_w} W"
                    )
                target["preferred_power_w"] = power
                purpose_aliases = {
                    "general": "mixed",
                    "home_reserve": "reserve",
                    "morning_sale": "sale",
                    "evening_sale": "sale",
                    "both_sales": "sale",
                    "cheap_home": "home",
                }
                purpose = purpose_aliases.get(
                    str(target.get("purpose") or "mixed"),
                    str(target.get("purpose") or "mixed"),
                )
                if purpose not in ("sale", "home", "reserve", "mixed"):
                    raise ValueError("Nieprawidłowe przeznaczenie profilu ładowania")
                target["purpose"] = purpose
                free_room = finite_float(target.get("minimum_free_room_kwh"))
                if free_room is None or not 0 <= free_room <= 200:
                    raise ValueError("Nieprawidłowa rezerwa miejsca na PV")
                target["minimum_free_room_kwh"] = free_room
                for key, default in (
                    ("charge_missing_only", True),
                    ("use_corrected_pv", True),
                    ("preserve_pv_room", True),
                    ("profitable_only", True),
                ):
                    target[key] = bool(target.get(key, default))
        return normalized

    async def async_set_user_profiles(self, profiles: dict[str, Any]) -> None:
        """Save a complete validated policy and only invalidate the local plan."""
        normalized = self.validate_user_profiles(
            profiles,
            max_power_w=self.effective_inverter_max_power_w,
        )
        for profile_id in ("morning_sale", "evening_sale", "charging"):
            profile = normalized.get("profiles", {}).get(profile_id)
            if not isinstance(profile, dict):
                continue
            power = finite_float(profile.get("preferred_power_w"))
            if power is not None:
                self.validate_manual_sell_power_w(
                    f"preferred_power_w profilu {profile_id}", power
                )
        self.user_profiles = normalized
        self._optimizer_generation_reason = "user_profiles_changed"
        await self.async_save_ai_data()
        self.request_optimizer_recalc("profile")
        self.notify_update()

    def ai_api_public_context(self) -> dict[str, Any]:
        """Expose status and masked configuration, never the API secret."""
        self._normalize_ai_api_limit_state(ha_now())
        daily_count = int(self.safe_float(self.ai_api_limit_state.get("count"), 0))
        return {
            "config": redact_ai_api_config(self.ai_api_config),
            **{
                key: value
                for key, value in self.ai_api_status.items()
                if key not in {"api_key", "authorization", "request_payload"}
            },
            "last_analysis": self.ai_api_cache.get("analysis"),
            "last_analysis_at": self.ai_api_cache.get("at"),
            "last_analysis_locale": self.ai_api_cache.get("locale"),
            "last_plan_id": self.ai_api_cache.get("plan_id"),
            "last_input_snapshot_id": self.ai_api_cache.get("input_snapshot_id"),
            "candidate": self.ai_api_cache.get("candidate"),
            "usage": self.ai_api_cache.get("usage"),
            "daily_limit": {
                "date": self.ai_api_limit_state.get("date"),
                "count": daily_count,
                "maximum": 8,
                "remaining": max(0, 8 - daily_count),
                "last_request_at": self.ai_api_limit_state.get("last_request_at"),
                "last_success_at": self.ai_api_limit_state.get("last_success_at"),
                "cooldown_seconds": 7200,
            },
        }

    def _ai_api_material_context(
        self,
        local_plan: dict[str, Any],
        now: datetime,
    ) -> tuple[str, dict[str, Any], dict[str, Any]]:
        """Return one bounded context shared by dedupe and the actual request."""
        battery_model = self.battery_model_context()
        battery = {
            "current_soc_pct": self.current_soc_or_none(),
            "soc_status": self.soc_diagnostics().get("status"),
            "capacity_kwh": battery_model.get("capacity_kwh"),
            "effective_min_soc_pct": battery_model.get("minimum", {}).get("effective_min_soc_pct"),
            "power_limit_w": battery_model.get("power_limit", {}).get("effective_limit_w"),
        }
        tariff = self.tariff_context(now)
        fingerprint = material_review_fingerprint(
            local_plan,
            battery,
            config=self.ai_api_config,
            user_profiles=self.user_profiles,
            tariff=tariff,
        )
        return fingerprint, battery, tariff

    def _normalize_ai_api_limit_state(self, now: datetime) -> None:
        """Reset only the local-day counter while retaining useful audit fields."""
        today = now.date().isoformat()
        state = self.ai_api_limit_state if isinstance(self.ai_api_limit_state, dict) else {}
        if str(state.get("date") or "") != today:
            state = {
                "date": today,
                "count": 0,
                "last_request_at": None,
                "last_success_at": state.get("last_success_at"),
                "last_input_fingerprint": state.get("last_input_fingerprint"),
            }
        else:
            state = {
                "date": today,
                "count": max(0, int(self.safe_float(state.get("count"), 0))),
                "last_request_at": state.get("last_request_at"),
                "last_success_at": state.get("last_success_at"),
                "last_input_fingerprint": state.get("last_input_fingerprint"),
            }
        self.ai_api_limit_state = state

    def _ai_api_cooldown_active(self, now: datetime) -> bool:
        last = self.ai_api_limit_state.get("last_request_at")
        try:
            return bool(last and (now - datetime.fromisoformat(str(last))).total_seconds() < 7200)
        except (TypeError, ValueError):
            return False

    async def _record_ai_api_attempt(self, attempt: int) -> None:
        """Count an actual outbound attempt immediately before session.post."""
        now = ha_now()
        self._normalize_ai_api_limit_state(now)
        count = int(self.ai_api_limit_state.get("count", 0))
        if count >= 8:
            raise ExternalAIDailyLimitError("Osiągnięto dzienny limit 8 zapytań AI")
        self.ai_api_limit_state["count"] = count + 1
        self.ai_api_limit_state["last_request_at"] = now.isoformat(timespec="seconds")
        self.ai_api_metrics["executed"] += 1
        if attempt:
            self.ai_api_metrics["retry"] += 1
        # Persist the reservation before the outbound POST. This makes the hard
        # daily cap restart-safe even if HA stops while a request is in flight.
        await self.async_save_ai_data()

    def update_ai_api_config(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Validate API options synchronously; caller persists config-entry options."""
        previous_secret = str(self.ai_api_config.get("api_key") or "")
        normalized = normalize_ai_api_config(raw, previous_secret)
        self.ai_api_config = normalized
        self.ai_api_status = {
            "status": "ready" if normalized.get("enabled") else "disabled",
            "provider": normalized.get("provider"),
            "model": normalized.get("model"),
            "last_error": None,
        }
        self._ai_api_last_call = None
        self._ai_api_last_attempt = None
        self._ai_api_running = False
        self.notify_update()
        return deepcopy(normalized)

    async def async_run_ai_api(
        self,
        *,
        connection_test: bool = False,
        force: bool = False,
    ) -> dict[str, Any]:
        """Run the optional reviewer; local plan and Deye remain untouched."""
        self.ai_api_metrics["requested"] += 1
        if not self.ai_api_config.get("enabled"):
            self.ai_api_status = {"status": "disabled", "last_error": "Asystent API jest wyłączony"}
            self.notify_update()
            return self.ai_api_status
        now = ha_now()
        self._normalize_ai_api_limit_state(now)
        if int(self.ai_api_limit_state.get("count", 0)) >= 8:
            self.ai_api_metrics["skipped_daily_limit"] += 1
            self.ai_api_status = {
                "status": "daily_limit",
                "last_error": "Osiągnięto dzienny limit 8 zapytań AI",
            }
            self.notify_update()
            return self.ai_api_public_context()
        if self._ai_api_running:
            return {**self.ai_api_public_context(), "status": "busy"}
        started_clock = time.perf_counter()
        self._ai_api_running = True
        self.ai_api_metrics["active"] += 1
        self.ai_api_metrics["max_active"] = max(
            self.ai_api_metrics["max_active"], self.ai_api_metrics["active"]
        )
        self.ai_api_status = {
            "status": "testing" if connection_test else "analysing",
            "provider": self.ai_api_config.get("provider"),
            "model": self.ai_api_config.get("model"),
            "last_error": None,
        }
        self.notify_update()
        try:
            return await self._async_run_ai_api_locked(
                now=now,
                connection_test=connection_test,
                force=force,
            )
        finally:
            self._ai_api_running = False
            self.ai_api_metrics["active"] = max(0, self.ai_api_metrics["active"] - 1)
            self.ai_api_metrics["last_duration_ms"] = round(
                (time.perf_counter() - started_clock) * 1000.0,
                1,
            )

    async def _async_run_ai_api_locked(
        self,
        *,
        now: datetime,
        connection_test: bool,
        force: bool,
    ) -> dict[str, Any]:
        """Execute one single-flight AI decision and provider request."""
        try:
            if force:
                optimizer_task = self.request_optimizer_recalc("manual")
                if optimizer_task is not None:
                    await asyncio.shield(optimizer_task)
            elif self._optimizer_recalc_task is not None:
                await asyncio.shield(self._optimizer_recalc_task)
            local_plan = self._optimizer_public_snapshot or self.optimizer_plan
            material_fingerprint, battery, tariff = self._ai_api_material_context(
                local_plan,
                now,
            )
            quality = local_plan.get("data_quality") if isinstance(local_plan, dict) else {}
            if not connection_test and isinstance(quality, dict) and quality.get("fail_closed"):
                self.ai_api_metrics["skipped_fail_closed"] += 1
                self.ai_api_status = {
                    "status": "blocked_fail_closed",
                    "last_error": "Lokalny plan jest fail-closed — zapytanie AI pominięto",
                }
                return self.ai_api_public_context()
            if (
                not connection_test
                and self.ai_api_limit_state.get("last_input_fingerprint") == material_fingerprint
                and self.ai_api_limit_state.get("last_success_at")
                and self.ai_api_cache.get("material_fingerprint") == material_fingerprint
                and isinstance(self.ai_api_cache.get("analysis"), dict)
            ):
                self.ai_api_metrics["skipped_same_input"] += 1
                self.ai_api_status = {"status": "cached_same_input", "last_error": None}
                return self.ai_api_public_context()
            if not force and self._ai_api_cooldown_active(now):
                self.ai_api_metrics["skipped_cooldown"] += 1
                self.ai_api_status = {
                    "status": "cooldown",
                    "last_error": "Automatyczna analiza AI ma 2-godzinny cooldown",
                }
                return self.ai_api_public_context()
            if not connection_test:
                self._ai_api_last_attempt = now
            payload = build_private_payload(
                local_plan,
                battery,
                config=self.ai_api_config,
                user_profiles=self.user_profiles,
                tariff=tariff,
            )
            from homeassistant.helpers.aiohttp_client import async_get_clientsession

            response = await request_ai_analysis(
                async_get_clientsession(self.hass),
                self.ai_api_config,
                payload,
                connection_test=connection_test,
                timeout_seconds=30,
                inverter_max_power_w=self.effective_inverter_max_power_w,
                on_attempt=self._record_ai_api_attempt,
            )
        except asyncio.CancelledError:
            raise
        except Exception as err:
            self.ai_api_status = {
                "status": "error",
                "provider": self.ai_api_config.get("provider"),
                "model": self.ai_api_config.get("model"),
                "last_error": str(err)[:500],
                "at": now.isoformat(timespec="seconds"),
            }
            self.ai_api_metrics["failed"] += 1
            self.notify_update()
            await self.async_save_ai_data()
            return self.ai_api_status

        if not connection_test:
            self._ai_api_last_call = now
            self.ai_api_limit_state["last_success_at"] = now.isoformat(timespec="seconds")
            self.ai_api_limit_state["last_input_fingerprint"] = material_fingerprint
        self.ai_api_status = {
            "status": "connected" if connection_test else "ok",
            "provider": response.get("provider"),
            "model": response.get("model"),
            "response_ms": response.get("response_ms"),
            "json_schema": response.get("json_schema"),
            "last_error": None,
            "at": now.isoformat(timespec="seconds"),
        }
        if not connection_test:
            analysis = response.get("analysis") if isinstance(response.get("analysis"), dict) else {}
            candidate = None
            alternative = analysis.get("alternative") if isinstance(analysis.get("alternative"), dict) else {}
            if alternative.get("enabled") and alternative.get("hours") and self._optimizer_last_inputs:
                try:
                    candidate_job = partial(
                        simulate_alternative,
                        self._optimizer_last_inputs,
                        strategy=str(local_plan.get("selected_variant") or "balanced"),
                        changes=alternative.get("hours"),
                    )
                    executor = getattr(self.hass, "async_add_executor_job", None)
                    candidate_result = (
                        await executor(candidate_job)
                        if callable(executor)
                        else await asyncio.to_thread(candidate_job)
                    )
                    candidate = {
                        key: deepcopy(candidate_result.get(key))
                        for key in (
                            "source_plan_id", "source_input_snapshot_id",
                            "candidate_plan_id", "candidate_changes", "comparison",
                            "schema_valid", "locally_simulated", "accepted_by_core",
                            "acceptance", "locally_validated", "manual_confirmation_required",
                            "writes_performed",
                        )
                    }
                except ValueError as err:
                    candidate = {
                        "schema_valid": False,
                        "locally_simulated": False,
                        "accepted_by_core": False,
                        "locally_validated": False,
                        "validation_error": str(err),
                        "writes_performed": False,
                    }
            self.ai_api_cache = {
                "at": now.isoformat(timespec="seconds"),
                "plan_id": local_plan.get("plan_id"),
                "input_snapshot_id": local_plan.get("input_snapshot_id"),
                "material_fingerprint": material_fingerprint,
                "locale": "pl-PL",
                "analysis": analysis,
                "candidate": candidate,
                "usage": response.get("usage"),
            }
        self.ai_api_metrics["completed"] += 1
        self.notify_update()
        await self.async_save_ai_data()
        return self.ai_api_public_context()

    def schedule_ai_api_analysis(self, *, force: bool = False) -> None:
        """Start at most one asynchronous API review without blocking the tick."""
        if not self.ai_api_config.get("enabled"):
            return
        if self._ai_api_task is not None and not self._ai_api_task.done():
            return
        if not force:
            now = ha_now()
            self._normalize_ai_api_limit_state(now)
            if int(self.ai_api_limit_state.get("count", 0)) >= 8:
                self.ai_api_metrics["skipped_daily_limit"] += 1
                return
            local_plan = self._optimizer_public_snapshot or self.optimizer_plan
            quality = local_plan.get("data_quality") if isinstance(local_plan, dict) else {}
            if isinstance(quality, dict) and quality.get("fail_closed"):
                self.ai_api_metrics["skipped_fail_closed"] += 1
                return
            fingerprint, _battery, _tariff = self._ai_api_material_context(
                local_plan,
                now,
            )
            if (
                self.ai_api_limit_state.get("last_input_fingerprint") == fingerprint
                and self.ai_api_limit_state.get("last_success_at")
                and self.ai_api_cache.get("material_fingerprint") == fingerprint
                and isinstance(self.ai_api_cache.get("analysis"), dict)
            ):
                self.ai_api_metrics["skipped_same_input"] += 1
                return
            if self._ai_api_cooldown_active(now):
                self.ai_api_metrics["skipped_cooldown"] += 1
                return
        self._ai_api_task = self.hass.async_create_task(
            self.async_run_ai_api(force=force)
        )

    async def async_add_ai_analysis(self, analysis: dict[str, Any]) -> None:
        analysis = dict(analysis)
        analysis.setdefault("event", "suggestion")
        if analysis.get("event") == "suggestion":
            latest = next((item for item in self.ai_history if item.get("event", "suggestion") == "suggestion"), None)
            if latest and analysis.get("fingerprint") and latest.get("fingerprint") == analysis.get("fingerprint"):
                return
        self.ai_history = [analysis, *self.ai_history][:365]
        await self.async_save_ai_data()
        self.notify_update()

    async def async_rate_ai_analysis(self, timestamp: float, rating: int) -> None:
        for item in self.ai_history:
            if self.safe_float(item.get("timestamp"), -1) == timestamp:
                item["rating"] = max(1, min(5, int(rating)))
                item["rated_at"] = int(ha_now().timestamp() * 1000)
                await self.async_save_ai_data()
                self.notify_update()
                return

    async def async_clear_ai_history(self) -> None:
        self.ai_history = []
        await self.async_save_ai_data()
        self.notify_update()

    def _validate_future_plan_updates(self, updates: Any) -> list[dict[str, Any]]:
        """Validate a dated AI plan without touching the live 24-hour schedule."""
        if not isinstance(updates, list) or not updates:
            raise ValueError("Plan na jutro nie zawiera wybranych godzin")
        numeric_limits = {
            "sell_power": (0.0, float(self.effective_inverter_max_power_w)),
            "discharge_current": (0.0, 240.0),
            "charge_current": (0.0, 240.0),
            "grid_charge_current": (0.0, 240.0),
            "minimum_sell_soc": (0.0, 100.0),
            "tou_soc": (0.0, 100.0),
            "min_sell_price": (0.0, 5.0),
        }
        allowed = {"slot_key", "enabled", "mode", "charge_enabled", *numeric_limits}
        normalized: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw in updates:
            raw = dict(raw) if isinstance(raw, dict) else raw
            if not isinstance(raw, dict):
                raise ValueError("Każda pozycja planu musi być obiektem")
            # ``min_soc`` remains an old spelling of the Selling First
            # threshold.  ``tou_soc`` is deliberately independent.
            if "min_soc" in raw:
                raw.setdefault("minimum_sell_soc", raw.pop("min_soc"))
            unknown = set(raw) - allowed
            if unknown:
                raise ValueError(f"Nieobsługiwane pola planu: {', '.join(sorted(unknown))}")
            slot_key = str(raw.get("slot_key") or "")
            if slot_key not in self.slots or slot_key in seen:
                raise ValueError(f"Nieprawidłowa lub powtórzona godzina planu: {slot_key}")
            seen.add(slot_key)
            item: dict[str, Any] = {"slot_key": slot_key}
            if "enabled" in raw:
                item["enabled"] = bool(raw["enabled"])
            if "charge_enabled" in raw:
                item["charge_enabled"] = bool(raw["charge_enabled"])
            if "mode" in raw:
                mode = normalize_manager_mode(str(raw["mode"]))
                if mode not in SLOT_MODES:
                    raise ValueError(f"Nieobsługiwany tryb planu: {mode}")
                item["mode"] = mode
            for name, (minimum, maximum) in numeric_limits.items():
                if name not in raw:
                    continue
                value = float(raw[name])
                if not math.isfinite(value) or not minimum <= value <= maximum:
                    raise ValueError(f"{name} musi mieścić się w zakresie {minimum:g}–{maximum:g}")
                item[name] = value
            if item.get("mode") == MODE_SELLING_FIRST:
                # Keep price/SOC thresholds as revalidation metadata, but never
                # persist legacy current, TOU SOC or Grid Charge as part of the
                # executable Tomorrow sell contract.
                for field_name in (
                    "discharge_current",
                    "charge_current",
                    "grid_charge_current",
                    "tou_soc",
                    "charge_enabled",
                ):
                    item.pop(field_name, None)
            normalized.append(item)
        return normalized

    @staticmethod
    def _future_plan_normal_intent(slot_key: str) -> dict[str, Any]:
        """Return a storage-safe Normal Operation intent for one dated hour.

        FuturePlan stores ownership of the logical action, not a snapshot of
        unrelated inverter limits.  ``charge_enabled=False`` is the one
        explicit cleanup flag needed to prevent an old Charge action from
        surviving when the dated target is materialised JIT.
        """
        return {
            "slot_key": slot_key,
            "enabled": True,
            "mode": MODE_NORMAL_OPERATION,
            "charge_enabled": False,
        }

    def _build_authoritative_future_plan_updates(
        self,
        selected_updates: Any,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Build a canonical dated 24-hour target from selected special actions."""
        selected_list = self._validate_future_plan_updates(selected_updates)
        selected: dict[str, dict[str, Any]] = {}
        for update in selected_list:
            slot_key = str(update.get("slot_key") or "")
            mode = str(update.get("mode") or "")
            if mode not in {MODE_SELLING_FIRST, MODE_CHARGE}:
                raise ValueError(
                    f"FuturePlan przyjmuje wyłącznie wybrane akcje Sprzedaż/Ładowanie: {slot_key}"
                )
            if update.get("enabled") is False:
                raise ValueError(f"Wybrana akcja FuturePlan nie może być wyłączona: {slot_key}")
            if mode == MODE_SELLING_FIRST:
                if "sell_power" not in update:
                    raise ValueError(
                        f"Wybrana akcja Sprzedaż wymaga sell_power: {slot_key}"
                    )
                update = self._sanitize_ai_sell_execution_update(update)
            selected[slot_key] = update

        target = [
            dict(selected[key])
            if key in selected
            else self._future_plan_normal_intent(key)
            for key, _label, _start, _end in SLOTS
        ]
        if len(target) != 24 or {str(item.get("slot_key")) for item in target} != set(self.slots):
            raise ValueError("Nie udało się zbudować kompletnego FuturePlan 24 h")
        return target, [key for key, _label, _start, _end in SLOTS if key in selected]

    def _schedule_slot_fingerprint(self, slot_key: str) -> str:
        """Return the lightweight logical identity used by FuturePlan ownership."""
        slot = self.slots[slot_key]
        return snapshot_id({
            "enabled": bool(slot.enabled),
            "mode": slot.mode,
            "physical_work_mode": slot.physical_work_mode,
            "sell_power": float(slot.sell_power),
            "discharge_current": float(slot.discharge_current),
            "charge_enabled": bool(slot.charge_enabled),
            "charge_current": float(slot.charge_current),
            "grid_charge_current": float(slot.grid_charge_current),
            "minimum_sell_soc": float(slot.minimum_sell_soc),
            "tou_soc": None if slot.tou_soc is None else float(slot.tou_soc),
            "min_sell_price": float(slot.min_sell_price),
        })

    def _claim_schedule_slots(
        self,
        slot_keys: list[str],
        source: str,
        context: dict[str, Any] | None = None,
    ) -> int:
        """Advance one schedule generation and record the writer of each slot."""
        keys = [key for key in dict.fromkeys(slot_keys) if key in self.slots]
        if not keys:
            return self.schedule_revision
        self.schedule_revision += 1
        revision = self.schedule_revision
        details = context if isinstance(context, dict) else {}
        for key in keys:
            self.schedule_slot_revisions[key] = revision
            self.schedule_slot_ownership[key] = {
                "source": source,
                "revision": revision,
                "plan_id": str(details.get("plan_id") or ""),
                "target_date": str(details.get("target_date") or ""),
                "slot_key": key,
                "intent_revision": int(self.safe_float(details.get("intent_revision"), 0)),
                "fingerprint": self._schedule_slot_fingerprint(key),
                "changed_at": ha_now().isoformat(timespec="seconds"),
            }
        return revision

    def _future_plan_acceptance_bases(self) -> dict[str, dict[str, Any]]:
        """Capture only the revision/hash needed for the MANUAL WINS check."""
        return {
            key: {
                "base_revision": int(self.schedule_slot_revisions.get(key, 0)),
                "base_fingerprint": self._schedule_slot_fingerprint(key),
            }
            for key in self.slots
        }

    def _future_plan_manual_conflict(
        self, plan: dict[str, Any], slot_key: str
    ) -> bool:
        bases = plan.get("slot_bases")
        base = bases.get(slot_key) if isinstance(bases, dict) else None
        if not isinstance(base, dict):
            # Restored pre-8C pending plans use their stored/current schedule as
            # a fail-safe baseline; completed legacy rows are migrated terminally.
            return False
        current_revision = int(self.schedule_slot_revisions.get(slot_key, 0))
        current_fingerprint = self._schedule_slot_fingerprint(slot_key)
        if (
            current_revision == int(self.safe_float(base.get("base_revision"), 0))
            and current_fingerprint == str(base.get("base_fingerprint") or "")
        ):
            return False
        owner = self.schedule_slot_ownership.get(slot_key, {})
        return not (
            owner.get("source") == "future_plan"
            and owner.get("plan_id") == str(plan.get("plan_id") or "")
            and owner.get("target_date") == str(plan.get("date") or "")
        )

    @staticmethod
    def _future_plan_overall_status(slot_results: dict[str, Any]) -> str:
        statuses = {
            str(value.get("status") or "")
            for value in slot_results.values()
            if isinstance(value, dict)
        }
        if statuses & {"blocked", "missed", "manual_override"}:
            return "partial"
        if statuses and statuses <= {"confirmed", "superseded", "cancelled"}:
            return "confirmed"
        return "scheduled"

    async def _async_finish_future_plan_physical(
        self, confirmed: bool, reason: str = "", expected: dict[str, Any] | None = None
    ) -> None:
        """Correlate the existing inverter confirmation with one active intent."""
        plan = self.future_plan
        if not isinstance(plan, dict) or plan.get("status") not in {
            "scheduled", "partial", "confirmed"
        }:
            return
        now = ha_now()
        slot_key = f"{now.hour:02d}_{(now.hour + 1) % 24:02d}"
        results = dict(plan.get("slot_results") or {})
        result = results.get(slot_key)
        if not isinstance(result, dict) or result.get("status") not in {
            "logical_applied", "physical_pending"
        }:
            return
        correlation = result.get("correlation")
        owner = self.schedule_slot_ownership.get(slot_key, {})
        exact = (
            isinstance(correlation, dict)
            and correlation.get("plan_id") == str(plan.get("plan_id") or "")
            and correlation.get("target_date") == str(plan.get("date") or "")
            and correlation.get("slot_key") == slot_key
            and int(self.safe_float(correlation.get("intent_revision"), 0))
            == int(self.safe_float(owner.get("intent_revision"), -1))
            and owner.get("source") == "future_plan"
            and owner.get("fingerprint") == self._schedule_slot_fingerprint(slot_key)
        )
        writes_before = int(self.safe_float(correlation.get("physical_write_count_before"), -1)) if isinstance(correlation, dict) else -1
        physically_written = self._physical_write_count > writes_before >= 0
        expected_matches = (
            isinstance(expected, dict)
            and str(correlation.get("expected_fingerprint") or "")
            == snapshot_id(expected)
        ) if isinstance(correlation, dict) else False
        allowed = (
            confirmed
            and exact
            and physically_written
            and expected_matches
            and self.control_mode == "Schedule"
            and self._control_is_active()
            and not self.emergency_stop
            and str(plan.get("date") or "") == now.date().isoformat()
        )
        timestamp = now.isoformat(timespec="seconds")
        if allowed:
            results[slot_key] = {
                **result,
                "status": "confirmed",
                "confirmed_at": timestamp,
                "transaction_id": _CONTROL_TRANSACTION_ID.get(),
                "confirmation": "write_readback_success",
            }
            self._set_plan_execution_lifecycle(
                str(plan.get("date") or ""), slot_key,
                deployment_status="confirmed", deployed_at=timestamp,
                deployment_reason=None,
            )
        elif not confirmed:
            results[slot_key] = {
                **result,
                "status": "blocked",
                "reason": reason or "Fizyczna transakcja lub readback nie powiodły się",
                "resolved_at": timestamp,
            }
        else:
            return
        self.future_plan = {
            **plan,
            "status": self._future_plan_overall_status(results),
            "slot_results": results,
            "updated_at": timestamp,
        }
        await self.async_save_ai_data()
        await self.async_save_learning_history()
        self._notify_update_for("future_plan")

    async def _async_cleanup_future_plan_slots(self, current: datetime) -> None:
        """Reset expired dated intents only while the old plan still owns them."""
        cleanup: list[dict[str, Any]] = []
        cleaned_keys: list[str] = []
        today = current.date().isoformat()
        for key, owner in list(self.schedule_slot_ownership.items()):
            if not isinstance(owner, dict) or owner.get("source") != "future_plan":
                continue
            target_date = str(owner.get("target_date") or "")
            start_hour = int(key.split("_", 1)[0])
            expired = target_date < today or (
                target_date == today and current.hour > start_hour
            )
            if not expired or owner.get("fingerprint") != self._schedule_slot_fingerprint(key):
                continue
            cleanup.append(self._future_plan_normal_intent(key))
            cleaned_keys.append(key)
        if not cleanup:
            return
        await self.async_apply_schedule_patch(
            cleanup, change_source="future_cleanup",
            source_context={"cleanup": True},
        )
        for key in cleaned_keys:
            owner = self.schedule_slot_ownership.get(key, {})
            if owner.get("source") == "future_cleanup":
                self.schedule_slot_ownership.pop(key, None)
        self.mark_config_saved()

    def _normalize_stored_future_plan(
        self,
        raw_plan: Any,
    ) -> tuple[dict[str, Any], bool]:
        """Migrate selected-only FuturePlan safely to an authoritative day target."""
        if not isinstance(raw_plan, dict) or not raw_plan:
            return {}, bool(raw_plan)
        plan = deepcopy(raw_plan)
        updates = plan.get("updates")
        if not isinstance(updates, list) or not updates:
            if plan.get("status") in {"scheduled", "partial"}:
                return ({
                    **plan,
                    "status": "cancelled",
                    "reason": "Legacy FuturePlan nie zawiera bezpiecznych akcji; wymagane ponowne zatwierdzenie",
                    "migration_requires_reapproval": True,
                }, True)
            return plan, False
        try:
            # Never infer a special action from the live schedule.  For both an
            # old selected-only payload and a stored v2 target, only explicit
            # Sell/Charge rows retain special ownership; every missing/Normal
            # hour is rebuilt as canonical Normal Operation.
            selected_raw = [
                item
                for item in updates
                if isinstance(item, dict)
                and normalize_manager_mode(str(item.get("mode") or ""))
                in {MODE_SELLING_FIRST, MODE_CHARGE}
            ]
            target, selected_keys = self._build_authoritative_future_plan_updates(selected_raw)
        except (TypeError, ValueError) as err:
            if plan.get("status") in {"scheduled", "partial"}:
                return ({
                    **plan,
                    "status": "cancelled",
                    "reason": f"Legacy FuturePlan wymaga ponownego zatwierdzenia: {err}",
                    "migration_requires_reapproval": True,
                }, True)
            return plan, False

        validations = plan.get("slot_validations")
        validations = validations if isinstance(validations, dict) else {}
        slot_results = deepcopy(plan.get("slot_results")) if isinstance(plan.get("slot_results"), dict) else {}
        legacy_lifecycle = int(self.safe_float(plan.get("lifecycle_schema_version"), 0)) < FUTURE_PLAN_LIFECYCLE_SCHEMA_VERSION
        if legacy_lifecycle:
            for key, result in list(slot_results.items()):
                if not isinstance(result, dict):
                    continue
                if str(result.get("status") or "") in {"completed", "deployed"}:
                    slot_results[key] = {
                        **result,
                        "status": "legacy_unconfirmed",
                        "reason": "Legacy wynik bez dowodu fizycznego write/readback; nie wykonuj ponownie",
                    }
        for result in slot_results.values():
            if isinstance(result, dict) and result.get("status") == "physical_pending":
                correlation = result.get("correlation")
                if isinstance(correlation, dict):
                    correlation["physical_write_count_before"] = self._physical_write_count
                    correlation["restored_pending"] = True
        canonical = {
            **plan,
            "intent_schema_version": FUTURE_PLAN_INTENT_SCHEMA_VERSION,
            "lifecycle_schema_version": FUTURE_PLAN_LIFECYCLE_SCHEMA_VERSION,
            "intent_revision": max(1, int(self.safe_float(plan.get("intent_revision"), 1))),
            "authoritative_day": True,
            "replace_day": True,
            "ownership": "optimizer_core_authoritative_day",
            "updates": target,
            "selected_slot_keys": selected_keys,
            "slot_results": slot_results,
            "slot_bases": (
                deepcopy(plan.get("slot_bases"))
                if isinstance(plan.get("slot_bases"), dict)
                else self._future_plan_acceptance_bases()
            ),
            "slot_validations": {
                key: deepcopy(validations[key])
                for key in selected_keys
                if isinstance(validations.get(key), dict)
            },
        }
        if legacy_lifecycle and any(
            isinstance(value, dict) and value.get("status") == "legacy_unconfirmed"
            for value in slot_results.values()
        ):
            canonical["status"] = "legacy_unconfirmed"
        return canonical, canonical != raw_plan

    @staticmethod
    def _plan_execution_key(date_key: str, hour: int) -> str:
        return f"{date_key}:{hour:02d}"

    def _compact_plan_execution_row(
        self,
        row: dict[str, Any],
        plan: dict[str, Any],
        current: datetime,
    ) -> dict[str, Any]:
        """Freeze one optimizer row without exposing the full optimizer payload."""
        date_key = str(row.get("date") or "")
        hour = max(0, min(23, int(self.safe_float(row.get("hour"), 0))))
        current_key = self._plan_execution_key(current.date().isoformat(), current.hour)
        row_key = self._plan_execution_key(date_key, hour)
        dispatch_status = str(row.get("dispatch_status") or "")
        proposal_status = (
            "blocked"
            if dispatch_status == "blocked"
            else "proposed"
            if bool(row.get("proposed"))
            else "skipped"
        )
        return {
            "schema_version": HISTORY_SCHEMA_VERSION,
            "date": date_key,
            "hour": hour,
            "label": str(row.get("label") or f"{hour:02d}:00–{(hour + 1) % 24:02d}:00"),
            "plan_id": str(plan.get("plan_id") or ""),
            "generated_at": str(plan.get("generated_at") or ""),
            "strategy": str(plan.get("strategy") or ""),
            "proposal_status": proposal_status,
            "action": str(row.get("action") or "none"),
            "mode": str(row.get("mode") or ""),
            "profile_id": str(row.get("profile_id") or ""),
            "decision_source": str(row.get("decision_source") or ""),
            "planned_power_w": round(self.safe_float(row.get("planned_power_w"), 0), 2),
            "planned_energy_kwh": round(self.safe_float(row.get("planned_energy_kwh"), 0), 5),
            "soc_start_pct": row.get("soc_start_pct"),
            "soc_end_pct": row.get("soc_end_pct", row.get("soc_after")),
            "hard_min_soc_pct": row.get("hard_min_soc_pct"),
            "effective_min_soc_pct": row.get("effective_min_soc_pct"),
            "solcast_kwh": row.get("solcast_kwh"),
            "corrected_pv_kwh": row.get("corrected_pv_kwh"),
            "forecast_low_kwh": row.get("forecast_low_kwh"),
            "forecast_high_kwh": row.get("forecast_high_kwh"),
            "load_kwh": row.get("load_kwh", row.get("home_load_kwh")),
            "expected_import_kwh": row.get("expected_import_kwh"),
            "expected_export_kwh": row.get("expected_export_kwh"),
            "buy_price": row.get("buy_price"),
            "effective_buy_price": row.get("effective_buy_price"),
            "sell_price": row.get("sell_price"),
            "distribution": row.get("distribution"),
            "net_result_pln": row.get("net_result", row.get("balance_pln")),
            "confidence": row.get("confidence"),
            "confidence_components": deepcopy(row.get("confidence_components") or {}),
            "reason_codes": [str(value) for value in row.get("reason_codes", [])][:12],
            "limit_reason": row.get("limit_reason"),
            "data_quality": deepcopy(row.get("data_quality") or {}),
            "approval_status": "not_selected",
            "deployment_status": "not_deployed",
            "actual_status": "waiting",
            "frozen_at": (
                current.isoformat(timespec="seconds")
                if row_key <= current_key
                else None
            ),
        }

    def _sync_plan_execution_archive(
        self,
        plan: dict[str, Any],
        current: datetime | None = None,
    ) -> bool:
        """Keep the latest future proposal, while never rewriting frozen hours."""
        if not isinstance(plan, dict):
            return False
        current = current or ha_now()
        rows = [row for row in plan.get("rows", []) if isinstance(row, dict)]
        if not rows:
            return False
        existing = {
            self._plan_execution_key(
                str(row.get("date") or ""),
                max(0, min(23, int(self.safe_float(row.get("hour"), 0)))),
            ): dict(row)
            for row in self.plan_execution_archive
            if isinstance(row, dict) and row.get("date")
        }
        current_key = self._plan_execution_key(current.date().isoformat(), current.hour)
        changed = False
        for source in rows:
            compact = self._compact_plan_execution_row(source, plan, current)
            key = self._plan_execution_key(compact["date"], compact["hour"])
            previous = existing.get(key)
            preserve = bool(
                previous
                and (
                    previous.get("frozen_at")
                    or previous.get("approval_status") in {"approved", "cancelled"}
                    or previous.get("deployment_status") in {"deployed", "blocked"}
                    or previous.get("actual")
                    or key < current_key
                )
            )
            if preserve:
                continue
            if previous:
                for lifecycle_key in (
                    "approval_status",
                    "approved_at",
                    "deployment_status",
                    "deployed_at",
                    "deployment_reason",
                    "actual_status",
                    "actual",
                ):
                    if lifecycle_key in previous:
                        compact[lifecycle_key] = deepcopy(previous[lifecycle_key])
            if previous != compact:
                existing[key] = compact
                changed = True
        normalized = sorted(
            existing.values(),
            key=lambda item: (
                str(item.get("date") or ""),
                int(self.safe_float(item.get("hour"), 0)),
            ),
            reverse=True,
        )[:2160]
        if normalized != self.plan_execution_archive:
            self.plan_execution_archive = normalized
            changed = True
        return changed

    def _set_plan_execution_lifecycle(
        self,
        date_key: str,
        slot_key: str,
        **changes: Any,
    ) -> None:
        try:
            hour = int(str(slot_key).split("_", 1)[0])
        except (TypeError, ValueError):
            return
        key = self._plan_execution_key(date_key, hour)
        for row in self.plan_execution_archive:
            if not isinstance(row, dict):
                continue
            if self._plan_execution_key(
                str(row.get("date") or ""),
                int(self.safe_float(row.get("hour"), 0)),
            ) != key:
                continue
            row.update({name: deepcopy(value) for name, value in changes.items()})
            row.setdefault("frozen_at", ha_now().isoformat(timespec="seconds"))
            return
        source = next(
            (
                row for row in self.optimizer_plan.get("rows", [])
                if isinstance(row, dict)
                and str(row.get("date") or "") == date_key
                and int(self.safe_float(row.get("hour"), 0)) == hour
            ),
            None,
        )
        if source is not None:
            row = self._compact_plan_execution_row(
                source,
                self.optimizer_plan,
                ha_now(),
            )
        else:
            row = {
                "schema_version": HISTORY_SCHEMA_VERSION,
                "date": date_key,
                "hour": hour,
                "label": f"{hour:02d}:00–{(hour + 1) % 24:02d}:00",
                "proposal_status": "missing",
                "approval_status": "not_selected",
                "deployment_status": "not_deployed",
                "actual_status": "waiting",
                "frozen_at": ha_now().isoformat(timespec="seconds"),
            }
        row.update({name: deepcopy(value) for name, value in changes.items()})
        self.plan_execution_archive = sorted(
            [row, *self.plan_execution_archive],
            key=lambda item: (
                str(item.get("date") or ""),
                int(self.safe_float(item.get("hour"), 0)),
            ),
            reverse=True,
        )[:2160]

    def _attach_plan_execution_actual(self, completed: dict[str, Any]) -> None:
        """Attach finalized measurements and transparent forecast errors."""
        date_key = str(completed.get("local_date") or "")
        hour = int(self.safe_float(completed.get("local_hour"), 0))
        key = self._plan_execution_key(date_key, hour)
        target = next(
            (
                row for row in self.plan_execution_archive
                if isinstance(row, dict)
                and self._plan_execution_key(
                    str(row.get("date") or ""),
                    int(self.safe_float(row.get("hour"), 0)),
                ) == key
            ),
            None,
        )
        if target is None:
            target = {
                "schema_version": HISTORY_SCHEMA_VERSION,
                "date": date_key,
                "hour": hour,
                "label": f"{hour:02d}:00–{(hour + 1) % 24:02d}:00",
                "proposal_status": "missing",
                "approval_status": "not_selected",
                "deployment_status": "not_deployed",
            }
            self.plan_execution_archive.append(target)
        actual_pv = finite_float(completed.get("pv_kwh"))
        actual_load = finite_float(completed.get("load_kwh"))
        actual_import = finite_float(completed.get("grid_import_kwh"))
        actual_export = finite_float(completed.get("grid_export_kwh"))
        actual_soc = finite_float(completed.get("soc_end"))
        planned_pv = finite_float(target.get("corrected_pv_kwh"))
        planned_load = finite_float(target.get("load_kwh"))
        planned_soc = finite_float(target.get("soc_end_pct"))
        sell_price = finite_float(completed.get("sell_price_avg"))
        buy_price = finite_float(completed.get("buy_price_avg"))
        tariff = completed.get("tariff") if isinstance(completed.get("tariff"), dict) else {}
        distribution = (
            0.0
            if self.price_contract("buy").get("includes_distribution_variable") is True
            else self.safe_float(tariff.get("distribution_rate"), 0)
        )
        net_result = (
            actual_export * sell_price
            - actual_import * (buy_price + distribution)
            if actual_export is not None
            and actual_import is not None
            and sell_price is not None
            and buy_price is not None
            else None
        )
        target["actual"] = {
            "pv_kwh": round(actual_pv, 5) if actual_pv is not None else None,
            "load_kwh": round(actual_load, 5) if actual_load is not None else None,
            "grid_import_kwh": round(actual_import, 5) if actual_import is not None else None,
            "grid_export_kwh": round(actual_export, 5) if actual_export is not None else None,
            "battery_charge_kwh": (
                round(value, 5)
                if (value := finite_float(completed.get("battery_charge_kwh"))) is not None
                else None
            ),
            "battery_discharge_kwh": (
                round(value, 5)
                if (value := finite_float(completed.get("battery_discharge_kwh"))) is not None
                else None
            ),
            "soc_end_pct": actual_soc,
            "sell_price_pln_kwh": round(sell_price, 5) if sell_price is not None else None,
            "buy_price_pln_kwh": round(buy_price, 5) if buy_price is not None else None,
            "net_result_pln": round(net_result, 5) if net_result is not None else None,
            "complete": bool(completed.get("complete")),
            "completeness_percent": completed.get("completeness_percent"),
            "source_quality": deepcopy(completed.get("source_quality") or {}),
        }
        target["errors"] = {
            "pv_kwh": (
                None
                if planned_pv is None or actual_pv is None
                else round(actual_pv - planned_pv, 5)
            ),
            "load_kwh": (
                None
                if planned_load is None or actual_load is None
                else round(actual_load - planned_load, 5)
            ),
            "soc_pct": (
                None
                if planned_soc is None or actual_soc is None
                else round(actual_soc - planned_soc, 3)
            ),
            "pv_percent": (
                None
                if planned_pv is None or actual_pv is None or abs(planned_pv) < 0.05
                else round((actual_pv - planned_pv) / abs(planned_pv) * 100, 1)
            ),
            "load_percent": (
                None
                if planned_load is None or actual_load is None or abs(planned_load) < 0.05
                else round((actual_load - planned_load) / abs(planned_load) * 100, 1)
            ),
        }
        target["actual_status"] = (
            "completed" if completed.get("complete") else "partial"
        )
        target["frozen_at"] = target.get("frozen_at") or ha_now().isoformat(timespec="seconds")
        self.plan_execution_archive = sorted(
            self.plan_execution_archive,
            key=lambda item: (
                str(item.get("date") or ""),
                int(self.safe_float(item.get("hour"), 0)),
            ),
            reverse=True,
        )[:2160]

    def plan_execution_day(self, date_key: str | None = None) -> dict[str, Any]:
        """Return a read-only, compact plan-versus-execution view for one day."""
        selected_date = str(date_key or ha_now().date().isoformat())
        try:
            selected_date = datetime.fromisoformat(selected_date).date().isoformat()
        except (TypeError, ValueError) as err:
            raise ValueError("Data musi mieć format RRRR-MM-DD") from err
        rows = sorted(
            [
                deepcopy(row)
                for row in self.plan_execution_archive
                if isinstance(row, dict) and row.get("date") == selected_date
            ],
            key=lambda row: int(self.safe_float(row.get("hour"), 0)),
        )
        actual_rows = [row for row in rows if isinstance(row.get("actual"), dict)]
        sum_field = lambda source, name: round(
            sum(self.safe_float(item.get(name), 0) for item in source),
            4,
        )
        actual_values = [row["actual"] for row in actual_rows]
        error_values = [
            abs(value)
            for row in rows
            if isinstance(row.get("errors"), dict)
            and (value := finite_float(row["errors"].get("pv_percent"))) is not None
        ]
        return {
            "schema_version": HISTORY_SCHEMA_VERSION,
            "date": selected_date,
            "rows": rows,
            "summary": {
                "hours_planned": len(rows),
                "hours_measured": len(actual_rows),
                "planned_pv_kwh": sum_field(rows, "corrected_pv_kwh") if rows else None,
                "actual_pv_kwh": sum_field(actual_values, "pv_kwh") if actual_rows else None,
                "planned_load_kwh": sum_field(rows, "load_kwh") if rows else None,
                "actual_load_kwh": sum_field(actual_values, "load_kwh") if actual_rows else None,
                "planned_import_kwh": sum_field(rows, "expected_import_kwh") if rows else None,
                "actual_import_kwh": sum_field(actual_values, "grid_import_kwh") if actual_rows else None,
                "planned_export_kwh": sum_field(rows, "expected_export_kwh") if rows else None,
                "actual_export_kwh": sum_field(actual_values, "grid_export_kwh") if actual_rows else None,
                "planned_result_pln": sum_field(rows, "net_result_pln") if rows else None,
                "actual_result_pln": sum_field(actual_values, "net_result_pln") if actual_rows else None,
                "pv_mean_absolute_percent_error": (
                    round(sum(error_values) / len(error_values), 1)
                    if error_values
                    else None
                ),
            },
        }

    def plan_execution_index(self) -> dict[str, Any]:
        dates = sorted(
            {
                str(row.get("date"))
                for row in self.plan_execution_archive
                if isinstance(row, dict) and row.get("date")
            },
            reverse=True,
        )
        return {
            "schema_version": HISTORY_SCHEMA_VERSION,
            "available_dates": dates[:90],
            "retention_days": 90,
            "stored_hours": len(self.plan_execution_archive),
        }

    async def async_save_future_plan(self, payload: dict[str, Any]) -> None:
        """Persist an accepted authoritative target for the next calendar day."""
        if not isinstance(payload, dict):
            raise ValueError("Plan na jutro musi być obiektem")
        optimizer_quality = (
            self.optimizer_plan.get("data_quality", {})
            if isinstance(self.optimizer_plan, dict)
            else {}
        )
        learning_summary = self.learning_summary()
        maturity_contract = learning_summary.get("learning_maturity", {})
        readiness = (
            self.optimizer_plan.get("execution_readiness", {})
            if isinstance(self.optimizer_plan, dict)
            else {}
        )
        tomorrow_readiness = (
            (readiness.get("by_day") or {}).get("tomorrow", {})
            if isinstance(readiness, dict) and isinstance(readiness.get("by_day"), dict)
            else {}
        )
        if (
            maturity_contract.get("application_ready") is False
            or optimizer_quality.get("learning_apply_allowed") is False
            or (
                isinstance(tomorrow_readiness, dict)
                and tomorrow_readiness
                and tomorrow_readiness.get("status") != "confirmable"
            )
        ):
            raise ValueError(
                "Plan na jutro nie ma statusu „Gotowy do potwierdzenia” (dry-run/podgląd); "
                "można go analizować, ale nie można go wdrożyć"
            )
        expected_date = (ha_now().date() + timedelta(days=1)).isoformat()
        plan_date = str(payload.get("date") or "")
        if plan_date != expected_date:
            raise ValueError(f"Plan można zapisać wyłącznie na jutro ({expected_date})")
        if payload.get("replace_day") is False:
            raise ValueError("FuturePlan na jutro wymaga autorytatywnego replace_day=true")
        updates, selected_keys = self._build_authoritative_future_plan_updates(
            payload.get("updates")
        )
        supplied_validations = (
            payload.get("slot_validations")
            if isinstance(payload.get("slot_validations"), dict)
            else {}
        )
        previous_plan = self.future_plan if isinstance(self.future_plan, dict) else {}
        superseded_plans = list(previous_plan.get("superseded_plans") or [])[-4:]
        intent_revision = 1
        if previous_plan and str(previous_plan.get("date") or "") == plan_date:
            intent_revision = max(
                1, int(self.safe_float(previous_plan.get("intent_revision"), 1)) + 1
            )
            superseded_plans.append({
                "plan_id": str(previous_plan.get("plan_id") or ""),
                "date": plan_date,
                "status": "superseded",
                "superseded_at": ha_now().isoformat(timespec="seconds"),
            })
            for old_key in previous_plan.get("selected_slot_keys") or []:
                self._set_plan_execution_lifecycle(
                    plan_date, str(old_key), approval_status="superseded",
                    deployment_status="superseded",
                    deployment_reason="Zastąpiono nowszą akceptacją FuturePlan",
                )
        created_at = ha_now().isoformat(timespec="seconds")
        self.future_plan = {
            "plan_id": str(payload.get("plan_id") or ""),
            "date": plan_date,
            "status": "scheduled",
            "created_at": created_at,
            "updated_at": created_at,
            "strategy": str(payload.get("strategy") or "balanced"),
            "intent_schema_version": FUTURE_PLAN_INTENT_SCHEMA_VERSION,
            "lifecycle_schema_version": FUTURE_PLAN_LIFECYCLE_SCHEMA_VERSION,
            "intent_revision": intent_revision,
            "authoritative_day": True,
            "replace_day": True,
            "ownership": "optimizer_core_authoritative_day",
            "updates": updates,
            "selected_slot_keys": selected_keys,
            "slot_validations": {
                key: deepcopy(supplied_validations[key])
                for key in selected_keys
                if isinstance(supplied_validations.get(key), dict)
            },
            "slot_results": {
                str(update["slot_key"]): {
                    "status": "approved",
                    "approved_at": created_at,
                    "intent_revision": intent_revision,
                }
                for update in updates
            },
            "slot_bases": self._future_plan_acceptance_bases(),
            "superseded_plans": superseded_plans[-5:],
            "labels": [str(value) for value in payload.get("labels", []) if value is not None][:24],
        }
        approved_at = self.future_plan["created_at"]
        for slot_key in selected_keys:
            self._set_plan_execution_lifecycle(
                plan_date,
                slot_key,
                approval_status="approved",
                approved_at=approved_at,
                approved_plan_id=self.future_plan["plan_id"],
            )
        for validation in self.future_plan["slot_validations"].values():
            if not isinstance(validation, dict):
                continue
            profile_id = str(validation.get("profile_id") or "")
            if profile_id:
                self._set_profile_execution_status(
                    profile_id,
                    plan_date,
                    "waiting",
                    plan_id=self.future_plan["plan_id"],
                )
        await self.async_add_ai_analysis({
            "timestamp": int(ha_now().timestamp() * 1000),
            "event": "future_plan_scheduled",
            "date": plan_date,
            "selected_hours": self.future_plan["labels"],
        })
        await self.async_save_ai_data()
        await self.async_save_learning_history()
        self.request_optimizer_recalc("future_plan")
        self._notify_update_for("future_plan")

    async def async_cancel_future_plan(self, reason: str = "Anulowano przez użytkownika") -> None:
        if not self.future_plan:
            return
        plan_date = str(self.future_plan.get("date") or ha_now().date().isoformat())
        selected_keys = self.future_plan.get("selected_slot_keys")
        if not isinstance(selected_keys, list):
            selected_keys = [
                str(update.get("slot_key") or "")
                for update in self.future_plan.get("updates", [])
                if isinstance(update, dict)
                and normalize_manager_mode(str(update.get("mode") or ""))
                in {MODE_SELLING_FIRST, MODE_CHARGE}
            ]
        for slot_key in selected_keys:
            self._set_plan_execution_lifecycle(
                plan_date,
                str(slot_key or ""),
                approval_status="cancelled",
                deployment_status="cancelled",
                deployment_reason=reason,
            )
        validations = self.future_plan.get("slot_validations")
        if isinstance(validations, dict):
            for validation in validations.values():
                if not isinstance(validation, dict):
                    continue
                profile_id = str(validation.get("profile_id") or "")
                if profile_id:
                    self._set_profile_execution_status(
                        profile_id,
                        plan_date,
                        "cancelled",
                        failure_reason=reason,
                        plan_id=str(self.future_plan.get("plan_id") or ""),
                    )
        self.future_plan = {
            **self.future_plan,
            "status": "cancelled",
            "cancelled_at": ha_now().isoformat(timespec="seconds"),
            "reason": reason,
        }
        await self.async_save_ai_data()
        await self.async_save_learning_history()
        self.request_optimizer_recalc("future_plan")
        self._notify_update_for("future_plan")

    async def async_process_future_plan(self) -> None:
        """Revalidate and apply only the accepted slot that is starting now."""
        current_time = ha_now()
        await self._async_cleanup_future_plan_slots(current_time)
        plan = self.future_plan
        if not plan or plan.get("status") not in {"scheduled", "partial"}:
            return
        today = current_time.date().isoformat()
        plan_date = str(plan.get("date") or "")
        if plan_date > today:
            return
        if plan_date < today:
            results = dict(plan.get("slot_results") or {})
            terminal = {"confirmed", "blocked", "missed", "manual_override", "superseded", "cancelled", "legacy_unconfirmed"}
            for update in plan.get("updates") or []:
                if not isinstance(update, dict):
                    continue
                key = str(update.get("slot_key") or "")
                if str((results.get(key) or {}).get("status") or "") not in terminal:
                    results[key] = {
                        "status": "missed",
                        "reason": "Datowany slot wygasł; brak catch-up",
                        "resolved_at": current_time.isoformat(timespec="seconds"),
                    }
            self.future_plan = {
                **plan, "status": self._future_plan_overall_status(results),
                "slot_results": results,
                "updated_at": current_time.isoformat(timespec="seconds"),
            }
            await self.async_save_ai_data()
            return
        current_slot_key = f"{current_time.hour:02d}_{(current_time.hour + 1) % 24:02d}"
        profile_id = ""
        execution_stage = "validation"
        slot_results = dict(plan.get("slot_results") or {})
        try:
            updates = self._validate_future_plan_updates(plan.get("updates"))
            results_changed = False
            terminal_statuses = {
                "confirmed", "blocked", "missed", "manual_override",
                "superseded", "cancelled", "legacy_unconfirmed",
            }
            for update in updates:
                slot_key = str(update.get("slot_key") or "")
                start_hour = int(slot_key.split("_", 1)[0])
                previous_result = slot_results.get(slot_key, {})
                if (
                    start_hour < current_time.hour
                    and str(previous_result.get("status") or "") not in terminal_statuses
                ):
                    reason = "Slot minął, gdy Home Assistant nie wykonał zaakceptowanego planu"
                    slot_results[slot_key] = {
                        "status": "missed",
                        "reason": reason,
                        "resolved_at": current_time.isoformat(timespec="seconds"),
                    }
                    self._set_plan_execution_lifecycle(
                        plan_date,
                        slot_key,
                        deployment_status="missed",
                        deployed_at=None,
                        deployment_reason=reason,
                    )
                    results_changed = True
            current_update = next(
                (item for item in updates if item.get("slot_key") == current_slot_key),
                None,
            )
            current_result = slot_results.get(current_slot_key, {})
            if current_update is None or str(current_result.get("status") or "") in terminal_statuses:
                if results_changed:
                    has_problem = any(
                        str(item.get("status") or "") in {"missed", "blocked"}
                        for item in slot_results.values()
                        if isinstance(item, dict)
                    )
                    pending = any(
                        int(str(item.get("slot_key")).split("_", 1)[0]) > current_time.hour
                        and str(slot_results.get(str(item.get("slot_key")), {}).get("status") or "")
                        not in terminal_statuses
                        for item in updates
                    )
                    self.future_plan = {
                        **plan,
                        "status": "partial" if has_problem else "scheduled" if pending else "completed",
                        "slot_results": slot_results,
                        "updated_at": current_time.isoformat(timespec="seconds"),
                    }
                    await self.async_save_ai_data()
                    await self.async_save_learning_history()
                    self.notify_update()
                return
            if str(current_result.get("status") or "") in {"logical_applied", "physical_pending"}:
                # The existing manager tick/reconcile path owns the physical
                # transaction. Do not rewrite or create a second transaction.
                return
            if self._future_plan_manual_conflict(plan, current_slot_key):
                reason = "Zastąpione ręcznie po akceptacji FuturePlan — MANUAL WINS"
                slot_results[current_slot_key] = {
                    "status": "manual_override",
                    "reason": reason,
                    "resolved_at": current_time.isoformat(timespec="seconds"),
                }
                self._set_plan_execution_lifecycle(
                    plan_date, current_slot_key,
                    deployment_status="manual_override", deployed_at=None,
                    deployment_reason=reason,
                )
                self.future_plan = {
                    **plan, "status": "partial", "slot_results": slot_results,
                    "updated_at": current_time.isoformat(timespec="seconds"),
                }
                await self.async_save_ai_data()
                await self.async_save_learning_history()
                self._notify_update_for("future_plan")
                return
            validation = (
                plan.get("slot_validations", {}).get(current_slot_key, {})
                if isinstance(plan.get("slot_validations"), dict)
                else {}
            )
            validation = validation if isinstance(validation, dict) else {}
            profile_id = str(validation.get("profile_id") or "")
            selling = current_update.get("mode") == MODE_SELLING_FIRST
            charging = current_update.get("mode") == MODE_CHARGE
            minimum_soc = self.safe_float(
                validation.get("minimum_soc", current_update.get("minimum_sell_soc")),
                0,
            )
            minimum_price = self.safe_float(
                validation.get("minimum_price", current_update.get("min_sell_price")),
                0,
            )
            selling_needing_soc = selling and minimum_soc > 0
            selling_needing_price = selling and (
                "minimum_price" in validation or "min_sell_price" in current_update
            )
            if selling_needing_soc and self.current_soc_or_none() is None:
                raise FuturePlanTransientError("oczekiwanie na aktualny, wiarygodny SOC")
            if selling_needing_price and self.state_float_or_none(self.price_sensor) is None:
                raise FuturePlanTransientError("oczekiwanie na aktualną cenę sprzedaży")
            current_soc = self.current_soc_or_none()
            current_price = self.state_float_or_none(self.price_sensor)
            if (
                selling_needing_soc
                and current_soc is not None
                and current_soc <= minimum_soc
            ):
                raise RuntimeError("aktualny SOC nie pozwala bezpiecznie rozpocząć slotu")
            if (
                selling_needing_price
                and current_price is not None
                and current_price + 1e-9 < minimum_price
            ):
                raise RuntimeError("aktualna cena jest niższa od minimalnej ceny profilu")
            if not self.data_available:
                raise FuturePlanTransientError("falownik lub wymagana encja sterująca jest chwilowo niedostępna")
            if (
                charging
                and validation.get("charge_source") in ("grid", "pv_and_grid")
                and not self.entity_available(self.grid_power_sensor)
            ):
                raise FuturePlanTransientError("oczekiwanie na wiarygodny odczyt stanu sieci")
            planned_power = self.safe_float(
                current_update.get("sell_power", validation.get("power_limit_w")),
                0,
            )
            allowed_power = self.safe_float(validation.get("power_limit_w"), 0)
            if allowed_power > 0 and planned_power > allowed_power + 1e-6:
                raise RuntimeError("moc slotu przekracza aktualny limit profilu lub falownika")
            effective_buy_price = None
            if charging:
                tariff = self.tariff_context(current_time)
                canonical = self.canonical_price_context(
                    current_time,
                    [row for row in tariff.get("hourly_profile", [])[:48] if isinstance(row, dict)],
                )
                price_row = next((
                    row
                    for row in canonical.get("buy", {}).get("rows", [])
                    if row.get("date") == current_time.date().isoformat()
                    and row.get("hour") == current_time.hour
                    and row.get("quality") == "ready"
                ), None)
                effective_buy_price = finite_float(
                    price_row.get("final_price_pln_kwh") if price_row else None
                )
                maximum_effective_price = self.safe_float(
                    validation.get("maximum_effective_price"),
                    0,
                )
                if maximum_effective_price > 0:
                    if effective_buy_price is None:
                        raise FuturePlanTransientError("oczekiwanie na aktualną cenę zakupu")
                    if effective_buy_price > maximum_effective_price + 1e-9:
                        raise RuntimeError(
                            "efektywny koszt zakupu z OSD przekracza limit profilu"
                        )
            if validation.get("deadline"):
                deadline_hour = int(str(validation["deadline"]).split(":", 1)[0])
                if current_time.hour >= deadline_hour and not bool(validation.get("deadline_next_day")):
                    raise RuntimeError("minął termin realizacji profilu")
            execution = next(
                (
                    item
                    for item in reversed(self.profile_execution)
                    if isinstance(item, dict)
                    and str(item.get("profile_id") or "") == profile_id
                    and str(item.get("date") or "") == plan_date
                ),
                None,
            )
            executed_energy = self.safe_float(
                execution.get("executed_kwh", execution.get("actual_energy_kwh"))
                if execution else 0,
                0,
            )
            remaining_target = self.safe_float(
                execution.get("remaining_kwh")
                if execution else validation.get("remaining_target_kwh"),
                0,
            )
            target_energy = self.safe_float(validation.get("target_energy_kwh"), 0)
            if profile_id and target_energy > 0 and remaining_target <= 1e-6:
                raise RuntimeError("cel profilu został już wykonany")
            possible_remaining = max(
                0.0,
                self.safe_float(validation.get("possible_energy_kwh"), 0)
                - executed_energy,
            )
            if (
                not bool(validation.get("allow_partial", True))
                and possible_remaining + 1e-6 < remaining_target
            ):
                raise RuntimeError("pełny pozostały cel profilu nie jest już możliwy")
            planned_energy = max(
                0.0,
                self.safe_float(validation.get("planned_energy_kwh"), 0),
            )
            planned_price = self.safe_float(validation.get("planned_price"), 0)
            revalidated_result = self.safe_float(
                validation.get("profile_net_result_pln"),
                0,
            )
            if selling and current_price is not None:
                revalidated_result += (current_price - planned_price) * planned_energy
            elif charging and effective_buy_price is not None:
                revalidated_result -= (effective_buy_price - planned_price) * planned_energy
            if revalidated_result + 1e-6 < self.safe_float(validation.get("min_net_result"), 0):
                raise RuntimeError("wynik netto profilu spadł poniżej wymaganego minimum")
            if (
                selling
                and bool(validation.get("allow_partial", True))
                and remaining_target > 1e-6
                and planned_energy > remaining_target
            ):
                duration = max(
                    1.0,
                    self.safe_float(validation.get("duration_minutes"), 60),
                )
                current_update = {
                    **current_update,
                    "sell_power": min(
                        self.safe_float(current_update.get("sell_power"), 0),
                        round(remaining_target * 1000 * 60 / duration),
                    ),
                }
            if (
                current_update.get("mode") == MODE_CHARGE
                and current_soc is not None
                and validation.get("max_soc_before_pv_pct") is not None
                and current_soc >= self.safe_float(validation.get("max_soc_before_pv_pct"), 100)
            ):
                raise RuntimeError("brak wymaganego miejsca na prognozowaną produkcję PV")
            if profile_id:
                self._set_profile_execution_status(
                    profile_id,
                    plan_date,
                    "running",
                    plan_id=str(plan.get("plan_id") or ""),
                )
            execution_stage = "write"
            execution_update = (
                self._sanitize_ai_sell_execution_update(current_update)
                if selling
                else current_update
            )
            intent_revision = int(self.safe_float(plan.get("intent_revision"), 1))
            writes_before = self._physical_write_count
            await self.async_apply_schedule_patch(
                [execution_update], ai_source=True,
                change_source="future_plan",
                source_context={
                    "plan_id": str(plan.get("plan_id") or ""),
                    "target_date": plan_date,
                    "intent_revision": intent_revision,
                },
            )
            expected_physical = {
                "System Work Mode": self.target_mode,
                "Max Sell Power": self.applied_sell_power,
                "Prąd rozładowania": self.target_discharge_current,
                "Prąd ładowania baterii": self.target_charge_current,
                "Prąd ładowania z sieci": (
                    self.active_slot.grid_charge_current
                    if self.active_charge_slot
                    else self.default_grid_charge_current
                ),
            }
            next_lifecycle = (
                "physical_pending"
                if self._control_is_active() and not self.emergency_stop
                else "logical_applied"
            )
            self._set_plan_execution_lifecycle(
                plan_date,
                current_slot_key,
                deployment_status=next_lifecycle,
                deployed_at=None,
                deployment_reason="Logical target zapisany; oczekiwanie na physical write/readback",
            )
            slot_results[current_slot_key] = {
                "status": next_lifecycle,
                "validated_at": current_time.isoformat(timespec="seconds"),
                "logical_applied_at": current_time.isoformat(timespec="seconds"),
                "correlation": {
                    "plan_id": str(plan.get("plan_id") or ""),
                    "target_date": plan_date,
                    "slot_key": current_slot_key,
                    "intent_revision": intent_revision,
                    "schedule_revision": int(self.schedule_slot_revisions.get(current_slot_key, 0)),
                    "physical_write_count_before": writes_before,
                    "expected_fingerprint": snapshot_id(expected_physical),
                },
            }
            pending = [
                item
                for item in updates
                if item.get("slot_key") not in slot_results
                and int(str(item.get("slot_key")).split("_", 1)[0]) > current_time.hour
            ]
            self.future_plan = {
                **plan,
                "status": self._future_plan_overall_status(slot_results),
                "slot_results": slot_results,
                "updated_at": current_time.isoformat(timespec="seconds"),
            }
            await self.async_add_ai_analysis({
                "timestamp": int(ha_now().timestamp() * 1000),
                "event": "future_plan_slot_logical_applied",
                "date": plan_date,
                "slot_key": current_slot_key,
            })
            await self.async_save_ai_data()
            await self.async_save_learning_history()
        except FuturePlanTransientError as err:
            self._set_plan_execution_lifecycle(
                plan_date,
                current_slot_key,
                deployment_status="waiting_data",
                deployed_at=None,
                deployment_reason=str(err),
            )
            slot_results[current_slot_key] = {
                "status": "waiting_data",
                "reason": str(err),
                "last_attempt_at": ha_now().isoformat(timespec="seconds"),
            }
            has_problem = any(
                item.get("status") in {"blocked", "missed"}
                for item in slot_results.values()
                if isinstance(item, dict)
            )
            self.future_plan = {
                **plan,
                "status": "partial" if has_problem else "scheduled",
                "slot_results": slot_results,
                "updated_at": ha_now().isoformat(timespec="seconds"),
                "reason": str(err),
            }
            await self.async_save_ai_data()
            await self.async_save_learning_history()
        except Exception as err:
            self._set_plan_execution_lifecycle(
                plan_date,
                current_slot_key,
                deployment_status="blocked",
                deployed_at=None,
                deployment_reason=str(err),
            )
            if profile_id:
                self._set_profile_execution_status(
                    profile_id,
                    plan_date,
                    "failed" if execution_stage == "write" else "blocked",
                    failure_reason=str(err),
                    plan_id=str(plan.get("plan_id") or ""),
                )
            self.future_plan = {
                **plan,
                "status": "partial",
                "slot_results": {
                    **slot_results,
                    current_slot_key: {
                        "status": "blocked",
                        "reason": str(err),
                        "validated_at": ha_now().isoformat(timespec="seconds"),
                    },
                },
                "failed_at": ha_now().isoformat(timespec="seconds"),
                "reason": str(err),
            }
            await self.async_save_ai_data()
            await self.async_save_learning_history()
        self.request_optimizer_recalc("future_plan")
        self.notify_update()

    async def async_clear_all_history(self) -> None:
        self.ai_history = []
        self.solcast_history = []
        self.solcast_tracking = {}
        self.learning_history = []
        self.learning_tracking = {}
        self.energy_samples = []
        self._energy_recent_details = []
        self._energy_revision += 1
        self.daily_archive = []
        self.monthly_archive = []
        self.energy_counter_state = {}
        self.load_profile_7x24 = {}
        self.pv_learning_profile = {}
        self.profile_execution = []
        self._profile_execution_revision += 1
        self.plan_execution_archive = []
        self._invalidate_learning_summary_cache()
        await self.async_save_ai_data()
        await self.async_save_solcast_history()
        await self.async_save_learning_history()
        await self.async_save_energy_history()
        self.request_optimizer_recalc("learning")
        self._notify_update_for("learning")

    async def async_load_solcast_history(self) -> None:
        self._solcast_store = Store(self.hass, 1, f"{DOMAIN}_{self.entry_id}_solcast_history")
        raw = await self._solcast_store.async_load()
        data, migrated = migrate_solcast_payload(raw)
        history = data.get("history")
        tracking = data.get("tracking")
        self.solcast_history = history[:1825] if isinstance(history, list) else []
        self.solcast_tracking = tracking if isinstance(tracking, dict) else {}
        self._invalidate_learning_summary_cache()
        if migrated:
            await self.async_save_solcast_history()

    async def async_save_solcast_history(self) -> None:
        if self._solcast_store is None:
            return
        await self._solcast_store.async_save({
            "schema_version": HISTORY_SCHEMA_VERSION,
            "history": self.solcast_history[:1825],
            "tracking": self.solcast_tracking,
        })

    async def async_update_solcast_history(self) -> None:
        now = ha_now()
        today = now.date().isoformat()
        forecast_reading = self.solcast_forecast_today_reading()
        forecast = max(0, self.safe_float(forecast_reading.get("value"), 0))
        actual = max(0, self.state_float(self.daily_pv_production_sensor, 0))
        summary_tracking_before = (
            self.solcast_tracking.get("forecast"),
            self.solcast_tracking.get("initial_forecast_kwh"),
            self.solcast_tracking.get("latest_forecast_kwh"),
            self.solcast_tracking.get("actual"),
        )
        tracked_day = str(self.solcast_tracking.get("date") or "")
        try:
            valid_tracked_day = (
                datetime.strptime(tracked_day, "%Y-%m-%d").date().isoformat()
                if tracked_day
                else ""
            )
        except ValueError:
            valid_tracked_day = ""
        if valid_tracked_day > today:
            valid_tracked_day = ""
        missing_day = not valid_tracked_day
        tracked_day = valid_tracked_day
        changed_day = bool(tracked_day and tracked_day != today)
        if changed_day:
            previous_forecast = self.safe_float(
                self.solcast_tracking.get("initial_forecast_kwh", self.solcast_tracking.get("forecast")),
                0,
            )
            previous_latest = self.safe_float(
                self.solcast_tracking.get("latest_forecast_kwh", self.solcast_tracking.get("forecast")),
                previous_forecast,
            )
            previous_actual = self.safe_float(self.solcast_tracking.get("actual"), 0)
            # Do not turn a missing/invalid forecast into a completed accuracy
            # day. The tracker still rolls forward and existing history stays.
            if previous_forecast > 0:
                error = previous_actual - previous_forecast
                error_percent = error / previous_forecast * 100
                accuracy = max(0, 100 - abs(error_percent))
                sales = self.sales_stats.get("daily", {}).get(tracked_day, {})
                for item in self.ai_history:
                    timestamp = self.safe_float(item.get("timestamp"), 0)
                    item_day = datetime.fromtimestamp(timestamp / 1000, tz=now.tzinfo).date().isoformat() if timestamp > 0 else ""
                    if item.get("event") == "accepted" and item_day == tracked_day and not item.get("outcome"):
                        item["outcome"] = {
                            "sold_kwh": round(self.safe_float(sales.get("kwh"), 0), 3),
                            "sold_value": round(self.safe_float(sales.get("value"), 0), 2),
                            "pv_accuracy_percent": round(accuracy, 1),
                        }
                        item["evaluated_at"] = int(now.timestamp() * 1000)
                self.solcast_history = [{
                    "date": tracked_day,
                    "forecast_kwh": round(previous_forecast, 3),
                    "initial_forecast_kwh": round(previous_forecast, 3),
                    "latest_forecast_kwh": round(previous_latest, 3),
                    "forecast_snapshots": list(self.solcast_tracking.get("forecast_snapshots") or []),
                    "actual_kwh": round(previous_actual, 3),
                    "error_kwh": round(error, 3),
                    "error_percent": round(error_percent, 1),
                    "accuracy_percent": round(accuracy, 1),
                    "day_complete": True,
                }, *[row for row in self.solcast_history if row.get("date") != tracked_day]][:1825]
                self._invalidate_learning_summary_cache()
                await self.async_add_ai_analysis({
                    "timestamp": int(now.timestamp() * 1000),
                    "event": "daily_summary",
                    "date": tracked_day,
                    "forecast_kwh": round(previous_forecast, 3),
                    "actual_kwh": round(previous_actual, 3),
                    "accuracy_percent": round(accuracy, 1),
                })
            self.solcast_tracking = {}
        if missing_day or not self.solcast_tracking:
            preserved_snapshots = [
                dict(row)
                for row in (self.solcast_tracking.get("forecast_snapshots") or [])[-72:]
                if isinstance(row, dict)
            ]
            self.solcast_tracking = {
                "date": today,
                "forecast": forecast,
                "initial_forecast_kwh": forecast if forecast > 0 else None,
                "latest_forecast_kwh": forecast if forecast > 0 else None,
                "forecast_snapshots": preserved_snapshots,
                "actual": actual,
                "updated_at": now.isoformat(),
                "forecast_status": forecast_reading.get("status"),
                "forecast_source": forecast_reading.get("entity_id"),
                "forecast_last_updated": forecast_reading.get("last_updated"),
            }
        else:
            if self.safe_float(self.solcast_tracking.get("initial_forecast_kwh"), 0) <= 0 and forecast > 0:
                self.solcast_tracking["initial_forecast_kwh"] = forecast
                self.solcast_tracking["forecast"] = forecast
            if forecast > 0:
                self.solcast_tracking["latest_forecast_kwh"] = forecast
            self.solcast_tracking["actual"] = actual
            self.solcast_tracking["updated_at"] = now.isoformat()
            self.solcast_tracking["forecast_status"] = forecast_reading.get("status")
            self.solcast_tracking["forecast_source"] = forecast_reading.get("entity_id")
            self.solcast_tracking["forecast_last_updated"] = forecast_reading.get("last_updated")
        snapshots = self.solcast_tracking.setdefault("forecast_snapshots", [])
        snapshot_hour = now.replace(minute=0, second=0, microsecond=0).isoformat()
        if forecast > 0 and not any(str(row.get("timestamp")) == snapshot_hour for row in snapshots if isinstance(row, dict)):
            snapshots.append({"timestamp": snapshot_hour, "forecast_kwh": round(forecast, 3)})
            self.solcast_tracking["forecast_snapshots"] = snapshots[-72:]
        summary_tracking_after = (
            self.solcast_tracking.get("forecast"),
            self.solcast_tracking.get("initial_forecast_kwh"),
            self.solcast_tracking.get("latest_forecast_kwh"),
            self.solcast_tracking.get("actual"),
        )
        if summary_tracking_after != summary_tracking_before:
            self._invalidate_learning_summary_cache()
        if changed_day or missing_day or now.minute % 15 == 0:
            await self.async_save_solcast_history()

    async def async_load_learning_history(self) -> None:
        self._learning_store = Store(self.hass, 1, f"{DOMAIN}_{self.entry_id}_learning_history")
        raw = await self._learning_store.async_load()
        data, migrated = migrate_learning_payload(raw)
        history = data.get("history")
        tracking = data.get("tracking")
        self.learning_history = history[:17520] if isinstance(history, list) else []
        self.learning_tracking = tracking if isinstance(tracking, dict) else {}
        self.learning_revision = max(0, int(finite_float(data.get("learning_revision")) or 0))
        self.history_watermark = str(data.get("history_watermark") or "")
        self.load_profile_7x24 = data.get("load_profile_7x24") if isinstance(data.get("load_profile_7x24"), dict) else {}
        self.pv_learning_profile = data.get("pv_profile") if isinstance(data.get("pv_profile"), dict) else {}
        self.profile_execution = data.get("profile_execution")[:17520] if isinstance(data.get("profile_execution"), list) else []
        self._profile_execution_revision += 1
        if migrated:
            self._rebuild_learning_profiles_from_history()
            await self.async_save_learning_history()
        else:
            self._learning_last_saved_fingerprint = snapshot_id(
                self._learning_store_fingerprint_payload()
            )
        self._invalidate_learning_summary_cache()

    def _rebuild_learning_profiles_from_history(self) -> None:
        """Relearn canonical profiles once after migration to per-channel quality."""
        load_profile: dict[str, Any] = {}
        pv_profile: dict[str, Any] = {}
        for row in reversed(self.learning_history):
            if not isinstance(row, dict):
                continue
            try:
                moment = datetime.fromisoformat(str(row.get("hour")))
            except (TypeError, ValueError):
                continue
            channels = row.get("channel_quality") if isinstance(row.get("channel_quality"), dict) else {}
            load_quality = channels.get("load") if isinstance(channels.get("load"), dict) else {}
            pv_quality = channels.get("pv") if isinstance(channels.get("pv"), dict) else {}
            load_profile = update_load_profile(
                load_profile,
                moment=moment,
                load_kwh=finite_float(row.get("load_kwh")),
                complete=load_quality.get("level") == "full",
                quality_score=self.safe_float(load_quality.get("quality_score"), 0),
                completeness_percent=self.safe_float(load_quality.get("coverage_percent"), 0),
            )
            pv_profile = update_pv_profile(
                pv_profile,
                moment=moment,
                forecast_kwh=finite_float(row.get("forecast_hourly_snapshot_kwh")),
                actual_kwh=finite_float(row.get("pv_kwh")),
                flags=dict(row.get("quality_flags") or {}),
                complete=pv_quality.get("level") == "full",
                quality_score=self.safe_float(pv_quality.get("quality_score"), 0),
                completeness_percent=self.safe_float(pv_quality.get("coverage_percent"), 0),
            )
        self.load_profile_7x24 = load_profile
        self.pv_learning_profile = pv_profile

    def _learning_store_payload(self) -> dict[str, Any]:
        """Build the latest learning payload only when persistence is requested."""
        return {
            "schema_version": HISTORY_SCHEMA_VERSION,
            "history": self.learning_history[:17520],
            "tracking": self.learning_tracking,
            "load_profile_7x24": self.load_profile_7x24,
            "pv_profile": self.pv_learning_profile,
            "profile_execution": self.profile_execution[:17520],
            "learning_revision": self.learning_revision,
            "history_watermark": self.history_watermark,
        }

    def _learning_store_fingerprint_payload(self) -> dict[str, Any]:
        """Bound change detection to revision markers, not multi-year payloads."""
        latest_history = self.learning_history[0] if self.learning_history else {}
        return {
            "history": [len(self.learning_history), latest_history.get("hour")],
            # The active hour is small but may gain provider-specific fields;
            # include it completely so concurrent latest-wins writes stay exact.
            "tracking": self.learning_tracking,
            "load_profile": [id(self.load_profile_7x24), len(self.load_profile_7x24)],
            "pv_profile": [id(self.pv_learning_profile), len(self.pv_learning_profile)],
            "profile_execution": [
                self._profile_execution_revision,
                len(self.profile_execution),
            ],
            "learning_revision": self.learning_revision,
            "history_watermark": self.history_watermark,
        }

    def request_learning_save(self) -> Any:
        """Coalesce background learning Store requests into one tracked task."""
        self._learning_save_dirty = True
        task = self._learning_save_task
        if (
            self._learning_store is None
            or self._startup_in_progress
            or self._unloading
            or (task is not None and not task.done())
        ):
            return task
        task = self.hass.async_create_task(self.async_save_learning_history())
        self._learning_save_task = task
        return task

    async def async_save_learning_history(self, *, force: bool = False) -> None:
        """Persist learning state single-flight with one latest follow-up."""
        if self._learning_store is None or (self._unloading and not force):
            return
        self._learning_save_dirty = True
        if self._startup_in_progress:
            return
        current = asyncio.current_task()
        active = self._learning_save_task
        if active is not None and active is not current and not active.done():
            await asyncio.shield(active)
            return
        if active is None or active.done():
            self._learning_save_task = current
        follow_up_used = False
        try:
            while True:
                self._learning_save_dirty = False
                prepare_started = time.perf_counter()
                payload = self._learning_store_payload()
                fingerprint = snapshot_id(
                    self._learning_store_fingerprint_payload()
                )
                self._performance.observe_ms(
                    "learning_store_prepare",
                    (time.perf_counter() - prepare_started) * 1000.0,
                )
                if fingerprint != self._learning_last_saved_fingerprint:
                    store_started = time.perf_counter()
                    await self._learning_store.async_save(payload)
                    self._performance.observe_ms(
                        "learning_store_save",
                        (time.perf_counter() - store_started) * 1000.0,
                    )
                    self._learning_last_saved_fingerprint = fingerprint
                if self._learning_save_dirty and not follow_up_used:
                    follow_up_used = True
                    continue
                break
        finally:
            if self._learning_save_task is current:
                self._learning_save_task = None
        if self._learning_save_dirty and not self._unloading:
            self.request_learning_save()

    async def async_load_energy_history(self) -> None:
        self._samples_store = Store(self.hass, 1, f"{DOMAIN}_{self.entry_id}_energy_samples")
        raw = await self._samples_store.async_load()
        data, migrated = migrate_energy_payload(raw)
        self.energy_samples = data.get("samples", []) if isinstance(data.get("samples"), list) else []
        self._energy_recent_details = (
            data.get("recent_details", [])[-288:]
            if isinstance(data.get("recent_details"), list)
            else []
        )
        self.daily_archive = data.get("daily", []) if isinstance(data.get("daily"), list) else []
        self.monthly_archive = data.get("monthly", []) if isinstance(data.get("monthly"), list) else []
        self.energy_counter_state = data.get("counter_state") if isinstance(data.get("counter_state"), dict) else {}
        checkpoint = data.get("learning_checkpoint")
        if isinstance(checkpoint, dict) and checkpoint:
            current_stamp = str(self.learning_tracking.get("last_sample") or "")
            checkpoint_stamp = str(checkpoint.get("last_sample") or "")
            if checkpoint_stamp > current_stamp:
                # Energy Store is already written once per minute. Reusing that
                # atomic write recovers the active learning hour without a new
                # Store, timer or save task.
                self.learning_tracking = deepcopy(checkpoint)
        last = data.get("last_sample")
        try:
            self._last_energy_sample_at = datetime.fromisoformat(str(last)) if last else None
        except (TypeError, ValueError):
            self._last_energy_sample_at = None
        self._energy_revision = 1 if migrated else 0
        self._energy_saved_revision = -1 if migrated else 0
        # Keep an in-memory reference to the untouched legacy payload until the
        # compact Store write succeeds. Store itself remains atomic on disk.
        self._energy_legacy_payload_backup = raw if migrated and isinstance(raw, dict) else None
        if migrated:
            await self.async_save_energy_history()

    def _energy_store_payload(self) -> dict[str, Any]:
        """Build a small, stable payload without copying legacy sample details."""
        return {
            "schema_version": HISTORY_SCHEMA_VERSION,
            "energy_format_version": ENERGY_COMPACT_FORMAT_VERSION,
            "samples": list(self.energy_samples),
            "recent_details": list(self._energy_recent_details[-288:]),
            "daily": list(self.daily_archive),
            "monthly": list(self.monthly_archive),
            "counter_state": dict(self.energy_counter_state),
            "last_sample": (
                self._last_energy_sample_at.isoformat()
                if self._last_energy_sample_at
                else None
            ),
            "learning_checkpoint": deepcopy(self.learning_tracking),
        }

    def request_energy_save(self) -> Any:
        """Coalesce energy Store writes; one latest-wins follow-up is enough."""
        self._energy_save_dirty = True
        task = self._energy_save_task
        if (
            self._samples_store is None
            or self._startup_in_progress
            or self._unloading
            or (task is not None and not task.done())
        ):
            return task
        task = self.hass.async_create_task(self.async_save_energy_history())
        self._energy_save_task = task
        return task

    async def async_save_energy_history(self, *, force: bool = False) -> None:
        if self._samples_store is None or (self._unloading and not force):
            return
        self._energy_save_dirty = True
        current = asyncio.current_task()
        active = self._energy_save_task
        if active is not None and active is not current and not active.done():
            await asyncio.shield(active)
            return
        if active is None or active.done():
            self._energy_save_task = current
        follow_up_used = False
        try:
            while True:
                self._energy_save_dirty = False
                revision = self._energy_revision
                if revision != self._energy_saved_revision:
                    prepare_started = time.perf_counter()
                    payload = self._energy_store_payload()
                    self._performance.observe_ms(
                        "energy_store_prepare",
                        (time.perf_counter() - prepare_started) * 1000.0,
                    )
                    store_started = time.perf_counter()
                    await self._samples_store.async_save(payload)
                    self._performance.observe_ms(
                        "energy_store_save",
                        (time.perf_counter() - store_started) * 1000.0,
                    )
                    self._energy_saved_revision = revision
                    self._energy_legacy_payload_backup = None
                if self._energy_save_dirty and not follow_up_used:
                    follow_up_used = True
                    continue
                break
        finally:
            if self._energy_save_task is current:
                self._energy_save_task = None
        if self._energy_save_dirty and not self._unloading:
            self.request_energy_save()

    def _archive_energy_samples(self, now: datetime) -> None:
        cutoff = now - timedelta(days=90)
        old = []
        retained = []
        for sample in self.energy_samples:
            try:
                stamp = datetime.fromisoformat(str(sample.get("timestamp")))
                is_old = stamp < cutoff
            except (TypeError, ValueError):
                continue
            (old if is_old else retained).append(sample)
        self.energy_samples = retained
        if not old:
            return
        grouped: dict[str, list[dict[str, Any]]] = {}
        for sample in old:
            grouped.setdefault(str(sample.get("timestamp"))[:10], []).append(sample)
        existing = {str(row.get("date")): row for row in self.daily_archive}
        for day, samples in grouped.items():
            row: dict[str, Any] = {"date": day, "samples": len(samples)}
            for key in ("pv_power", "load_power", "grid_power", "battery_power", "soc", "sell_price", "buy_price"):
                values = [self.safe_float(item.get(key), 0) for item in samples if item.get(key) is not None]
                row[f"{key}_avg"] = round(sum(values) / len(values), 3) if values else None
            def integrated(key: str, direction: int = 1) -> float | None:
                total = 0.0
                valid = 0
                for item in samples:
                    measurement = finite_float(item.get(key))
                    if measurement is None:
                        continue
                    hours = max(0.0, min(900.0, self.safe_float(item.get("interval_seconds"), 300))) / 3600
                    value = measurement * direction
                    total += max(0.0, value) / 1000 * hours
                    valid += 1
                return round(total, 3) if valid else None

            row["pv_kwh"] = integrated("pv_power")
            row["load_kwh"] = integrated("load_power")
            row["grid_import_kwh"] = integrated("grid_power")
            row["grid_export_kwh"] = integrated("grid_power", -1)
            row["battery_charge_kwh"] = integrated("battery_power", -1)
            row["battery_discharge_kwh"] = integrated("battery_power")
            existing[day] = row
        daily_cutoff = (now - timedelta(days=1825)).date().isoformat()
        expired_daily = [row for day, row in existing.items() if day < daily_cutoff]
        self.daily_archive = sorted(
            (row for day, row in existing.items() if day >= daily_cutoff),
            key=lambda row: str(row.get("date")),
            reverse=True,
        )
        months: dict[str, list[dict[str, Any]]] = {}
        for row in self.daily_archive:
            months.setdefault(str(row.get("date"))[:7], []).append(row)
        energy_keys = ("pv_kwh", "load_kwh", "grid_import_kwh", "grid_export_kwh", "battery_charge_kwh", "battery_discharge_kwh")
        def month_row(month: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
            totals = {}
            for key in energy_keys:
                values = [
                    value
                    for row in rows
                    if (value := finite_float(row.get(key))) is not None
                ]
                totals[key] = round(sum(values), 3) if values else None
            return {
                "month": month,
                "days": len(rows),
                "samples": sum(int(row.get("samples", 0)) for row in rows),
                **totals,
            }
        retained_months = [month_row(month, rows) for month, rows in sorted(months.items(), reverse=True)]
        permanent = {
            str(row.get("month")): row
            for row in self.monthly_archive
            if str(row.get("month")) < daily_cutoff[:7]
        }
        expired_months: dict[str, list[dict[str, Any]]] = {}
        for row in expired_daily:
            expired_months.setdefault(str(row.get("date"))[:7], []).append(row)
        for month, rows in expired_months.items():
            permanent[month] = month_row(month, rows)
        self.monthly_archive = sorted([*retained_months, *permanent.values()], key=lambda row: str(row.get("month")), reverse=True)

    def _energy_counter_measurements(self, now: datetime) -> dict[str, Any]:
        """Read optional energy counters and persist reset-safe deltas."""
        definitions = {
            "daily_pv": self.daily_pv_production_sensor,
            "daily_load": self.daily_load_consumption_sensor,
            "daily_grid_import": self.daily_energy_bought_sensor,
            "daily_grid_export": self.daily_energy_sold_sensor,
            "daily_battery_charge": self.daily_battery_charge_sensor,
            "daily_battery_discharge": self.daily_battery_discharge_sensor,
        }
        timestamp = now.isoformat(timespec="seconds")
        day = now.date().isoformat()
        result: dict[str, Any] = {}
        for key, entity_id in definitions.items():
            state = self.hass.states.get(entity_id) if entity_id else None
            unit = state.attributes.get("unit_of_measurement") if state is not None else None
            value = energy_kwh(state.state, unit) if state is not None else None
            state_class = str(state.attributes.get("state_class") or "") if state is not None else ""
            device_class = str(state.attributes.get("device_class") or "") if state is not None else ""
            total_increasing = state_class == "total_increasing"
            if value is None:
                result[key] = {
                    "entity_id": entity_id,
                    "value_kwh": None,
                    "delta_kwh": None,
                    "status": "invalid_unit" if state is not None and state.state not in ("unknown", "unavailable", "none", "") else "unavailable",
                    "unit": unit,
                    "state_class": state_class or None,
                    "device_class": device_class or None,
                    "used_for_history": False,
                }
                continue
            update = update_energy_counter(
                self.energy_counter_state.get(key),
                value_kwh=value,
                day=day,
                timestamp=timestamp,
                total_increasing=total_increasing,
            )
            self.energy_counter_state[key] = update.state
            result[key] = {
                "entity_id": entity_id,
                "value_kwh": round(value, 6),
                "delta_kwh": round(update.delta_kwh, 6),
                "status": "reset" if update.reset_detected else "ok",
                "reset_detected": update.reset_detected,
                "first_sample": update.first_sample,
                "unit": unit,
                "state_class": state_class or None,
                "device_class": device_class or None,
                "used_for_history": True,
                "preferred_long_term": total_increasing and device_class == "energy",
            }
        self.data_quality["energy_counters"] = result
        return result

    async def async_update_energy_sample(self) -> None:
        now = ha_now()
        if self._last_energy_sample_at:
            try:
                if (now - self._last_energy_sample_at).total_seconds() < 55:
                    return
            except TypeError:
                self._last_energy_sample_at = None
        collect_started = time.perf_counter()
        readings = self._telemetry_readings()
        load = readings["load"]
        battery = readings["battery"]
        fields = {
            "pv_power": readings["pv"].get("value"),
            "load_power": load.get("value"),
            "load_l1_power": readings["load_l1"].get("value"),
            "load_l2_power": readings["load_l2"].get("value"),
            "load_l3_power": readings["load_l3"].get("value"),
            "grid_power": readings["grid"].get("value"),
            "battery_power": battery.get("value"),
            "soc": readings["soc"].get("value"),
            "sell_price": readings["sell_price"].get("value"),
            "buy_price": readings["buy_price"].get("value"),
            "daily_pv": self.state_float_or_none(self.daily_pv_production_sensor),
        }
        fields.update(split_directional_power(
            grid_power_w=fields["grid_power"],
            battery_power_w=fields["battery_power"],
        ))
        interval_seconds = 60.0
        if self._last_energy_sample_at is not None:
            try:
                interval_seconds = max(0.0, min(120.0, (now - self._last_energy_sample_at).total_seconds()))
            except TypeError:
                interval_seconds = 60.0
        tariff = self.tariff_context(now)
        weather = self.weather_context()
        live_state = self.live_state_context(readings, now)
        sample = {
            "schema_version": HISTORY_SCHEMA_VERSION,
            "timestamp": now.replace(microsecond=0).isoformat(),
            "interval_seconds": round(interval_seconds, 1),
            **fields,
            "missing": [key for key, value in fields.items() if value is None],
            "readings": {
                name: {
                    "value": item.get("value"),
                    "status": item.get("status"),
                    "quality": item.get("quality"),
                    "source": item.get("source"),
                    "last_updated": item.get("last_updated"),
                    "usable_for_learning": item.get("value") is not None
                    and item.get("quality") != "unavailable",
                }
                for name, item in readings.items()
            },
            "source_quality": self.source_quality_context(),
            "live_state": live_state,
            "control": {
                "mode": live_state.get("active_mode"),
                "power_w": live_state.get("active_power_w"),
                "slot_key": live_state.get("slot_key"),
            },
            "solcast": {
                "current_power_w": self._measurement(self.solcast_current_power_sensor).get("value"),
                "forecast_today_kwh": self.solcast_forecast_today_value(),
                "forecast_remaining_kwh": self.state_float_or_none(self.solcast_remaining_today_sensor),
            },
            "weather": {
                key: weather.get(key)
                for key in (
                    "available", "condition", "temperature", "humidity",
                    "cloud_coverage", "precipitation_probability",
                    "risk_factor", "last_updated",
                )
            },
            "energy_counters": self._energy_counter_measurements(now),
            "tariff": {
                key: tariff.get(key)
                for key in ("provider", "plan", "zone", "season", "day_type", "distribution_rate", "catalog_version")
            },
        }
        self.energy_samples.append(compact_energy_sample(sample))
        self._energy_recent_details = [*self._energy_recent_details[-287:], sample]
        self._last_energy_sample_at = now
        self._archive_energy_samples(now)
        self._energy_revision += 1
        self._performance.observe_ms(
            "energy_collect",
            (time.perf_counter() - collect_started) * 1000.0,
        )
        self._performance.set_value("energy_sample_count", len(self.energy_samples))
        self.request_energy_save()

    async def async_update_weather_forecast(self) -> None:
        entity_id = self.weather_entity
        if not entity_id or not self.entity_available(entity_id):
            self.weather_forecast = []
            self.weather_daily_forecast = []
            self.weather_last_error = "Encja pogody jest niedostępna"
            return

        async def fetch_forecast(kind: str) -> list[dict[str, Any]]:
            response = await self.hass.services.async_call(
                "weather",
                "get_forecasts",
                {"type": kind},
                target={"entity_id": entity_id},
                blocking=True,
                return_response=True,
            )
            payload = response.get(entity_id, response) if isinstance(response, dict) else {}
            forecast = payload.get("forecast", []) if isinstance(payload, dict) else []
            return [row for row in forecast if isinstance(row, dict)] if isinstance(forecast, list) else []

        previous_hourly = list(self.weather_forecast)
        previous_daily = list(self.weather_daily_forecast)
        errors: list[str] = []
        hourly: list[dict[str, Any]] = []
        daily: list[dict[str, Any]] = []

        async def fetch_optional(kind: str) -> list[dict[str, Any]]:
            try:
                return await asyncio.wait_for(
                    fetch_forecast(kind),
                    timeout=max(0.01, float(self.weather_forecast_timeout)),
                )
            except TimeoutError:
                errors.append(
                    f"{kind}: timeout po {max(0.01, float(self.weather_forecast_timeout)):.2f} s"
                )
            except Exception as err:  # Weather is optional and must never fail DEM startup.
                errors.append(f"{kind}: {err}")
            return []

        hourly, daily = await asyncio.gather(
            fetch_optional("hourly"),
            fetch_optional("daily"),
        )

        # Compatibility fallback for older weather entities exposing forecast as an attribute.
        if not hourly:
            state = self.hass.states.get(entity_id)
            fallback = state.attributes.get("forecast", []) if state is not None else []
            hourly = [row for row in fallback if isinstance(row, dict)] if isinstance(fallback, list) else []
        if errors and not hourly:
            hourly = previous_hourly
        if errors and not daily:
            daily = previous_daily

        # Some providers implement only the hourly endpoint. Build a truthful
        # daily summary from those samples instead of displaying invented zeros.
        if not daily and hourly:
            grouped: dict[str, list[dict[str, Any]]] = {}
            local_now = ha_now()
            for row in hourly:
                raw_time = row.get("datetime", row.get("time"))
                try:
                    stamp = datetime.fromisoformat(str(raw_time).replace("Z", "+00:00"))
                    if local_now.tzinfo is not None and stamp.tzinfo is not None:
                        stamp = stamp.astimezone(local_now.tzinfo)
                    day_key = stamp.date().isoformat()
                except (TypeError, ValueError):
                    continue
                grouped.setdefault(day_key, []).append(row)
            for day_key, rows in sorted(grouped.items())[:7]:
                temperatures = [
                    self.safe_float(row.get("temperature"), float("nan"))
                    for row in rows
                    if row.get("temperature") is not None
                ]
                temperatures = [value for value in temperatures if value == value]
                condition_counts: dict[str, int] = {}
                for row in rows:
                    condition = str(row.get("condition") or "")
                    if condition:
                        condition_counts[condition] = condition_counts.get(condition, 0) + 1
                condition = max(condition_counts, key=condition_counts.get) if condition_counts else None
                probabilities = [
                    self.safe_float(row.get("precipitation_probability"), 0)
                    for row in rows
                    if row.get("precipitation_probability") is not None
                ]
                daily.append({
                    "datetime": day_key,
                    "condition": condition,
                    "temperature": max(temperatures) if temperatures else None,
                    "templow": min(temperatures) if temperatures else None,
                    "precipitation_probability": max(probabilities) if probabilities else None,
                    "derived_from_hourly": True,
                })

        self.weather_forecast = hourly[:48]
        self.weather_daily_forecast = daily[:7]
        self.weather_last_error = "; ".join(errors)
        if hourly or daily:
            self.weather_last_updated = ha_now().isoformat(timespec="seconds")

    def _new_learning_hour(self, hour_key: str, now: datetime) -> dict[str, Any]:
        tariff = self.tariff_context(now)
        weather = self.weather_context()
        solcast_power = self._measurement(self.solcast_current_power_sensor)
        hourly_snapshot = (
            max(0.0, float(solcast_power["value"])) / 1000
            if solcast_power.get("value") is not None else None
        )
        corrected, correction_factor, correction_samples = corrected_pv_forecast(
            self.pv_learning_profile,
            moment=now,
            forecast_kwh=hourly_snapshot,
        )
        pv_measurement = self._measurement(self.pv_power_sensor)
        soc = self.current_soc_or_none()
        flags = pv_quality_flags(
            battery_soc=soc,
            work_mode=self.state_text(self.work_mode_select),
            grid_available=self.entity_available(self.grid_power_sensor),
            actual_power_w=pv_measurement.get("value"),
            inverter_limit_w=min(
                finite_float(self.ai_settings.get("inverterPowerW")) or float("inf"),
                self.effective_inverter_max_power_w,
            ),
            sensor_stale=pv_measurement.get("status") == "stale",
            manual_override=self.control_mode != "Schedule",
        )
        return {
            "schema_version": HISTORY_SCHEMA_VERSION,
            "hour": hour_key,
            "local_date": now.date().isoformat(),
            "local_hour": now.hour,
            "last_sample": now.isoformat(),
            "samples": 0,
            "channels": {
                name: new_channel()
                for name in (
                    "pv", "load", "load_l1", "load_l2", "load_l3",
                    "grid", "battery", "soc", "sell_price", "buy_price",
                )
            },
            "pv_kwh": 0.0,
            "load_kwh": 0.0,
            "load_l1_kwh": 0.0,
            "load_l2_kwh": 0.0,
            "load_l3_kwh": 0.0,
            "grid_import_kwh": 0.0,
            "grid_export_kwh": 0.0,
            "battery_charge_kwh": 0.0,
            "battery_discharge_kwh": 0.0,
            "soc_sum": 0.0,
            "soc_samples": 0,
            "soc_min": None,
            "soc_max": None,
            "soc_start": soc,
            "soc_end": None,
            "sell_price_sum": 0.0,
            "buy_price_sum": 0.0,
            "solcast_forecast_kwh": self.solcast_forecast_today_value(),
            "forecast_initial_kwh": self.safe_float(
                self.solcast_tracking.get("initial_forecast_kwh", self.solcast_tracking.get("forecast")),
                0,
            ),
            "forecast_latest_kwh": self.safe_float(
                self.solcast_tracking.get("latest_forecast_kwh", self.solcast_tracking.get("forecast")),
                0,
            ),
            "forecast_hourly_snapshot_kwh": hourly_snapshot,
            "forecast_corrected_kwh": corrected,
            "forecast_snapshot_at": now.isoformat(timespec="seconds"),
            "forecast_correction_factor": correction_factor,
            "forecast_correction_samples": correction_samples,
            "daily_pv_kwh": max(0, self.state_float(self.daily_pv_production_sensor, 0)),
            "source_quality": self.source_quality_context(),
            "quality_flags": flags,
            "action": self.active_slot.mode if self.active_slot.enabled else MODE_NORMAL_OPERATION,
            "control": {
                "slot_key": self.active_slot.key,
                "mode": self.active_slot.mode if self.active_slot.enabled else MODE_NORMAL_OPERATION,
                "sell_power_w": max(0.0, float(self.active_slot.sell_power or 0.0)),
                "discharge_current_a": max(0.0, float(self.active_slot.discharge_current or 0.0)),
                "charge_current_a": max(0.0, float(self.active_slot.charge_current or 0.0)),
                "grid_charge_current_a": max(0.0, float(self.active_slot.grid_charge_current or 0.0)),
            },
            "weather_forecast": {
                key: weather.get(key)
                for key in (
                    "available", "condition", "temperature", "humidity",
                    "cloud_coverage", "precipitation_probability",
                    "risk_factor", "last_updated",
                )
            },
            "plan_id": self.future_plan.get("plan_id") if isinstance(self.future_plan, dict) else None,
            "tariff": {
                key: tariff.get(key)
                for key in ("provider", "plan", "zone", "season", "day_type", "distribution_rate", "catalog_version")
            },
        }

    def _finalize_learning_hour(
        self,
        tracking: dict[str, Any],
        *,
        update_models: bool = True,
    ) -> dict[str, Any]:
        samples = max(1, int(tracking.get("samples", 0)))
        soc_samples = int(tracking.get("soc_samples", 0))
        source_quality = tracking.get("source_quality", {})
        quality_score = self.safe_float(source_quality.get("score"), 0) if isinstance(source_quality, dict) else 0
        channels = tracking.get("channels") if isinstance(tracking.get("channels"), dict) else {}
        channel_quality = {
            name: channel_summary(item)
            for name, item in channels.items()
            if isinstance(item, dict)
        }

        def available(name: str) -> bool:
            return int(channel_quality.get(name, {}).get("valid_samples", 0)) > 0

        def energy_value(field: str, channel: str) -> float | None:
            return (
                round(self.safe_float(tracking.get(field), 0), 4)
                if available(channel)
                else None
            )

        essential = ("pv", "load", "grid", "battery", "soc")
        complete = all(
            channel_quality.get(name, {}).get("level") == "full"
            for name in essential
        )
        load_kwh = energy_value("load_kwh", "load")
        pv_kwh = energy_value("pv_kwh", "pv")
        grid_import_kwh = energy_value("grid_import_kwh", "grid")
        grid_export_kwh = energy_value("grid_export_kwh", "grid")
        battery_charge_kwh = energy_value("battery_charge_kwh", "battery")
        battery_discharge_kwh = energy_value("battery_discharge_kwh", "battery")
        hourly_balance = energy_balance(
            pv_kwh=pv_kwh,
            load_kwh=load_kwh,
            grid_import_kwh=grid_import_kwh,
            grid_export_kwh=grid_export_kwh,
            battery_charge_kwh=battery_charge_kwh,
            battery_discharge_kwh=battery_discharge_kwh,
        )
        solcast_hourly = finite_float(tracking.get("forecast_hourly_snapshot_kwh"))
        solcast_error = (
            pv_kwh - solcast_hourly
            if pv_kwh is not None and solcast_hourly is not None
            else None
        )
        solcast_accuracy = (
            max(0.0, 100.0 - abs(solcast_error) / solcast_hourly * 100.0)
            if solcast_error is not None and solcast_hourly and solcast_hourly > 0
            else None
        )
        weather_actual = self.weather_context()
        result = {
            "schema_version": HISTORY_SCHEMA_VERSION,
            "hour": tracking.get("hour"),
            "local_date": tracking.get("local_date"),
            "local_hour": tracking.get("local_hour"),
            "samples": int(tracking.get("samples", 0)),
            "pv_kwh": pv_kwh,
            "load_kwh": load_kwh,
            "load_l1_kwh": energy_value("load_l1_kwh", "load_l1"),
            "load_l2_kwh": energy_value("load_l2_kwh", "load_l2"),
            "load_l3_kwh": energy_value("load_l3_kwh", "load_l3"),
            "grid_import_kwh": grid_import_kwh,
            "grid_export_kwh": grid_export_kwh,
            "battery_charge_kwh": battery_charge_kwh,
            "battery_discharge_kwh": battery_discharge_kwh,
            "soc_avg": round(self.safe_float(tracking.get("soc_sum"), 0) / soc_samples, 1) if soc_samples else None,
            "soc_min": round(self.safe_float(tracking.get("soc_min"), 0), 1) if tracking.get("soc_min") is not None else None,
            "soc_max": round(self.safe_float(tracking.get("soc_max"), 0), 1) if tracking.get("soc_max") is not None else None,
            "soc_start": tracking.get("soc_start"),
            "soc_end": tracking.get("soc_last"),
            "sell_price_avg": (
                round(
                    self.safe_float(tracking.get("sell_price_sum"), 0)
                    / max(1, int(channel_quality.get("sell_price", {}).get("valid_samples", 0))),
                    3,
                )
                if available("sell_price")
                else None
            ),
            "buy_price_avg": (
                round(
                    self.safe_float(tracking.get("buy_price_sum"), 0)
                    / max(1, int(channel_quality.get("buy_price", {}).get("valid_samples", 0))),
                    3,
                )
                if available("buy_price")
                else None
            ),
            "solcast_forecast_kwh": round(self.safe_float(tracking.get("solcast_forecast_kwh"), 0), 3),
            "forecast_initial_kwh": tracking.get("forecast_initial_kwh"),
            "forecast_latest_kwh": tracking.get("forecast_latest_kwh"),
            "forecast_hourly_snapshot_kwh": tracking.get("forecast_hourly_snapshot_kwh"),
            "forecast_corrected_kwh": tracking.get("forecast_corrected_kwh"),
            "forecast_snapshot_at": tracking.get("forecast_snapshot_at"),
            "forecast_correction_factor": tracking.get("forecast_correction_factor"),
            "daily_pv_kwh": round(self.safe_float(tracking.get("daily_pv_kwh"), 0), 3),
            "complete": complete,
            "completeness_percent": round(
                sum(item.get("coverage_percent", 0) for item in channel_quality.values())
                / max(1, len(channel_quality)),
                1,
            ),
            "channel_quality": channel_quality,
            "energy_balance": hourly_balance,
            "source_quality": source_quality,
            "quality_flags": tracking.get("quality_flags", {}),
            "energy_counters": tracking.get("energy_counters", {}),
            "action": tracking.get("action"),
            "control": tracking.get("control", {}),
            "plan_id": tracking.get("plan_id"),
            "tariff": tracking.get("tariff", {}),
            "weather_forecast": tracking.get("weather_forecast", {}),
            "weather_actual": {
                key: weather_actual.get(key)
                for key in (
                    "available", "condition", "temperature", "humidity",
                    "cloud_coverage", "precipitation_probability",
                    "risk_factor", "last_updated",
                )
            },
            "solcast_error_kwh": round(solcast_error, 4) if solcast_error is not None else None,
            "solcast_accuracy_percent": round(solcast_accuracy, 1) if solcast_accuracy is not None else None,
        }
        try:
            moment = datetime.fromisoformat(str(tracking.get("hour")))
        except (TypeError, ValueError):
            moment = ha_now().replace(minute=0, second=0, microsecond=0)
        if update_models:
            self.load_profile_7x24 = update_load_profile(
                self.load_profile_7x24,
                moment=moment,
                load_kwh=result["load_kwh"],
                complete=channel_quality.get("load", {}).get("level") == "full",
                quality_score=self.safe_float(channel_quality.get("load", {}).get("quality_score"), 0),
                completeness_percent=self.safe_float(channel_quality.get("load", {}).get("coverage_percent"), 0),
            )
            flags = dict(result.get("quality_flags") or {})
            flags["fallback_used"] = bool(source_quality.get("fallback_in_use")) if isinstance(source_quality, dict) else False
            self.pv_learning_profile = update_pv_profile(
                self.pv_learning_profile,
                moment=moment,
                forecast_kwh=finite_float(result.get("forecast_hourly_snapshot_kwh")),
                actual_kwh=result["pv_kwh"],
                flags=flags,
                complete=channel_quality.get("pv", {}).get("level") == "full",
                quality_score=self.safe_float(channel_quality.get("pv", {}).get("quality_score"), 0),
                completeness_percent=self.safe_float(channel_quality.get("pv", {}).get("coverage_percent"), 0),
            )
            self._invalidate_learning_summary_cache()
        return result

    def _set_profile_execution_status(
        self,
        profile_id: str,
        date_key: str,
        status: str,
        *,
        failure_reason: str | None = None,
        plan_id: str | None = None,
    ) -> dict[str, Any]:
        """Create or transition one complete, local profile execution record."""
        allowed_statuses = {
            "waiting",
            "running",
            "completed",
            "partial",
            "blocked",
            "failed",
            "skipped",
            "cancelled",
            "manual_override",
        }
        if status not in allowed_statuses:
            raise ValueError(f"Nieobsługiwany status wykonania profilu: {status}")
        profiles = (
            self.user_profiles.get("profiles", {})
            if isinstance(self.user_profiles, dict)
            else {}
        )
        profile = profiles.get(profile_id, {}) if isinstance(profiles, dict) else {}
        if not isinstance(profile, dict):
            profile = {}
        plan = self.optimizer_plan if isinstance(self.optimizer_plan, dict) else {}
        planned_rows = sorted(
            (
                row
                for row in plan.get("rows", [])
                if isinstance(row, dict)
                and str(row.get("profile_id") or "") == profile_id
                and str(row.get("date") or "") == date_key
            ),
            key=lambda row: int(self.safe_float(row.get("hour"), 0)),
        )
        previous = next(
            (
                row
                for row in self.profile_execution
                if isinstance(row, dict)
                and str(row.get("profile_id") or "") == profile_id
                and str(row.get("date") or "") == date_key
            ),
            {},
        )
        action = str(
            next(
                (
                    row.get("action")
                    for row in planned_rows
                    if row.get("action") in {"sell", "charge"}
                ),
                "charge" if profile_id == "charging" or profile.get("type") == "charging" else "sell",
            )
        )
        profile_type = "charging" if action == "charge" else "sale"
        target = max(
            0.0,
            self.safe_float(
                profile.get("target_value")
                if profile_type == "charging" and profile.get("target_type") == "energy"
                else profile.get("target_energy_kwh"),
                previous.get("target_kwh", 0),
            ),
        )
        planned = sum(
            max(0.0, self.safe_float(row.get("planned_energy_kwh"), 0))
            for row in planned_rows
        )
        if planned <= 0:
            planned = max(0.0, self.safe_float(previous.get("planned_kwh"), 0))
        executed = max(
            0.0,
            self.safe_float(
                previous.get("executed_kwh", previous.get("actual_energy_kwh")),
                0,
            ),
        )
        price_values = [
            self.safe_float(
                row.get("effective_buy_price") if profile_type == "charging" else row.get("sell_price"),
                0,
            )
            for row in planned_rows
            if (
                row.get("effective_buy_price")
                if profile_type == "charging"
                else row.get("sell_price")
            )
            is not None
        ]
        planned_import = sum(
            max(
                0.0,
                self.safe_float(
                    row.get("expected_import_kwh", row.get("grid_to_battery_kwh")),
                    0,
                ),
            )
            for row in planned_rows
        )
        planned_export = sum(
            max(
                0.0,
                self.safe_float(
                    row.get("expected_export_kwh", row.get("battery_to_grid_kwh")),
                    0,
                ),
            )
            for row in planned_rows
        )
        now_text = ha_now().isoformat(timespec="seconds")
        entry = {
            "plan_id": plan_id or plan.get("plan_id") or previous.get("plan_id"),
            "profile_id": profile_id,
            "profile_type": profile_type,
            "date": date_key,
            "window_start": profile.get("start", previous.get("window_start")),
            "window_end": profile.get("end", previous.get("window_end")),
            "target_kwh": round(target, 5),
            "planned_kwh": round(planned, 5),
            "executed_kwh": round(executed, 5),
            "remaining_kwh": round(max(0.0, target - executed), 5),
            "planned_soc_start": (
                planned_rows[0].get("soc_start_pct")
                if planned_rows
                else previous.get("planned_soc_start")
            ),
            "planned_soc_end": (
                planned_rows[-1].get("soc_end_pct")
                if planned_rows
                else previous.get("planned_soc_end")
            ),
            "actual_soc_start": previous.get("actual_soc_start"),
            "actual_soc_end": previous.get("actual_soc_end"),
            "planned_price": (
                round(sum(price_values) / len(price_values), 5)
                if price_values
                else previous.get("planned_price")
            ),
            "actual_average_price": self.safe_float(
                previous.get("actual_average_price"),
                0,
            ),
            "planned_import_kwh": round(
                planned_import
                if planned_rows
                else self.safe_float(previous.get("planned_import_kwh"), 0),
                5,
            ),
            "actual_import_kwh": round(
                max(0.0, self.safe_float(previous.get("actual_import_kwh"), 0)),
                5,
            ),
            "planned_export_kwh": round(
                planned_export
                if planned_rows
                else self.safe_float(previous.get("planned_export_kwh"), 0),
                5,
            ),
            "actual_export_kwh": round(
                max(0.0, self.safe_float(previous.get("actual_export_kwh"), 0)),
                5,
            ),
            "planned_result_pln": round(
                sum(self.safe_float(row.get("net_result"), 0) for row in planned_rows)
                if planned_rows
                else self.safe_float(previous.get("planned_result_pln"), 0),
                5,
            ),
            "actual_result_pln": round(
                self.safe_float(previous.get("actual_result_pln"), 0),
                5,
            ),
            "status": status,
            "failure_reason": failure_reason,
            "data_quality": previous.get("data_quality", {}),
            "created_at": previous.get("created_at") or now_text,
            "updated_at": now_text,
            # Backward-compatible aliases consumed by existing history/UI.
            "planned_energy_kwh": round(planned, 5),
            "actual_energy_kwh": round(executed, 5),
            "source": previous.get("source", "local_profile_lifecycle"),
        }
        self.profile_execution = [
            entry,
            *[
                row
                for row in self.profile_execution
                if not (
                    isinstance(row, dict)
                    and str(row.get("profile_id") or "") == profile_id
                    and str(row.get("date") or "") == date_key
                )
            ],
        ][:17520]
        self._profile_execution_revision += 1
        return entry

    def _sync_profile_execution_from_plan(
        self,
        plan: dict[str, Any],
        current: datetime,
    ) -> None:
        """Seed lifecycle records from the authoritative backend plan."""
        impacts = plan.get("profile_impacts")
        rows = plan.get("rows")
        if not isinstance(impacts, list) or not isinstance(rows, list):
            return
        current_date = current.date().isoformat()
        for impact in impacts:
            if not isinstance(impact, dict) or not bool(impact.get("enabled")):
                continue
            profile_id = str(impact.get("profile_id") or "")
            if not profile_id:
                continue
            profile_rows = [
                row
                for row in rows
                if isinstance(row, dict)
                and str(row.get("profile_id") or "") == profile_id
            ]
            dates = sorted(
                {
                    str(row.get("date") or "")
                    for row in profile_rows
                    if row.get("date")
                }
            ) or [current_date]
            impact_status = str(impact.get("status") or "")
            for date_key in dates:
                existing = next(
                    (
                        row
                        for row in self.profile_execution
                        if isinstance(row, dict)
                        and str(row.get("profile_id") or "") == profile_id
                        and str(row.get("date") or "") == date_key
                    ),
                    {},
                )
                if (
                    existing.get("plan_id") == plan.get("plan_id")
                    and existing.get("status")
                    in {"completed", "cancelled", "failed", "manual_override"}
                ):
                    continue
                failure_reason = None
                if impact_status.startswith("blocked_"):
                    status = "blocked"
                    failure_reason = str(
                        impact.get("block_reason")
                        or impact_status.removeprefix("blocked_")
                    )
                elif impact_status == "no_qualified_hours":
                    status = "skipped"
                    failure_reason = str(
                        impact.get("skip_reason") or "no_qualified_hours"
                    )
                elif impact_status == "completed":
                    status = "completed"
                elif impact_status == "partially_executed":
                    status = "partial"
                else:
                    dated_rows = [
                        row
                        for row in profile_rows
                        if str(row.get("date") or "") == date_key
                    ]
                    hours = [
                        int(self.safe_float(row.get("hour"), 0))
                        for row in dated_rows
                    ]
                    if date_key > current_date or (
                        date_key == current_date
                        and hours
                        and current.hour < min(hours)
                    ):
                        status = "waiting"
                    elif date_key < current_date or (
                        date_key == current_date
                        and hours
                        and current.hour > max(hours)
                    ):
                        status = (
                            "partial"
                            if self.safe_float(
                                existing.get(
                                    "executed_kwh",
                                    existing.get("actual_energy_kwh"),
                                ),
                                0,
                            )
                            > 0
                            else "skipped"
                        )
                    else:
                        status = "running"
                self._set_profile_execution_status(
                    profile_id,
                    date_key,
                    status,
                    failure_reason=failure_reason,
                    plan_id=str(plan.get("plan_id") or ""),
                )

    def _record_profile_execution(self, completed: dict[str, Any]) -> None:
        """Record measured profile progress locally; never write a Deye setting."""
        try:
            moment = datetime.fromisoformat(str(completed.get("hour")))
        except (TypeError, ValueError):
            return
        planned_row = next(
            (
                row for row in self.optimizer_plan.get("rows", [])
                if isinstance(row, dict)
                and str(row.get("date") or "") == moment.date().isoformat()
                and str(row.get("hour", "")) == str(moment.hour)
                and row.get("profile_id")
            ),
            None,
        )
        if not planned_row:
            return
        profile_id = str(planned_row.get("profile_id"))
        action = str(planned_row.get("action") or "none")
        if action == "sell":
            actual = min(
                max(0.0, self.safe_float(completed.get("grid_export_kwh"), 0)),
                max(0.0, self.safe_float(completed.get("battery_discharge_kwh"), 0)),
            )
        elif action == "charge":
            actual = min(
                max(0.0, self.safe_float(completed.get("grid_import_kwh"), 0)),
                max(0.0, self.safe_float(completed.get("battery_charge_kwh"), 0)),
            )
        else:
            return
        profile = (
            self.user_profiles.get("profiles", {}).get(profile_id, {})
            if isinstance(self.user_profiles, dict)
            else {}
        )
        if not isinstance(profile, dict):
            profile = {}
        date_key = moment.date().isoformat()
        planned_rows = [
            row
            for row in self.optimizer_plan.get("rows", [])
            if isinstance(row, dict)
            and str(row.get("profile_id") or "") == profile_id
            and str(row.get("date") or "") == date_key
        ]
        previous = next(
            (
                row for row in self.profile_execution
                if isinstance(row, dict)
                and row.get("profile_id") == profile_id
                and row.get("date") == date_key
            ),
            {},
        )
        previous_actual = max(
            0.0,
            self.safe_float(
                previous.get("executed_kwh", previous.get("actual_energy_kwh")),
                0,
            ),
        )
        executed = previous_actual + actual
        target = max(
            0.0,
            self.safe_float(
                profile.get("target_value")
                if profile.get("type") == "charging" and profile.get("target_type") == "energy"
                else profile.get("target_energy_kwh"),
                0,
            ),
        )
        planned = sum(
            max(0.0, self.safe_float(row.get("planned_energy_kwh"), 0))
            for row in planned_rows
        )
        actual_import = max(0.0, self.safe_float(previous.get("actual_import_kwh"), 0)) + max(
            0.0, self.safe_float(completed.get("grid_import_kwh"), 0)
        )
        actual_export = max(0.0, self.safe_float(previous.get("actual_export_kwh"), 0)) + max(
            0.0, self.safe_float(completed.get("grid_export_kwh"), 0)
        )
        actual_price = self.safe_float(
            completed.get("sell_price_avg") if action == "sell" else completed.get("buy_price_avg"),
            0,
        )
        previous_price = self.safe_float(previous.get("actual_average_price"), 0)
        actual_average_price = (
            (previous_price * previous_actual + actual_price * actual) / executed
            if executed > 1e-9
            else 0.0
        )
        end_hour = int(str(profile.get("end") or "00:00").split(":", 1)[0])
        window_finished = moment.hour == (end_hour - 1) % 24
        quality_flags = completed.get("quality_flags")
        manual_override = (
            self.control_mode != "Schedule"
            or (
                isinstance(quality_flags, dict)
                and bool(quality_flags.get("manual_override"))
            )
        )
        previous_status = str(previous.get("status") or "")
        if manual_override:
            status = "manual_override"
        elif previous_status in {"blocked", "failed", "cancelled", "manual_override"}:
            status = previous_status
        else:
            status = (
                "completed"
                if target > 0 and executed + 1e-6 >= target
                else "partial"
                if window_finished and executed > 0
                else "skipped"
                if window_finished
                else "running"
            )
        created_at = previous.get("created_at") or moment.isoformat(timespec="seconds")
        entry = {
            "profile_id": profile_id,
            "profile_type": "charging" if action == "charge" else "sale",
            "plan_id": self.optimizer_plan.get("plan_id"),
            "date": date_key,
            "hour": moment.hour,
            "action": action,
            "window_start": profile.get("start"),
            "window_end": profile.get("end"),
            "target_kwh": round(target, 5),
            "planned_kwh": round(planned, 5),
            "executed_kwh": round(executed, 5),
            "remaining_kwh": round(max(0.0, target - executed), 5),
            "planned_soc_start": planned_rows[0].get("soc_start_pct") if planned_rows else None,
            "planned_soc_end": planned_rows[-1].get("soc_end_pct") if planned_rows else None,
            "actual_soc_start": previous.get("actual_soc_start", completed.get("soc_start")),
            "actual_soc_end": completed.get("soc_end"),
            "planned_price": round(
                sum(
                    self.safe_float(
                        row.get("sell_price") if action == "sell" else row.get("effective_buy_price"),
                        0,
                    )
                    for row in planned_rows
                ) / len(planned_rows),
                5,
            ) if planned_rows else None,
            "actual_average_price": round(actual_average_price, 5),
            "planned_import_kwh": round(sum(self.safe_float(row.get("expected_import_kwh"), 0) for row in planned_rows), 5),
            "actual_import_kwh": round(actual_import, 5),
            "planned_export_kwh": round(sum(self.safe_float(row.get("expected_export_kwh"), 0) for row in planned_rows), 5),
            "actual_export_kwh": round(actual_export, 5),
            "planned_result_pln": round(sum(self.safe_float(row.get("net_result"), 0) for row in planned_rows), 5),
            "actual_result_pln": round(actual_export * actual_average_price - actual_import * actual_average_price, 5),
            "status": status,
            "failure_reason": (
                "Ręczna zmiana trybu podczas realizacji profilu"
                if manual_override
                else previous.get("failure_reason")
                if status in {"blocked", "failed", "cancelled"}
                else None
            ),
            "data_quality": completed.get("source_quality", {}),
            "created_at": created_at,
            "updated_at": moment.isoformat(timespec="seconds"),
            # Backward-compatible aliases consumed by existing history/UI.
            "planned_energy_kwh": round(planned, 5),
            "actual_energy_kwh": round(executed, 5),
            "source": "local_measurement",
        }
        self.profile_execution = [
            entry,
            *[
                row for row in self.profile_execution
                if not (
                    isinstance(row, dict)
                    and row.get("profile_id") == profile_id
                    and row.get("date") == entry["date"]
                )
            ],
        ][:17520]
        self._profile_execution_revision += 1

    async def async_update_learning_history(self) -> None:
        now = ha_now()
        hour_key = now.strftime("%Y-%m-%dT%H:00:00%z")
        archive_changed = False
        completed_learning_hour = False
        if self.learning_tracking.get("hour") != hour_key:
            if self.learning_tracking.get("hour"):
                completed = self._finalize_learning_hour(self.learning_tracking)
                self._attach_plan_execution_actual(completed)
                archive_changed = True
                self.learning_history = [
                    completed,
                    *[row for row in self.learning_history if row.get("hour") != completed["hour"]],
                ][:17520]
                completed_hour = str(completed.get("hour") or "")
                if completed_hour and completed_hour != self.history_watermark:
                    self.history_watermark = completed_hour
                    if any(
                        item.get("usable_for_learning")
                        for item in (completed.get("channel_quality") or {}).values()
                        if isinstance(item, dict)
                    ):
                        self.learning_revision += 1
                self._invalidate_learning_summary_cache()
                self._record_profile_execution(completed)
                completed_learning_hour = True
            self.learning_tracking = self._new_learning_hour(hour_key, now)
            if self.optimizer_plan:
                archive_changed = (
                    self._sync_plan_execution_archive(self.optimizer_plan, now)
                    or archive_changed
                )
        if archive_changed:
            await self.async_save_ai_data()

        tracking = self.learning_tracking
        try:
            previous = datetime.fromisoformat(str(tracking.get("last_sample")))
            elapsed_seconds = max(0.0, min(120.0, (now - previous).total_seconds()))
        except (TypeError, ValueError):
            elapsed_seconds = 0.0
        hours = elapsed_seconds / 3600.0

        readings = self._telemetry_readings()
        pv_power = readings["pv"].get("value")
        load_power = readings["load"].get("value")
        phase_values = [
            readings["load_l1"].get("value"),
            readings["load_l2"].get("value"),
            readings["load_l3"].get("value"),
        ]
        grid_power = readings["grid"].get("value")
        battery_power = readings["battery"].get("value")
        soc = readings["soc"].get("value")
        sell_price = readings["sell_price"].get("value")
        buy_price = readings["buy_price"].get("value")

        channel_state = tracking.setdefault("channels", {})
        for name, reading in readings.items():
            channel_state[name] = record_channel(
                channel_state.get(name),
                value=reading.get("value"),
                elapsed_seconds=elapsed_seconds,
                quality=str(reading.get("quality") or "unavailable"),
                status=str(reading.get("status") or "unavailable"),
                source=str(reading.get("source") or "unavailable"),
            )

        if pv_power is not None:
            tracking["pv_kwh"] = self.safe_float(tracking.get("pv_kwh"), 0) + max(0, float(pv_power)) / 1000 * hours
        if load_power is not None:
            tracking["load_kwh"] = self.safe_float(tracking.get("load_kwh"), 0) + max(0, float(load_power)) / 1000 * hours
        for index, value in enumerate(phase_values, start=1):
            if value is not None:
                key = f"load_l{index}_kwh"
                tracking[key] = self.safe_float(tracking.get(key), 0) + max(0, float(value)) / 1000 * hours
        if grid_power is not None:
            tracking["grid_import_kwh"] = self.safe_float(tracking.get("grid_import_kwh"), 0) + max(0, float(grid_power)) / 1000 * hours
            tracking["grid_export_kwh"] = self.safe_float(tracking.get("grid_export_kwh"), 0) + max(0, -float(grid_power)) / 1000 * hours
        if battery_power is not None:
            tracking["battery_charge_kwh"] = self.safe_float(tracking.get("battery_charge_kwh"), 0) + max(0, -float(battery_power)) / 1000 * hours
            tracking["battery_discharge_kwh"] = self.safe_float(tracking.get("battery_discharge_kwh"), 0) + max(0, float(battery_power)) / 1000 * hours
        tracking["samples"] = int(tracking.get("samples", 0)) + 1
        if soc is not None:
            tracking["soc_sum"] = self.safe_float(tracking.get("soc_sum"), 0) + soc
            tracking["soc_samples"] = int(tracking.get("soc_samples", 0)) + 1
            tracking["soc_last"] = soc
        if sell_price is not None:
            tracking["sell_price_sum"] = self.safe_float(tracking.get("sell_price_sum"), 0) + float(sell_price)
        if buy_price is not None:
            tracking["buy_price_sum"] = self.safe_float(tracking.get("buy_price_sum"), 0) + float(buy_price)
        if soc is not None:
            tracking["soc_min"] = soc if tracking.get("soc_min") is None else min(self.safe_float(tracking.get("soc_min"), soc), soc)
            tracking["soc_max"] = soc if tracking.get("soc_max") is None else max(self.safe_float(tracking.get("soc_max"), soc), soc)
        tracking["daily_pv_kwh"] = max(0, self.state_float(self.daily_pv_production_sensor, 0))
        tracking["source_quality"] = self.source_quality_context()
        tracking["live_state"] = self.live_state_context(readings, now)
        latest_flags = pv_quality_flags(
            battery_soc=soc,
            work_mode=self.state_text(self.work_mode_select),
            grid_available=self.entity_available(self.grid_power_sensor),
            actual_power_w=self._measurement(self.pv_power_sensor).get("value"),
            inverter_limit_w=min(
                finite_float(self.ai_settings.get("inverterPowerW")) or float("inf"),
                self.effective_inverter_max_power_w,
            ),
            sensor_stale=self._measurement(self.pv_power_sensor).get("status") == "stale",
            manual_override=self.control_mode != "Schedule",
        )
        existing_flags = tracking.setdefault("quality_flags", {})
        for key, value in latest_flags.items():
            existing_flags[key] = bool(existing_flags.get(key)) or bool(value)
        tracking["energy_counters"] = dict(self.data_quality.get("energy_counters") or {})
        tracking["last_sample"] = now.isoformat()

        if now.minute % 15 == 0:
            await self.async_save_learning_history()
        if completed_learning_hour:
            self.request_optimizer_recalc("learning")
            self._notify_update_for("learning")

    def _invalidate_learning_summary_cache(self) -> None:
        """Invalidate the heavy learning snapshot after a semantic data change."""
        self._learning_summary_generation += 1
        self._learning_summary_cache_key = ""
        self._learning_summary_cache = {}

    def learning_summary(self) -> dict[str, Any]:
        """Return one immutable-by-convention snapshot for unchanged inputs."""
        self._performance.inc("learning_summary_wrapper_calls")
        current_weather = self.weather_context()
        current_tariff = self.tariff_context()
        price_coverage_today = len(self.price_map(self.price_sensor))
        price_coverage_tomorrow = len(
            self.price_map(self.sell_price_tomorrow_sensor, False)
        )
        cache_key = snapshot_id({
            "generation": self._learning_summary_generation,
            "learning_revision": self.learning_revision,
            "history_watermark": self.history_watermark,
            # Runtime history/profile mutations replace these containers.  The
            # identity/length guards also keep direct fixture replacement safe.
            "learning_history": [id(self.learning_history), len(self.learning_history)],
            "solcast_history": [id(self.solcast_history), len(self.solcast_history)],
            "load_profile": id(self.load_profile_7x24),
            "pv_profile": id(self.pv_learning_profile),
            # The current-day Solcast progress changes in-place between ticks.
            "solcast_tracking": {
                "date": self.solcast_tracking.get("date"),
                "forecast": self.solcast_tracking.get("forecast"),
                "latest_forecast_kwh": self.solcast_tracking.get("latest_forecast_kwh"),
                "actual": self.solcast_tracking.get("actual"),
                "updated_at": self.solcast_tracking.get("updated_at"),
                "forecast_status": self.solcast_tracking.get("forecast_status"),
            },
            # learning_summary exposes counts, not the archive contents.
            "energy_counts": [
                len(self.energy_samples),
                len(self.daily_archive),
                len(self.monthly_archive),
            ],
            "price_coverage": [price_coverage_today, price_coverage_tomorrow],
            # These are public parts of the summary and therefore semantic cache
            # inputs even though they are much cheaper than the history scans.
            "weather": current_weather,
            "tariff": current_tariff,
            "sources": {
                "pv_power": self.pv_power_sensor,
                "load_power": self.load_power_sensor,
                "grid_power": self.grid_power_sensor,
                "battery_power": self.battery_power_sensor,
                "battery_soc": self.battery_soc_sensor,
                "daily_pv": self.daily_pv_production_sensor,
                "solcast": self.solcast_forecast_today_sensor,
                "sell_price": self.price_sensor,
                "buy_price": self.buy_price_today_sensor,
                "weather": self.weather_entity,
            },
        })
        if cache_key == self._learning_summary_cache_key:
            self._performance.inc("learning_summary_cache_hits")
            return self._learning_summary_cache
        build_started = time.perf_counter()
        summary = self._build_learning_summary(
            current_weather=current_weather,
            current_tariff=current_tariff,
            price_coverage_today=price_coverage_today,
            price_coverage_tomorrow=price_coverage_tomorrow,
        )
        self._performance.observe_ms(
            "learning_summary_build",
            (time.perf_counter() - build_started) * 1000.0,
        )
        self._learning_summary_cache = summary
        self._learning_summary_cache_key = cache_key
        return summary

    def _build_learning_summary(
        self,
        *,
        current_weather: dict[str, Any],
        current_tariff: dict[str, Any],
        price_coverage_today: int,
        price_coverage_tomorrow: int,
    ) -> dict[str, Any]:
        """Build the uncached learning result without changing its contract."""
        rows = self.learning_history
        dates = {str(row.get("hour", ""))[:10] for row in rows if row.get("hour")}
        channel_names = (
            "pv", "load", "load_l1", "load_l2", "load_l3",
            "grid", "battery", "soc", "sell_price", "buy_price",
        )
        channel_diagnostics: dict[str, dict[str, Any]] = {}
        for name in channel_names:
            summaries = [
                row.get("channel_quality", {}).get(name)
                for row in rows
                if isinstance(row.get("channel_quality"), dict)
                and isinstance(row.get("channel_quality", {}).get(name), dict)
            ]
            channel_diagnostics[name] = {
                "hours": len(summaries),
                "usable_hours": sum(1 for item in summaries if item.get("usable_for_learning")),
                "full_hours": sum(1 for item in summaries if item.get("level") == "full"),
                "partial_hours": sum(1 for item in summaries if item.get("level") == "partial"),
                "very_low_hours": sum(1 for item in summaries if item.get("level") == "very_low"),
                "missing_hours": sum(1 for item in summaries if item.get("level") == "missing"),
                "average_coverage_percent": round(
                    sum(self.safe_float(item.get("coverage_percent"), 0) for item in summaries)
                    / max(1, len(summaries)),
                    1,
                ) if summaries else None,
                "average_quality_score": round(
                    sum(self.safe_float(item.get("quality_score"), 0) for item in summaries)
                    / max(1, len(summaries)),
                    1,
                ) if summaries else None,
            }
        complete_by_day: dict[str, set[int]] = {}
        for row in rows:
            if not row.get("complete"):
                continue
            day = str(row.get("hour", ""))[:10]
            hour_text = str(row.get("hour", ""))[11:13]
            if day and hour_text.isdigit():
                complete_by_day.setdefault(day, set()).add(int(hour_text))
        completed_days = sum(1 for hours in complete_by_day.values() if len(hours) == 24)
        legacy_stage = learning_stage(completed_days)

        def valid_average(matches: list[dict[str, Any]], key: str, digits: int) -> float | None:
            values = [
                value
                for row in matches
                if (value := finite_float(row.get(key))) is not None
            ]
            return round(sum(values) / len(values), digits) if values else None

        per_hour: list[dict[str, Any]] = []
        for hour in range(24):
            matches = [row for row in rows if str(row.get("hour", ""))[11:13] == f"{hour:02d}"]
            if not matches:
                continue
            per_hour.append({
                "hour": f"{hour:02d}:00",
                "samples": len(matches),
                "pv_kwh": valid_average(matches, "pv_kwh", 3),
                "load_kwh": valid_average(matches, "load_kwh", 3),
                "grid_export_kwh": valid_average(matches, "grid_export_kwh", 3),
                "battery_charge_kwh": valid_average(matches, "battery_charge_kwh", 3),
                "battery_discharge_kwh": valid_average(matches, "battery_discharge_kwh", 3),
                "soc_avg": valid_average(matches, "soc_avg", 1),
                "sell_price_avg": valid_average(matches, "sell_price_avg", 3),
                "buy_price_avg": valid_average(matches, "buy_price_avg", 3),
            })
        completed_rows = [
            row for row in self.solcast_history
            if row.get("accuracy_percent") is not None
            and self.safe_float(row.get("forecast_kwh"), 0) > 0
            and row.get("day_complete", True)
        ]
        accuracy_rows = [self.safe_float(row.get("accuracy_percent"), 0) for row in completed_rows]
        correction_rows = [
            max(0.5, min(1.5, self.safe_float(row.get("actual_kwh"), 0) / self.safe_float(row.get("forecast_kwh"), 1)))
            for row in completed_rows
        ]
        # The global Solcast correction starts conservatively and converges only
        # after a representative history.  Newest completed days have the
        # strongest influence, while a short history remains close to 1.0.
        weighted_correction = None
        if correction_rows:
            recency_weights = [0.90 ** index for index in range(len(correction_rows))]
            raw_correction = sum(
                value * weight
                for value, weight in zip(correction_rows, recency_weights)
            ) / sum(recency_weights)
            history_weight = min(1.0, len(correction_rows) / 21.0)
            weighted_correction = 1.0 + (raw_correction - 1.0) * history_weight
        historical_accuracy = (
            round(sum(accuracy_rows) / len(accuracy_rows), 1)
            if accuracy_rows
            else None
        )
        current_metrics = self.solcast_current_day_metrics(
            historical_accuracy_pct=historical_accuracy,
        )
        latest = completed_rows[0] if completed_rows else {}
        usable_hours = sum(
            1
            for row in rows
            if any(
                item.get("usable_for_learning")
                for item in (row.get("channel_quality") or {}).values()
                if isinstance(item, dict)
            )
        )
        load_cells = self._learning_profile_stats(self.load_profile_7x24)["covered_cells"]
        pv_stats = self._learning_profile_stats(self.pv_learning_profile)
        last_hour = max(
            (str(row.get("hour")) for row in rows if row.get("hour")),
            default=None,
        )
        maturity = learning_maturity(
            valid_hours=usable_hours,
            complete_days=completed_days,
            load_covered_cells=load_cells,
            pv_covered_cells=pv_stats["covered_cells"],
            pv_accepted_samples=pv_stats["accepted_samples"],
            pv_rejected_samples=pv_stats["rejected_samples"],
            forecast_accuracy_days=len(accuracy_rows),
            history_last_hour=last_hour,
            now=ha_now(),
        )
        # Compatibility alias: callers may still inspect the old stage shape,
        # but readiness comes from evidence and Core ignores the legacy cap when
        # ``learning_maturity`` is present.
        stage = {
            **legacy_stage,
            "legacy_status": legacy_stage["status"],
            "status": maturity["label"],
            "dry_run": not maturity["application_ready"],
            "apply_allowed": maturity["application_ready"],
            "suggestion_ready": maturity["score"] > 0,
            "legacy": True,
        }
        tariff_groups: dict[tuple[str, ...], list[dict[str, Any]]] = {}
        for row in rows:
            tariff = row.get("tariff") if isinstance(row.get("tariff"), dict) else {}
            if not tariff:
                continue
            key = (
                str(tariff.get("provider") or ""),
                str(tariff.get("plan") or ""),
                str(tariff.get("zone") or ""),
                str(tariff.get("day_type") or ""),
                str(tariff.get("season") or ""),
                str(row.get("hour") or "")[11:13],
            )
            tariff_groups.setdefault(key, []).append(row)
        tariff_learning = []
        for key, matches in tariff_groups.items():
            count = len(matches)
            tariff_learning.append({
                "provider": key[0], "plan": key[1], "zone": key[2],
                "day_type": key[3], "season": key[4], "hour": key[5],
                "samples": count,
                "load_kwh": round(sum(self.safe_float(row.get("load_kwh"), 0) for row in matches) / count, 3),
                "grid_import_kwh": round(sum(self.safe_float(row.get("grid_import_kwh"), 0) for row in matches) / count, 3),
                "battery_charge_kwh": round(sum(self.safe_float(row.get("battery_charge_kwh"), 0) for row in matches) / count, 3),
            })
        return {
            "schema_version": HISTORY_SCHEMA_VERSION,
            "retention_days": 730,
            "retention": {"raw_1_min_days": 90, "hourly_months": 24, "daily_years": 5, "monthly_limit": None},
            "raw_samples": len(self.energy_samples),
            "daily_archive_rows": len(self.daily_archive),
            "monthly_archive_rows": len(self.monthly_archive),
            "observed_days": len(dates),
            "recorded_days": completed_days,
            "completed_full_days": completed_days,
            "recorded_hours": len(rows),
            "usable_hours": usable_hours,
            "history_first_hour": min(
                (str(row.get("hour")) for row in rows if row.get("hour")),
                default=None,
            ),
            "history_last_hour": max(
                (str(row.get("hour")) for row in rows if row.get("hour")),
                default=None,
            ),
            "channel_diagnostics": channel_diagnostics,
            "learning_stage": stage,
            "learning_maturity": maturity,
            "learning_revision": self.learning_revision,
            "history_watermark": self.history_watermark or last_hour or "",
            "readiness": stage["readiness"],
            "load_profile_7x24": self.load_profile_7x24,
            "load_profile_diagnostics": load_profile_diagnostics(
                self.load_profile_7x24,
                completed_days=completed_days,
            ),
            "pv_profile": self.pv_learning_profile,
            "pv_profile_diagnostics": pv_profile_diagnostics(
                self.pv_learning_profile,
                completed_days=completed_days,
            ),
            "data_coverage": {
                "prices_today": price_coverage_today,
                "prices_tomorrow": price_coverage_tomorrow,
                "weather": min(48, len(self.weather_forecast)),
            },
            "solcast_accuracy_avg": historical_accuracy,
            "solcast_correction_factor": round(weighted_correction, 3) if weighted_correction is not None else None,
            "solcast_accuracy_days": len(accuracy_rows),
            "solcast_last_accuracy": latest.get("accuracy_percent"),
            "solcast_last_date": latest.get("date"),
            "current_forecast_progress": current_metrics.get("realization_today_pct"),
            "typical_daily_pv_kwh": round(sum(row["pv_kwh"] or 0 for row in per_hour), 2),
            "typical_daily_load_kwh": round(sum(row["load_kwh"] or 0 for row in per_hour), 2),
            "typical_daily_grid_export_kwh": round(sum(row["grid_export_kwh"] or 0 for row in per_hour), 2),
            "typical_daily_battery_charge_kwh": round(sum(row["battery_charge_kwh"] or 0 for row in per_hour), 2),
            "typical_daily_battery_discharge_kwh": round(sum(row["battery_discharge_kwh"] or 0 for row in per_hour), 2),
            "sources": {
                "pv_power": self.pv_power_sensor,
                "load_power": self.load_power_sensor,
                "grid_power": self.grid_power_sensor,
                "battery_power": self.battery_power_sensor,
                "battery_soc": self.battery_soc_sensor,
                "daily_pv": self.daily_pv_production_sensor,
                "solcast": self.solcast_forecast_today_sensor,
                "sell_price": self.price_sensor,
                "buy_price": self.buy_price_today_sensor,
                "weather": self.weather_entity,
            },
            "weather": current_weather,
            "tariff": current_tariff,
            "tariff_learning": tariff_learning[:500],
            "hourly_profile": per_hour,
        }

    def history_daily_summary(self) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = {}
        for row in self.learning_history:
            day = str(row.get("hour") or "")[:10]
            if not day:
                continue
            item = grouped.setdefault(day, {"date": day})
            for key in ("pv_kwh", "load_kwh", "grid_import_kwh", "grid_export_kwh", "battery_charge_kwh", "battery_discharge_kwh"):
                value = finite_float(row.get(key))
                if value is not None:
                    item[key] = self.safe_float(item.get(key), 0) + value
            soc_min = finite_float(row.get("soc_min"))
            soc_max = finite_float(row.get("soc_max"))
            if soc_min is not None:
                item["soc_min"] = min(self.safe_float(item.get("soc_min"), soc_min), soc_min)
            if soc_max is not None:
                item["soc_max"] = max(self.safe_float(item.get("soc_max"), soc_max), soc_max)
        for day, values in self.sales_stats.get("daily", {}).items():
            item = grouped.setdefault(day, {"date": day})
            item["sold_kwh"] = self.safe_float(values.get("kwh"), 0)
            item["sold_value"] = self.safe_float(values.get("value"), 0)
        for row in self.solcast_history:
            day = str(row.get("date") or "")
            item = grouped.setdefault(day, {"date": day})
            item.update({
                "forecast_kwh": self.safe_float(row.get("forecast_kwh"), 0),
                "actual_kwh": self.safe_float(row.get("actual_kwh"), 0),
                "accuracy_percent": self.safe_float(row.get("accuracy_percent"), 0),
            })
        tracking_day = str(self.solcast_tracking.get("date") or "")
        if tracking_day:
            metrics = self.solcast_current_day_metrics()
            forecast = metrics.get("forecast_today_kwh")
            actual = metrics.get("production_today_kwh")
            grouped.setdefault(tracking_day, {"date": tracking_day}).update({
                "forecast_kwh": forecast,
                "actual_kwh": actual,
                "accuracy_percent": None,
                "realization_today_pct": metrics.get("realization_today_pct"),
                # Compatibility alias; it is sourced from the same canonical
                # value and is no longer calculated independently.
                "forecast_progress_percent": metrics.get("realization_today_pct"),
                "forecast_difference_today_kwh": metrics.get("forecast_difference_today_kwh"),
                "solcast_data_status": metrics.get("data_status"),
                "day_complete": False,
            })
        for row in self.daily_archive:
            day = str(row.get("date") or "")
            if day:
                grouped.setdefault(day, dict(row))
        return [
            {key: round(value, 3) if isinstance(value, float) else value for key, value in row.items()}
            for _day, row in sorted(grouped.items(), reverse=True)[:1825]
        ]

    def history_monthly_summary(self) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = {}
        for row in self.history_daily_summary():
            month = str(row.get("date") or "")[:7]
            if not month:
                continue
            item = grouped.setdefault(month, {"month": month, "days": 0})
            item["days"] += 1
            for key in ("pv_kwh", "load_kwh", "grid_import_kwh", "grid_export_kwh", "battery_charge_kwh", "battery_discharge_kwh", "sold_kwh", "sold_value", "forecast_kwh", "actual_kwh"):
                item[key] = self.safe_float(item.get(key), 0) + self.safe_float(row.get(key), 0)
        for row in self.monthly_archive:
            month = str(row.get("month") or "")
            if month and month not in grouped:
                grouped[month] = dict(row)
        return [
            {key: round(value, 3) if isinstance(value, float) else value for key, value in row.items()}
            for _month, row in sorted(grouped.items(), reverse=True)
        ]

    def safe_float(self, value: Any, default: float = 0) -> float:
        number = finite_float(value)
        return default if number is None else number

    def solcast_forecast_today_reading(self) -> dict[str, Any]:
        """Resolve today's full forecast with source and freshness metadata."""
        configured = self._measurement(
            self.solcast_forecast_today_sensor,
            kind="energy",
            stale_after_seconds=_SOLCAST_DAILY_FORECAST_STALE_SECONDS,
        )
        if configured.get("status") == "ok" and self.safe_float(configured.get("value"), 0) > 0:
            return configured

        for state in self.hass.states.async_all("sensor"):
            entity_id = state.entity_id.lower()
            friendly_name = str(state.attributes.get("friendly_name") or "").lower()
            searchable = f"{entity_id} {friendly_name}"
            if "solcast" not in searchable:
                continue
            if not any(token in searchable for token in ("prognoza_na_dzis", "prognoza na dziś", "forecast_today", "forecast today")):
                continue
            if any(token in searchable for token in ("pozostal", "remaining", "aktualna_moc", "current_power", "szczyt", "peak")):
                continue
            candidate = self._measurement(
                state.entity_id,
                kind="energy",
                stale_after_seconds=_SOLCAST_DAILY_FORECAST_STALE_SECONDS,
            )
            if candidate.get("status") == "ok" and self.safe_float(candidate.get("value"), 0) > 0:
                candidate["source"] = "discovered_renamed_entity"
                return candidate

        actual = self._measurement(
            self.daily_pv_production_sensor,
            kind="energy",
            stale_after_seconds=_SOLCAST_TRACKING_STALE_SECONDS,
        )
        remaining = self._measurement(
            self.solcast_remaining_today_sensor,
            kind="energy",
            stale_after_seconds=_SOLCAST_TRACKING_STALE_SECONDS,
        )
        remaining_value = self.safe_float(remaining.get("value"), 0)
        if (
            actual.get("status") == "ok"
            and remaining.get("status") == "ok"
            and remaining_value > 0
        ):
            return {
                "entity_id": self.solcast_remaining_today_sensor,
                "value": max(0, self.safe_float(actual.get("value"), 0)) + remaining_value,
                "unit": "kWh",
                "last_updated": remaining.get("last_updated"),
                "status": "derived_actual_plus_remaining",
                "quality": "degraded",
                "source": "actual_plus_remaining",
            }
        if configured.get("status") == "ok":
            configured["status"] = "zero_forecast"
            configured["quality"] = "unavailable"
        return configured

    def solcast_forecast_today_value(self) -> float:
        """Return the fresh full-day forecast value or the compatibility zero."""
        reading = self.solcast_forecast_today_reading()
        if reading.get("status") not in ("ok", "derived_actual_plus_remaining"):
            return 0
        return max(0, self.safe_float(reading.get("value"), 0))

    def solcast_current_day_metrics(
        self,
        *,
        historical_accuracy_pct: Any = None,
    ) -> dict[str, Any]:
        """Return the single O(1) current-day Solcast presentation contract."""
        now = ha_now()
        today = now.date().isoformat()
        tracking = self.solcast_tracking if isinstance(self.solcast_tracking, dict) else {}
        tracking_day = str(tracking.get("date") or "")
        forecast = finite_float(
            tracking.get("latest_forecast_kwh", tracking.get("forecast"))
        )
        production = finite_float(tracking.get("actual"))
        status = str(tracking.get("forecast_status") or "legacy_tracking")
        updated_at = tracking.get("updated_at")
        stale_tracking = False
        if updated_at:
            try:
                updated = datetime.fromisoformat(str(updated_at))
                tracking_age = self._timestamp_age_seconds(updated)
                stale_tracking = (
                    tracking_age is not None
                    and tracking_age > _SOLCAST_TRACKING_STALE_SECONDS
                )
            except (TypeError, ValueError):
                stale_tracking = True
        if tracking_day != today:
            status = "stale_local_day"
        elif stale_tracking:
            status = "stale"
        elif (
            status in ("ok", "derived_actual_plus_remaining", "legacy_tracking")
            and (forecast is None or forecast <= 0)
        ):
            status = "zero_forecast"

        forecast_usable = (
            status in ("ok", "derived_actual_plus_remaining", "legacy_tracking")
            and forecast is not None
            and forecast > 0
        )
        production_usable = (
            tracking_day == today
            and production is not None
            and production >= 0
        )
        usable = forecast_usable and production_usable
        canonical_forecast = max(0.0, forecast) if forecast_usable else None
        canonical_production = max(0.0, production) if production_usable else None
        realization = (
            canonical_production / canonical_forecast * 100
            if usable and canonical_forecast is not None and canonical_production is not None
            else None
        )
        difference = (
            canonical_production - canonical_forecast
            if usable and canonical_forecast is not None and canonical_production is not None
            else None
        )
        remaining = self._measurement(
            self.solcast_remaining_today_sensor,
            kind="energy",
            stale_after_seconds=_SOLCAST_TRACKING_STALE_SECONDS,
        )
        tomorrow = self._measurement(
            self.solcast_forecast_tomorrow_sensor,
            kind="energy",
            stale_after_seconds=_SOLCAST_DAILY_FORECAST_STALE_SECONDS,
        )

        def rounded(value: Any, digits: int = 3) -> float | None:
            number = finite_float(value)
            return round(number, digits) if number is not None else None

        return {
            "local_day": today,
            "tracking_day": tracking_day or None,
            "forecast_today_kwh": rounded(canonical_forecast),
            "production_today_kwh": rounded(canonical_production),
            "remaining_forecast_kwh": (
                rounded(max(0.0, self.safe_float(remaining.get("value"), 0)))
                if remaining.get("status") == "ok"
                else None
            ),
            "realization_today_pct": rounded(realization, 1),
            "historical_accuracy_pct": rounded(historical_accuracy_pct, 1),
            "forecast_difference_today_kwh": rounded(difference),
            "forecast_tomorrow_kwh": (
                rounded(max(0.0, self.safe_float(tomorrow.get("value"), 0)))
                if tomorrow.get("status") == "ok"
                else None
            ),
            "data_status": (
                "ok"
                if usable
                else "production_unavailable"
                if forecast_usable and not production_usable
                else status
            ),
            "forecast_source": tracking.get("forecast_source") or self.solcast_forecast_today_sensor,
            "forecast_source_status": status,
            "tracking_updated_at": updated_at,
            "initial_forecast_kwh": rounded(tracking.get("initial_forecast_kwh", tracking.get("forecast"))),
        }

    def ensure_current_day_stats(self, day: str) -> None:
        if not self.sales_stats:
            self.sales_stats = self.empty_sales_stats()
        if self.sales_stats.get("current_day") == day:
            return

        previous_day = str(self.sales_stats.get("current_day") or "")
        if previous_day:
            kwh = sum(self.safe_float(values.get("kwh"), 0) for values in self.sales_stats.get("hourly", {}).values())
            value = sum(self.safe_float(values.get("value"), 0) for values in self.sales_stats.get("hourly", {}).values())
            daily = self.sales_stats.setdefault("daily", {})
            daily[previous_day] = {"kwh": round(kwh, 4), "value": round(value, 4)}
            for old_day in sorted(daily)[:-1825]:
                daily.pop(old_day, None)

        self.sales_stats["current_day"] = day
        self.sales_stats["hourly"] = self.empty_hourly_stats()
        self._stats_dirty = True

    def refresh_sales_totals(self) -> None:
        hourly = self.sales_stats.get("hourly", {}) if self.sales_stats else {}
        current_hour = f"{ha_now().hour:02d}"
        current = hourly.get(current_hour, {})
        integrated_kwh = sum(self.safe_float(values.get("kwh"), 0) for values in hourly.values())
        integrated_value = sum(self.safe_float(values.get("value"), 0) for values in hourly.values())
        counter = self._measurement(self.daily_energy_sold_sensor, kind="energy")
        provider_kwh = counter.get("value")
        self.sold_energy_today = round(float(provider_kwh) if provider_kwh is not None else integrated_kwh, 4)
        # The provider counter has no hourly price breakdown. Keep the monetary
        # result based on the Manager's hourly integration instead of inventing
        # a historical price for the counter difference.
        self.sold_value_today = round(integrated_value, 4)
        self.data_quality["sales_today"] = {
            "energy_source": "daily_export_counter" if provider_kwh is not None else "integrated_grid_power",
            "provider_export_kwh": None if provider_kwh is None else round(float(provider_kwh), 4),
            "integrated_export_kwh": round(integrated_kwh, 4),
            "difference_kwh": None if provider_kwh is None else round(float(provider_kwh) - integrated_kwh, 4),
            "value_source": "integrated_hourly_prices",
        }
        self.sold_energy_current_hour = round(self.safe_float(current.get("kwh"), 0), 4)
        self.sold_value_current_hour = round(self.safe_float(current.get("value"), 0), 4)

    def sales_hourly_today(self) -> list[dict[str, Any]]:
        hourly = self.sales_stats.get("hourly", {}) if self.sales_stats else {}
        data: list[dict[str, Any]] = []
        for hour in range(24):
            key = f"{hour:02d}"
            values = hourly.get(key, {})
            kwh = round(self.safe_float(values.get("kwh"), 0), 4)
            value = round(self.safe_float(values.get("value"), 0), 4)
            data.append(
                {
                    "hour": hour,
                    "label": f"{hour:02d}-{(hour + 1) % 24:02d}",
                    "kwh": kwh,
                    "value": value,
                    "avg_price": round(value / kwh, 4) if kwh > 0 else 0,
                }
            )
        return data

    def sales_daily_rows(self, days: int | None = None, month_only: bool = False) -> list[dict[str, Any]]:
        today = ha_now().date()
        daily = dict(self.sales_stats.get("daily", {}) if self.sales_stats else {})
        daily[today.isoformat()] = {"kwh": self.sold_energy_today, "value": self.sold_value_today}
        rows: list[dict[str, Any]] = []
        for day, values in sorted(daily.items()):
            try:
                date_obj = datetime.fromisoformat(day).date()
            except ValueError:
                continue
            if month_only and (date_obj.year != today.year or date_obj.month != today.month):
                continue
            rows.append(
                {
                    "date": day,
                    "label": date_obj.strftime("%d.%m"),
                    "kwh": round(self.safe_float(values.get("kwh"), 0), 4),
                    "value": round(self.safe_float(values.get("value"), 0), 4),
                }
            )
        if days is not None:
            rows = rows[-days:]
        return rows

    @property
    def sales_week_rows(self) -> list[dict[str, Any]]:
        return self.sales_daily_rows(days=7)

    @property
    def sales_month_rows(self) -> list[dict[str, Any]]:
        return self.sales_daily_rows(month_only=True)

    async def async_update_sold_energy_today(self) -> None:
        current = ha_now()
        current_day = current.date().isoformat()
        self.ensure_current_day_stats(current_day)
        self._energy_day = current_day
        if self._energy_last_update is None:
            self._energy_last_update = current
            self._stats_dirty = True
            self.refresh_sales_totals()
            await self.async_save_sales_stats()
            return
        delta_seconds = max((current - self._energy_last_update).total_seconds(), 0)
        delta_seconds = min(delta_seconds, 300)
        delta_hours = delta_seconds / 3600
        self._energy_last_update = current
        grid_power = self.normalized_grid_power()
        exported_power_w = max(0, -grid_power)
        if exported_power_w > 0 and delta_hours > 0:
            kwh = (exported_power_w / 1000) * delta_hours
            value = kwh * max(self.state_float(self.price_sensor, 0), 0)
            hour_key = f"{current.hour:02d}"
            hourly = self.sales_stats.setdefault("hourly", self.empty_hourly_stats())
            values = hourly.setdefault(hour_key, {"kwh": 0.0, "value": 0.0})
            values["kwh"] = round(self.safe_float(values.get("kwh"), 0) + kwh, 6)
            values["value"] = round(self.safe_float(values.get("value"), 0) + value, 6)
            self._stats_dirty = True
        self.refresh_sales_totals()
        await self.async_save_sales_stats()

    @property
    def active_min_sell_soc(self) -> float:
        if (
            self.control_mode == "Schedule"
            and self.active_slot.enabled
            and self.active_slot.mode == MODE_SELLING_FIRST
            and self.active_slot.minimum_sell_soc > 0
        ):
            return self.active_slot.minimum_sell_soc
        return self.min_sell_soc

    @property
    def active_min_sell_price(self) -> float:
        if self.control_mode == "Schedule" and self.active_slot.enabled and self.active_slot.min_sell_price > 0:
            return self.active_slot.min_sell_price
        return self.price_sell_threshold if self.price_guard_enabled else 0

    @property
    def soc_ok(self) -> bool:
        if not self.soc_guard_enabled or self.active_min_sell_soc <= 0:
            return True
        soc = self.current_soc_or_none()
        return soc is not None and 0 <= soc <= 100 and soc > self.active_min_sell_soc

    @property
    def price_ok(self) -> bool:
        if self.active_min_sell_price <= 0:
            return True
        price = self.state_float_or_none(self.price_sensor)
        return price is not None and price >= self.active_min_sell_price

    @property
    def sell_allowed(self) -> bool:
        return (
            not self.emergency_stop
            and self.data_available
            and self.soc_ok
            and self.price_ok
            and self.control_mode != "Protect Battery"
        )

    def _selling_slot_guard_issue(self) -> tuple[str, str] | None:
        """Classify a Selling First guard as a normal block or a data error.

        A valid SOC or price below the slot threshold is an expected runtime
        condition, not a failed Deye transaction.  An absent or malformed
        source remains an error because the manager cannot make a safe
        selling decision from it.
        """
        if not (
            self.control_mode == "Schedule"
            and self.active_slot.enabled
            and self.active_slot.mode == MODE_SELLING_FIRST
        ):
            return None

        if self.soc_guard_enabled and self.active_min_sell_soc > 0:
            soc = self.current_soc_or_none()
            if soc is None or not 0 <= soc <= 100:
                return ("error", "Brak poprawnego odczytu SOC dla sprzedaży")
            if soc <= self.active_min_sell_soc:
                return (
                    "blocked",
                    f"Sprzedaż wstrzymana: SOC {soc:.0f}% osiągnął lub jest niższy od limitu "
                    f"{self.active_min_sell_soc:.0f}%",
                )

        if self.active_min_sell_price > 0:
            price = self.state_float_or_none(self.price_sensor)
            if price is None:
                return ("error", "Brak poprawnego odczytu ceny sprzedaży")
            if price < self.active_min_sell_price:
                return (
                    "blocked",
                    f"Sprzedaż wstrzymana: cena {price:.2f} PLN/kWh jest niższa od progu "
                    f"{self.active_min_sell_price:.2f} PLN/kWh",
                )
        return None

    def _selling_slot_is_blocked(self) -> bool:
        issue = self._selling_slot_guard_issue()
        return issue is not None and issue[0] == "blocked"

    def _sell_block_fingerprint(self, reason: str) -> str:
        """Identify one continuous, normal sale block without repeated writes."""
        return f"{self.active_slot_key()}:{reason.split(':', 1)[0]}"

    @property
    def charge_allowed(self) -> bool:
        """Compatibility status for manual charge controls.

        It never grants grid charging.  That permission belongs exclusively
        to the active Charge slot's explicit ``charge_enabled`` flag.
        """
        return not self.emergency_stop and self.data_available

    @property
    def active_charge_slot(self) -> bool:
        """Whether the current schedule slot uses its copied Charge settings."""
        return (
            self.control_mode == "Schedule"
            and self.active_slot.enabled
            and self.active_slot.mode == MODE_CHARGE
        )

    @property
    def target_mode(self) -> str:
        if self.control_mode == "Manual Sell":
            return MODE_SELLING_FIRST
        if self.control_mode in ("Stop Sell", "Protect Battery", "Charge Battery"):
            # Polish manager model: these override actions fall back to normal
            # operation.  The physical topology is resolved separately.
            return MODE_NORMAL_OPERATION
        if (
            self.control_mode == "Schedule"
            and self.active_slot.enabled
            and self.active_slot.mode == MODE_SELLING_FIRST
            and self._selling_slot_is_blocked()
        ):
            return self.default_work_mode
        if self.active_charge_slot:
            # Charge is a manager profile, not a fourth Deye work mode.  Keep
            # the user's selected default logical mode (Normalna Praca).
            return self.default_work_mode
        if self.active_slot.enabled:
            return self.active_slot.mode
        return self.default_work_mode

    @property
    def target_sell_power(self) -> float:
        if self.control_mode == "Manual Sell":
            return self.manual_sell_power
        if self.control_mode != "Schedule":
            return self.default_sell_power
        if self.active_slot.enabled and self.active_slot.mode == MODE_SELLING_FIRST and self._selling_slot_is_blocked():
            return self.default_sell_power
        if self.active_charge_slot:
            return self.default_sell_power
        return self.active_slot.sell_power if self.active_slot.enabled else self.default_sell_power

    @property
    def applied_sell_power(self) -> float:
        """Sell power normalized for safe automatic Deye writes."""
        return self.normalize_automatic_sell_power_w(self.target_sell_power)

    @property
    def target_discharge_current(self) -> float:
        if self.control_mode == "Manual Sell":
            return self.manual_discharge_current
        if self.control_mode != "Schedule":
            return self.default_discharge_current
        if self.active_slot.enabled and self.active_slot.mode == MODE_SELLING_FIRST and self._selling_slot_is_blocked():
            return self.default_discharge_current
        if self.active_charge_slot:
            return self._effective_slot_discharge_current(self.active_slot)
        if (
            self.active_slot.enabled
            and self.active_slot.mode == MODE_SELLING_FIRST
            and self.active_slot.ai_sell_power_only
        ):
            # AI/Core Sell owns only the action and sell power.  The global
            # battery current remains the independently configured user limit.
            return self.user_schedule_discharge_current
        return (
            self._effective_slot_discharge_current(self.active_slot)
            if self.active_slot.enabled
            else self.default_discharge_current
        )

    def _effective_slot_discharge_current(self, slot: SlotSettings) -> float:
        """Resolve legacy zero as an unset schedule value, never a 0 A command.

        Old RestoreEntity rows and freshly enabled Normal Operation slots can
        contain the dataclass default ``0`` even though the user-owned global
        discharge limit is non-zero. Positive per-slot edits stay authoritative.
        """
        value = self.safe_float(slot.discharge_current, 0)
        if value > 0:
            return slot.discharge_current
        if slot.mode == MODE_CHARGE:
            charge_profile_value = self.safe_float(
                self.charge_profile_discharge_current,
                0,
            )
            if charge_profile_value > 0:
                return charge_profile_value
        return self.user_schedule_discharge_current

    @property
    def user_schedule_discharge_current(self) -> float:
        """Return the user-owned global discharge limit for automatic selling."""
        value = self.safe_float(self.normal_profile_discharge_current, 0)
        if value > 0:
            return value
        return self.default_discharge_current

    @property
    def target_charge_current(self) -> float:
        if self.control_mode == "Charge Battery":
            return self.manual_charge_current
        if self.active_charge_slot:
            return self.active_slot.charge_current
        if (
            self.control_mode == "Schedule"
            and self.active_slot.enabled
            and self.active_slot.mode == MODE_SELLING_FIRST
            and self._selling_slot_is_blocked()
        ):
            return self.default_charge_current
        if self.control_mode == "Schedule" and self.active_slot.enabled:
            return (
                self.active_slot.charge_current
                if self.active_slot.charge_current > 0
                else self.default_charge_current
            )
        return self.default_charge_current

    def _planned_manager_action_text(self) -> str:
        """Describe the existing decision path in stable, user-facing Polish."""

        if self.emergency_stop:
            action = "Zatrzymanie awaryjne"
        elif self.control_mode == "Manual Sell":
            power_kw = f"{self.manual_sell_power / 1000:.1f}".replace(".", ",")
            action = f"Sprzedaż ręczna — {power_kw} kW"
        elif self.control_mode == "Charge Battery":
            action = f"Ładowanie baterii — {self.manual_charge_current:.0f} A"
        elif self.control_mode == "Stop Sell":
            action = "Sprzedaż zatrzymana — ustawienia domyślne"
        elif self.control_mode == "Protect Battery":
            action = "Ochrona baterii — ustawienia domyślne"
        elif self.control_mode != "Schedule" or not self.scheduler_enabled:
            action = "Harmonogram wyłączony — brak działania"
        elif not self.active_slot.enabled:
            action = "Slot wyłączony — ustawienia domyślne"
        elif self.active_slot.mode == MODE_SELLING_FIRST:
            guard_issue = self._selling_slot_guard_issue()
            if guard_issue is not None:
                _kind, reason = guard_issue
                action = reason.replace(":", " —", 1)
            else:
                power_kw = f"{self.applied_sell_power / 1000:.1f}".replace(".", ",")
                action = f"Sprzedaż — {power_kw} kW"
        elif self.active_slot.mode == MODE_CHARGE:
            source = "z sieci" if self.active_slot.charge_enabled else "z PV"
            target_soc = self.safe_float(self.active_slot.tou_soc, 0)
            action = (
                f"Ładowanie {source} — {self.target_charge_current:.0f} A, "
                f"cel SOC {target_soc:.0f}%"
            )
        else:
            measurement = (
                "CT"
                if self._active_physical_work_mode() == MODE_ZERO_EXPORT_CT
                else "Load"
            )
            action = f"Normalna praca — pomiar {measurement}"

        if not self._control_is_active():
            return f"{action} — tylko monitorowanie"
        return action

    def _executed_manager_action_text(
        self,
        *,
        result: bool,
        physical_writes: int,
    ) -> str:
        """Summarize the actual outcome of one completed Manager cycle."""

        if self.emergency_stop:
            return "Nie wykonano — zatrzymanie awaryjne"
        if self._pending_control_transaction:
            return f"Oczekiwanie na potwierdzenie: {self.planned_manager_action}"
        if self.planned_manager_action.startswith("Sprzedaż wstrzymana"):
            return self.planned_manager_action.replace(
                "Sprzedaż wstrzymana", "Nie wykonano sprzedaży", 1
            )
        if result:
            if physical_writes > 0:
                return f"Zastosowano: {self.planned_manager_action}"
            return "Bez zmian — ustawienia zgodne"
        if "Przywrócono poprzednie ustawienia" in self.last_error:
            return "Przywrócono poprzednie ustawienia po błędzie"
        if self.last_error:
            detail = " ".join(str(self.last_error).split())[:160]
            return f"Błąd wykonania — {detail}"
        return f"Nie wykonano: {self.planned_manager_action}"

    @property
    def manager_status(self) -> str:
        if not self._control_is_active():
            return "TYLKO MONITOROWANIE"
        if self.emergency_stop:
            return "ZATRZYMANIE AWARYJNE"
        if not self.data_available:
            return "BRAK DANYCH"
        if self.mapping_error and self.control_mode == "Schedule":
            return "BŁĄD MAPOWANIA"
        if self.control_mode == "Protect Battery":
            return "OCHRONA BATERII"
        if self.control_mode == "Manual Sell":
            return "SPRZEDAŻ RĘCZNA"
        if self.control_mode == "Charge Battery":
            return "ŁADOWANIE BATERII"
        if self.control_mode == "Stop Sell":
            return "WSTRZYMANA SPRZEDAŻ"
        if self.control_mode == "Schedule":
            if not self.scheduler_enabled:
                return "HARMONOGRAM WYŁĄCZONY"
            if not self.active_slot.enabled:
                return "SLOT WYŁĄCZONY"
            guard_issue = self._selling_slot_guard_issue()
            if guard_issue and guard_issue[0] == "blocked":
                return "SPRZEDAŻ ZABLOKOWANA"
            if self.last_schedule_attempt.get("status") == "failed" and self.last_schedule_attempt.get("slot") == self.active_slot_key():
                return "BŁĄD APLIKACJI HARMONOGRAMU"
            if self.active_slot.mode == MODE_SELLING_FIRST and not self.soc_ok:
                return "SOC ZA NISKIE"
            if self.active_slot.mode == MODE_SELLING_FIRST and not self.price_ok:
                return "CENA ZA NISKA"
            if self.active_charge_slot:
                return "ŁADOWANIE Z SIECI" if self.active_slot.charge_enabled else "ŁADOWANIE Z PV"
            if self.active_slot.mode == MODE_SELLING_FIRST:
                return "SPRZEDAŻ AKTYWNA"
            if self.active_slot.mode == MODE_NORMAL_OPERATION:
                physical = self.active_slot.physical_work_mode
                if physical == MODE_ZERO_EXPORT_CT:
                    return "NORMALNA PRACA (CT)"
                return "NORMALNA PRACA (LOAD)"
            return "OCZEKIWANIE"
        return "OCZEKIWANIE"

    def _active_physical_work_mode(self) -> str:
        """Return the physical work mode variant for the current active slot."""
        if self.active_slot and self.active_slot.enabled and self.active_slot.physical_work_mode:
            return self.active_slot.physical_work_mode
        return self.normal_profile_physical_work_mode

    def default_normal_physical_work_mode(self) -> str:
        """Return the explicit default variant or the pre-5F.1 profile fallback."""
        if self.default_physical_work_mode in PHYSICAL_NORMAL_MODES:
            return str(self.default_physical_work_mode)
        if self.normal_profile_physical_work_mode in PHYSICAL_NORMAL_MODES:
            return str(self.normal_profile_physical_work_mode)
        return str(provider_profile(self.data).default_normal_mode)

    def _normalize_work_mode_input(self, mode: str) -> tuple[str, str | None]:
        """Accept either logical manager mode or a physical normal variant."""
        if mode in PHYSICAL_NORMAL_MODES:
            return (MODE_NORMAL_OPERATION, mode)
        normalized = normalize_manager_mode(mode)
        if normalized in MANAGER_MODES:
            return (normalized, None)
        return (mode, None)

    async def async_set_work_mode(self, mode: str) -> None:
        profile = provider_profile(self.data)
        if not profile.basic_control:
            raise ValueError(f"Provider {profile.label} does not support inverter control")
        mode, physical_override = self._normalize_work_mode_input(mode)
        physical = physical_override or (
            self._active_physical_work_mode() if mode == MODE_NORMAL_OPERATION else None
        )
        option = logical_mode_option(self.data, mode, physical)
        if profile.needs_aux_export_switch and mode != MODE_SELLING_FIRST:
            await self.async_set_switch(self.work_mode_aux_entity, False)
        await self._async_physical_service_call(
            "select",
            "select_option",
            {"entity_id": self.work_mode_select, "option": option},
            target_value=option,
        )
        if profile.needs_aux_export_switch and mode == MODE_SELLING_FIRST:
            await self.async_set_switch(self.work_mode_aux_entity, True)

    async def async_set_work_mode_if_needed(self, mode: str) -> bool:
        """Avoid re-sending an unchanged select option during a schedule tick."""
        state = self.hass.states.get(self.work_mode_select)
        aux_ok = True
        profile = provider_profile(self.data)
        mode, physical_override = self._normalize_work_mode_input(mode)
        if profile.needs_aux_export_switch:
            aux_state = self.hass.states.get(self.work_mode_aux_entity)
            aux_ok = aux_state is not None and aux_state.state == ("on" if mode == MODE_SELLING_FIRST else "off")
        physical = physical_override or (
            self._active_physical_work_mode() if mode == MODE_NORMAL_OPERATION else None
        )
        if state is not None and logical_mode_matches(self.data, mode, str(state.state), physical) and aux_ok:
            self._performance.inc("inverter_write_skipped_same_value")
            return False
        await self.async_set_work_mode(mode)
        return True

    async def async_set_number(self, entity_id: str | None, value: float) -> None:
        if entity_id:
            await self._async_physical_service_call(
                "number",
                "set_value",
                {"entity_id": entity_id, "value": value},
                target_value=value,
            )

    async def async_set_number_if_needed(self, entity_id: str | None, value: float) -> bool:
        """Write a number only when Deye does not already report that value."""
        state = self.hass.states.get(entity_id) if entity_id else None
        current = None if state is None else self.safe_float(state.state, float("nan"))
        if current is not None and math.isfinite(current) and math.isclose(current, float(value), abs_tol=0.1):
            self._performance.inc("inverter_write_skipped_same_value")
            return False
        await self.async_set_number(entity_id, value)
        return True

    async def async_set_switch(self, entity_id: str | None, value: bool) -> None:
        if entity_id:
            await self._async_physical_service_call(
                "switch",
                "turn_on" if value else "turn_off",
                {"entity_id": entity_id},
                target_value="on" if value else "off",
            )

    async def async_set_switch_if_needed(self, entity_id: str | None, value: bool) -> bool:
        """Write a switch only if its current state differs from the target."""
        state = self.hass.states.get(entity_id) if entity_id else None
        if state is not None and state.state == ("on" if value else "off"):
            self._performance.inc("inverter_write_skipped_same_value")
            return False
        await self.async_set_switch(entity_id, value)
        return True

    async def async_set_time(self, entity_id: str | None, value: str) -> None:
        if entity_id:
            domain = entity_id.split(".", 1)[0]
            if domain == "time":
                time_value = value if len(value) == 8 else f"{value}:00"
                await self._async_physical_service_call(
                    "time",
                    "set_value",
                    {"entity_id": entity_id, "time": time_value},
                    target_value=time_value,
                )
                return
            if domain == "select":
                state = self.hass.states.get(entity_id)
                options = None if state is None else (getattr(state, "attributes", {}) or {}).get("options")
                option = format_time_option(options, value)
                await self._async_physical_service_call(
                    "select",
                    "select_option",
                    {"entity_id": entity_id, "option": option},
                    target_value=option,
                )
                return
            raise ValueError(f"Unsupported time entity domain: {entity_id}")

    async def async_set_boolean_control(self, entity_id: str | None, value: bool, role: str) -> None:
        if not entity_id:
            raise ValueError(f"Missing {role} entity")
        domain = entity_id.split(".", 1)[0]
        if domain == "switch":
            await self.async_set_switch(entity_id, value)
            return
        if domain == "select":
            option = provider_boolean_option(self.data, role, value)
            state = self.hass.states.get(entity_id)
            options = None if state is None else (getattr(state, "attributes", {}) or {}).get("options")
            resolved_option = resolve_select_option(options, option)
            if resolved_option is None:
                raise ValueError(f"Unsupported option for {entity_id}: {option}")
            await self._async_physical_service_call(
                "select",
                "select_option",
                {"entity_id": entity_id, "option": resolved_option},
                target_value=resolved_option,
            )
            return
        raise ValueError(f"Unsupported {role} entity domain: {entity_id}")

    def _validate_number_entity(self, label: str, entity_id: str | None, value: float) -> None:
        """Validate a Number entity and its Home Assistant limits before write."""
        if not entity_id or not entity_id.startswith("number."):
            raise ValueError(f"Missing required Deye number entity: {label}")
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable", "none", ""):
            raise ValueError(f"Unavailable Deye number entity: {label}")
        numeric = float(value)
        if not math.isfinite(numeric):
            raise ValueError(f"Invalid numeric value for {label}")
        attrs = getattr(state, "attributes", {}) or {}
        minimum = self.safe_float(attrs.get("min"), float("-inf"))
        maximum = self.safe_float(attrs.get("max"), float("inf"))
        step = self.safe_float(attrs.get("step"), 0)
        if numeric < minimum or numeric > maximum:
            raise ValueError(f"{label} must be between {minimum:g} and {maximum:g}")
        if step > 0 and math.isfinite(minimum):
            steps = (numeric - minimum) / step
            if not math.isclose(steps, round(steps), abs_tol=1e-6):
                raise ValueError(f"{label} must follow step {step:g}")

    def _validate_select_entity(self, label: str, entity_id: str | None, option: str) -> None:
        if not entity_id or not entity_id.startswith("select."):
            raise ValueError(f"Missing required Deye select entity: {label}")
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable", "none", ""):
            raise ValueError(f"Unavailable Deye select entity: {label}")
        options = (getattr(state, "attributes", {}) or {}).get("options")
        if isinstance(options, (list, tuple)) and option not in options:
            raise ValueError(f"Unsupported option for {label}: {option}")

    def _validate_switch_entity(self, label: str, entity_id: str | None) -> None:
        if not entity_id or not entity_id.startswith("switch."):
            raise ValueError(f"Missing required Deye switch entity: {label}")
        state = self.hass.states.get(entity_id)
        if state is None or state.state not in ("on", "off"):
            raise ValueError(f"Unavailable Deye switch entity: {label}")

    def _validate_time_entity(self, label: str, entity_id: str | None, value: str) -> None:
        allowed = provider_profile(self.data).tou_start_domains
        if not entity_id or entity_id.split(".", 1)[0] not in allowed:
            raise ValueError(f"Missing required Deye time entity: {label}")
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable", "none", ""):
            raise ValueError(f"Unavailable Deye time entity: {label}")
        try:
            hour, minute = (int(part) for part in value.split(":")[:2])
        except (TypeError, ValueError):
            raise ValueError(f"Invalid time for {label}: {value}") from None
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError(f"Invalid time for {label}: {value}")
        if entity_id.startswith("select."):
            options = (getattr(state, "attributes", {}) or {}).get("options")
            option = format_time_option(options, value)
            if isinstance(options, (list, tuple)) and option not in options:
                raise ValueError(f"Unsupported time option for {label}: {value}")

    def _validate_boolean_control_entity(
        self, label: str, entity_id: str | None, value: bool, role: str
    ) -> None:
        item = provider_profile(self.data)
        allowed = item.tou_grid_domains
        if not entity_id or entity_id.split(".", 1)[0] not in allowed:
            raise ValueError(f"Missing required Deye {role} entity: {label}")
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable", "none", ""):
            raise ValueError(f"Unavailable Deye {role} entity: {label}")
        if entity_id.startswith("switch."):
            if state.state not in ("on", "off"):
                raise ValueError(f"Unavailable Deye switch entity: {label}")
            return
        option = provider_boolean_option(self.data, role, value)
        options = (getattr(state, "attributes", {}) or {}).get("options")
        if isinstance(options, (list, tuple)) and resolve_select_option(options, option) is None:
            raise ValueError(f"Unsupported option for {label}: {option}")

    def _validate_control_plan(
        self,
        mode: str,
        sell_power: float,
        discharge_current: float,
        charge_current: float,
        grid_charge_current: float,
    ) -> None:
        """Reject an invalid control plan before the first write to Deye."""
        profile = provider_profile(self.data)
        if not profile.basic_control:
            raise ValueError(f"Provider {profile.label} does not support inverter control")
        if mode not in WORK_MODES:
            raise ValueError(f"Unsupported Deye work mode: {mode}")
        values = {
            "Max Sell Power": (sell_power, 0.0, float(self.effective_inverter_max_power_w)),
            "Maximum Battery Discharge Current": (discharge_current, 0.0, 240.0),
            "Maximum Battery Charge Current": (charge_current, 0.0, 240.0),
            "Maximum Battery Grid Charge Current": (grid_charge_current, 0.0, 240.0),
        }
        for label, (raw_value, minimum, maximum) in values.items():
            value = float(raw_value)
            if not math.isfinite(value) or not minimum <= value <= maximum:
                raise ValueError(f"{label} must be between {minimum:g} and {maximum:g}")
        self._validate_select_entity(
            "System Work Mode",
            self.work_mode_select,
            logical_mode_option(self.data, mode, self._active_physical_work_mode()),
        )
        if profile.needs_aux_export_switch:
            self._validate_switch_entity("Solar Export", self.work_mode_aux_entity)
        # Logical 0 W is always allowed; physical entity range is checked only
        # for positive values that may be written to the inverter.
        if sell_power > 0:
            self._validate_number_entity("Max Sell Power", self.max_sell_power_number, sell_power)
        self._validate_number_entity(
            "Maximum Battery Discharge Current", self.discharge_current_number, discharge_current
        )
        self._validate_number_entity(
            "Maximum Battery Charge Current", self.charge_current_number, charge_current
        )
        self._validate_number_entity(
            "Maximum Battery Grid Charge Current", self.grid_charge_current_number, grid_charge_current
        )

    async def async_verify_control_values(
        self,
        mode: str | None,
        sell_power: float | None,
        discharge_current: float,
        charge_current: float,
        grid_charge_current: float,
        physical_work_mode: str | None = None,
    ) -> list[str]:
        """Read the current control state once, without writing it again.

        Some Deye integrations publish the requested values several seconds
        after the service call.  Re-sending a mode during that interval can
        undo a perfectly valid in-flight change, therefore delayed polling is
        handled by the pending transaction instead of this verifier.

        ``sell_power`` may be None when the sell-power number was intentionally
        not written because the active mode does not require selling or the
        physical entity does not accept 0 W.
        """
        self._performance.inc("inverter_readback")
        expected_numbers: dict[str | None, tuple[str, float]] = {
            self.discharge_current_number: ("Maximum Battery Discharge Current", float(discharge_current)),
        }
        if sell_power is not None and self.max_sell_power_number:
            expected_numbers[self.max_sell_power_number] = ("Max Sell Power", float(sell_power))
        if self.charge_current_number:
            expected_numbers[self.charge_current_number] = ("Maximum Battery Charge Current", float(charge_current))
        if self.grid_charge_current_number:
            expected_numbers[self.grid_charge_current_number] = ("Maximum Battery Grid Charge Current", float(grid_charge_current))
        unconfirmed: list[str] = []
        if mode is not None:
            mode_state = self.hass.states.get(self.work_mode_select)
            if mode_state is None or not logical_mode_matches(self.data, mode, str(mode_state.state), physical_work_mode):
                actual_mode = "brak" if mode_state is None else str(mode_state.state)
                expected_mode = logical_mode_option(self.data, mode, physical_work_mode)
                unconfirmed.append(f"System Work Mode={actual_mode} (oczekiwano {expected_mode})")
            profile = provider_profile(self.data)
            if profile.needs_aux_export_switch:
                aux_state = self.hass.states.get(self.work_mode_aux_entity)
                expected_aux = "on" if mode == MODE_SELLING_FIRST else "off"
                if aux_state is None or aux_state.state != expected_aux:
                    actual_aux = "brak" if aux_state is None else str(aux_state.state)
                    unconfirmed.append(f"Solar Export={actual_aux} (oczekiwano {expected_aux})")
        for entity_id, (label, expected) in expected_numbers.items():
            state = self.hass.states.get(entity_id)
            actual = None if state is None else self.safe_float(state.state, float("nan"))
            if actual is None or not math.isfinite(actual) or not math.isclose(actual, expected, abs_tol=0.1):
                actual_label = "brak" if actual is None or not math.isfinite(actual) else f"{actual:g}"
                unconfirmed.append(f"{label}={actual_label} (oczekiwano {expected:g})")
        return unconfirmed

    def _pending_control_key(self) -> str:
        """Identify the user-visible target that owns an in-flight write."""
        return (
            f"{self.control_mode}:{self.active_slot_key()}"
            if self.control_mode == "Schedule"
            else self.control_mode
        )

    def _clear_pending_control_transaction(self) -> None:
        self._pending_control_transaction = {}
        if self.unsub_confirmation_timer:
            self.unsub_confirmation_timer()
            self.unsub_confirmation_timer = None
        if self.unsub_confirmation_listener:
            self.unsub_confirmation_listener()
            self.unsub_confirmation_listener = None
        if self.unsub_confirmation_poll:
            self.unsub_confirmation_poll()
            self.unsub_confirmation_poll = None

    def _control_confirmation_entities(self) -> list[str]:
        """Return every Deye entity whose state confirms a control write."""
        return [
            entity_id
            for entity_id in (
                self.work_mode_select,
                self.work_mode_aux_entity,
                self.max_sell_power_number,
                self.discharge_current_number,
                self.charge_current_number,
                self.grid_charge_current_number,
            )
            if entity_id
        ]

    def _start_schedule_input_listener(self) -> None:
        """Coalesce material planning inputs and refresh the remaining horizon."""
        if self.unsub_input_listener:
            return
        if self._soc_quality_signature is None:
            self._soc_quality_signature = self._soc_semantic_signature(
                self.soc_diagnostics()
            )
        reason_groups = (
            ("soc", (self.battery_soc_sensor,)),
            ("price_today", (self.price_sensor, self.buy_price_today_sensor)),
            ("price_tomorrow", (self.sell_price_tomorrow_sensor, self.buy_price_tomorrow_sensor)),
            (
                "solcast",
                (
                    self.solcast_forecast_today_sensor,
                    self.solcast_remaining_today_sensor,
                    self.solcast_forecast_tomorrow_sensor,
                ),
            ),
            ("pv", (self.pv_power_sensor,)),
            ("load", (self.load_power_sensor,)),
            ("grid", (self.grid_power_sensor,)),
            ("battery_power", (self.battery_power_sensor,)),
            (
                "soc_health",
                (self.battery_bms_voltage_sensor, self.battery_current_sensor),
            ),
            ("weather", (self.weather_entity,)),
        )
        reason_by_entity: dict[str, str] = {}
        for reason, entity_ids in reason_groups:
            for entity_id in entity_ids:
                if entity_id and not self._is_own_output_entity_id(entity_id):
                    reason_by_entity.setdefault(entity_id, reason)
        entities = list(reason_by_entity)
        if not entities:
            return
        self._optimizer_input_reasons = reason_by_entity
        self._optimizer_listener_entity_ids = tuple(entities)

        @callback
        def _on_input_change(event: Any) -> None:
            event_data = getattr(event, "data", event if isinstance(event, dict) else {})
            entity_id = str(event_data.get("entity_id") or "")
            if self._is_own_output_entity_id(entity_id):
                self.runtime_metrics["self_entity_event_ignored"] += 1
                return
            reason = reason_by_entity.get(entity_id)
            if reason is None:
                return
            self.runtime_metrics["external_input_event_count"] += 1
            soc_semantics_changed = False
            if reason == "soc":
                soc_semantics_changed = self._observe_soc_source_event(event)
                # A complete HA state event proves both the report and its
                # unchanged value. Compatibility test doubles that expose only
                # entity_id retain the historical material-event behavior.
                if "new_state" in event_data and not soc_semantics_changed:
                    # An identical report only renews freshness. It must not
                    # create a Core, publish, Store, schedule or TOU storm.
                    self._performance.inc("soc_report_timestamp_only")
                    return
            elif reason in {"pv", "load", "grid", "battery_power", "soc_health"}:
                soc_semantics_changed = self._observe_soc_sibling_event(event)
                if soc_semantics_changed:
                    # One granular proxy publication makes stale→valid recovery
                    # visible without waiting for a source SOC event or reload.
                    self._notify_entities_from_cache(
                        {"battery_soc"}, reason="soc_quality_transition"
                    )
                    self.request_sensor_snapshot_refresh({"ai_state", "diagnostics"})
                    reason = "soc"
                elif reason == "soc_health" or self._state_event_is_report_only(event_data):
                    self._performance.inc("soc_health_timestamp_only")
                    return
            self._optimizer_debounce_reasons.add(reason)
            self._optimizer_generation_reason = f"material_live_input_changed:{reason}"
            coalesced = bool(self.unsub_input_debounce)
            self._performance.record_input_event(
                entity_id,
                accepted=not coalesced,
                coalesced=coalesced,
            )
            if self.unsub_input_debounce:
                return

            @callback
            def _on_debounce(_now: datetime) -> None:
                self.unsub_input_debounce = None
                reasons = set(self._optimizer_debounce_reasons)
                self._optimizer_debounce_reasons.clear()
                self.request_optimizer_recalc(reasons or {"manual"})
                self.schedule_ai_api_analysis()

            self.unsub_input_debounce = async_track_point_in_time(
                self.hass, _on_debounce, ha_now() + timedelta(seconds=2)
            )

        self.unsub_input_listener = async_track_state_change_event(
            self.hass, entities, _on_input_change
        )

    @staticmethod
    def _is_own_output_entity_id(entity_id: str | None) -> bool:
        """Reject every Deye Manager output even if selected as a Core source."""
        if not entity_id or "." not in entity_id:
            return False
        return entity_id.split(".", 1)[1].startswith("deye_energy_manager_")

    def _schedule_pending_control_poll(self, delay: float | None = None) -> None:
        """Read pending writes quickly without ever sending them again."""
        if not self._pending_control_transaction or self.unsub_confirmation_poll:
            return
        if delay is None:
            # State changes are the preferred confirmation mechanism.  These
            # short read-only checks are a fallback for late Deye updates.
            poll_index = int(self._pending_control_transaction.get("poll_index", 0))
            delay = (0.5, 1.0, 2.0)[min(poll_index, 2)]
            self._pending_control_transaction["poll_index"] = poll_index + 1

        @callback
        def _on_poll(_now: datetime) -> None:
            self.unsub_confirmation_poll = None
            self.hass.async_create_task(self._async_recheck_pending_control())

        self.unsub_confirmation_poll = async_track_point_in_time(
            self.hass,
            _on_poll,
            ha_now() + timedelta(seconds=delay),
        )

    def _start_pending_control_watchers(self) -> None:
        """Confirm from Deye state events first, with a read-only poll fallback."""
        if not self.unsub_confirmation_listener:
            entities = self._control_confirmation_entities()

            @callback
            def _on_state_change(_event: Any) -> None:
                if self._pending_control_transaction:
                    self.hass.async_create_task(self._async_recheck_pending_control())

            self.unsub_confirmation_listener = async_track_state_change_event(
                self.hass, entities, _on_state_change
            )
        self._schedule_pending_control_poll()

    def _schedule_pending_control_timeout(self) -> None:
        """Finish delayed confirmation at the promised deadline, not next tick."""
        if self.unsub_confirmation_timer:
            self.unsub_confirmation_timer()
            self.unsub_confirmation_timer = None

        @callback
        def _on_timeout(_now: datetime) -> None:
            self.unsub_confirmation_timer = None
            self.hass.async_create_task(self._async_finish_pending_control_confirmation())

        self.unsub_confirmation_timer = async_track_point_in_time(
            self.hass,
            _on_timeout,
            ha_now() + timedelta(seconds=self.control_confirmation_timeout),
        )

    async def _async_finish_pending_control_confirmation(self) -> None:
        """Perform one final serialized read when the confirmation window ends."""
        await self._async_recheck_pending_control()

    async def _async_recheck_pending_control(self) -> None:
        """Recheck a pending write under the transaction lock without re-writing."""
        async with self._operation_lock:
            pending = self._pending_control_transaction
            if not pending:
                return
            await self._async_confirm_or_wait_for_control(
                dict(pending.get("expected") or {}),
                str(pending.get("stage") or "potwierdzenie falownika"),
            )
            if self._pending_control_transaction:
                self._schedule_pending_control_poll()

    async def _async_confirm_or_wait_for_control(
        self, expected: dict[str, Any], stage: str, *, started: bool = False, success_message: str = ""
    ) -> bool | None:
        """Confirm an in-flight write, or leave it pending without re-writing.

        ``True`` is returned both when the write is fully confirmed and when it
        is still being awaited within ``control_confirmation_timeout``. In the
        latter case the pending transaction stays active and will be rechecked
        by state listeners or the next poll. ``False`` means the confirmation
        window expired and defaults were restored. ``None`` means that the
        caller must perform the first write.
        """
        if not self._control_is_active():
            self._clear_pending_control_transaction()
            self.executed_manager_action = "Nie wykonano — sterowanie wyłączone"
            await self._async_finish_future_plan_physical(
                False, "Sterowanie wyłączone przed fizycznym potwierdzeniem"
            )
            return False
        if started:
            self._performance.inc("inverter_confirmation_started")
        key = self._pending_control_key()
        pending = self._pending_control_transaction
        if not started:
            if not pending:
                return None
            if pending.get("key") != key or pending.get("expected") != expected:
                self._clear_pending_control_transaction()
                return None
        unconfirmed = await self.async_verify_control_values(
            expected.get("System Work Mode"),
            None if expected.get("Max Sell Power") is None else float(expected.get("Max Sell Power", 0)),
            float(expected.get("Prąd rozładowania", 0)),
            float(expected.get("Prąd ładowania baterii", 0)),
            float(expected.get("Prąd ładowania z sieci", 0)),
            self._active_physical_work_mode(),
        )
        if not unconfirmed:
            self._performance.inc("inverter_confirmation_completed")
            self._clear_pending_control_transaction()
            self.record_schedule_attempt("applied", "potwierdzenie", expected, "Potwierdzono pełny zestaw ustawień slotu")
            self._clear_slot_failure_latch()
            self.last_action = f"Applied {self.control_mode}"
            if success_message:
                self.last_action = f"{self.last_action}. {success_message}"
            self.last_error = ""
            self.mark_settings_applied()
            await self._async_finish_future_plan_physical(True, expected=expected)
            self._notify_update_for("confirmation")
            return True

        now = ha_now().timestamp()
        if started:
            self._pending_control_transaction = {
                "key": key,
                "slot": self.active_slot_key(),
                "expected": dict(expected),
                "stage": stage,
                "started_at": now,
                "poll_index": 0,
            }
            pending = self._pending_control_transaction
            self._schedule_pending_control_timeout()
            self._start_pending_control_watchers()
        elapsed = max(0.0, now - float(pending.get("started_at", now)))
        remaining = max(0, math.ceil(self.control_confirmation_timeout - elapsed))
        if elapsed < self.control_confirmation_timeout:
            message = f"Oczekiwanie na potwierdzenie falownika ({remaining} s): {'; '.join(unconfirmed)}"
            self.record_schedule_attempt("pending", "potwierdzenie falownika", expected, message)
            self.last_action = "Oczekiwanie na potwierdzenie ustawień przez falownik"
            self.last_error = ""
            self._notify_update_for("confirmation")
            return True

        self._clear_pending_control_transaction()
        self._performance.inc("inverter_confirmation_timeout")
        reason = f"Niepotwierdzone ustawienia po {int(self.control_confirmation_timeout)} s: {'; '.join(unconfirmed)}"
        failed = await self._async_handle_slot_failure(reason, "potwierdzenie falownika", expected)
        await self._async_finish_future_plan_physical(False, reason)
        return failed

    async def async_apply_safe_defaults(self, reason: str) -> bool:
        async with self._control_operation("safe_defaults") as transaction_id:
            return await self._async_apply_safe_defaults_impl(reason, transaction_id)

    async def _async_apply_safe_defaults_impl(
        self, reason: str, transaction_id: str | None = None
    ) -> bool:
        """Apply user defaults as the single fail-safe path without forced zeroes."""
        mode = self.default_work_mode
        mode_input = (
            self.default_normal_physical_work_mode()
            if mode == MODE_NORMAL_OPERATION
            else mode
        )
        capped_sell_power = min(self.default_sell_power, self.effective_inverter_max_power_w)
        cap_message = ""
        if capped_sell_power < self.default_sell_power:
            cap_message = f"Moc sprzedaży domyślnej ograniczona z {self.default_sell_power} W do {capped_sell_power} W"
            _LOGGER.warning("%s (effective limit %s W)", cap_message, self.effective_inverter_max_power_w)
        failures: list[str] = []
        try:
            self._validate_control_plan(
                mode,
                capped_sell_power,
                self.default_discharge_current,
                self.default_charge_current,
                self.default_grid_charge_current,
            )
        except Exception as err:
            failures.append(str(err))

        operations = (
            ("Max Sell Power", self.async_set_number, (self.max_sell_power_number, capped_sell_power)),
            (
                "Maximum Battery Discharge Current",
                self.async_set_number,
                (self.discharge_current_number, self.default_discharge_current),
            ),
            (
                "Maximum Battery Charge Current",
                self.async_set_number,
                (self.charge_current_number, self.default_charge_current),
            ),
            (
                "Maximum Battery Grid Charge Current",
                self.async_set_number,
                (self.grid_charge_current_number, self.default_grid_charge_current),
            ),
            ("System Work Mode", self.async_set_work_mode, (mode_input,)),
        )
        if not failures:
            for label, writer, args in operations:
                try:
                    await writer(*args)
                except ControlDisabledError:
                    raise
                except Exception as err:
                    failures.append(f"{label}: {err}")

        if not failures:
            failures.extend(
                await self.async_verify_control_values(
                    mode,
                    capped_sell_power,
                    self.default_discharge_current,
                    self.default_charge_current,
                    self.default_grid_charge_current,
                    self.default_normal_physical_work_mode(),
                )
            )

        if failures:
            if not self._control_result_is_current(transaction_id):
                raise ControlDisabledError(self._control_block_message())
            try:
                await self.async_set_work_mode(mode_input)
            except ControlDisabledError:
                raise
            except Exception as err:
                failures.append(f"System Work Mode: {err}")
            self.last_action = "Nie udało się w pełni zastosować ustawień domyślnych — sprawdź falownik."
            self.last_error = (
                f"KRYTYCZNY błąd częściowego zapisu ({reason}). "
                f"Niepotwierdzone wartości: {'; '.join(failures)}"
            )
            self.notify_update()
            return False

        if not self._control_result_is_current(transaction_id):
            raise ControlDisabledError(self._control_block_message())
        self.last_action = f"{reason}. Zastosowano ustawienia domyślne."
        if cap_message:
            self.last_action = f"{self.last_action} {cap_message}"
        self.last_error = self.last_action
        self.notify_update()
        return True

    def _tou_entity(self, idx: int, kind: str) -> str:
        configured = self.data.get(conf_tou_entity(idx, kind))
        return str(configured or "")

    @staticmethod
    def _time_to_minutes(value: Any) -> int | None:
        """Return minutes after midnight for an HA time state."""
        text = str(value or "").strip()
        try:
            hour, minute = (int(part) for part in text.split(":", 2)[:2])
        except (TypeError, ValueError):
            return None
        if not 0 <= hour <= 23 or not 0 <= minute <= 59:
            return None
        return hour * 60 + minute

    @classmethod
    def _tou_hour_boundary(cls, value: Any, label: str) -> str:
        """Validate and normalize the hourly boundary supported by Stage 5C."""
        text = str(value or "").strip()
        minutes = cls._time_to_minutes(text)
        if minutes is None:
            raise ValueError(f"{label} musi mieć poprawny format GG:MM")
        if minutes % 60:
            raise ValueError(
                f"{label} musi wskazywać pełną godzinę w formacie GG:00; "
                "minuty inne niż 00 nie są obsługiwane"
            )
        return f"{minutes // 60:02d}:00"

    def _validated_tou_start_vector(
        self,
        slot: int,
        *,
        start: str | None = None,
        end: str | None = None,
    ) -> list[str]:
        """Return a valid proposed six-start vector before a boundary write."""
        starts: list[str] = []
        for idx in range(1, 7):
            entity_id = self._tou_entity(idx, "start")
            raw = self.state_text(entity_id)
            try:
                starts.append(self._tou_hour_boundary(raw, f"Od slotu {idx}"))
            except ValueError as err:
                raise ValueError(
                    f"Nie można zweryfikować pełnego układu Deye TOU 6/6: {err}"
                ) from None

        next_slot = 1 if slot == 6 else slot + 1
        normalized_start = (
            self._tou_hour_boundary(start, "Od") if start is not None else None
        )
        normalized_end = (
            self._tou_hour_boundary(end, "Do") if end is not None else None
        )
        if normalized_start is not None:
            starts[slot - 1] = normalized_start
        if normalized_end is not None:
            starts[next_slot - 1] = normalized_end
        if normalized_start is not None and normalized_end is not None and normalized_start == normalized_end:
            raise ValueError("Pola Od i Do nie mogą wskazywać tej samej godziny")

        minutes = [self._time_to_minutes(value) for value in starts]
        if any(value is None for value in minutes):
            raise ValueError("Nieprawidłowy układ startów Deye Time Of Use")
        numeric = [int(value) for value in minutes]
        if len(set(numeric)) != 6:
            raise ValueError("Każdy z sześciu startów Deye Time Of Use musi być unikalny")
        if any(numeric[idx] >= numeric[idx + 1] for idx in range(5)):
            raise ValueError(
                "Starty Deye Time Of Use muszą mieć ścisłą kolejność slotów 1–6; "
                "przejście przez północ jest dozwolone wyłącznie między slotem 6 i 1"
            )

        wraps = sum(
            1
            for idx in range(6)
            if numeric[(idx + 1) % 6] <= numeric[idx]
        )
        if wraps != 1 or numeric[0] >= numeric[-1]:
            raise ValueError(
                "Układ Deye Time Of Use musi zawierać dokładnie jedno przejście "
                "przez północ między slotem 6 i 1"
            )

        coverage = [0] * 24
        for idx, start_minute in enumerate(numeric):
            end_minute = numeric[(idx + 1) % 6]
            if idx == 5:
                end_minute += 24 * 60
            if end_minute <= start_minute:
                raise ValueError("Zakres Deye Time Of Use nie może mieć zerowej długości")
            for hour in range(start_minute // 60, end_minute // 60):
                coverage[hour % 24] += 1
        if any(count != 1 for count in coverage):
            raise ValueError(
                "Zakresy Deye Time Of Use muszą bez nakładania pokrywać pełne 24 godziny"
            )
        return starts

    def physical_tou_soc_for_slot(self, slot_key: str) -> float | None:
        """Read the physical Deye TOU SOC covering an hourly schedule slot.

        This is used only to seed a missing new helper.  An existing restored
        slot value, including an intentional zero, always has priority.
        """
        slot_row = next((row for row in SLOTS if row[0] == slot_key), None)
        if slot_row is None:
            return None
        target = int(slot_row[2]) * 60
        starts = [
            self._time_to_minutes(self.state_text(self._tou_entity(idx, "start")))
            for idx in range(1, 7)
        ]
        if any(value is None for value in starts):
            return None
        for offset, start in enumerate(starts):
            end = starts[(offset + 1) % 6]
            if start == end:
                continue
            contains = start <= target < end if start < end else target >= start or target < end
            if not contains:
                continue
            value = self.safe_float(
                self.state_text(self._tou_entity(offset + 1, "soc")),
                float("nan"),
            )
            return value if math.isfinite(value) and 0 <= value <= 100 else None
        return None

    def tou_mapping_errors(self) -> list[str]:
        return [item["entity_id"] for item in self.tou_mapping_diagnostics()["entities"] if not item["ok"]]

    @staticmethod
    def _physical_tou_soc_for_slot(slot: SlotSettings) -> float | None:
        """Return the physical Deye Time Of Use SOC for a schedule slot.

        The value is always the user-owned ``tou_soc``; ``minimum_sell_soc`` is
        a logical sale-guard and is never used as the physical SOC.
        """
        return None if slot.tou_soc is None else float(slot.tou_soc)

    def mark_slot_tou_soc_restored(self, slot_key: str) -> None:
        """Signal that the per-slot tou_soc number entity has been added."""
        self._restored_slot_tou_soc_keys.add(slot_key)

    def mark_slot_minimum_sell_soc_restored(self, slot_key: str) -> None:
        """Signal that the per-slot minimum_sell_soc number entity has been added."""
        self._restored_slot_minimum_sell_soc_keys.add(slot_key)

    def _selling_tou_soc_migration_ready(self) -> bool:
        """Return True only after all required per-slot entities are restored."""
        if not self.slots:
            return False
        return (
            len(self._restored_slot_mode_keys) == len(self.slots)
            and len(self._restored_slot_tou_soc_keys) == len(self.slots)
            and len(self._restored_slot_minimum_sell_soc_keys) == len(self.slots)
        )

    def _migrate_selling_tou_soc(self) -> None:
        """Idempotently resolve tou_soc for Selling First slots after restore.

        Order of sources for a Selling First slot with ``tou_soc is None``:
        1. Existing restored ``tou_soc`` (already present, nothing to do).
        2. Physical Deye TOU readback for that hour, when the provider exposes it.
        3. ``minimum_sell_soc`` as a backward-compatibility fallback when the
           provider does not expose a physical readback.
        4. Leave ``None`` and keep the migration incomplete until the next tick
           if a physical readback capability exists but the value is not yet
           readable (e.g. ``unknown`` / ``unavailable``).

        The migration is not driven by ``schedule_schema_version``; it relies on
        the presence of the restored per-slot entities and a valid physical readback.
        """
        if self._tou_soc_migration_done:
            return
        if not self._selling_tou_soc_migration_ready():
            return
        readback_supported = provider_profile(self.data).native_tou
        unresolved: list[str] = []
        for slot in self.slots.values():
            if not (slot.enabled and slot.mode == MODE_SELLING_FIRST):
                continue
            if slot.tou_soc is not None:
                continue
            physical_soc: float | None = None
            if readback_supported:
                try:
                    physical_soc = self.physical_tou_soc_for_slot(slot.key)
                except Exception:
                    physical_soc = None
            if physical_soc is not None:
                slot.tou_soc = float(physical_soc)
                continue
            if readback_supported:
                # Physical readback capability exists but the state is not yet
                # available; wait for the next tick instead of guessing.
                unresolved.append(slot.key)
                continue
            if math.isfinite(slot.minimum_sell_soc):
                slot.tou_soc = float(slot.minimum_sell_soc)
                continue
            unresolved.append(slot.key)
        if not unresolved:
            self._tou_soc_migration_done = True

    def _effective_physical_tou_soc_for_slot(self, slot: SlotSettings) -> float:
        """Return a finite physical TOU SOC for every schedule slot."""
        soc = self._physical_tou_soc_for_slot(slot)
        if soc is not None:
            return float(soc)
        fallback = self.normal_profile_tou_soc
        if fallback is not None and math.isfinite(fallback):
            return float(fallback)
        return 100.0

    def _tou_transaction_lock(self) -> asyncio.Lock:
        """Return the per-TOU-operation lock, creating it lazily."""
        if self._tou_transaction_lock_obj is None:
            self._tou_transaction_lock_obj = asyncio.Lock()
        return self._tou_transaction_lock_obj

    def _reserve_tou_write(self) -> object:
        """Reserve the single TOU writer synchronously, before any lock wait.

        An asyncio task cannot be pre-empted between the pending check and the
        assignment because this helper contains no await.  This makes two
        simultaneous service calls race-safe while retaining the Stage 5B lock
        as a second line of serialization inside the transaction executor.
        """
        if self.tou_write_pending:
            raise ValueError("Trwa zapis Deye Time Of Use")
        owner = object()
        self._tou_pending_owner = owner
        self.tou_write_pending = True
        self.tou_operation_started_at = ha_now()
        self.tou_operation_status = "writing"
        self.tou_contract_status = "writing"
        self.tou_last_error = ""
        self._notify_update_for("tou_reserve")
        return owner

    def _release_tou_write(self, owner: object) -> None:
        """Release only the reservation owned by the finishing operation."""
        if self._tou_pending_owner is not owner:
            return
        self._tou_pending_owner = None
        self.tou_write_pending = False
        self._notify_update_for("tou_release")

    def _tou_confirmation_event(self) -> asyncio.Event:
        """Return the event used to wake the TOU confirmation loop."""
        if self._tou_confirmation_event_obj is None:
            self._tou_confirmation_event_obj = asyncio.Event()
        return self._tou_confirmation_event_obj

    def _tou_field_matches(self, entity_id: str | None, field: str, expected_logical: Any) -> bool:
        """Compare current HA state with the logical expected value using provider normalization."""
        if not entity_id:
            return False
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable", "none", ""):
            return False
        actual = str(state.state)
        if field == "start" or field == "end":
            return self._time_to_minutes(actual) == self._time_to_minutes(expected_logical)
        if field == "soc":
            numeric = self.safe_float(actual, float("nan"))
            return math.isfinite(numeric) and math.isclose(numeric, float(expected_logical), abs_tol=0.1)
        if field == "grid":
            return state_matches_boolean(self.data, "grid", bool(expected_logical), actual)
        return actual == str(expected_logical)

    def _tou_provider_value(self, entity_id: str | None, field: str, logical_value: Any) -> Any:
        """Return the exact provider value that must be written to an entity."""
        if not entity_id:
            return None
        if field in ("start", "end"):
            state = self.hass.states.get(entity_id)
            options = (getattr(state, "attributes", {}) or {}).get("options") if state else None
            return format_time_option(options, str(logical_value))
        if field == "soc":
            return float(logical_value)
        if field == "grid":
            option = provider_boolean_option(self.data, "grid", bool(logical_value))
            if entity_id.split(".", 1)[0] == "select":
                state = self.hass.states.get(entity_id)
                options = (getattr(state, "attributes", {}) or {}).get("options") if state else None
                resolved = resolve_select_option(options, option)
                if resolved is not None:
                    return resolved
            return option
        return logical_value

    def _make_tou_transaction_item(
        self,
        entity_id: str,
        field: str,
        slot_index: int,
        logical_value: Any,
        snapshot: dict[str, str],
    ) -> dict[str, Any]:
        """Build one entry of the TOU write transaction plan."""
        state = self.hass.states.get(entity_id)
        current_raw = str(state.state) if state is not None else ""
        snapshot[entity_id] = current_raw
        provider_value = self._tou_provider_value(entity_id, field, logical_value)
        changed = not self._tou_field_matches(entity_id, field, logical_value)
        capability_field = "grid_charge" if field == "grid" else field
        capability = self._tou_field_capability(
            slot_index, capability_field, entity_id
        )
        actual = self._tou_field_actual_value(entity_id, capability_field)
        if field in ("start", "end"):
            previous_logical = current_raw
        elif field == "soc":
            previous_logical = self.safe_float(current_raw, None)
        elif field == "grid":
            previous_logical = state_matches_boolean(self.data, "grid", True, current_raw)
        else:
            previous_logical = current_raw
        return {
            "entity_id": entity_id,
            "field": field,
            "slot_index": slot_index,
            "current_raw_value": current_raw,
            "previous_logical_value": previous_logical,
            "actual": actual,
            "expected": logical_value,
            "expected_logical_value": logical_value,
            "expected_provider_value": provider_value,
            "changed": changed,
            "written": False,
            "confirmed": not changed,
            "status": "waiting" if changed else "unchanged",
            "writable": capability["writable"],
            "capability": capability,
        }

    def _build_tou_transaction_plan(
        self,
        mapping: TouMapping,
        *,
        end_overrides: dict[int, str] | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, str]]:
        """Create the complete diff plan for a 6-slot physical TOU write.

        Unused physical ranges keep their current start/SOC; only their Grid
        Charge source is forced to disabled.
        """
        snapshot: dict[str, str] = {}
        items: list[dict[str, Any]] = []
        for idx in range(1, 7):
            item = mapping.slots[idx - 1] if idx <= len(mapping.slots) else None
            start_entity = self._tou_entity(idx, "start")
            soc_entity = self._tou_entity(idx, "soc")
            grid_entity = self._tou_entity(idx, "grid")
            end_override = (end_overrides or {}).get(idx)
            if item is None:
                start_state = self.hass.states.get(start_entity)
                soc_state = self.hass.states.get(soc_entity)
                start_logical = str(start_state.state) if start_state is not None else None
                soc_logical = self.safe_float(soc_state.state if soc_state is not None else "", None)
                grid_logical = False
            else:
                start_logical = f"{int(item.start):02d}:00"
                soc_logical = float(item.soc)
                grid_logical = bool(item.grid_charge)
            if start_entity:
                items.append(
                    self._make_tou_transaction_item(
                        start_entity, "start", idx, start_logical, snapshot
                    )
                )
            if end_override and start_entity:
                items.append(
                    self._make_tou_transaction_item(
                        start_entity, "end", idx, end_override, snapshot
                    )
                )
            if soc_entity and soc_logical is not None:
                items.append(
                    self._make_tou_transaction_item(
                        soc_entity, "soc", idx, soc_logical, snapshot
                    )
                )
            if grid_entity:
                items.append(
                    self._make_tou_transaction_item(
                        grid_entity, "grid", idx, grid_logical, snapshot
                    )
                )
        return items, snapshot

    def _start_tou_confirmation_listener(self, entity_ids: list[str]) -> None:
        """Start a temporary state-changed listener that only wakes the wait loop."""
        self._stop_tou_confirmation_listener()
        if not entity_ids:
            return
        event = self._tou_confirmation_event()

        @callback
        def _on_state_change(_event: Any) -> None:
            event.set()

        self._tou_confirmation_unsub = async_track_state_change_event(
            self.hass, entity_ids, _on_state_change
        )

    def _stop_tou_confirmation_listener(self) -> None:
        """Detach the temporary TOU confirmation listener."""
        if self._tou_confirmation_unsub is not None:
            self._tou_confirmation_unsub()
            self._tou_confirmation_unsub = None

    async def _async_wait_for_tou_confirmation(
        self,
        items: list[dict[str, Any]],
        operation_name: str,
        expected_value_key: str = "expected_logical_value",
        *,
        allow_control_cancel: bool = True,
    ) -> list[dict[str, Any]]:
        """Wait until every written entity reports the expected value.

        Uses one common deadline of ``control_confirmation_timeout``.  A
        temporary state-changed listener wakes the polling loop, but the event
        itself does not count as confirmation.
        """
        written = [item for item in items if item.get("written")]
        if not written:
            return []
        self._performance.inc("inverter_confirmation_started")
        written_ids = [item["entity_id"] for item in written]
        self._start_tou_confirmation_listener(written_ids)
        event = self._tou_confirmation_event()
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.control_confirmation_timeout
        try:
            while True:
                self._performance.inc("inverter_readback")
                if (
                    allow_control_cancel
                    and self._active_tou_cancel_event is not None
                    and self._active_tou_cancel_event.is_set()
                ):
                    raise ControlDisabledError(
                        "Przerwano zapis TOU przez wyłączenie Sterowania Deye"
                    )
                unconfirmed = [
                    item
                    for item in written
                    if not self._tou_field_matches(
                        item["entity_id"], item["field"], item[expected_value_key]
                    )
                ]
                for item in written:
                    capability_field = (
                        "grid_charge" if item["field"] == "grid" else item["field"]
                    )
                    item["actual"] = self._tou_field_actual_value(
                        item["entity_id"], capability_field
                    )
                if not unconfirmed:
                    self._performance.inc("inverter_confirmation_completed")
                    for item in written:
                        item["confirmed"] = True
                        item["status"] = "confirmed"
                    return []
                remaining = deadline - loop.time()
                if remaining <= 0:
                    break
                event.clear()
                try:
                    await asyncio.wait_for(event.wait(), timeout=min(remaining, 0.5))
                except asyncio.TimeoutError:
                    pass
            for item in unconfirmed:
                capability_field = (
                    "grid_charge" if item["field"] == "grid" else item["field"]
                )
                item["actual"] = self._tou_field_actual_value(
                    item["entity_id"], capability_field
                )
                item["status"] = (
                    "unavailable" if item["actual"] is None else "mismatch"
                )
            self._performance.inc("inverter_confirmation_timeout")
            return unconfirmed
        finally:
            self._stop_tou_confirmation_listener()

    async def _async_rollback_tou_transaction(
        self, items: list[dict[str, Any]], snapshot: dict[str, str]
    ) -> tuple[bool, list[str]]:
        """Restore only entities that were actually written.

        Returns success flag and a list of remaining unconfirmed entities.
        """
        written = [item for item in items if item.get("written")]
        if written:
            self._performance.inc("inverter_rollback")
        errors: list[str] = []
        for item in written:
            entity_id = item["entity_id"]
            raw_value = snapshot.get(entity_id)
            if raw_value is None:
                continue
            try:
                await self._async_restore_raw_entity(entity_id, raw_value)
                item["legacy_status"] = "rollback_written"
            except Exception as err:
                item["legacy_status"] = f"rollback_error: {err}"
                item["status"] = "unavailable"
                errors.append(f"{entity_id}: {err}")
        if errors:
            return False, errors
        unconfirmed = await self._async_wait_for_tou_confirmation(
            items,
            "rollback",
            expected_value_key="previous_logical_value",
            allow_control_cancel=False,
        )
        for item in unconfirmed:
            item["legacy_status"] = "rollback_unconfirmed"
            item["status"] = (
                "unavailable" if item.get("actual") is None else "mismatch"
            )
        for item in written:
            capability_field = "grid_charge" if item["field"] == "grid" else item["field"]
            item["actual"] = self._tou_field_actual_value(item["entity_id"], capability_field)
            if item not in unconfirmed:
                item["legacy_status"] = "rollback_confirmed"
                item["status"] = "rolled_back"
                item["confirmed"] = True
        return not unconfirmed, [item["entity_id"] for item in unconfirmed]

    async def _async_execute_tou_transaction(
        self,
        operation_name: str,
        items: list[dict[str, Any]],
        snapshot: dict[str, str],
        *,
        finalize_contract: bool = True,
    ) -> tuple[bool, list[dict[str, Any]], str]:
        """Write only changed TOU entities, confirm, and rollback on failure.

        Returns ``(success, items, message)``.  The public operation owns and
        clears the synchronous pending reservation.
        """
        if not items:
            self.tou_operation_status = "success" if finalize_contract else "confirming"
            self.tou_contract_status = "confirmed" if finalize_contract else "waiting"
            return True, [], ""
        changed_items = [item for item in items if item.get("changed")]
        self._performance.inc(
            "inverter_write_skipped_same_value",
            len(items) - len(changed_items),
        )
        if not changed_items:
            self.tou_operation_status = "success" if finalize_contract else "confirming"
            self.tou_contract_status = "confirmed" if finalize_contract else "waiting"
            self.tou_transaction_log = list(items)
            return True, items, ""

        async with self._tou_transaction_lock():
            transaction_id = _CONTROL_TRANSACTION_ID.get()
            self._set_control_transaction_snapshot(transaction_id, snapshot)
            cancel_event = asyncio.Event()
            self._active_tou_cancel_event = cancel_event
            self.tou_operation_status = "writing"
            self.tou_contract_status = "writing"
            self.tou_last_error = ""
            self.tou_transaction_log = list(items)
            self._notify_update_for("tou_write")

            try:
                # Validate every changed entity before writing.
                for item in changed_items:
                    idx = item["slot_index"]
                    field = item["field"]
                    entity_id = item["entity_id"]
                    value = item["expected_logical_value"]
                    if field in ("start", "end"):
                        self._validate_time_entity(f"TOU {idx} {field}", entity_id, value)
                    elif field == "soc":
                        self._validate_number_entity(f"TOU {idx} SOC", entity_id, value)
                    elif field == "grid":
                        self._validate_boolean_control_entity(
                            f"TOU {idx} Grid Charge", entity_id, bool(value), "grid"
                        )

                self._last_tou_write_started = True

                # Deterministic write order: start/end, soc, grid.
                write_order = {"start": 0, "end": 0, "soc": 1, "grid": 2}
                changed_items.sort(key=lambda item: (write_order.get(item["field"], 99), item["slot_index"]))

                for item in changed_items:
                    if cancel_event.is_set():
                        raise ControlDisabledError(
                            "Przerwano zapis TOU przez wyłączenie Sterowania Deye"
                        )
                    field = item["field"]
                    entity_id = item["entity_id"]
                    provider_value = item["expected_provider_value"]
                    if field in ("start", "end"):
                        await self.async_set_time(entity_id, provider_value)
                    elif field == "soc":
                        await self.async_set_number(entity_id, float(provider_value))
                    elif field == "grid":
                        await self.async_set_boolean_control(entity_id, bool(item["expected_logical_value"]), "grid")
                    item["written"] = True
                    item["status"] = "waiting"

                self.tou_operation_status = "confirming"
                self.tou_contract_status = "waiting"
                self._notify_update_for("tou_confirmation")
                unconfirmed = await self._async_wait_for_tou_confirmation(items, operation_name)
                if unconfirmed:
                    raise RuntimeError(
                        "brak potwierdzenia encji: " + ", ".join(
                            f"{item['entity_id']} ({item['field']})" for item in unconfirmed
                        )
                    )
                if self._control_result_is_current(transaction_id):
                    self.tou_operation_status = "success" if finalize_contract else "confirming"
                    self.tou_contract_status = "confirmed" if finalize_contract else "waiting"
                return True, items, ""
            except ControlDisabledError as err:
                if not self._control_transaction_is_stale(transaction_id):
                    self.tou_operation_status = "rollback"
                    self.tou_contract_status = "rollback"
                rollback_snapshot = {
                    item["entity_id"]: snapshot[item["entity_id"]]
                    for item in items
                    if item.get("written") and item.get("entity_id") in snapshot
                }
                try:
                    with self._control_rollback_scope(transaction_id, rollback_snapshot):
                        rollback_ok, rollback_errors = await self._async_rollback_tou_transaction(
                            items, snapshot
                        )
                except Exception as rollback_err:
                    rollback_ok = False
                    rollback_errors = [str(rollback_err)]
                message = str(err)
                if rollback_errors:
                    message += ". Rollback: " + ", ".join(rollback_errors)
                if not self._control_transaction_is_stale(transaction_id):
                    self.tou_operation_status = "cancelled" if rollback_ok else "critical"
                    self.tou_contract_status = "rollback" if rollback_ok else "rollback_failed"
                    self.tou_last_error = message
                return False, items, message
            except asyncio.CancelledError:
                if not self._control_transaction_is_stale(transaction_id):
                    self.tou_operation_status = "rollback"
                    self.tou_contract_status = "rollback"
                try:
                    rollback_snapshot = {
                        item["entity_id"]: snapshot[item["entity_id"]]
                        for item in items
                        if item.get("written") and item.get("entity_id") in snapshot
                    }
                    with self._control_rollback_scope(transaction_id, rollback_snapshot):
                        rollback_ok, _rollback_errors = await self._async_rollback_tou_transaction(items, snapshot)
                except Exception as rollback_err:
                    rollback_ok = False
                    _LOGGER.warning("TOU rollback after cancellation failed: %s", rollback_err)
                if not self._control_transaction_is_stale(transaction_id):
                    self.tou_contract_status = "rollback" if rollback_ok else "rollback_failed"
                    self.tou_last_error = f"{operation_name} anulowane"
                raise
            except Exception as err:
                if not self._control_transaction_is_stale(transaction_id):
                    self.tou_operation_status = "rollback"
                    self.tou_contract_status = "rollback"
                rollback_snapshot = {
                    item["entity_id"]: snapshot[item["entity_id"]]
                    for item in items
                    if item.get("written") and item.get("entity_id") in snapshot
                }
                with self._control_rollback_scope(transaction_id, rollback_snapshot):
                    rollback_ok, rollback_errors = await self._async_rollback_tou_transaction(
                        items, snapshot
                    )
                if rollback_ok:
                    message = f"Błąd {operation_name}: {err}. Przywrócono poprzednie ustawienia."
                else:
                    message = (
                        f"KRYTYCZNY błąd {operation_name}: {err}. "
                        f"Nie potwierdzono pełnego przywrócenia: {', '.join(rollback_errors)}"
                    )
                if not self._control_transaction_is_stale(transaction_id):
                    self.tou_operation_status = "error" if rollback_ok else "critical"
                    self.tou_contract_status = "rollback" if rollback_ok else "rollback_failed"
                    self.tou_last_error = message
                return False, items, message
            finally:
                self.tou_transaction_log = list(items)
                if self._active_tou_cancel_event is cancel_event:
                    self._active_tou_cancel_event = None
                self.notify_update()

    def schedule_to_tou_mapping(self) -> TouMapping:
        """Build the physical Deye TOU mapping from the 24-hour schedule.

        The mapping compresses the schedule into ranges where the physical key
        (effective Deye TOU SOC, hourly Grid Charge flag) is identical.  Logical
        manager modes and other runtime overlays are not part of the key.
        """
        raw: list[tuple[int, float, bool]] = []
        for index, (_key, _label, _start, _end) in enumerate(SLOTS):
            slot = self.slots[_key]
            soc = self._effective_physical_tou_soc_for_slot(slot)
            # ``charge_enabled`` is the physical hourly Grid Charge flag.
            grid_charge = bool(slot.charge_enabled)
            start_hour = int(_start)
            end_hour = int(_end) if _end > start_hour else 24
            for hour in range(start_hour, end_hour):
                raw.append((hour, round(float(soc), 1), grid_charge))

        if len(raw) != 24:
            raise ValueError(f"Schedule must cover exactly 24 hours, got {len(raw)}")

        compressed: list[TouMappingSlot] = []
        for hour, soc, grid_charge in raw:
            if compressed:
                last = compressed[-1]
                if round(last.soc, 1) == soc and last.grid_charge == grid_charge:
                    last.end = hour + 1
                    last.source_hours.append(hour)
                    continue
            compressed.append(
                TouMappingSlot(
                    index=len(compressed) + 1,
                    start=hour,
                    end=hour + 1,
                    soc=soc,
                    grid_charge=grid_charge,
                    source_hours=[hour],
                    provider_fields={},
                )
            )

        # Wrap the 24-hour cycle: a range ending at 24 is represented as 0.
        for slot in compressed:
            if slot.end == 24:
                slot.end = 0

        # Deye exposes exactly six physical TOU ranges.  If the natural schedule
        # still needs more, we fail before writing anything.
        if len(compressed) > 6:
            return TouMapping(slots=compressed)

        # If fewer than six ranges are needed, deterministically split the
        # longest range until we have six slots.
        while len(compressed) < 6:
            split_index = -1
            longest = 0
            for index, segment in enumerate(compressed):
                segment_end = 24 if segment.end == 0 else int(segment.end)
                duration = segment_end - int(segment.start)
                if duration > longest and duration > 1:
                    longest = duration
                    split_index = index
            if split_index < 0:
                break
            segment = compressed[split_index]
            segment_end = 24 if segment.end == 0 else int(segment.end)
            middle = int(segment.start) + (segment_end - int(segment.start)) // 2
            first = TouMappingSlot(
                index=segment.index,
                start=segment.start,
                end=middle,
                soc=segment.soc,
                grid_charge=segment.grid_charge,
                source_hours=[h for h in segment.source_hours if h < middle],
                provider_fields=segment.provider_fields,
            )
            second = TouMappingSlot(
                index=segment.index + 1,
                start=middle,
                end=segment.end,
                soc=segment.soc,
                grid_charge=segment.grid_charge,
                source_hours=[h for h in segment.source_hours if h >= middle],
                provider_fields=segment.provider_fields,
            )
            compressed[split_index : split_index + 1] = [first, second]
            # Reindex after a split.
            for idx, item in enumerate(compressed, start=1):
                item.index = idx

        return TouMapping(slots=compressed)

    @property
    def _tou_mapping(self) -> TouMapping:
        return self.schedule_to_tou_mapping()

    def schedule_mapping_snapshot(self) -> list[dict[str, Any]]:
        """Expose the single backend 24 h -> Deye TOU mapping used for writes."""
        mapping = self._tou_mapping
        return [
            {
                "range": item.index,
                "start": int(item.start),
                "end": int(item.end),
                "tou_soc": item.soc,
                "grid_charge": bool(item.grid_charge),
            }
            for item in mapping.slots
        ]

    def read_physical_tou_mapping(self) -> TouMapping:
        """Read the current six physical Deye TOU ranges from the inverter."""
        starts_minutes: list[int | None] = []
        for idx in range(1, 7):
            text = self.state_text(self._tou_entity(idx, "start"))
            minutes = self._time_to_minutes(text)
            starts_minutes.append(minutes)
        if any(value is None for value in starts_minutes):
            raise ValueError("Nie można odczytać wszystkich startów Deye Time Of Use")
        soc_values: list[float] = []
        for idx in range(1, 7):
            value = self.safe_float(self.state_text(self._tou_entity(idx, "soc")), float("nan"))
            if not math.isfinite(value) or not 0 <= value <= 100:
                raise ValueError(f"Nieprawidłowy SOC Deye Time Of Use slot {idx}: {value}")
            soc_values.append(value)
        grid_values: list[bool] = []
        for idx in range(1, 7):
            state = self.state_text(self._tou_entity(idx, "grid"))
            logical = provider_boolean_state(self.data, "grid", state)
            if logical is None:
                raise ValueError(
                    f"Nieprawidłowe źródło ładowania Deye Time Of Use slot {idx}: {state}"
                )
            grid_values.append(logical)

        slots: list[TouMappingSlot] = []
        for idx in range(6):
            start_hour = starts_minutes[idx] // 60
            end_hour = starts_minutes[(idx + 1) % 6] // 60
            if start_hour == end_hour:
                source_hours: list[int] = []
            elif start_hour < end_hour:
                source_hours = list(range(start_hour, end_hour))
            else:
                source_hours = list(range(start_hour, 24)) + list(range(0, end_hour))
            slots.append(
                TouMappingSlot(
                    index=idx + 1,
                    start=start_hour,
                    end=end_hour,
                    soc=soc_values[idx],
                    grid_charge=grid_values[idx],
                    source_hours=source_hours,
                    provider_fields={},
                )
            )
        return TouMapping(slots=slots)

    def tou_mapping_to_schedule_patch(self, mapping: TouMapping | None = None) -> list[dict[str, Any]]:
        """Build a schedule patch that reflects only the physical TOU SOC/Grid Charge.

        Manager logical modes, sell power, charge/discharge/grid charge currents,
        minimum sell price and the logical sale guard ``minimum_sell_soc`` are
        preserved.  Only ``tou_soc`` and the hourly ``charge_enabled`` flag are
        updated.
        """
        if mapping is None:
            mapping = self.read_physical_tou_mapping()
        hour_to_physical: dict[int, tuple[float, bool]] = {}
        for slot in mapping.slots:
            for hour in slot.source_hours:
                hour_to_physical[hour] = (slot.soc, slot.grid_charge)
        if len(hour_to_physical) != 24:
            raise ValueError(f"Fizyczna mapa TOU pokrywa {len(hour_to_physical)} godzin, wymagane 24")

        patch: list[dict[str, Any]] = []
        for _key, _label, start, end in SLOTS:
            start_hour = int(start)
            end_hour = int(end) if end > start_hour else 24
            hours = [h % 24 for h in range(start_hour, end_hour)]
            if not hours or hours[0] not in hour_to_physical:
                continue
            start_soc, start_grid = hour_to_physical[hours[0]]
            update: dict[str, Any] = {"slot_key": _key, "charge_enabled": start_grid}
            # In 5A.1 physical TOU SOC is independent of the logical mode.  The
            # logical sale guard ``minimum_sell_soc`` is never overwritten here.
            update["tou_soc"] = start_soc
            patch.append(update)
        return patch

    @staticmethod
    def _tou_mapping_rows(mapping: TouMapping) -> list[tuple[int, int, float, bool]]:
        """Return the physical fields used by the strict 5C.2 round-trip check."""
        return [
            (
                int(slot.start) % 24,
                int(slot.end) % 24,
                round(float(slot.soc), 1),
                bool(slot.grid_charge),
            )
            for slot in mapping.slots
        ]

    @classmethod
    def _tou_mappings_match(cls, actual: TouMapping, expected: TouMapping) -> bool:
        """Compare exact six-slot physical boundaries, SOC and Grid Charge."""
        return len(actual.slots) == 6 and len(expected.slots) == 6 and cls._tou_mapping_rows(actual) == cls._tou_mapping_rows(expected)

    @staticmethod
    def _tou_signature(rows: list[tuple[int, int, float, bool]]) -> str:
        """Return a deterministic logical signature for normalized TOU rows."""
        return "|".join(
            f"{start:04d}-{end:04d}:{round(float(soc), 1):.1f}:{int(bool(grid))}"
            for start, end, soc, grid in rows
        )

    @staticmethod
    def _expected_tou_readback_rows(
        mapping: TouMapping,
    ) -> list[tuple[int, int, float, bool]]:
        """Represent the expected schedule map in physical readback units."""
        return [
            (
                (int(slot.start) % 24) * 60,
                (int(slot.end) % 24) * 60,
                round(float(slot.soc), 1),
                bool(slot.grid_charge),
            )
            for slot in mapping.slots
        ]

    def _physical_tou_readback_rows(self) -> list[tuple[int, int, float, bool]]:
        """Read and normalize the complete physical 6/6 TOU state.

        Time/select values are normalized to minutes after midnight, SOC to one
        decimal place and provider-specific Grid/source options to a logical
        boolean.  Unknown, unavailable or partially configured readback fails
        closed and never produces a signature.
        """
        starts: list[int] = []
        socs: list[float] = []
        grids: list[bool] = []
        for idx in range(1, 7):
            start_entity = self._tou_entity(idx, "start")
            soc_entity = self._tou_entity(idx, "soc")
            grid_entity = self._tou_entity(idx, "grid")
            start_state = self.hass.states.get(start_entity) if start_entity else None
            soc_state = self.hass.states.get(soc_entity) if soc_entity else None
            grid_state = self.hass.states.get(grid_entity) if grid_entity else None
            start = self._time_to_minutes(start_state.state if start_state is not None else None)
            soc = self.safe_float(soc_state.state if soc_state is not None else None, float("nan"))
            grid = provider_boolean_state(
                self.data, "grid", grid_state.state if grid_state is not None else None
            )
            if start is None:
                raise ValueError(f"Nie można potwierdzić startu Deye Time Of Use slot {idx}")
            if not math.isfinite(soc) or not 0 <= soc <= 100:
                raise ValueError(f"Nie można potwierdzić SOC Deye Time Of Use slot {idx}")
            if grid is None:
                raise ValueError(
                    f"Nie można potwierdzić Grid Charge Deye Time Of Use slot {idx}"
                )
            starts.append(start)
            socs.append(round(float(soc), 1))
            grids.append(bool(grid))
        return [
            (starts[idx], starts[(idx + 1) % 6], socs[idx], grids[idx])
            for idx in range(6)
        ]

    @staticmethod
    def _tou_mismatched_fields(
        expected: list[tuple[int, int, float, bool]],
        physical: list[tuple[int, int, float, bool]],
    ) -> list[str]:
        """List exact normalized physical fields that differ from the plan."""
        names = ("start", "end", "soc", "grid_charge")
        mismatched: list[str] = []
        for index, (expected_row, physical_row) in enumerate(
            zip(expected, physical, strict=False), start=1
        ):
            for field_index, name in enumerate(names):
                if expected_row[field_index] != physical_row[field_index]:
                    mismatched.append(f"slot_{index}.{name}")
        if len(expected) != len(physical):
            mismatched.append("slot_count")
        return mismatched

    def _refresh_tou_reconciliation_state(
        self, mapping: TouMapping | None = None
    ) -> bool:
        """Compare the expected map with confirmed physical readback.

        This method is read-only with respect to HA entities.  It is used by the
        normal polling cycle and immediately before deciding whether a cached
        TOU write can be skipped.
        """
        profile = provider_profile(self.data)
        try:
            expected_mapping = mapping if mapping is not None else self._tou_mapping
            if len(expected_mapping.slots) != 6:
                raise ValueError(
                    f"Oczekiwana mapa Deye Time Of Use ma {len(expected_mapping.slots)} slotów zamiast 6"
                )
            expected_rows = self._expected_tou_readback_rows(expected_mapping)
            self.tou_expected_signature = self._tou_signature(expected_rows)
        except Exception as err:
            self.tou_expected_signature = ""
            self.tou_physical_signature = ""
            self.tou_readback_complete = False
            self.tou_reconciliation_in_sync = False
            self.tou_mismatched_fields = []
            self.tou_reconciliation_status = "error"
            self.tou_last_reconciliation_error = str(err)
            return False

        try:
            if profile.native_tou:
                capability_rows = self.tou_slot_capabilities()
                if not all(
                    row["fields"][field]["supported"]
                    and row["fields"][field]["readable"]
                    for row in capability_rows
                    for field in ("start", "soc", "grid_charge")
                ):
                    raise ValueError("readback 6/6 jest niepełny lub niedostępny")
            physical_rows = self._physical_tou_readback_rows()
        except Exception as err:
            self.tou_physical_signature = ""
            self.tou_readback_complete = False
            self.tou_reconciliation_in_sync = False
            self.tou_mismatched_fields = []
            self.tou_reconciliation_status = (
                "read_only" if not profile.native_tou else "waiting_readback"
            )
            self.tou_last_reconciliation_error = (
                "Nie można potwierdzić fizycznego Deye Time Of Use: " + str(err)
            )
            return False

        physical_signature = self._tou_signature(physical_rows)
        mismatched = self._tou_mismatched_fields(expected_rows, physical_rows)
        self.tou_physical_signature = physical_signature
        self.tou_readback_complete = True
        self.tou_mismatched_fields = mismatched
        self.tou_reconciliation_in_sync = not mismatched
        self.tou_last_reconciliation_error = ""
        if not mismatched:
            self.tou_reconciliation_status = "in_sync"
            self._last_physical_tou_signature = physical_signature
            self._last_external_tou_mismatch_signature = ""
            return True

        mismatch_signature = f"{self.tou_expected_signature}>{physical_signature}"
        if mismatch_signature != self._last_external_tou_mismatch_signature:
            self.tou_last_external_mismatch_at = ha_now().isoformat(timespec="seconds")
            self._last_external_tou_mismatch_signature = mismatch_signature
        if not profile.native_tou:
            self.tou_reconciliation_status = "read_only"
        elif self.emergency_stop:
            self.tou_reconciliation_status = "blocked_emergency_stop"
        elif not self._control_is_active():
            self.tou_reconciliation_status = "blocked_control_disabled"
        else:
            self.tou_reconciliation_status = "mismatch"
        return False

    def tou_reconciliation_diagnostics(self) -> dict[str, Any]:
        """Expose Stage 5D reconciliation state without changing the schedule."""
        return {
            "expected_signature": self.tou_expected_signature or None,
            "physical_signature": self.tou_physical_signature or None,
            "in_sync": self.tou_reconciliation_in_sync,
            "readback_complete": self.tou_readback_complete,
            "last_external_mismatch_at": self.tou_last_external_mismatch_at or None,
            "mismatched_fields": list(self.tou_mismatched_fields),
            "reconciliation_status": self.tou_reconciliation_status,
            "last_reconciliation_error": self.tou_last_reconciliation_error or None,
        }

    def _apply_reverse_sync_patch_locked(
        self, updates: list[dict[str, Any]]
    ) -> list[int]:
        """Apply only physical hourly fields while ``_operation_lock`` is held.

        This deliberately does not call ``async_apply_schedule_patch`` and does
        not schedule reconciliation.  The confirmed physical readback is the
        source of truth for this local mutation.
        """
        if not updates:
            raise ValueError("Reverse sync Deye TOU nie zawiera żadnych godzin")
        changed_hours: list[int] = []
        seen: set[str] = set()
        slot_hours = {key: int(start) for key, _label, start, _end in SLOTS}
        for update in updates:
            if not isinstance(update, dict):
                raise ValueError("Nieprawidłowy wpis reverse sync Deye TOU")
            if set(update) != {"slot_key", "tou_soc", "charge_enabled"}:
                raise ValueError(
                    "Reverse sync Deye TOU może zmieniać wyłącznie tou_soc i charge_enabled"
                )
            slot_key = str(update["slot_key"])
            if slot_key not in self.slots or slot_key in seen:
                raise ValueError(f"Nieprawidłowy slot reverse sync: {slot_key}")
            seen.add(slot_key)
            soc = float(update["tou_soc"])
            if not math.isfinite(soc) or not 0 <= soc <= 100:
                raise ValueError(f"Nieprawidłowy SOC reverse sync dla {slot_key}: {soc}")
            grid = bool(update["charge_enabled"])
            target = self.slots[slot_key]
            if target.tou_soc != soc or target.charge_enabled != grid:
                changed_hours.append(slot_hours[slot_key])
            target.tou_soc = soc
            target.charge_enabled = grid
        if len(seen) != 24:
            raise ValueError(
                f"Reverse sync Deye TOU objął {len(seen)} godzin, wymagane 24"
            )
        return sorted(changed_hours)

    def _tou_raw_snapshot(self) -> dict[str, str]:
        """Capture every physical value that can be touched by a TOU write."""
        entity_ids = [entity_id for _label, entity_id in self._tou_entities() if entity_id]
        snapshot: dict[str, str] = {}
        for entity_id in dict.fromkeys(entity_ids):
            state = self.hass.states.get(entity_id)
            if state is None or state.state in ("unknown", "unavailable", "none", ""):
                raise ValueError(f"Nie można odczytać wartości przed zapisem: {entity_id}")
            snapshot[entity_id] = str(state.state)
        return snapshot

    async def _async_restore_raw_entity(self, entity_id: str, raw_value: str) -> None:

        """Restore an exact HA state, preserving Generator/Both select options."""
        domain = entity_id.split(".", 1)[0]
        current = self.hass.states.get(entity_id)
        if current is not None:
            if domain == "number":
                actual_number = self.safe_float(current.state, float("nan"))
                target_number = self.safe_float(raw_value, float("nan"))
                if math.isfinite(actual_number) and math.isfinite(target_number) and math.isclose(
                    actual_number, target_number, abs_tol=0.1
                ):
                    return
            elif domain == "time":
                if self._time_to_minutes(current.state) == self._time_to_minutes(raw_value):
                    return
            elif str(current.state) == str(raw_value):
                return
        if domain == "select":
            await self._async_physical_service_call(
                "select",
                "select_option",
                {"entity_id": entity_id, "option": raw_value},
                target_value=raw_value,
            )
            return
        if domain == "switch":
            await self.async_set_switch(entity_id, raw_value == "on")
            return
        if domain == "time":
            await self.async_set_time(entity_id, raw_value)
            return
        if domain == "number":
            await self.async_set_number(entity_id, float(raw_value))
            return
        raise ValueError(f"Nieobsługiwana encja przywracania: {entity_id}")


    async def async_apply_time_of_use_map(self) -> bool:
        self._ensure_control_active()
        reservation = self._reserve_tou_write()
        try:
            async with self._control_operation("apply_tou_map") as transaction_id:
                return await self._async_apply_time_of_use_map_impl(transaction_id)
        finally:
            self._release_tou_write(reservation)

    async def _async_apply_time_of_use_map_impl(
        self, transaction_id: str | None = None
    ) -> bool:

        self._last_tou_write_started = False
        profile = provider_profile(self.data)
        mapping = self._tou_mapping
        if self.emergency_stop:
            if self._refresh_tou_reconciliation_state(mapping):
                return True
            self.tou_reconciliation_status = "blocked_emergency_stop"
            self.last_error = (
                "Wykryto rozbieżność Deye Time Of Use, ale aktywne jest zatrzymanie awaryjne."
            )
            self.notify_update()
            return False
        if len(mapping) > 6:
            self._refresh_tou_reconciliation_state(mapping)
            self.last_action = f"Time Of Use map skipped: {len(mapping)} segments"
            self.last_error = f"Mapowanie wymaga {len(mapping)} zakresów; Deye obsługuje maksymalnie 6"
            self.notify_update()
            return False
        if not profile.native_tou:
            self._refresh_tou_reconciliation_state(mapping)
            self.last_error = (
                f"{profile.label} nie udostępnia bezpiecznego sterowania Time Of Use w Home Assistant. "
                "Harmonogram nie został zapisany."
            )
            self.notify_update()
            return False
        missing_soc = [
            self.slots[key].label
            for key, _label, _start, _end in SLOTS
            if self._physical_tou_soc_for_slot(self.slots[key]) is None
        ]
        if missing_soc:
            self.tou_reconciliation_status = "waiting_readback"
            self.tou_reconciliation_in_sync = False
            self.tou_last_reconciliation_error = (
                "Nie można potwierdzić fizycznego Deye Time Of Use: brak tou_soc w Harmonogramie"
            )
            self.last_error = (
                "SOC baterii Deye (TOU) wymaga potwierdzenia dla slotów: "
                + ", ".join(missing_soc)
            )
            self.notify_update()
            return False
        readback_matches = self._refresh_tou_reconciliation_state(mapping)
        missing = self.tou_mapping_errors()
        if missing:
            self._last_tou_signature = ""
            self.last_error = "Brak wymaganych encji Deye Time Of Use: " + ", ".join(missing)
            self.notify_update()
            return False

        signature = self.tou_expected_signature
        if readback_matches:
            self._last_tou_signature = signature
            self._last_physical_tou_signature = self.tou_physical_signature
            return True

        if not self.tou_readback_complete:
            self._last_tou_signature = ""
            self.last_error = (
                self.tou_last_reconciliation_error
                or "Nie można potwierdzić fizycznego Deye Time Of Use"
            )
            self.notify_update()
            return False

        self.tou_reconciliation_status = "reconciling"
        self.tou_last_reconciliation_error = ""
        self.notify_update()
        items, snapshot = self._build_tou_transaction_plan(mapping)
        success, _items, message = await self._async_execute_tou_transaction(
            "uzgadniania Deye Time Of Use", items, snapshot
        )
        if not success:
            if not self._control_transaction_is_stale(transaction_id):
                self._last_tou_signature = ""
                self.tou_reconciliation_status = "error"
                self.tou_last_reconciliation_error = message
                self.last_error = message
                self.notify_update()
            return False

        if self._control_result_is_current(transaction_id):
            confirmed = self._refresh_tou_reconciliation_state(mapping)
            if not confirmed:
                self._last_tou_signature = ""
                self.tou_reconciliation_status = "error"
                self.tou_last_reconciliation_error = (
                    self.tou_last_reconciliation_error
                    or "Nie można potwierdzić fizycznego Deye Time Of Use po uzgodnieniu"
                )
                self.last_error = self.tou_last_reconciliation_error
                self.notify_update()
                return False
            self._last_tou_signature = signature
            self._last_physical_tou_signature = self.tou_physical_signature
        return True

    async def _async_reverse_sync_after_manual_tou_locked(
        self,
        transaction_id: str | None,
        items: list[dict[str, Any]],
        physical_snapshot: dict[str, str],
        schedule_snapshot: dict[str, SlotSettings],
    ) -> None:
        """Apply confirmed physical TOU readback locally and verify round-trip."""
        self.tou_contract_status = "waiting"
        self.reverse_sync_status = "applying"
        self.reverse_sync_last_error = ""
        self.reverse_sync_changed_hours = []
        self.reverse_sync_round_trip_ok = None
        self.notify_update()
        try:
            if not self._control_result_is_current(transaction_id) or not self._control_is_active():
                raise ControlDisabledError(self._control_block_message())

            capability_rows = self.tou_slot_capabilities()
            full_readback = all(
                row["fields"][field]["readable"]
                for row in capability_rows
                for field in ("start", "soc", "grid_charge")
            )
            if not full_readback:
                raise ValueError(
                    "Reverse sync wymaga pełnego potwierdzonego readbacku "
                    "Deye Time Of Use 6/6."
                )

            # Read and validate every physical field again.  The request payload
            # is intentionally not used as the reverse-sync source of truth.
            self._validated_tou_start_vector(1)
            confirmed_mapping = self.read_physical_tou_mapping()
            patch = self.tou_mapping_to_schedule_patch(confirmed_mapping)
            changed_hours = self._apply_reverse_sync_patch_locked(patch)
            round_trip = self.schedule_to_tou_mapping()
            if not self._tou_mappings_match(confirmed_mapping, round_trip):
                adjacent_equal = any(
                    round(float(confirmed_mapping.slots[idx].soc), 1)
                    == round(float(confirmed_mapping.slots[(idx + 1) % 6].soc), 1)
                    and bool(confirmed_mapping.slots[idx].grid_charge)
                    == bool(confirmed_mapping.slots[(idx + 1) % 6].grid_charge)
                    for idx in range(6)
                )
                detail = (
                    " Sąsiednie fizyczne sloty mają identyczny SOC i Grid Charge; "
                    "obecny algorytm 24 h → 6/6 nie przechowuje takiej granicy."
                    if adjacent_equal
                    else ""
                )
                raise ValueError(
                    "Round-trip Deye TOU nie odtworzył potwierdzonej mapy 6/6."
                    + detail
                )

            self.reverse_sync_changed_hours = changed_hours
            self.reverse_sync_round_trip_ok = True
            self.reverse_sync_status = "confirmed"
            self.reverse_sync_last_error = ""
            self.tou_contract_status = "confirmed"
            self.tou_operation_status = "success"
        except (Exception, asyncio.CancelledError) as err:
            self.slots = {key: replace(slot) for key, slot in schedule_snapshot.items()}
            self.reverse_sync_status = "rollback"
            self.reverse_sync_round_trip_ok = False
            rollback_snapshot = {
                item["entity_id"]: physical_snapshot[item["entity_id"]]
                for item in items
                if item.get("written") and item.get("entity_id") in physical_snapshot
            }
            try:
                with self._control_rollback_scope(transaction_id, rollback_snapshot):
                    rollback_ok, rollback_errors = await self._async_rollback_tou_transaction(
                        items, physical_snapshot
                    )
            except Exception as rollback_err:
                rollback_ok = False
                rollback_errors = [str(rollback_err)]

            base_error = str(err) or err.__class__.__name__
            if rollback_ok:
                message = (
                    f"Błąd reverse sync Deye Time Of Use: {base_error}. "
                    "Przywrócono Harmonogram i poprzednie ustawienia fizyczne."
                )
                self.reverse_sync_status = "rollback"
                self.tou_contract_status = "rollback"
                self.tou_operation_status = "error"
            else:
                message = (
                    f"KRYTYCZNY błąd reverse sync Deye Time Of Use: {base_error}. "
                    "Nie potwierdzono pełnego przywrócenia ustawień fizycznych: "
                    + ", ".join(rollback_errors)
                )
                self.reverse_sync_status = "rollback_failed"
                self.tou_contract_status = "rollback_failed"
                self.tou_operation_status = "critical"
            self.reverse_sync_last_error = message
            self.tou_last_error = message
            self.last_error = message
            self.tou_transaction_log = list(items)
            self.notify_update()
            if isinstance(err, asyncio.CancelledError):
                raise
            if isinstance(err, ControlDisabledError):
                raise ControlDisabledError(message) from err
            raise ValueError(message) from err

    async def async_set_physical_tou_slot(
        self,
        slot: int,
        start: str | None = None,
        end: str | None = None,
        soc: float | None = None,
        grid_charge: bool | None = None,
    ) -> None:
        """Write only supplied physical TOU fields through the provider adapter."""
        profile = provider_profile(self.data)
        if not profile.native_tou:
            raise ValueError(
                f"{profile.label} nie udostępnia bezpiecznej edycji Deye Time Of Use"
            )
        if slot < 1 or slot > 6:
            raise ValueError("Numer slotu Deye Time Of Use musi mieścić się w zakresie 1–6")
        supplied = {
            "start": start is not None,
            "end": end is not None,
            "soc": soc is not None,
            "grid_charge": grid_charge is not None,
        }
        if not any(supplied.values()):
            raise ValueError("Podaj co najmniej jedno pole Deye Time Of Use do zmiany")
        self._ensure_control_active()

        normalized_start: str | None = None
        normalized_end: str | None = None
        if supplied["start"] or supplied["end"]:
            proposed = self._validated_tou_start_vector(
                slot, start=start, end=end
            )
            normalized_start = proposed[slot - 1] if supplied["start"] else None
            next_slot = 1 if slot == 6 else slot + 1
            normalized_end = proposed[next_slot - 1] if supplied["end"] else None
        if supplied["soc"]:
            numeric_soc = float(soc)
            if not math.isfinite(numeric_soc) or not 0 <= numeric_soc <= 100:
                raise ValueError("SOC Deye Time Of Use musi mieścić się w zakresie 0–100%")
        if supplied["grid_charge"] and not isinstance(grid_charge, bool):
            raise ValueError("Ładowanie z sieci musi mieć wartość prawda/fałsz")

        next_slot = 1 if slot == 6 else slot + 1
        capability_row = self.tou_slot_capabilities()[slot - 1]
        capabilities = capability_row["fields"]
        for field_name, present in supplied.items():
            if not present:
                continue
            capability = capabilities[field_name]
            if not capability["supported"]:
                raise ValueError(
                    f"Provider {profile.label} nie obsługuje pola {field_name} "
                    f"dla slotu Deye Time Of Use {slot}"
                )
            if not capability["writable"]:
                raise ValueError(
                    f"Pole {field_name} slotu Deye Time Of Use {slot} nie jest obecnie zapisywalne"
                )

        reservation = self._reserve_tou_write()
        try:
            async with self._operation_lock:
                async with self._control_operation("manual_tou") as transaction_id:
                    schedule_snapshot = {
                        key: replace(value) for key, value in self.slots.items()
                    }
                    start_entity = self._tou_entity(slot, "start")
                    end_entity = self._tou_entity(next_slot, "start")
                    soc_entity = self._tou_entity(slot, "soc")
                    grid_entity = self._tou_entity(slot, "grid")
                    snapshot: dict[str, str] = {}
                    items: list[dict[str, Any]] = []
                    if normalized_start is not None:
                        items.append(
                            self._make_tou_transaction_item(
                                start_entity, "start", slot, normalized_start, snapshot
                            )
                        )
                    if normalized_end is not None:
                        items.append(
                            self._make_tou_transaction_item(
                                end_entity, "end", slot, normalized_end, snapshot
                            )
                        )
                    if supplied["soc"]:
                        items.append(
                            self._make_tou_transaction_item(
                                soc_entity, "soc", slot, float(soc), snapshot
                            )
                        )
                    if supplied["grid_charge"]:
                        items.append(
                            self._make_tou_transaction_item(
                                grid_entity, "grid", slot, bool(grid_charge), snapshot
                            )
                        )

                    success, _items, message = await self._async_execute_tou_transaction(
                        "ręcznego zapisu Deye Time Of Use",
                        items,
                        snapshot,
                        finalize_contract=False,
                    )
                    if not success:
                        if self._control_transaction_is_stale():
                            raise ControlDisabledError(self._control_block_message())
                        self.last_error = message
                        self.notify_update()
                        raise ValueError(message)

                    await self._async_reverse_sync_after_manual_tou_locked(
                        transaction_id,
                        items,
                        snapshot,
                        schedule_snapshot,
                    )
                    # Reverse sync adopts only a Manager-owned, confirmed manual
                    # edit.  Refresh the physical signature from readback so the
                    # next tick sees agreement and cannot create a write loop.
                    self._last_tou_signature = ""
                    self._refresh_tou_reconciliation_state()
                    self.last_error = ""
                    self.last_action = f"Ręcznie zapisano Deye Time Of Use — slot {slot}"
                    self.mark_config_saved()
        finally:
            self._release_tou_write(reservation)


    async def async_apply_slot_grid_charge(self, slot_key: str) -> bool:
        """Apply the schedule after a physical TOU Grid Charge change for one hour."""
        if slot_key not in self.slots:
            raise ValueError(f"Unknown schedule slot: {slot_key}")
        self._last_tou_signature = ""
        self._clear_slot_failure_latch()
        self.mark_config_saved()
        self.notify_update()
        if not self._control_is_active():
            self.last_action = (
                "Zmiany zapisano w Harmonogramie. Sterowanie Deye jest wyłączone — "
                "nie wysłano ich do falownika."
            )
            self.executed_manager_action = "Nie wykonano — sterowanie wyłączone"
            self.notify_update()
            return True
        return bool(await self.async_tick())

    def _normal_day_replace_update(self, slot: SlotSettings) -> dict[str, Any]:
        """Return the canonical Normal Operation target for one unselected hour.

        The full-day AI contract removes old execution intent without touching
        the independent logical selling guard or physical TOU SOC.  When an old
        special action is cleared, execution numbers are reset to the user's
        Normal Operation template and Grid Charge permission is always removed.
        """
        update: dict[str, Any] = {"slot_key": slot.key}
        normal_physical_mode = (
            self.normal_profile_physical_work_mode
            if self.normal_profile_physical_work_mode in PHYSICAL_NORMAL_MODES
            else self.default_normal_physical_work_mode()
        )
        if slot.mode != MODE_NORMAL_OPERATION:
            update.update({
                "enabled": True,
                "mode": MODE_NORMAL_OPERATION,
                "charge_enabled": False,
                "physical_work_mode": normal_physical_mode,
                "sell_power": self.normal_profile_sell_power,
                "discharge_current": self.normal_profile_discharge_current,
                "charge_current": self.normal_profile_charge_current,
                "grid_charge_current": self.normal_profile_grid_charge_current,
            })
        else:
            if not slot.enabled:
                update["enabled"] = True
            if slot.charge_enabled:
                update["charge_enabled"] = False
            if slot.physical_work_mode not in PHYSICAL_NORMAL_MODES:
                update["physical_work_mode"] = normal_physical_mode
        return update

    def _build_target_schedule_today(
        self,
        selected_updates: list[dict[str, Any]],
        date: str | None,
    ) -> tuple[list[dict[str, Any]], set[str], set[str]]:
        """Build one authoritative 24-hour target from selected AI actions."""
        today = ha_now().date().isoformat()
        if str(date or "") != today:
            raise ValueError(
                f"Pełnodniowe Apply Today wymaga dzisiejszej daty {today}"
            )
        if not isinstance(selected_updates, list) or not selected_updates:
            raise ValueError(
                "Pełnodniowe Apply Today wymaga co najmniej jednej wybranej akcji specjalnej"
            )

        selected: dict[str, dict[str, Any]] = {}
        slot_start = {key: int(start) for key, _label, start, _end in SLOTS}
        current_hour = ha_now().hour
        for raw in selected_updates:
            if not isinstance(raw, dict):
                raise ValueError("Każda wybrana akcja Apply Today musi być obiektem")
            update = dict(raw)
            slot_key = str(update.get("slot_key") or "")
            if slot_key not in self.slots:
                raise ValueError(f"Unknown schedule slot: {slot_key}")
            if slot_key in selected:
                raise ValueError(f"Powtórzona wybrana godzina Apply Today: {slot_key}")
            if slot_start[slot_key] < current_hour:
                raise ValueError(
                    f"Wybrana godzina {slot_key} już minęła; odśwież plan bez catch-up"
                )
            mode = str(update.get("mode") or "")
            if mode not in {MODE_SELLING_FIRST, MODE_CHARGE}:
                raise ValueError(
                    f"Apply Today przyjmuje wyłącznie wybrane akcje Sprzedaż/Ładowanie: {slot_key}"
                )
            if update.get("enabled") is False:
                raise ValueError(f"Wybrana akcja Apply Today nie może być wyłączona: {slot_key}")
            if mode == MODE_SELLING_FIRST:
                if "sell_power" not in update:
                    raise ValueError(
                        f"Wybrana akcja Sprzedaż wymaga sell_power: {slot_key}"
                    )
                # Canonical AI/Core Sell contract: the selected slot owns only
                # its logical action and exact sell power.  Ignore every legacy
                # current/SOC/Grid Charge field instead of letting it become a
                # global inverter write.
                update = self._sanitize_ai_sell_execution_update(update)
            selected[slot_key] = update

        normal_keys = set(self.slots) - set(selected)
        ai_sell_keys = {
            key
            for key, update in selected.items()
            if update.get("mode") == MODE_SELLING_FIRST
        }
        target = [
            dict(selected[key])
            if key in selected
            else self._normal_day_replace_update(self.slots[key])
            for key, _label, _start, _end in SLOTS
        ]
        if len(target) != 24 or {str(item.get("slot_key")) for item in target} != set(self.slots):
            raise ValueError("Nie udało się zbudować kompletnego target_schedule_today 24 h")
        return target, normal_keys, ai_sell_keys

    @staticmethod
    def _sanitize_ai_sell_execution_update(update: dict[str, Any]) -> dict[str, Any]:
        """Return the complete executable AI Sell allowlist."""
        return {
            key: update[key]
            for key in ("slot_key", "enabled", "mode", "sell_power")
            if key in update
        }

    async def async_apply_schedule_patch(
        self,
        updates: list[dict[str, Any]],
        *,
        replace_day: bool = False,
        date: str | None = None,
        ai_source: bool = False,
        change_source: str | None = None,
        source_context: dict[str, Any] | None = None,
    ) -> None:
        """Validate and save logical slot changes, then reconcile Deye in background.

        The legacy/default contract remains a partial patch. ``replace_day`` is
        reserved for AI Apply Today and treats selected special actions as the
        authoritative allowlist for today's complete logical schedule.
        ``ai_source`` protects execution of a previously accepted Tomorrow plan.
        """
        if not isinstance(updates, list) or not updates:
            raise ValueError("Schedule patch must contain at least one slot")

        numeric_limits = {
            "sell_power": (0.0, float(self.effective_inverter_max_power_w)),
            "discharge_current": (0.0, 240.0),
            "charge_current": (0.0, 240.0),
            "grid_charge_current": (0.0, 240.0),
            "minimum_sell_soc": (0.0, 100.0),
            "tou_soc": (0.0, 100.0),
            "min_sell_price": (0.0, 5.0),
        }
        allowed_fields = {
            "enabled",
            "mode",
            "physical_work_mode",
            "charge_enabled",
            "force_copy_normal_profile",
            "force_copy_charge_profile",
            *numeric_limits,
        }

        async with self._operation_lock:
            previous_schedule_revision = self.schedule_revision
            previous_slot_revisions = deepcopy(self.schedule_slot_revisions)
            previous_slot_ownership = deepcopy(self.schedule_slot_ownership)
            normal_replace_keys: set[str] = set()
            ai_sell_power_only_keys: set[str] = set()
            if replace_day:
                (
                    updates,
                    normal_replace_keys,
                    ai_sell_power_only_keys,
                ) = self._build_target_schedule_today(updates, date)
            elif ai_source:
                updates = self._validate_future_plan_updates(updates)
                updates = [
                    self._sanitize_ai_sell_execution_update(update)
                    if update.get("mode") == MODE_SELLING_FIRST
                    else update
                    for update in updates
                ]
                ai_sell_power_only_keys = {
                    str(update.get("slot_key") or "")
                    for update in updates
                    if update.get("mode") == MODE_SELLING_FIRST
                }
            changed_keys = [
                str(update.get("slot_key") or "")
                for update in updates
                if isinstance(update, dict)
            ]
            effective_source = change_source or (
                "apply_today" if replace_day else
                "future_plan" if ai_source and isinstance(source_context, dict) and source_context.get("plan_id") else
                "optimizer_core" if ai_source else
                "manual"
            )
            previous_slots = {key: replace(slot) for key, slot in self.slots.items()}
            previous_scheduler = self.scheduler_enabled
            try:
                for update in updates:
                    update = dict(update) if isinstance(update, dict) else update
                    if not isinstance(update, dict):
                        raise ValueError("Each schedule update must be an object")
                    slot_key = str(update.get("slot_key") or "")
                    if slot_key not in self.slots:
                        raise ValueError(f"Unknown schedule slot: {slot_key}")
                    if "min_soc" in update:
                        update.setdefault("minimum_sell_soc", update.pop("min_soc"))
                    unknown = set(update) - allowed_fields - {"slot_key"}
                    if unknown:
                        raise ValueError(f"Unsupported schedule fields: {', '.join(sorted(unknown))}")
                    slot = self.slots[slot_key]
                    if replace_day or ai_source:
                        slot.ai_sell_power_only = slot_key in ai_sell_power_only_keys
                        if slot.ai_sell_power_only:
                            # Materialise the independent user/global value in
                            # the logical row so the schedule UI never presents
                            # a derived sell current as an executable limit.
                            slot.discharge_current = self.user_schedule_discharge_current
                    elif "mode" in update or "discharge_current" in update:
                        # A regular partial patch is an explicit manual edit and
                        # retains the pre-existing per-slot current contract.
                        slot.ai_sell_power_only = False
                    if "enabled" in update:
                        slot.enabled = bool(update["enabled"])
                    previous_mode = slot.mode
                    previous_tou_soc = slot.tou_soc
                    force_copy = bool(update.get("force_copy_normal_profile"))
                    force_copy_charge = bool(update.get("force_copy_charge_profile"))
                    if "mode" in update:
                        mode = str(update["mode"])
                        if mode not in SLOT_MODES:
                            raise ValueError(f"Unsupported slot mode: {mode}")
                        slot.mode = mode
                        if mode == MODE_NORMAL_OPERATION and (previous_mode != MODE_NORMAL_OPERATION or force_copy):
                            slot.enabled = True
                            # Copy the normal profile template once, or again when
                            # the user explicitly asks for a reload.
                            if self.normal_profile_physical_work_mode in PHYSICAL_NORMAL_MODES:
                                slot.physical_work_mode = self.normal_profile_physical_work_mode
                            if self.normal_profile_sell_power >= 0:
                                slot.sell_power = self.normal_profile_sell_power
                            if self.normal_profile_discharge_current >= 0:
                                slot.discharge_current = self.normal_profile_discharge_current
                            if self.normal_profile_charge_current >= 0:
                                slot.charge_current = self.normal_profile_charge_current
                            if self.normal_profile_grid_charge_current >= 0:
                                slot.grid_charge_current = self.normal_profile_grid_charge_current
                            if self.normal_profile_tou_soc is not None and self.normal_profile_tou_soc >= 0:
                                slot.tou_soc = self.normal_profile_tou_soc
                            if replace_day and slot_key in normal_replace_keys:
                                # TOU SOC is a separate physical contract. Full-day
                                # replacement clears the logical action, not this
                                # independently confirmed inverter value.
                                slot.tou_soc = previous_tou_soc
                        elif mode == MODE_CHARGE:
                            slot.enabled = True
                            if previous_mode != MODE_CHARGE or force_copy_charge:
                                slot.charge_current = self.charge_profile_charge_current
                                slot.discharge_current = self.charge_profile_discharge_current
                                slot.grid_charge_current = self.charge_profile_grid_charge_current
                                slot.tou_soc = self.charge_profile_target_soc
                                slot.charge_enabled = self.charge_profile_grid_enabled
                        elif previous_mode == MODE_NORMAL_OPERATION:
                            slot.physical_work_mode = None
                    if "physical_work_mode" in update:
                        physical_mode = str(update["physical_work_mode"] or "")
                        if slot.mode != MODE_NORMAL_OPERATION:
                            raise ValueError(
                                "physical_work_mode jest dozwolony wyłącznie dla Normalnej Pracy"
                            )
                        if physical_mode not in PHYSICAL_NORMAL_MODES:
                            raise ValueError(
                                f"Nieobsługiwany fizyczny tryb pracy: {physical_mode}"
                            )
                        slot.physical_work_mode = physical_mode
                    if "charge_enabled" in update:
                        # ``charge_enabled`` is the physical hourly Grid Charge flag
                        # and is independent of the logical manager mode.
                        slot.charge_enabled = bool(update["charge_enabled"])
                    for field_name, (minimum, maximum) in numeric_limits.items():
                        if field_name not in update:
                            continue
                        value = float(update[field_name])
                        if not math.isfinite(value) or not minimum <= value <= maximum:
                            raise ValueError(
                                f"{field_name} for {slot_key} must be between {minimum:g} and {maximum:g}"
                            )
                        if field_name == "sell_power":
                            self.validate_manual_sell_power_w(
                                f"sell_power dla {slot_key}", value
                            )
                        setattr(slot, field_name, value)

                if any(slot.enabled for slot in self.slots.values()):
                    self.scheduler_enabled = True
                metadata_changed = any(
                    self.slots[key].ai_sell_power_only
                    != previous_slots[key].ai_sell_power_only
                    for key in self.slots
                )
                logical_changed = self.scheduler_enabled != previous_scheduler or any(
                    replace(
                        self.slots[key],
                        ai_sell_power_only=previous_slots[key].ai_sell_power_only,
                    )
                    != previous_slots[key]
                    for key in self.slots
                )
                if replace_day and not logical_changed:
                    self._claim_schedule_slots(
                        changed_keys, effective_source, source_context
                    )
                    self.last_action = (
                        "Pełny plan na dziś jest już zgodny — brak zmian do zapisania"
                    )
                    if metadata_changed or changed_keys:
                        # Persist RestoreEntity attributes without scheduling a
                        # physical reconciliation for metadata-only ownership.
                        self.mark_config_saved()
                        self.notify_update()
                    return
                self._clear_pending_control_transaction()
                self._last_slot_failure_signature = ""
                if self.mapping_error:
                    raise ValueError(
                        f"Mapowanie wymaga {len(self._tou_mapping)} zakresów; "
                        "Deye obsługuje maksymalnie 6"
                    )
                self._claim_schedule_slots(
                    changed_keys, effective_source, source_context
                )
                self.mark_config_saved()
                if self._control_is_active() and not self.emergency_stop:
                    self._schedule_schedule_reconciliation()
                else:
                    self._schedule_reconcile_requested = False
                    blocked_reason = (
                        "aktywne jest zatrzymanie awaryjne"
                        if self.emergency_stop
                        else "Sterowanie Deye jest wyłączone"
                    )
                    self.last_action = (
                        f"Zmiany zapisano w Harmonogramie. {blocked_reason} — "
                        "nie wysłano ich do falownika."
                    )
                    self.executed_manager_action = f"Nie wykonano — {blocked_reason.lower()}"
                    self.notify_update()
            except Exception as err:
                self.slots = previous_slots
                self.scheduler_enabled = previous_scheduler
                self.schedule_revision = previous_schedule_revision
                self.schedule_slot_revisions = previous_slot_revisions
                self.schedule_slot_ownership = previous_slot_ownership
                self.notify_update()
                raise

    def _schedule_schedule_reconciliation(self) -> None:
        """Coalesce schedule edits and apply their physical effects asynchronously."""
        if not self._control_is_active():
            self._schedule_reconcile_requested = False
            return
        self._schedule_reconcile_requested = True
        task = self._schedule_reconcile_task
        if task is not None and not task.done():
            return
        self._schedule_reconcile_task = self.hass.async_create_task(
            self._async_reconcile_schedule_changes()
        )

    async def _async_reconcile_schedule_changes(self) -> None:
        """Apply the newest saved schedule without blocking the UI service call."""
        try:
            # A short debounce combines changes made in quick succession into
            # one physical TOU transaction.  The operation lock preserves the
            # existing serialization with timer ticks and direct controls.
            await asyncio.sleep(0.25)
            while self._schedule_reconcile_requested:
                self._schedule_reconcile_requested = False
                async with self._operation_lock:
                    try:
                        reconciled = await self._async_tick_impl()
                        if not reconciled:
                            await self._async_finish_future_plan_physical(
                                False, self.last_error or "Fizyczna synchronizacja nie powiodła się"
                            )
                    except asyncio.CancelledError:
                        raise
                    except ControlDisabledError as err:
                        self.last_action = str(err)
                        self.executed_manager_action = "Nie wykonano — sterowanie wyłączone"
                        self.notify_update()
                        return
                    except Exception as err:
                        await self.async_apply_safe_defaults(
                            "Nieudana synchronizacja zapisanego harmonogramu: "
                            f"{type(err).__name__}: {err}"
                        )
                        await self._async_finish_future_plan_physical(
                            False, f"{type(err).__name__}: {err}"
                        )
                if self._schedule_reconcile_requested:
                    await asyncio.sleep(0.25)
        finally:
            self._schedule_reconcile_task = None

    def _control_entities_to_write(
        self, mode: str
    ) -> tuple[dict[str, tuple[str, str]], list[str]]:
        """Return a snapshot of control entities that will be changed.

        The snapshot maps entity_id to (label, raw_state). Missing or unreadable
        entities are reported separately so the caller can abort before the
        first write.
        """
        profile = provider_profile(self.data)
        entities: list[tuple[str | None, str]] = [
            (self.work_mode_select, "System Work Mode"),
            (self.max_sell_power_number, "Max Sell Power"),
            (self.discharge_current_number, "Maximum Battery Discharge Current"),
            (self.charge_current_number, "Maximum Battery Charge Current"),
            (self.grid_charge_current_number, "Maximum Battery Grid Charge Current"),
        ]
        if profile.needs_aux_export_switch:
            entities.append((self.work_mode_aux_entity, "Solar Export"))
        snapshot: dict[str, tuple[str, str]] = {}
        missing: list[str] = []
        for entity_id, label in entities:
            if not entity_id:
                missing.append(label)
                continue
            state = self.hass.states.get(entity_id)
            if state is None or state.state in ("unknown", "unavailable", "none", ""):
                missing.append(label)
                continue
            domain = entity_id.split(".", 1)[0]
            if domain == "number":
                try:
                    value = float(state.state)
                    if not math.isfinite(value):
                        missing.append(label)
                        continue
                except (TypeError, ValueError):
                    missing.append(label)
                    continue
            elif domain == "switch":
                if state.state not in ("on", "off"):
                    missing.append(label)
                    continue
            snapshot[entity_id] = (label, str(state.state))
        return snapshot, missing

    def _logical_mode_from_raw(self, raw_mode: str) -> str | None:
        """Map a provider-specific raw mode option back to a logical work mode."""
        if logical_mode_matches(self.data, MODE_SELLING_FIRST, raw_mode):
            return MODE_SELLING_FIRST
        for physical_mode in PHYSICAL_NORMAL_MODES:
            if logical_mode_matches(
                self.data,
                MODE_NORMAL_OPERATION,
                raw_mode,
                physical_mode,
            ):
                return MODE_NORMAL_OPERATION
        return None

    def _physical_mode_from_raw(self, raw_mode: str) -> str | None:
        for physical_mode in PHYSICAL_NORMAL_MODES:
            if logical_mode_matches(
                self.data,
                MODE_NORMAL_OPERATION,
                raw_mode,
                physical_mode,
            ):
                return physical_mode
        return None

    async def _async_restore_work_mode_and_aux(self, snapshot: dict[str, tuple[str, str]]) -> None:
        """Restore work mode and optional aux switch using provider-safe order."""
        mode_entity = self.work_mode_select
        if not mode_entity:
            raise ValueError("Missing work mode entity")
        raw_mode = snapshot[mode_entity][1]
        profile = provider_profile(self.data)
        aux_entity = self.work_mode_aux_entity if profile.needs_aux_export_switch else None
        is_selling = logical_mode_matches(self.data, MODE_SELLING_FIRST, raw_mode)
        if is_selling and aux_entity:
            # Prepare aux before entering selling mode.
            await self._async_restore_raw_entity(aux_entity, "on")
        await self._async_restore_raw_entity(mode_entity, raw_mode)
        if not is_selling and aux_entity:
            await self._async_restore_raw_entity(aux_entity, "off")

    async def _async_rollback_control_values(
        self, snapshot: dict[str, tuple[str, str]]
    ) -> tuple[bool, str]:
        """Restore control entities from snapshot and confirm the readback.

        Returns ``(True, "")`` when every entity was restored and the readback
        matches the snapshot within the bounded confirmation window.  Otherwise
        returns ``(False, reason)`` so the caller can report the failing entity.
        """
        self._performance.inc("inverter_rollback")
        numbers: dict[str, tuple[str, float]] = {}
        mode_raw: str | None = None
        for entity_id, (label, raw_value) in snapshot.items():
            domain = entity_id.split(".", 1)[0]
            if domain == "number":
                try:
                    numbers[entity_id] = (label, float(raw_value))
                except (TypeError, ValueError):
                    return False, f"{label}: niepoprawna wartość snapshotu"
            elif entity_id == self.work_mode_select:
                mode_raw = raw_value

        if mode_raw is None:
            return False, "System Work Mode: brak w snapshotcie"

        try:
            # Restore numbers first, then work mode with aux as one unit.
            for entity_id, (label, value) in numbers.items():
                await self._async_restore_raw_entity(entity_id, str(value))
            await self._async_restore_work_mode_and_aux(snapshot)
        except Exception as exc:
            return False, f"{label}: {exc}"

        logical_mode = self._logical_mode_from_raw(mode_raw)
        if logical_mode is None:
            return False, "System Work Mode: nieznany tryb po rollbach"
        rollback_physical_mode = self._physical_mode_from_raw(mode_raw)
        expected = {
            "System Work Mode": logical_mode,
            "Max Sell Power": numbers.get(self.max_sell_power_number, ("", 0.0))[1],
            "Prąd rozładowania": numbers.get(self.discharge_current_number, ("", 0.0))[1],
            "Prąd ładowania baterii": numbers.get(self.charge_current_number, ("", 0.0))[1],
            "Prąd ładowania z sieci": numbers.get(self.grid_charge_current_number, ("", 0.0))[1],
        }
        deadline = asyncio.get_running_loop().time() + self.control_confirmation_timeout
        while True:
            unconfirmed = await self.async_verify_control_values(
                expected["System Work Mode"],
                expected["Max Sell Power"],
                expected["Prąd rozładowania"],
                expected["Prąd ładowania baterii"],
                expected["Prąd ładowania z sieci"],
                rollback_physical_mode or self._active_physical_work_mode(),
            )
            if not unconfirmed:
                return True, ""
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                return False, f"niepotwierdzony rollback: {', '.join(unconfirmed)}"
            await asyncio.sleep(min(0.5, remaining))

    async def _async_wait_for_control_confirmation(
        self,
        mode: str,
        sell_power: float,
        discharge_current: float,
        charge_current: float,
        grid_charge_current: float,
    ) -> bool:
        """Wait for Deye to publish the requested control values.

        Returns True when confirmed, False on timeout or when emergency_stop
        is set. Uses a monotonic clock.
        """
        deadline = asyncio.get_running_loop().time() + self.control_confirmation_timeout
        while True:
            if self.emergency_stop:
                return False
            if not self._control_is_active():
                return False
            unconfirmed = await self.async_verify_control_values(
                mode, sell_power, discharge_current, charge_current, grid_charge_current, self._active_physical_work_mode()
            )
            if not unconfirmed:
                return True
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                return False
            await asyncio.sleep(min(0.5, remaining))

    async def _async_rollback_with_shield(
        self, snapshot: dict[str, tuple[str, str]]
    ) -> None:
        """Attempt rollback during cancellation without blocking unload.

        The rollback itself may use ``control_confirmation_timeout`` to wait for
        readback confirmation. The 5-second limit here is only the outer safety
        cap for the cleanup phase; the rollback task is explicitly tracked and
        cancelled/awaited so it can never outlive the manager.
        """
        if self._rollback_task is not None and not self._rollback_task.done():
            self._rollback_task.cancel()
            try:
                await self._rollback_task
            except asyncio.CancelledError:
                pass
        self._rollback_task = asyncio.get_running_loop().create_task(
            self._async_rollback_control_values(snapshot)
        )
        try:
            await asyncio.wait_for(
                asyncio.shield(self._rollback_task),
                timeout=5.0,
            )
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass
        except Exception:
            pass
        finally:
            if not self._rollback_task.done():
                self._rollback_task.cancel()
            if not self._rollback_task.done():
                try:
                    await self._rollback_task
                except asyncio.CancelledError:
                    pass
            # Swallow any stored exception; the cancellation path only needs to
            # ensure the task is not left running.
            elif self._rollback_task.exception() is not None:
                pass
            self._rollback_task = None

    async def async_apply_settings(
        self,
        mode: str,
        sell_power: float,
        discharge_current: float,
        charge_current: float,
        grid_charge_current: float | None = None,
    ) -> None:
        """Apply direct inverter settings using a safe, serialized write order."""
        effective_grid_charge_current = grid_charge_current if grid_charge_current is not None else self.default_grid_charge_current
        self.validate_manual_sell_power_w("Moc sprzedaży", sell_power)
        physical_sell_power = self.normalize_automatic_sell_power_w(sell_power)
        async with self._operation_lock:
            async with self._control_operation("apply_settings") as transaction_id:
                if self.emergency_stop:
                    raise RuntimeError("Przerwane przez zatrzymanie awaryjne")
                if mode == MODE_SELLING_FIRST and not self.sell_allowed:
                    if self.emergency_stop:
                        raise RuntimeError("Przerwane przez zatrzymanie awaryjne")
                    await self.async_apply_safe_defaults("Sprzedaż zablokowana przez ochronę SOC lub ceny")
                    raise ValueError(self.decision_reason)
                try:
                    self._validate_control_plan(
                        mode,
                        sell_power,
                        discharge_current,
                        charge_current,
                        effective_grid_charge_current,
                    )
                except Exception as err:
                    if self.emergency_stop:
                        raise RuntimeError("Przerwane przez zatrzymanie awaryjne") from err
                    await self.async_apply_safe_defaults(f"Nieprawidłowy plan ustawień: {err}")
                    raise
                snapshot, missing = self._control_entities_to_write(mode)
                if missing:
                    raise RuntimeError(f"Brak czytelnych encji do snapshotu: {', '.join(missing)}")
                raw_snapshot = {
                    entity_id: raw_value
                    for entity_id, (_label, raw_value) in snapshot.items()
                }
                self._set_control_transaction_snapshot(transaction_id, raw_snapshot)
                try:
                    await self.async_set_number(self.charge_current_number, charge_current)
                    await self.async_set_number(
                        self.grid_charge_current_number,
                        effective_grid_charge_current,
                    )
                    applied_sell_power_native = await self.async_set_max_sell_power_number(physical_sell_power)
                    await self.async_set_number(self.discharge_current_number, discharge_current)
                    await self.async_set_work_mode(mode)
                    confirmed = await self._async_wait_for_control_confirmation(
                        mode,
                        applied_sell_power_native,
                        discharge_current,
                        charge_current,
                        effective_grid_charge_current,
                    )
                    if not confirmed:
                        if self.emergency_stop:
                            raise RuntimeError("Przerwane przez zatrzymanie awaryjne")
                        if not self._control_is_active():
                            raise ControlDisabledError(self._control_block_message())
                        raise RuntimeError("Niepotwierdzone ustawienia po czasie oczekiwania")
                except ControlDisabledError:
                    with self._control_rollback_scope(transaction_id, raw_snapshot):
                        await self._async_rollback_control_values(snapshot)
                    raise
                except asyncio.CancelledError:
                    with self._control_rollback_scope(transaction_id, raw_snapshot):
                        await self._async_rollback_with_shield(snapshot)
                    raise
                except Exception as err:
                    if self.emergency_stop:
                        raise RuntimeError("Przerwane przez zatrzymanie awaryjne") from err
                    with self._control_rollback_scope(transaction_id, raw_snapshot):
                        rollback_ok, rollback_reason = await self._async_rollback_control_values(snapshot)
                    if rollback_ok:
                        self.last_action = "Wycofano zmiany po błędzie apply_settings"
                        self.last_error = str(err)
                    else:
                        await self.async_apply_safe_defaults(
                            f"Błąd bezpośredniego zapisu ustawień: {err}. Rollback: {rollback_reason}"
                        )
                    raise
                if self._control_result_is_current(transaction_id):
                    self.last_action = "Zastosowano ustawienia bezpośrednie"
                    self.last_error = ""
                    self.executed_manager_action = "Wykonano: ustawienia bezpośrednie"

    def _slot_failure_fingerprint(self, reason: str) -> str:
        """Return a stable signature of an active-slot fault.

        This prevents the minute timer from restoring the same defaults over
        and over.  It changes when the slot, schedule, relevant source state
        or TOU mapping availability changes.
        """
        slot = self.active_slot
        control_entities = [
            self.work_mode_select,
            self.max_sell_power_number,
            self.discharge_current_number,
            self.charge_current_number,
            self.grid_charge_current_number,
            *self.tou_mapping_errors(),
        ]
        # Control values are deliberately represented only by availability:
        # applying defaults changes their values and must not defeat the
        # failure latch on the next minute tick.
        availability = [
            f"{entity_id}:{self.entity_available(entity_id)}" for entity_id in control_entities if entity_id
        ]
        sensor_states = [
            f"{entity_id}:{self.state_text(entity_id)}"
            for entity_id in (
                self.battery_soc_sensor if slot.mode == MODE_SELLING_FIRST else None,
                self.price_sensor if slot.mode == MODE_SELLING_FIRST and slot.min_sell_price > 0 else None,
            )
            if entity_id
        ]
        soc_quality = (
            str(self.soc_diagnostics().get("status") or "unknown")
            if slot.mode == MODE_SELLING_FIRST
            else "not_required"
        )
        slot_data = (
            slot.key, slot.enabled, slot.mode, slot.sell_power,
            slot.discharge_current, slot.charge_current,
            slot.grid_charge_current,
            slot.minimum_sell_soc, slot.tou_soc, slot.min_sell_price,
            slot.charge_enabled,
        )
        return repr((
            self.control_mode,
            slot_data,
            tuple(availability),
            tuple(sensor_states),
            soc_quality,
            self.mapping_error,
        ))

    def _clear_slot_failure_latch(self) -> None:
        self._last_slot_failure_signature = ""

    async def _async_handle_slot_failure(
        self, reason: str, stage: str, expected: dict[str, Any]
    ) -> bool:
        self._clear_pending_control_transaction()
        signature = self._slot_failure_fingerprint(stage)
        if signature == self._last_slot_failure_signature:
            message = f"{reason}. Ustawienia domyślne zostały już zastosowane dla tego samego błędu."
            self.record_schedule_attempt("failed", stage, expected, message)
            self.last_error = message
            self.notify_update()
            return False
        self._last_slot_failure_signature = signature
        self.record_schedule_attempt("failed", stage, expected, reason)
        await self.async_apply_safe_defaults(reason)
        return False

    def _report_tou_preflight_failure(self) -> bool:
        """Report an oversized TOU map without touching the inverter."""
        required = len(self._tou_mapping)
        reason = (
            f"Błąd mapowania: wymagane {required} zakresów, "
            "Deye obsługuje maksymalnie 6"
        )
        self._clear_pending_control_transaction()
        self.record_schedule_attempt("failed", "mapowanie TOU", {}, reason)
        self.last_action = "Nie zastosowano mapowania Deye Time Of Use"
        self.last_error = reason
        self.notify_update()
        return False

    async def async_apply_targets(self) -> bool:
        async with self._control_operation("apply_targets") as transaction_id:
            return await self._async_apply_targets_impl(transaction_id)

    async def _async_apply_targets_impl(
        self, transaction_id: str | None = None
    ) -> bool:
        if self.control_mode == "Schedule" and self.mapping_error:
            return self._report_tou_preflight_failure()
        if not self.data_available:
            return await self._async_handle_slot_failure(
                "Brak wymaganej encji sterującej Deye", "walidacja encji", {}
            )
        if (
            self.control_mode == "Schedule"
            and self.active_slot.enabled
            and self._last_slot_failure_signature
            and self._last_slot_failure_signature == self._slot_failure_fingerprint("")
        ):
            message = "Bieżący slot pozostaje zablokowany po poprzednim błędzie; ustawienia domyślne zostały już zastosowane."
            self.record_schedule_attempt("failed", "blokada po błędzie", {}, message)
            self.last_error = message
            self.notify_update()
            return False
        sell_requested = self.control_mode == "Manual Sell" or (
            self.control_mode == "Schedule"
            and self.active_slot.enabled
            and self.active_slot.mode == MODE_SELLING_FIRST
        )
        sell_block_reason = ""
        if sell_requested:
            guard_issue = self._selling_slot_guard_issue()
            if guard_issue and guard_issue[0] == "error":
                return await self._async_handle_slot_failure(
                    guard_issue[1], "warunki sprzedaży", {}
                )
            if guard_issue and guard_issue[0] == "blocked":
                sell_block_reason = guard_issue[1]
            elif not self.sell_allowed:
                reason = "Błąd ceny" if not self.price_ok else "Błąd lub brak odczytu SOC"
                return await self._async_handle_slot_failure(reason, "warunki sprzedaży", {})
        target_mode = self.target_mode
        target_sell_power = self.target_sell_power
        applied_sell_power = self.applied_sell_power
        target_discharge_current = self.target_discharge_current
        target_charge_current = self.target_charge_current
        grid_charge_current = self.default_grid_charge_current
        if self.control_mode == "Schedule" and self.active_slot.enabled:
            # A positive limit does not grant grid charging. Only the active
            # Charge slot's explicit flag may enable the physical TOU switch.
            grid_charge_current = (
                self.active_slot.grid_charge_current
                if self.active_charge_slot
                else self.default_grid_charge_current
            )
        expected = {"System Work Mode": target_mode, "Max Sell Power": applied_sell_power, "Prąd rozładowania": target_discharge_current, "Prąd ładowania baterii": target_charge_current, "Prąd ładowania z sieci": grid_charge_current}
        pending_result = await self._async_confirm_or_wait_for_control(expected, "potwierdzenie falownika")
        if pending_result is not None:
            return pending_result
        if sell_block_reason:
            block_signature = self._sell_block_fingerprint(sell_block_reason)
            if block_signature == self._last_sell_block_signature:
                unconfirmed = await self.async_verify_control_values(
                    expected["System Work Mode"],
                    None if expected["Max Sell Power"] is None else float(expected["Max Sell Power"]),
                    float(expected["Prąd rozładowania"]),
                    float(expected["Prąd ładowania baterii"]),
                    float(expected["Prąd ładowania z sieci"]),
                    self._active_physical_work_mode(),
                )
                if not unconfirmed:
                    self.record_schedule_attempt(
                        "blocked", "warunki sprzedaży", expected, sell_block_reason
                    )
                    self.last_action = sell_block_reason
                    self.last_error = ""
                    self.notify_update()
                    return True
            self._last_sell_block_signature = block_signature
        else:
            self._last_sell_block_signature = ""
        stage = "walidacja planu"
        cap_message = ""
        if applied_sell_power < target_sell_power:
            cap_message = (
                f"Moc ograniczona z {int(target_sell_power)} W do "
                f"{int(applied_sell_power)} W przez maksymalną moc falownika."
            )
        self.record_schedule_attempt("pending", stage, expected, cap_message)
        try:
            self._validate_control_plan(target_mode, applied_sell_power, target_discharge_current, target_charge_current, grid_charge_current)
            stage = "mapowanie Deye Time Of Use"
            if self.control_mode == "Schedule" and not await self.async_apply_time_of_use_map():
                if not self._control_is_active():
                    raise ControlDisabledError(self._control_block_message())
                message = f"Nieudana transakcja sterująca ({stage}): {self.last_error}"
                self.record_schedule_attempt("failed", stage, expected, message)
                self.last_action = "Nie zastosowano mapowania Deye Time Of Use"
                self.last_error = message
                self.notify_update()
                return False
            stage = "wartości liczbowe"
            await self.async_set_number_if_needed(self.charge_current_number, target_charge_current)
            await self.async_set_number_if_needed(self.grid_charge_current_number, grid_charge_current)
            applied_sell_power_native = await self.async_set_max_sell_power_number_if_needed(target_sell_power)
            expected["Max Sell Power"] = applied_sell_power_native
            await self.async_set_number_if_needed(self.discharge_current_number, target_discharge_current)
            stage = "tryb pracy"
            await self.async_set_work_mode_if_needed(target_mode)
        except ControlDisabledError as err:
            self._clear_pending_control_transaction()
            if not self._control_transaction_is_stale(transaction_id):
                self.record_schedule_attempt(
                    "cancelled",
                    stage,
                    expected,
                    "Przerwano przez wyłączenie Sterowania Deye",
                )
                self.last_action = str(err)
                self.executed_manager_action = "Nie wykonano — sterowanie wyłączone"
                self.notify_update()
            return False
        except Exception as err:
            message = f"Nieudana transakcja sterująca ({stage}): {err}"
            if stage == "mapowanie Deye Time Of Use" and not self._last_tou_write_started:
                # The complete TOU map was rejected before the first physical
                # call.  Report it without starting a defaults transaction;
                # the inverter remains exactly as it was.
                self.record_schedule_attempt("failed", stage, expected, message)
                self.last_action = "Nie zastosowano mapowania Deye Time Of Use"
                self.last_error = message
                self.notify_update()
                return False
            if self.control_mode == "Schedule" and self.active_slot.enabled:
                return await self._async_handle_slot_failure(message, stage, expected)
            self.record_schedule_attempt("failed", stage, expected, message)
            await self.async_apply_safe_defaults(message)
            return False
        return bool(await self._async_confirm_or_wait_for_control(expected, stage, started=True, success_message=cap_message))

    async def async_apply_default_values(self, reason: str = "Defaults applied") -> None:
        async with self._control_operation("apply_default_values") as transaction_id:
            await self._async_apply_default_values_impl(reason, transaction_id)

    async def _async_apply_default_values_impl(
        self,
        reason: str = "Defaults applied",
        transaction_id: str | None = None,
    ) -> None:
        capped_sell_power_w = self.normalize_automatic_sell_power_w(self.default_sell_power)
        mode_input = (
            self.default_normal_physical_work_mode()
            if self.default_work_mode == MODE_NORMAL_OPERATION
            else self.default_work_mode
        )
        cap_message = ""
        if capped_sell_power_w < self.default_sell_power:
            cap_message = f"Moc sprzedaży domyślnej ograniczona z {self.default_sell_power} W do {capped_sell_power_w} W"
            _LOGGER.warning("%s (effective limit %s W)", cap_message, self.effective_inverter_max_power_w)
        self._validate_control_plan(
            self.default_work_mode,
            capped_sell_power_w,
            self.default_discharge_current,
            self.default_charge_current,
            self.default_grid_charge_current,
        )
        try:
            capped_sell_power_native = await self.async_set_max_sell_power_number(self.default_sell_power)
            await self.async_set_number(self.discharge_current_number, self.default_discharge_current)
            await self.async_set_number(self.charge_current_number, self.default_charge_current)
            await self.async_set_number(self.grid_charge_current_number, self.default_grid_charge_current)
            unconfirmed = await self.async_verify_control_values(
                None,
                capped_sell_power_native,
                self.default_discharge_current,
                self.default_charge_current,
                self.default_grid_charge_current,
            )
            if unconfirmed:
                raise RuntimeError(f"Niepotwierdzone ustawienia domyślne: {'; '.join(unconfirmed)}")
            await self.async_set_work_mode(mode_input)
            unconfirmed = await self.async_verify_control_values(
                self.default_work_mode,
                capped_sell_power_native,
                self.default_discharge_current,
                self.default_charge_current,
                self.default_grid_charge_current,
                self.default_normal_physical_work_mode(),
            )
            if unconfirmed:
                raise RuntimeError(f"Niepotwierdzone ustawienia końcowe: {'; '.join(unconfirmed)}")
        except ControlDisabledError:
            raise
        except Exception as err:
            await self.async_apply_safe_defaults(f"Błąd ręcznego przywracania ustawień: {err}")
            raise
        if not self._control_result_is_current(transaction_id):
            raise ControlDisabledError(self._control_block_message())
        self.last_action = reason
        if cap_message:
            self.last_action = f"{self.last_action}. {cap_message}"
        self.last_error = ""
        self.mark_settings_applied()
        self.notify_update()

    async def async_save_charge_profile(self, profile: dict[str, Any]) -> None:
        """Atomically save the user-owned profile used by Charge slots."""
        values = {
            "charge_profile_charge_current": self.safe_float(profile.get("charge_current"), float("nan")),
            "charge_profile_discharge_current": self.safe_float(profile.get("discharge_current"), float("nan")),
            "charge_profile_grid_charge_current": self.safe_float(profile.get("grid_charge_current"), float("nan")),
            "charge_profile_target_soc": self.safe_float(profile.get("target_soc"), float("nan")),
        }
        grid_enabled = profile.get("grid_charge_enabled")
        if not isinstance(grid_enabled, bool):
            raise ValueError("Grid Charge musi mieć wartość TAK albo NIE")
        profile_entities = {
            "charge_profile_charge_current": ("Maximum Battery Charge Current", self.charge_current_number),
            "charge_profile_discharge_current": ("Maximum Battery Discharge Current", self.discharge_current_number),
            "charge_profile_grid_charge_current": ("Maximum Battery Grid Charge Current", self.grid_charge_current_number),
            # Every Deye TOU SOC input has the same physical range. Validate
            # the profile before persisting it or starting a schedule write.
            "charge_profile_target_soc": ("Deye Time Of Use SOC", self._tou_entity(1, "soc")),
        }
        for key, value in values.items():
            self._validate_number_entity(*profile_entities[key], value)
        previous = {
            key: getattr(self, key)
            for key in values
        }
        previous_grid = self.charge_profile_grid_enabled
        previous_loaded = self._charge_profile_loaded_from_store
        previous_saved_at = self.last_saved_at
        for key, value in values.items():
            setattr(self, key, value)
        self.charge_profile_grid_enabled = grid_enabled
        self._charge_profile_loaded_from_store = True
        self.last_saved_at = ha_now().isoformat(timespec="seconds")
        try:
            # Await the durable write before reporting success to the card.
            # This avoids a close/reopen race with five independent helpers.
            await self.async_save_ai_data()
        except Exception:
            for key, value in previous.items():
                setattr(self, key, value)
            self.charge_profile_grid_enabled = previous_grid
            self._charge_profile_loaded_from_store = previous_loaded
            self.last_saved_at = previous_saved_at
            self.notify_update()
            raise
        self.last_error = ""
        self.last_action = "Zapisano szablon ustawień ładowania"
        self.notify_update()
        # This is a template for future transitions into Charge.  Existing
        # Charge slots, including manual overrides, are deliberately untouched.

    async def async_save_normal_profile(self, values: dict[str, Any]) -> None:
        """Atomically save the user-owned Normal Operation template.

        The template is copied once into a slot when Normalna Praca is
        selected.  Later changes to this template never overwrite existing
        slots.  No inverter entity is written here.
        """
        physical_mode = str(values.get("physical_work_mode") or "")
        if physical_mode not in PHYSICAL_NORMAL_MODES:
            raise ValueError(
                "Fizyczny tryb Deye musi być Zero Export To Load albo Zero Export To CT"
            )
        profile_entities = {
            "normal_profile_sell_power": ("sell_power", "Max Sell Power", self.max_sell_power_number),
            "normal_profile_discharge_current": ("discharge_current", "Maximum Battery Discharge Current", self.discharge_current_number),
            "normal_profile_charge_current": ("charge_current", "Maximum Battery Charge Current", self.charge_current_number),
            "normal_profile_grid_charge_current": ("grid_charge_current", "Maximum Battery Grid Charge Current", self.grid_charge_current_number),
            "normal_profile_tou_soc": ("tou_soc", "Deye Time Of Use SOC", self._tou_entity(1, "soc")),
        }
        numeric = {}
        for runtime_key, (input_key, label, entity_id) in profile_entities.items():
            if input_key in values:
                value = self.safe_float(values.get(input_key), float("nan"))
                self._validate_number_entity(label, entity_id, value)
                numeric[runtime_key] = value
        if "sell_power" in values and math.isfinite(numeric.get("normal_profile_sell_power", float("nan"))):
            self.validate_manual_sell_power_w(
                "Moc sprzedaży profilu normalnego",
                numeric["normal_profile_sell_power"],
            )
        raw_option = logical_mode_option(
            self.data,
            MODE_NORMAL_OPERATION,
            physical_mode,
        )
        self._validate_select_entity("System Work Mode", self.work_mode_select, raw_option)
        all_keys = ("normal_profile_physical_work_mode", *profile_entities)
        previous = {key: getattr(self, key) for key in all_keys}
        previous_loaded = self._normal_profile_loaded_from_store
        previous_saved_at = self.last_saved_at
        self.normal_profile_physical_work_mode = physical_mode
        for key, value in numeric.items():
            setattr(self, key, value)
        self._normal_profile_loaded_from_store = True
        self.last_saved_at = ha_now().isoformat(timespec="seconds")
        try:
            await self.async_save_ai_data()
        except Exception:
            self.normal_profile_physical_work_mode = previous["normal_profile_physical_work_mode"]
            for key in profile_entities:
                setattr(self, key, previous[key])
            self._normal_profile_loaded_from_store = previous_loaded
            self.last_saved_at = previous_saved_at
            self.notify_update()
            raise
        self.last_error = ""
        self.last_action = "Zapisano ustawienia normalnej pracy"
        self.notify_update()
        # This is a template for future Normalna Praca transitions.  Existing
        # Normalna Praca slots, including manual overrides, are untouched.

    async def async_save_default_settings(self, values: dict[str, Any]) -> None:
        """Save the user-owned recovery profile without writing to Deye now."""
        mode = str(values.get("mode") or "")
        if mode not in WORK_MODES:
            raise ValueError("Domyślny tryb falownika jest nieprawidłowy")
        physical_mode = str(
            values.get("physical_work_mode") or self.default_normal_physical_work_mode()
        )
        if physical_mode not in PHYSICAL_NORMAL_MODES:
            raise ValueError("Wariant Normalnej Pracy jest nieprawidłowy")
        raw_option = logical_mode_option(
            self.data,
            mode,
            physical_mode if mode == MODE_NORMAL_OPERATION else None,
        )
        fields = {
            "default_sell_power": self.safe_float(values.get("sell_power"), float("nan")),
            "default_discharge_current": self.safe_float(values.get("discharge_current"), float("nan")),
            "default_charge_current": self.safe_float(values.get("charge_current"), float("nan")),
            "default_grid_charge_current": self.safe_float(values.get("grid_charge_current"), float("nan")),
        }
        if math.isfinite(fields["default_sell_power"]):
            self.validate_manual_sell_power_w("Domyślna moc sprzedaży", fields["default_sell_power"])
        default_entities = {
            "default_sell_power": ("Max Sell Power", self.max_sell_power_number),
            "default_discharge_current": ("Maximum Battery Discharge Current", self.discharge_current_number),
            "default_charge_current": ("Maximum Battery Charge Current", self.charge_current_number),
            "default_grid_charge_current": ("Maximum Battery Grid Charge Current", self.grid_charge_current_number),
        }
        self._validate_select_entity("System Work Mode", self.work_mode_select, raw_option)
        for key, value in fields.items():
            self._validate_number_entity(*default_entities[key], value)
        previous = {
            "default_work_mode": self.default_work_mode,
            "default_physical_work_mode": self.default_physical_work_mode,
            **{key: getattr(self, key) for key in fields},
        }
        previous_saved_at = self.last_saved_at
        self.default_work_mode = mode
        self.default_physical_work_mode = physical_mode
        for key, value in fields.items():
            setattr(self, key, value)
        self.last_saved_at = ha_now().isoformat(timespec="seconds")
        try:
            await self.async_save_ai_data()
        except Exception:
            for key, value in previous.items():
                setattr(self, key, value)
            self.last_saved_at = previous_saved_at
            self.notify_update()
            raise
        self.last_error = ""
        self.last_action = "Zapisano ustawienia domyślne"
        self.notify_update()

    async def async_manual_sell(self) -> None:
        self.control_mode = "Manual Sell"
        await self.async_tick()

    async def async_charge_now(self) -> None:
        self.control_mode = "Charge Battery"
        await self.async_tick()

    async def async_stop_selling(self, reason: str = "Stopped") -> None:
        await self.async_apply_safe_defaults(reason)

    async def async_request_stop(self) -> None:
        async with self._operation_lock:
            self._clear_pending_control_transaction()
            self.control_mode = "Stop Sell"
            self.planned_manager_action = "Ustawienia domyślne"
            if not self._control_is_active():
                self.executed_manager_action = "Nie wykonano — sterowanie wyłączone"
                self.last_action = "Zatrzymano logicznie. Sterowanie Deye jest wyłączone."
                self.notify_update()
                return
            await self.async_apply_safe_defaults("Sprzedaż zatrzymana")

    async def async_restore_defaults(self) -> None:
        async with self._operation_lock:
            self._clear_pending_control_transaction()
            applied = await self.async_apply_safe_defaults(
                "Ręczne zastosowanie ustawień domyślnych"
            )
            if not applied:
                raise RuntimeError(
                    self.last_error
                    or "Nie udało się potwierdzić pełnego zestawu ustawień domyślnych"
                )
            self.emergency_stop = False
            self.control_mode = "Schedule"
            self.scheduler_enabled = False
            self._clear_slot_failure_latch()
            self.last_action = "Zastosowano ustawienia domyślne"
            self.last_error = ""
            self.mark_settings_applied()
            self.notify_update()

    async def async_resume_manager(self) -> None:
        """Consciously re-enable Schedule after Stop Sell or an emergency stop."""
        async with self._operation_lock:
            self._clear_pending_control_transaction()
            self.emergency_stop = False
            self.control_mode = "Schedule"
            self.scheduler_enabled = True
            self._clear_slot_failure_latch()
            if not self._control_is_active():
                self.last_action = (
                    "Włączono logicznie Manager i harmonogram. Sterowanie Deye jest wyłączone."
                )
                self.executed_manager_action = "Nie wykonano — sterowanie wyłączone"
                self.mark_config_saved()
                self.notify_update()
                return
            applied = await self._async_tick_impl()
            if not applied:
                raise RuntimeError(self.last_error or "Nie udało się zastosować bieżącego slotu harmonogramu")
            self.last_action = "Włączono Manager i harmonogram"
            self.last_error = ""
            self.mark_config_saved()
            self.notify_update()

    async def async_emergency_stop(self) -> None:
        # Set the flag before taking the lock so any in-flight async_apply_settings
        # waiting for confirmation sees the abort signal immediately.
        self.emergency_stop = True
        self.planned_manager_action = self._planned_manager_action_text()
        async with self._operation_lock:
            self._clear_pending_control_transaction()
            self.control_mode = "Stop Sell"
            if not self._control_is_active():
                self.executed_manager_action = "Nie wykonano — zatrzymanie awaryjne"
                self.last_action = (
                    "Zatrzymanie awaryjne ustawiono logicznie. Sterowanie Deye jest wyłączone."
                )
                self.notify_update()
                return
            await self.async_apply_safe_defaults("Zatrzymanie awaryjne")

    async def _async_tick_impl(self, *_args: Any) -> bool:
        if self._refresh_soc_quality_signature():
            self._optimizer_generation_reason = "material_live_input_changed:soc_freshness"
            self.request_optimizer_recalc("soc")
        await self.async_update_sold_energy_today()
        await self.async_update_solcast_history()
        await self.async_update_learning_history()
        await self.async_update_energy_sample()
        if not self.weather_last_updated or ha_now().minute == 0:
            await self.async_update_weather_forecast()

        # Polling is sufficient for Stage 5D: every normal Manager cycle reads
        # the complete physical 6/6 state before any cache-based skip or write.
        # No service call is made by this diagnostic comparison.
        self._refresh_tou_reconciliation_state()
        self.planned_manager_action = self._planned_manager_action_text()
        if not self._control_is_active():
            self.executed_manager_action = (
                "Nie wykonano — zatrzymanie awaryjne"
                if self.emergency_stop
                else "Nie wykonano — sterowanie wyłączone"
            )
            self.notify_update()
            return True

        profile = provider_profile(self.data)
        if not profile.basic_control:
            self.executed_manager_action = (
                "Nie wykonano — zatrzymanie awaryjne"
                if self.emergency_stop
                else f"Nie wykonano — provider {profile.label} działa tylko do odczytu"
            )
            self.notify_update()
            return True

        async with self._control_operation("manager_tick") as transaction_id:
            writes_before = self._physical_write_count
            self.executed_manager_action = (
                f"Oczekiwanie na potwierdzenie: {self.planned_manager_action}"
            )
            result = True
            if self.emergency_stop:
                result = await self.async_apply_safe_defaults("Zatrzymanie awaryjne")
            elif self.control_mode == "Schedule" and self.mapping_error:
                result = self._report_tou_preflight_failure()
            elif self.control_mode in ("Manual Sell", "Charge Battery"):
                result = await self.async_apply_targets()
            elif self.control_mode in ("Stop Sell", "Protect Battery"):
                result = await self.async_apply_safe_defaults(
                    "Sprzedaż zatrzymana" if self.control_mode == "Stop Sell" else "Aktywna ochrona baterii"
                )
            elif self.scheduler_enabled:
                if self.active_slot.enabled:
                    result = await self.async_apply_targets()
                else:
                    await self.async_apply_default_values("Ustawienia domyślne")

            if self._control_result_is_current(transaction_id):
                self.executed_manager_action = self._executed_manager_action_text(
                    result=result,
                    physical_writes=self._physical_write_count - writes_before,
                )

        # Action sensors must publish the completed cycle even when energy
        # totals did not change and every target was already in sync.
        self._notify_update_for("tick_final")
        return result

    async def async_tick(self, *_args: Any) -> None:
        if self._tariff_catalog_manager is not None and self._tariff_catalog_manager.refresh_due():
            await self._tariff_catalog_manager.async_refresh()
            self._notify_update_for("tariff")
        # Resolve any missing selling slot tou_soc values before any plan or
        # control action can trigger a physical TOU mapping/write.  The migration
        # is idempotent and retries every tick until every selling slot can be
        # safely resolved.
        self._migrate_selling_tou_soc()
        await self.async_process_future_plan()
        async with self._operation_lock:
            try:
                await self._async_tick_impl(*_args)
            except ControlDisabledError as err:
                self._clear_pending_control_transaction()
                self.last_action = str(err)
                self.executed_manager_action = "Nie wykonano — sterowanie wyłączone"
                self._notify_update_for("tick_control_disabled")
            except Exception as err:
                await self.async_apply_safe_defaults(f"Nieudana transakcja sterująca: {type(err).__name__}: {err}")
                raise
        if self.ai_api_config.get("enabled"):
            self.schedule_ai_api_analysis()

    @callback
    def _performance_lag_tick(self, *_args: Any) -> None:
        self._performance.record_lag_tick()

    @callback
    def _performance_report_tick(self, *_args: Any) -> None:
        self._performance.emit_report(self)

    def _start_performance_instrumentation(self) -> None:
        """Keep the Stage 5G.3C profiler dormant in production.

        The diagnostic implementation remains available for isolated tests, but
        normal runtime registers no one-second lag probe, no payload traversal
        and no periodic aggregate log task.
        """
        return

    def _stop_performance_instrumentation(self) -> None:
        """Detach the only two Stage 5G.3C timers and clear private counters."""
        if self.unsub_performance_lag is not None:
            self.unsub_performance_lag()
            self.unsub_performance_lag = None
        if self.unsub_performance_report is not None:
            self.unsub_performance_report()
            self.unsub_performance_report = None
        self._performance.stop()

    def _hass_is_running(self) -> bool:
        """Return a version-tolerant view of the HA Core running state."""
        state = getattr(self.hass, "state", None)
        value = getattr(state, "value", state)
        return str(value or "").strip().lower() == "running"

    def _cancel_hass_started_listener(self) -> None:
        unsubscribe = self._unsub_hass_started
        self._unsub_hass_started = None
        if unsubscribe is not None:
            unsubscribe()

    @callback
    def _mark_initial_optimizer_done(self, task: Any) -> None:
        if self._unloading:
            return
        cancelled = bool(getattr(task, "cancelled", lambda: False)())
        exception = None
        if not cancelled:
            try:
                exception = task.exception()
            except (asyncio.CancelledError, AttributeError):
                cancelled = True
        self._initial_optimizer_completed = not cancelled and exception is None
        if self._initial_optimizer_completed:
            self.runtime_metrics["optimizer_initial_completed"] += 1

    @callback
    def _start_initial_optimizer(self) -> Any:
        """Launch the one initial Core only after HA is fully running."""
        if self._unloading or self._initial_optimizer_started:
            return self._optimizer_recalc_task
        self._cancel_hass_started_listener()
        self._initial_optimizer_pending = False
        self._initial_optimizer_started = True
        self.runtime_metrics["optimizer_initial_requested"] += 1
        reasons = set(self._optimizer_pending_reasons) or {"startup"}
        task = self.request_optimizer_recalc(reasons)
        # The restored cache may be published now; before STARTED no expensive
        # AI/diagnostics snapshot task is created.
        self.request_sensor_snapshot_refresh(
            set(self._sensor_snapshot_requested_keys) or {"ai_state", "diagnostics"}
        )
        if task is not None and hasattr(task, "add_done_callback"):
            task.add_done_callback(self._mark_initial_optimizer_done)
        return task

    def _register_hass_started_listener(self) -> None:
        """Register, but never await, one HOMEASSISTANT_STARTED callback."""
        if self._unloading or self._initial_optimizer_started or self._unsub_hass_started:
            return
        bus = getattr(self.hass, "bus", None)
        listen_once = getattr(bus, "async_listen_once", None)
        if not callable(listen_once):
            return

        @callback
        def _on_hass_started(_event: Any) -> None:
            self._unsub_hass_started = None
            self._start_initial_optimizer()

        self._unsub_hass_started = listen_once(
            _HOMEASSISTANT_STARTED_EVENT,
            _on_hass_started,
        )

    async def async_start(self) -> None:
        self._startup_in_progress = True
        self._unloading = False
        self._initial_optimizer_pending = True
        self._initial_optimizer_started = False
        self._initial_optimizer_completed = False
        self._cancel_hass_started_listener()
        started = False
        try:
            self._tariff_catalog_manager = TariffCatalogManager(
                self.hass,
                self.entry_id,
                str(self.data.get(CONF_TARIFF_CATALOG_URL, DEFAULT_TARIFF_CATALOG_URL)),
            )
            await self._tariff_catalog_manager.async_load()
            await self.async_load_sales_stats()
            await self.async_load_ai_data()
            await self.async_load_solcast_history()
            await self.async_update_solcast_history()
            await self.async_load_learning_history()
            await self.async_load_energy_history()
            # Restore the minute-level learning checkpoint from the already
            # existing compact Energy Store before finalising/updating an hour.
            await self.async_update_learning_history()
            await self.async_update_energy_sample()
            await self.async_update_weather_forecast()
            self._soc_quality_signature = self._soc_semantic_signature(
                self.soc_diagnostics()
            )
            self._start_schedule_input_listener()
            self.unsub_timer = async_track_time_interval(
                self.hass, self.async_tick, timedelta(minutes=1)
            )
            if self._tariff_catalog_manager.refresh_due():
                self._tariff_refresh_task = self.hass.async_create_task(
                    self.async_refresh_tariff_catalog()
                )
            started = True
        finally:
            self._startup_in_progress = False
        if started:
            if self._ai_save_dirty:
                self.request_ai_save()
            if self._learning_save_dirty:
                self.request_learning_save()
            if self._energy_save_dirty:
                self.request_energy_save()
            self.request_optimizer_recalc("startup")
            self.request_sensor_snapshot_refresh()

    @callback
    def finish_platform_setup(self) -> None:
        """Release restore-time gates and publish one coherent initial state."""
        if not self._platform_setup_in_progress:
            return
        self._platform_setup_in_progress = False
        pending_reasons = set(self._optimizer_pending_reasons) or {"startup"}
        self._optimizer_recalc_pending = True
        self._optimizer_pending_reasons.update(pending_reasons)
        requested_keys = set(self._sensor_snapshot_requested_keys) or {"ai_state", "diagnostics"}
        self._sensor_snapshot_pending = True
        self._sensor_snapshot_requested_keys.update(requested_keys)
        if self._hass_is_running():
            self._start_initial_optimizer()
        else:
            self._register_hass_started_listener()
        if self._platform_publish_pending:
            self._platform_publish_pending = False
            self._notify_entities_from_cache(reason="startup")
        self._start_performance_instrumentation()

    async def async_unload(self) -> None:
        self._unloading = True
        self._stop_performance_instrumentation()
        self._cancel_hass_started_listener()
        self._initial_optimizer_pending = False
        self._platform_setup_in_progress = False
        self._platform_publish_pending = False
        if self._active_tou_cancel_event is not None:
            self._active_tou_cancel_event.set()
        for meta in self._active_control_transactions.values():
            meta["stale"] = True
        self._stop_tou_confirmation_listener()
        self.tou_write_pending = False
        self._clear_pending_control_transaction()
        if self._schedule_reconcile_task is not None and not self._schedule_reconcile_task.done():
            self._schedule_reconcile_task.cancel()
        self._schedule_reconcile_task = None
        self._schedule_reconcile_requested = False
        if self._ai_api_task is not None and not self._ai_api_task.done():
            self._ai_api_task.cancel()
        self._ai_api_task = None
        background_tasks = [
            task
            for task in (
                self._optimizer_recalc_task,
                self._sensor_snapshot_task,
                self._ai_save_task,
                self._learning_save_task,
                self._energy_save_task,
                self._tariff_refresh_task,
            )
            if task is not None and not task.done()
        ]
        for task in background_tasks:
            task.cancel()
        if self.unsub_input_listener:
            self.unsub_input_listener()
            self.unsub_input_listener = None
        if self.unsub_input_debounce:
            self.unsub_input_debounce()
            self.unsub_input_debounce = None
        if self.unsub_timer:
            self.unsub_timer()
            self.unsub_timer = None
        if background_tasks:
            await asyncio.gather(*background_tasks, return_exceptions=True)
        self._optimizer_recalc_task = None
        self._optimizer_recalc_pending = False
        self._optimizer_pending_reasons.clear()
        self._optimizer_debounce_reasons.clear()
        self._optimizer_listener_entity_ids = ()
        self._optimizer_input_reasons.clear()
        self._sensor_snapshot_task = None
        self._sensor_snapshot_pending = False
        self._sensor_snapshot_requested_keys.clear()
        self._ai_save_task = None
        self._learning_save_task = None
        self._energy_save_task = None
        self._tariff_refresh_task = None
        # A cancelled Store task may have cleared its dirty flag immediately
        # before awaiting I/O. Forced final calls are fingerprint/revision gated,
        # so they are cheap when nothing changed and lossless when it did.
        await self.async_save_ai_data(force=True)
        await self.async_save_learning_history(force=True)
        if self._energy_revision != self._energy_saved_revision:
            await self.async_save_energy_history(force=True)
        await self.async_save_sales_stats()
        await self.async_save_solcast_history()

    def set_control_mode(self, mode: str) -> None:
        if mode in CONTROL_MODES:
            previous_mode = self.control_mode
            self.control_mode = mode
            if previous_mode == "Schedule" and mode != "Schedule":
                current = ha_now()
                active_profile_ids = {
                    str(row.get("profile_id"))
                    for row in self.optimizer_plan.get("rows", [])
                    if isinstance(row, dict)
                    and row.get("profile_id")
                    and str(row.get("date") or "") == current.date().isoformat()
                    and int(self.safe_float(row.get("hour"), -1)) == current.hour
                }
                for profile_id in active_profile_ids:
                    self._set_profile_execution_status(
                        profile_id,
                        current.date().isoformat(),
                        "manual_override",
                        failure_reason=f"Ręczna zmiana trybu: {mode}",
                    )
            if previous_mode != mode:
                self.request_optimizer_recalc("manual")
            self.notify_update()

    def set_work_mode_for_slot(self, slot_key: str, mode: str) -> None:
        if mode in SLOT_MODES:
            slot = self.slots[slot_key]
            previous_mode = slot.mode
            slot.mode = mode
            if mode == MODE_NORMAL_OPERATION and previous_mode != MODE_NORMAL_OPERATION:
                slot.enabled = True
                self.scheduler_enabled = True
                # Copy the normal profile template once into this slot.
                # Later changes to the template do not affect existing slots.
                if self.normal_profile_physical_work_mode in PHYSICAL_NORMAL_MODES:
                    slot.physical_work_mode = self.normal_profile_physical_work_mode
                if math.isfinite(self.normal_profile_sell_power) and 0 <= self.normal_profile_sell_power <= self.effective_inverter_max_power_w:
                    slot.sell_power = self.normal_profile_sell_power
                if math.isfinite(self.normal_profile_discharge_current) and 0 <= self.normal_profile_discharge_current <= 240:
                    slot.discharge_current = self.normal_profile_discharge_current
                if math.isfinite(self.normal_profile_charge_current) and 0 <= self.normal_profile_charge_current <= 240:
                    slot.charge_current = self.normal_profile_charge_current
                if math.isfinite(self.normal_profile_grid_charge_current) and 0 <= self.normal_profile_grid_charge_current <= 240:
                    slot.grid_charge_current = self.normal_profile_grid_charge_current
                if self.normal_profile_tou_soc is not None and math.isfinite(self.normal_profile_tou_soc) and 0 <= self.normal_profile_tou_soc <= 100:
                    slot.tou_soc = self.normal_profile_tou_soc
            elif mode == MODE_CHARGE:
                slot.enabled = True
                self.scheduler_enabled = True
                if previous_mode != MODE_CHARGE:
                    slot.charge_current = self.charge_profile_charge_current
                    slot.discharge_current = self.charge_profile_discharge_current
                    slot.grid_charge_current = self.charge_profile_grid_charge_current
                    slot.tou_soc = self.charge_profile_target_soc
                    slot.charge_enabled = self.charge_profile_grid_enabled
            elif previous_mode == MODE_NORMAL_OPERATION:
                slot.physical_work_mode = None
            self._clear_slot_failure_latch()
            if previous_mode != mode:
                self.request_optimizer_recalc("schedule")
            self.notify_update()

    def set_default_work_mode(self, mode: str) -> None:
        normalized = normalize_manager_mode(mode)
        if normalized in WORK_MODES:
            previous_mode = self.default_work_mode
            self.default_work_mode = normalized
            if previous_mode != normalized:
                self.request_optimizer_recalc("schedule")
            self.notify_update()
