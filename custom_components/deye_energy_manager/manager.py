from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
import math
from typing import Any

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
    CONF_WEATHER_ENTITY,
    CONF_PRICE_SOURCE,
    CONF_OSD_PROVIDER,
    CONF_TARIFF_PLAN,
    CONF_DISTRIBUTION_PEAK_RATE,
    CONF_DISTRIBUTION_OFFPEAK_RATE,
    CONF_CUSTOM_OFFPEAK_WINDOWS,
    CONF_TARIFF_MODE,
    CONF_PRICE_INCLUDES_DISTRIBUTION,
    CONF_TARIFF_CATALOG_URL,
    CONTROL_MODES,
    DOMAIN,
    MODE_SELLING_FIRST,
    MODE_CHARGE,
    MODE_NORMAL_OPERATION,
    MODE_ZERO_EXPORT,
    MODE_ZERO_EXPORT_CT,
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
    DEFAULT_BUY_PRICE_TODAY_SENSOR,
    DEFAULT_BUY_PRICE_TOMORROW_SENSOR,
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
    DEFAULT_SELL_PRICE_TOMORROW_SENSOR,
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
    DEFAULT_PRICE_SOURCE,
    DEFAULT_OSD_PROVIDER,
    DEFAULT_TARIFF_PLAN,
    DEFAULT_DISTRIBUTION_PEAK_RATE,
    DEFAULT_DISTRIBUTION_OFFPEAK_RATE,
    DEFAULT_CUSTOM_OFFPEAK_WINDOWS,
    DEFAULT_TARIFF_MODE,
    DEFAULT_PRICE_INCLUDES_DISTRIBUTION,
    DEFAULT_TARIFF_CATALOG_URL,
    DEFAULT_GRID_POSITIVE_IS_IMPORT,
    DEFAULT_BATTERY_POSITIVE_IS_DISCHARGE,
    DEFAULT_MAX_SELL_POWER,
    DEFAULT_DISCHARGE_CURRENT,
    DEFAULT_CHARGE_CURRENT,
    DEFAULT_GRID_CHARGE_CURRENT,
    DEFAULT_WORK_MODE_SELECT,
)
from .tariff_catalog import TariffCatalogManager
from .ai_planner import (
    ALGORITHM_VERSION,
    PLAN_SCHEMA_VERSION,
    build_plan_bundle,
    snapshot_id,
)
from .ai_assistant import (
    build_private_payload,
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
    HISTORY_SCHEMA_VERSION,
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
    PROVIDER_LABELS,
    TARIFF_LABELS,
    available_tariffs,
    catalog_hourly_profile,
    get_tariff,
    hourly_tariff_profile,
    parse_windows,
    tariff_availability,
    tariff_zone,
)


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
    # Business-only threshold for Selling First. It is never written to a
    # physical Deye Time Of Use SOC field.
    minimum_sell_soc: float = 0
    # Physical Deye Time Of Use SOC for this logical slot.  It is deliberately
    # unknown until restored from the user's prior configuration or explicitly
    # confirmed by the user.  It must never be inferred from minimum_sell_soc
    # or silently replaced by zero before a physical TOU write.
    tou_soc: float | None = None
    min_sell_price: float = 0


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
    default_work_mode: str = MODE_ZERO_EXPORT
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
    _samples_store: Store | None = None
    _tariff_catalog_manager: TariffCatalogManager | None = None
    _stats_dirty: bool = False
    sales_stats: dict[str, Any] = field(default_factory=dict)
    ai_settings: dict[str, Any] = field(default_factory=dict)
    ai_history: list[dict[str, Any]] = field(default_factory=list)
    optimizer_plan: dict[str, Any] = field(default_factory=dict)
    optimizer_plan_history: list[dict[str, Any]] = field(default_factory=list)
    plan_execution_archive: list[dict[str, Any]] = field(default_factory=list)
    _optimizer_input_snapshot_id: str = ""
    _optimizer_generation_reason: str = "startup"
    ai_api_config: dict[str, Any] = field(default_factory=dict)
    ai_api_status: dict[str, Any] = field(default_factory=lambda: {"status": "disabled"})
    ai_api_cache: dict[str, Any] = field(default_factory=dict)
    _ai_api_last_call: datetime | None = None
    _ai_api_task: Any = None
    future_plan: dict[str, Any] = field(default_factory=dict)
    solcast_history: list[dict[str, Any]] = field(default_factory=list)
    solcast_tracking: dict[str, Any] = field(default_factory=dict)
    learning_history: list[dict[str, Any]] = field(default_factory=list)
    learning_tracking: dict[str, Any] = field(default_factory=dict)
    energy_samples: list[dict[str, Any]] = field(default_factory=list)
    daily_archive: list[dict[str, Any]] = field(default_factory=list)
    monthly_archive: list[dict[str, Any]] = field(default_factory=list)
    energy_counter_state: dict[str, dict[str, Any]] = field(default_factory=dict)
    user_profiles: dict[str, Any] = field(default_factory=default_user_profiles)
    data_quality: dict[str, Any] = field(default_factory=dict)
    load_profile_7x24: dict[str, Any] = field(default_factory=dict)
    pv_learning_profile: dict[str, Any] = field(default_factory=dict)
    profile_execution: list[dict[str, Any]] = field(default_factory=list)
    weather_forecast: list[dict[str, Any]] = field(default_factory=list)
    weather_daily_forecast: list[dict[str, Any]] = field(default_factory=list)
    weather_last_updated: str = ""
    weather_last_error: str = ""
    _last_energy_sample_at: datetime | None = None
    slots: dict[str, SlotSettings] = field(default_factory=dict)
    last_action: str = "Idle"
    last_applied_at: str = ""
    last_saved_at: str = ""
    last_error: str = ""
    last_schedule_attempt: dict[str, Any] = field(default_factory=dict)
    control_confirmation_timeout: float = 12.0
    _pending_control_transaction: dict[str, Any] = field(default_factory=dict)
    unsub_confirmation_timer: Any = None
    unsub_confirmation_listener: Any = None
    unsub_confirmation_poll: Any = None
    unsub_input_listener: Any = None
    unsub_input_debounce: Any = None
    unsub_timer: Any = None
    entities: list[Any] = field(default_factory=list)
    _last_tou_signature: str = ""
    # Tracks whether the latest TOU operation crossed the preflight boundary
    # and issued at least one physical Deye service call.  Validation failures
    # must not trigger a second transaction that restores defaults.
    _last_tou_write_started: bool = False
    _last_slot_failure_signature: str = ""
    _last_sell_block_signature: str = ""
    _operation_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

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

    async def async_restore_slot_mode(self, slot_key: str, restored_mode: str) -> None:
        """Restore and idempotently migrate one legacy slot entity state."""
        slot = self.slots[slot_key]
        stored_physical = slot.physical_work_mode
        logical, physical, migrated = self.normalize_schedule_mode(restored_mode, stored_physical)
        slot.mode = logical
        slot.physical_work_mode = physical
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
    def work_mode_select(self) -> str:
        return self.data[CONF_WORK_MODE_SELECT]

    @property
    def max_sell_power_number(self) -> str:
        return self.data[CONF_MAX_SELL_POWER_NUMBER]

    @property
    def discharge_current_number(self) -> str:
        return self.data[CONF_DISCHARGE_CURRENT_NUMBER]

    @property
    def charge_current_number(self) -> str | None:
        return self.data.get(CONF_CHARGE_CURRENT_NUMBER)

    @property
    def grid_charge_current_number(self) -> str | None:
        return self.data.get(CONF_GRID_CHARGE_CURRENT_NUMBER, DEFAULT_GRID_CHARGE_CURRENT)

    @property
    def grid_power_sensor(self) -> str | None:
        configured = self.data.get(CONF_GRID_POWER_SENSOR)
        if configured and self.hass.states.get(configured) is not None:
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
        if self.hass.states.get(DEFAULT_BATTERY_SOC) is not None:
            return DEFAULT_BATTERY_SOC
        return configured

    def configured_sensor(self, key: str, default_entity: str) -> str | None:
        configured = self.data.get(key)
        if configured and self.hass.states.get(configured) is not None:
            return configured
        if self.hass.states.get(default_entity) is not None:
            return default_entity
        return configured or default_entity

    @property
    def price_sensor(self) -> str | None:
        configured = self.data.get(CONF_PRICE_SENSOR)
        if configured and self.hass.states.get(configured) is not None:
            return configured
        if self.hass.states.get(DEFAULT_PRICE_SENSOR) is not None:
            return DEFAULT_PRICE_SENSOR
        return configured

    @property
    def sell_price_tomorrow_sensor(self) -> str | None:
        configured = self.data.get(CONF_SELL_PRICE_TOMORROW_SENSOR)
        if configured and self.hass.states.get(configured) is not None:
            return configured
        if self.hass.states.get(DEFAULT_SELL_PRICE_TOMORROW_SENSOR) is not None:
            return DEFAULT_SELL_PRICE_TOMORROW_SENSOR
        return configured

    @property
    def buy_price_today_sensor(self) -> str | None:
        configured = self.data.get(CONF_BUY_PRICE_TODAY_SENSOR)
        if configured and self.hass.states.get(configured) is not None:
            return configured
        if self.hass.states.get(DEFAULT_BUY_PRICE_TODAY_SENSOR) is not None:
            return DEFAULT_BUY_PRICE_TODAY_SENSOR
        return configured

    @property
    def buy_price_tomorrow_sensor(self) -> str | None:
        configured = self.data.get(CONF_BUY_PRICE_TOMORROW_SENSOR)
        if configured and self.hass.states.get(configured) is not None:
            return configured
        if self.hass.states.get(DEFAULT_BUY_PRICE_TOMORROW_SENSOR) is not None:
            return DEFAULT_BUY_PRICE_TOMORROW_SENSOR
        return configured

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
    def price_source(self) -> str:
        return str(self.data.get(CONF_PRICE_SOURCE, DEFAULT_PRICE_SOURCE)).lower()

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
        from .tariffs import load_bundled_catalog

        return load_bundled_catalog()

    def normalized_grid_power(self) -> float:
        value = self.state_float(self.grid_power_sensor, 0)
        return value if bool(self.data.get(CONF_GRID_POSITIVE_IS_IMPORT, DEFAULT_GRID_POSITIVE_IS_IMPORT)) else -value

    def normalized_battery_power(self) -> float:
        value = self.state_float(self.battery_power_sensor, 0)
        return value if bool(self.data.get(CONF_BATTERY_POSITIVE_IS_DISCHARGE, DEFAULT_BATTERY_POSITIVE_IS_DISCHARGE)) else -value

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
        context = {
            "provider": self.osd_provider,
            "provider_name": PROVIDER_LABELS.get(self.osd_provider, self.osd_provider),
            "plan": self.tariff_plan,
            "plan_name": str(tariff.get("name")) if tariff else TARIFF_LABELS.get(self.tariff_plan, self.tariff_plan.upper()),
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
            "price_source": self.price_source,
            "price_includes_distribution": self.price_includes_distribution,
            "grid_positive_is_import": bool(self.data.get(CONF_GRID_POSITIVE_IS_IMPORT, DEFAULT_GRID_POSITIVE_IS_IMPORT)),
            "battery_positive_is_discharge": bool(self.data.get(CONF_BATTERY_POSITIVE_IS_DISCHARGE, DEFAULT_BATTERY_POSITIVE_IS_DISCHARGE)),
            "providers": providers,
            "tariffs": available_tariffs(catalog, self.osd_provider),
            "hourly_profile": profile,
        }
        if self._tariff_catalog_manager is not None:
            context.update(self._tariff_catalog_manager.status())
        return context

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
        price_source = str(settings.get(CONF_PRICE_SOURCE, self.price_source)).lower()
        if price_source not in ("pstryk", "pse_rce", "other", "none"):
            raise ValueError("Nieznane źródło cen energii")
        peak = self.safe_float(settings.get(CONF_DISTRIBUTION_PEAK_RATE), self.distribution_peak_rate)
        offpeak = self.safe_float(settings.get(CONF_DISTRIBUTION_OFFPEAK_RATE), self.distribution_offpeak_rate)
        if not 0 <= peak <= 10 or not 0 <= offpeak <= 10:
            raise ValueError("Stawka dystrybucyjna musi mieścić się w zakresie 0–10 PLN/kWh")
        windows = str(settings.get(CONF_CUSTOM_OFFPEAK_WINDOWS, self.custom_offpeak_windows)).strip()
        if mode == "manual" and not parse_windows(windows):
            raise ValueError("Profil ręczny wymaga poprawnych przedziałów godzin")
        return {
            CONF_TARIFF_MODE: mode,
            CONF_OSD_PROVIDER: provider,
            CONF_TARIFF_PLAN: plan,
            CONF_DISTRIBUTION_PEAK_RATE: round(peak, 5),
            CONF_DISTRIBUTION_OFFPEAK_RATE: round(offpeak, 5),
            CONF_CUSTOM_OFFPEAK_WINDOWS: windows,
            CONF_PRICE_SOURCE: price_source,
            CONF_PRICE_INCLUDES_DISTRIBUTION: bool(settings.get(CONF_PRICE_INCLUDES_DISTRIBUTION, self.price_includes_distribution)),
            CONF_GRID_POSITIVE_IS_IMPORT: bool(settings.get(CONF_GRID_POSITIVE_IS_IMPORT, self.data.get(CONF_GRID_POSITIVE_IS_IMPORT, DEFAULT_GRID_POSITIVE_IS_IMPORT))),
            CONF_BATTERY_POSITIVE_IS_DISCHARGE: bool(settings.get(CONF_BATTERY_POSITIVE_IS_DISCHARGE, self.data.get(CONF_BATTERY_POSITIVE_IS_DISCHARGE, DEFAULT_BATTERY_POSITIVE_IS_DISCHARGE))),
        }

    async def async_update_tariff_settings(self, settings: dict[str, Any]) -> dict[str, Any]:
        normalized = self.validate_tariff_settings(settings)
        previous = self.tariff_context()
        self.data.update(normalized)
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
        self.notify_update()
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

    @staticmethod
    def _hour_from_value(value: Any, fallback: int | None = None) -> int | None:
        if isinstance(value, (int, float)) and 0 <= int(value) <= 23:
            return int(value)
        text = str(value or "")
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return parsed.hour
        except (TypeError, ValueError):
            pass
        import re

        match = re.search(r"(?:^|\D)(\d{1,2})(?::\d{2})?", text)
        if match and 0 <= int(match.group(1)) <= 23:
            return int(match.group(1))
        return fallback if fallback is not None and 0 <= fallback <= 23 else None

    def price_map(self, entity_id: str | None, allow_state_fallback: bool = True) -> dict[int, float]:
        """Read common hourly-price attribute layouts used by Polish integrations."""
        state = self.hass.states.get(entity_id) if entity_id else None
        if state is None:
            return {}
        result: dict[int, float] = {}

        def add(item: Any, fallback: int | None = None) -> None:
            hour: int | None = fallback
            value: float | None = None
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                hour = self._hour_from_value(item[0], fallback)
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
                        hour = self._hour_from_value(item[key], fallback)
                        break
                value = self._price_from_object(item)
            else:
                try:
                    value = float(item)
                except (TypeError, ValueError):
                    value = None
            if hour is not None and value is not None and math.isfinite(value):
                result.setdefault(hour, value)

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
        if not result:
            value = self.state_float_or_none(entity_id)
            if value is not None and math.isfinite(value):
                result[ha_now().hour] = value
        return result

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
        power = effective_power_limit(
            plan_limit_w=self.safe_float(settings.get("maxSellPower"), 5000),
            export_limit_w=finite_float(settings.get("exportLimitW")),
            inverter_limit_w=finite_float(settings.get("inverterPowerW")),
            current_limit_a=self.safe_float(settings.get("maxBatteryCurrentA"), self.manual_discharge_current or 120),
            battery_voltage_v=voltage,
            entity_limit_w=self.state_float_or_none(self.max_sell_power_number),
        )
        return {
            "capacity_kwh": capacity,
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

    def ai_plan_48h(self) -> dict[str, Any]:
        """Build the read-only AI proposal payload exposed to the Lovelace card."""
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
            if self.price_includes_distribution
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
        today_forecast = self.solcast_forecast_today_value()
        today_actual = max(0, self.state_float(self.daily_pv_production_sensor, 0))
        remaining = max(0, self.state_float(self.solcast_remaining_today_sensor, 0))
        if remaining <= 0:
            remaining = max(0, today_forecast - today_actual)
        selected_strategy = str(settings.get("strategy") or "balanced")
        if selected_strategy == "autoconsumption":
            selected_strategy = "safe"
        current = ha_now()
        load_forecasts = [
            forecast_load(self.load_profile_7x24, current.replace(minute=0, second=0, microsecond=0) + timedelta(hours=index))
            for index in range(48)
        ]
        live_state = self.live_state_context()
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
                if (value := self.state_float_or_none(self.battery_soc_sensor)) is not None
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
            "max_sell_power_w": self.safe_float(settings.get("maxSellPower"), 5000),
            "effective_power_limit_w": battery_model["power_limit"]["effective_limit_w"],
            "current_hour_remaining_minutes": battery_model["current_hour_remaining_minutes"],
            "charge_kwh_per_hour": max(0.25, self.safe_float(settings.get("batteryCapacityKwh"), 10) * 0.25),
            "min_sell_price": self.safe_float(settings.get("minSellPrice"), 0),
            "max_buy_price": self.safe_float(settings.get("maxBuyPrice"), 999),
            "allow_battery_sell": bool(settings.get("allowBatterySell", True)),
            "allow_grid_charge": bool(settings.get("allowGridCharge", True)),
            "sell_prices": [self.price_map(self.price_sensor), self.price_map(self.sell_price_tomorrow_sensor, False)],
            "buy_prices": [self.price_map(self.buy_price_today_sensor), self.price_map(self.buy_price_tomorrow_sensor, False)],
            "distribution": distribution,
            "price_includes_distribution": self.price_includes_distribution,
            "osd_data_complete": osd_data_complete,
            "osd_available_hours": osd_available_hours,
            "tariff_context": {
                key: tariff.get(key)
                for key in (
                    "provider", "provider_name", "plan", "plan_name", "mode",
                    "configured", "tariff_error", "price_source",
                    "price_includes_distribution", "hourly_profile",
                )
            },
            "buy_price_source": self.buy_price_today_sensor,
            "pv_forecast": [remaining, max(0, self.state_float(self.solcast_forecast_tomorrow_sensor, 0))],
            "pv_forecast_full": [today_forecast, max(0, self.state_float(self.solcast_forecast_tomorrow_sensor, 0))],
            "pv_forecast_available": [
                self.entity_available(self.solcast_forecast_today_sensor),
                self.entity_available(self.solcast_forecast_tomorrow_sensor),
            ],
            "forecast_correction": self.safe_float(learning.get("solcast_correction_factor"), 1),
            "forecast_accuracy": learning.get("solcast_accuracy_avg"),
            "pv_profile": [self.safe_float(by_hour.get(hour, {}).get("pv_kwh"), 0) for hour in range(24)],
            "load_profile": [self.safe_float(by_hour.get(hour, {}).get("load_kwh"), 0) for hour in range(24)],
            "load_profile_48h": [value for value, _source, _samples in load_forecasts],
            "load_profile_sources_48h": [
                {"source": source, "samples": samples}
                for _value, source, samples in load_forecasts
            ],
            "weather_factors": self._weather_factors_48h(),
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
            "user_profiles": self.user_profiles,
            "profile_execution": self.profile_execution,
            "data_quality": source_quality,
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
        }
        current_snapshot_id = snapshot_id(payload)
        if (
            self.optimizer_plan
            and current_snapshot_id == self._optimizer_input_snapshot_id
            and self.optimizer_plan.get("algorithm_version") == ALGORITHM_VERSION
            and self.optimizer_plan.get("plan_schema_version") == PLAN_SCHEMA_VERSION
        ):
            result = deepcopy(self.optimizer_plan)
        else:
            result = build_plan_bundle(payload, selected_strategy)
            previous = deepcopy(self.optimizer_plan) if self.optimizer_plan else None
            if previous:
                previous["superseded_by_plan_id"] = result.get("plan_id")
                self.optimizer_plan_history = [previous, *self.optimizer_plan_history][:30]
            self.optimizer_plan = deepcopy(result)
            self._sync_profile_execution_from_plan(result, current)
            self._optimizer_input_snapshot_id = current_snapshot_id
            self._optimizer_generation_reason = "cached_until_input_change"
            if self._ai_store is not None:
                self.hass.async_create_task(self.async_save_ai_data())
            if self._learning_store is not None:
                self.hass.async_create_task(self.async_save_learning_history())
        archive_changed = self._sync_plan_execution_archive(result, current)
        if archive_changed and self._ai_store is not None:
            self.hass.async_create_task(self.async_save_ai_data())
        forecast_hours = [
            {
                "timestamp": f"{row.get('date')}T{int(row.get('hour', 0)):02d}:00:00{current.strftime('%z')[:3]}:{current.strftime('%z')[3:]}",
                "soc_end_pct": row.get("soc_end_pct", row.get("soc_after")),
            }
            for row in result.get("rows", [])
            if isinstance(row, dict)
        ]
        result["battery_model"] = battery_model
        result["profile_execution"] = deepcopy(self.profile_execution)
        result["soc_timeline"] = build_soc_timeline(
            now=current,
            historical_hours=self.learning_history,
            current_soc_pct=self.state_float_or_none(self.battery_soc_sensor),
            forecast_hours=forecast_hours,
        )
        return result

    def register_entity(self, entity: Any) -> None:
        self.entities.append(entity)

    @callback
    def notify_update(self) -> None:
        for entity in list(self.entities):
            if getattr(entity, "hass", None) is not None:
                entity.async_write_ha_state()

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
        value = (
            power_w(state.state, unit)
            if state is not None and kind == "power"
            else energy_kwh(state.state, unit)
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
            "unit": unit or None,
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

    def source_quality_context(self) -> dict[str, Any]:
        """Return the exact source/fallback status consumed by learning."""
        load = self.load_power_reading()
        battery = self.battery_power_reading()
        sources = {
            "load_power": load,
            "battery_power": battery,
            "pv_power": self._measurement(self.pv_power_sensor),
            "grid_power": self._measurement(self.grid_power_sensor),
            "battery_soc": self._measurement(self.battery_soc_sensor, kind="raw"),
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
        grid = self._measurement(self.grid_power_sensor)
        if grid.get("value") is not None:
            grid = dict(grid)
            grid["value"] = (
                float(grid["value"])
                if bool(self.data.get(CONF_GRID_POSITIVE_IS_IMPORT, DEFAULT_GRID_POSITIVE_IS_IMPORT))
                else -float(grid["value"])
            )
        return {
            "pv": self._measurement(self.pv_power_sensor),
            "load": load,
            "load_l1": self._measurement(self.load_l1_power_sensor),
            "load_l2": self._measurement(self.load_l2_power_sensor),
            "load_l3": self._measurement(self.load_l3_power_sensor),
            "grid": grid,
            "battery": battery,
            "soc": self._measurement(self.battery_soc_sensor, kind="raw"),
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
        required = [
            self.work_mode_select,
            self.max_sell_power_number,
            self.discharge_current_number,
            self.charge_current_number,
            self.grid_charge_current_number,
        ]
        return all(self.entity_available(entity_id) for entity_id in required)

    @property
    def required_entities_complete(self) -> bool:
        """Check that all entities required for full integration mapping are available.

        Unlike ``data_available`` this includes the battery SOC sensor, which is
        mandatory for complete operation and safe Selling First guards even
        though Zero Export slots can execute without it.
        """
        required = [
            self.work_mode_select,
            self.max_sell_power_number,
            self.discharge_current_number,
            self.charge_current_number,
            self.grid_charge_current_number,
            self.battery_soc_sensor,
        ]
        return all(self.entity_available(entity_id) for entity_id in required)

    @property
    def mapping_error(self) -> bool:
        return len(self._compress_schedule_segments()) > 6

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
        if status == "MAPPING ERROR":
            return f"Mapowanie wymaga {len(self._compress_schedule_segments())} zakresów; Deye obsługuje 6"
        if status == "NO DATA":
            return "Brak wymaganych danych lub encji sterujących falownikiem"
        if status == "SELL BLOCKED":
            issue = self._selling_slot_guard_issue()
            return issue[1] if issue else "Sprzedaż wstrzymana przez warunek aktywnego slotu"
        if status == "PRICE TOO LOW":
            price = self.state_float(self.price_sensor, 0)
            return f"Cena {price:.2f} PLN/kWh jest niższa od progu {self.active_min_sell_price:.2f} PLN/kWh"
        if status == "SOC TOO LOW":
            soc = self.state_float(self.battery_soc_sensor, 0)
            return f"SOC {soc:.0f}% jest niższy od limitu {self.active_min_sell_soc:.0f}%"
        reasons = {
            "SLOT DISABLED": "Bieżący slot jest wyłączony; obowiązują ustawienia domyślne",
            "SCHEDULER OFF": "Harmonogram jest wyłączony; manager oczekuje",
            "STOPPED": "Sterowanie zatrzymane; obowiązują ustawienia domyślne",
            "EMERGENCY STOP": "Aktywne zatrzymanie awaryjne",
            "PROTECT BATTERY": "Aktywna ochrona baterii",
            "MANUAL SELL": "Aktywny ręczny tryb sprzedaży",
            "CHARGE BATTERY": "Aktywne ręczne ładowanie baterii",
            "GRID CHARGE ACTIVE": "Ładowanie z sieci według harmonogramu",
            "PV CHARGE ACTIVE": "Ładowanie z PV według harmonogramu",
            "SELLING ACTIVE": "Warunki sprzedaży są spełnione",
            "ZERO EXPORT CT ACTIVE": "Aktywny tryb Normalna Praca — Deye: Zero Export To CT",
            "ZERO EXPORT LOAD ACTIVE": "Aktywny tryb Normalna Praca — Deye: Zero Export To Load",
            "WAITING": "Manager oczekuje na zmianę warunków lub kolejny slot",
        }
        return reasons.get(status, status)

    def mark_settings_applied(self) -> None:
        self.last_applied_at = ha_now().isoformat(timespec="seconds")

    def mark_config_saved(self) -> None:
        self.last_saved_at = ha_now().isoformat(timespec="seconds")
        if self._ai_store is not None:
            self.hass.async_create_task(self.async_save_ai_data())
        self.notify_update()

    def _tou_entities(self) -> list[tuple[str, str]]:
        entities = [("Deye Time Of Use", "switch.deye_inverter_time_of_use")]
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
        return {"ok": not missing, "missing": missing, "entities": entities}

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
        segments = self._compress_schedule_segments()
        current_hour = ha_now().hour
        rows: list[dict[str, Any]] = []
        for idx in range(1, 7):
            segment = segments[idx - 1] if idx <= len(segments) else None
            expected_start = (
                f"{int(segment['start']):02d}:00" if segment is not None else None
            )
            expected_end = None
            active = False
            if segment is not None:
                end_hour = 24 if int(segment["end"]) == 0 else int(segment["end"])
                expected_end = f"{end_hour % 24:02d}:00"
                active = int(segment["start"]) <= current_hour < end_hour
            rows.append({
                "range": idx,
                "active": active,
                "expected_start": expected_start,
                "expected_end": expected_end,
                "expected_soc": segment.get("tou_soc") if segment is not None else None,
                "actual_start": self.state_text(self._tou_entity(idx, "start")),
                "actual_soc": self.state_text(self._tou_entity(idx, "soc")),
                "expected_grid_charge": bool(segment and segment.get("grid_charge")),
                "actual_grid_charge": self.state_text(self._tou_entity(idx, "grid")),
            })
        return rows

    def active_slot_control_diagnostics(self) -> dict[str, Any]:
        """Keep logical sale guards separate from physical TOU/control values."""
        slot = self.active_slot
        charge_slot = bool(slot.enabled and slot.mode == MODE_CHARGE)
        effective_soc = slot.tou_soc
        physical_tou = self.physical_tou_snapshot()
        active_range = next((row for row in physical_tou if row["active"]), None)
        expected_grid_current = (
            slot.grid_charge_current
            if charge_slot
            else self.default_grid_charge_current
        )
        return {
            "slot": slot.key,
            "mode": slot.mode if slot.enabled else "Wyłączony",
            "minimum_sell_soc": slot.minimum_sell_soc,
            "tou_soc": slot.tou_soc,
            "charge_profile_target_soc": self.charge_profile_target_soc,
            "effective_tou_soc": effective_soc,
            "physical_range": active_range.get("range") if active_range else None,
            "physical_soc_actual": active_range.get("actual_soc") if active_range else "brak",
            "grid_charge_expected": bool(charge_slot and slot.charge_enabled),
            "grid_charge_actual": active_range.get("actual_grid_charge") if active_range else "brak",
            "currents": {
                "charge_expected": self.target_charge_current,
                "charge_actual": self.state_text(self.charge_current_number),
                "discharge_expected": self.target_discharge_current,
                "discharge_actual": self.state_text(self.discharge_current_number),
                "grid_charge_expected": expected_grid_current,
                "grid_charge_actual": self.state_text(self.grid_charge_current_number),
            },
        }

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
        mapping_status = "ERROR" if self.mapping_error else ("TOU ERROR" if not tou["ok"] else "OK")
        return {"integration_version": "0.7.9", "connected": self.data_available, "required_entities_complete": self.required_entities_complete, "entities": entities,
                "last_saved_at": self.last_saved_at or "never", "last_applied_at": self.last_applied_at or "never",
                "last_error": self.last_error or "none", "last_schedule_attempt": self.last_schedule_attempt,
                "manager_status": self.manager_status, "mapping_status": mapping_status,
                "mapping_segments": len(self._compress_schedule_segments()), "tou": tou,
                "physical_tou": self.physical_tou_snapshot(),
                "active_slot_control": self.active_slot_control_diagnostics(),
                "soc_semantics": {
                    "minimum_sell_soc": "warunek Selling First; nie jest zapisywany do Deye TOU",
                    "tou_soc": "fizyczny SOC Deye TOU dla slotów niebędących Charge",
                    "charge_profile_target_soc": "fizyczny SOC Deye TOU dla wszystkich slotów Charge",
                },
                "charge_profile": {
                    "grid_charge_enabled": self.charge_profile_grid_enabled,
                    "charge_current": self.charge_profile_charge_current,
                    "discharge_current": self.charge_profile_discharge_current,
                    "grid_charge_current": self.charge_profile_grid_charge_current,
                    "target_soc": self.charge_profile_target_soc,
                },
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
        self.user_profiles = data.get("user_profiles") if isinstance(data.get("user_profiles"), dict) else default_user_profiles()
        optimizer_plan = data.get("optimizer_plan")
        optimizer_history = data.get("optimizer_plan_history")
        self.optimizer_plan = optimizer_plan if isinstance(optimizer_plan, dict) else {}
        self.optimizer_plan_history = optimizer_history[:30] if isinstance(optimizer_history, list) else []
        plan_execution_archive = data.get("plan_execution_archive")
        self.plan_execution_archive = (
            plan_execution_archive[:2160]
            if isinstance(plan_execution_archive, list)
            else []
        )
        self._optimizer_input_snapshot_id = str(data.get("optimizer_input_snapshot_id") or "")
        self._optimizer_generation_reason = "startup_or_restored_state"
        future_plan = data.get("future_plan")
        self.future_plan = future_plan if isinstance(future_plan, dict) else {}
        self.last_saved_at = str(data.get("last_saved_at") or "")
        self.schedule_schema_version = max(0, int(self.safe_float(data.get("schedule_schema_version"), 0)))

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
                and 0 <= numeric["normal_profile_sell_power"] <= 13000
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

    async def async_save_ai_data(self) -> None:
        if self._ai_store is None:
            return
        await self._ai_store.async_save({
            "schema_version": HISTORY_SCHEMA_VERSION,
            "settings": self.ai_settings,
            "history": self.ai_history[:365],
            "user_profiles": self.user_profiles,
            "optimizer_plan": self.optimizer_plan,
            "optimizer_plan_history": self.optimizer_plan_history[:30],
            "plan_execution_archive": self.plan_execution_archive[:2160],
            "optimizer_input_snapshot_id": self._optimizer_input_snapshot_id,
            "future_plan": self.future_plan,
            "last_saved_at": self.last_saved_at,
            "schedule_schema_version": self.schedule_schema_version,
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
        })

    async def async_set_ai_settings(self, settings: dict[str, Any]) -> None:
        self.ai_settings = dict(settings)
        self._optimizer_input_snapshot_id = ""
        self._optimizer_generation_reason = "settings_changed"
        await self.async_save_ai_data()
        self.notify_update()

    @staticmethod
    def validate_user_profiles(payload: dict[str, Any]) -> dict[str, Any]:
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
                if power is not None and not 0 < power <= 13000:
                    raise ValueError(f"Moc profilu {profile_id} musi być w zakresie 1–13000 W")
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
                if power is not None and not 0 < power <= 13000:
                    raise ValueError("Moc profilu ładowania musi być w zakresie 1–13000 W")
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
        normalized = self.validate_user_profiles(profiles)
        self.user_profiles = normalized
        self._optimizer_input_snapshot_id = ""
        self._optimizer_generation_reason = "user_profiles_changed"
        await self.async_save_ai_data()
        self.notify_update()

    def ai_api_public_context(self) -> dict[str, Any]:
        """Expose status and masked configuration, never the API secret."""
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
        }

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
        self.notify_update()
        return deepcopy(normalized)

    async def async_run_ai_api(
        self,
        *,
        connection_test: bool = False,
        force: bool = False,
    ) -> dict[str, Any]:
        """Run the optional reviewer; local plan and Deye remain untouched."""
        if not self.ai_api_config.get("enabled"):
            self.ai_api_status = {"status": "disabled", "last_error": "Asystent API jest wyłączony"}
            self.notify_update()
            return self.ai_api_status
        now = ha_now()
        if (
            not connection_test
            and not force
            and self._ai_api_last_call is not None
            and (now - self._ai_api_last_call).total_seconds() < 3600
        ):
            return self.ai_api_public_context()
        self.ai_api_status = {
            "status": "testing" if connection_test else "analysing",
            "provider": self.ai_api_config.get("provider"),
            "model": self.ai_api_config.get("model"),
            "last_error": None,
        }
        self.notify_update()
        try:
            local_plan = self.ai_plan_48h()
            battery = self.battery_model_context()
            payload = build_private_payload(
                local_plan,
                {
                    "current_soc_pct": self.state_float_or_none(self.battery_soc_sensor),
                    "capacity_kwh": battery.get("capacity_kwh"),
                    "effective_min_soc_pct": battery.get("minimum", {}).get("effective_min_soc_pct"),
                    "power_limit_w": battery.get("power_limit", {}).get("effective_limit_w"),
                },
                config=self.ai_api_config,
                user_profiles=self.user_profiles,
                tariff=self.tariff_context(now),
            )
            from homeassistant.helpers.aiohttp_client import async_get_clientsession

            response = await request_ai_analysis(
                async_get_clientsession(self.hass),
                self.ai_api_config,
                payload,
                connection_test=connection_test,
                timeout_seconds=30,
            )
        except Exception as err:
            # Secret, endpoint body and exception traceback are intentionally not stored.
            self.ai_api_status = {
                "status": "error",
                "provider": self.ai_api_config.get("provider"),
                "model": self.ai_api_config.get("model"),
                "last_error": str(err)[:500],
                "at": now.isoformat(timespec="seconds"),
            }
            self.notify_update()
            return self.ai_api_status
        self._ai_api_last_call = now
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
            self.ai_api_cache = {
                "at": now.isoformat(timespec="seconds"),
                "plan_id": local_plan.get("plan_id"),
                "locale": "pl-PL",
                "analysis": response.get("analysis"),
            }
        self.notify_update()
        return self.ai_api_public_context()

    def schedule_ai_api_analysis(self, *, force: bool = False) -> None:
        """Start at most one asynchronous API review without blocking the tick."""
        if not self.ai_api_config.get("enabled"):
            return
        if self._ai_api_task is not None and not self._ai_api_task.done():
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
            "sell_power": (0.0, 13000.0),
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
                mode = str(raw["mode"])
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
            normalized.append(item)
        return normalized

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
            if self.price_includes_distribution
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
        """Persist an explicitly accepted plan for the next calendar day."""
        if not isinstance(payload, dict):
            raise ValueError("Plan na jutro musi być obiektem")
        expected_date = (ha_now().date() + timedelta(days=1)).isoformat()
        plan_date = str(payload.get("date") or "")
        if plan_date != expected_date:
            raise ValueError(f"Plan można zapisać wyłącznie na jutro ({expected_date})")
        updates = self._validate_future_plan_updates(payload.get("updates"))
        self.future_plan = {
            "plan_id": str(payload.get("plan_id") or ""),
            "date": plan_date,
            "status": "scheduled",
            "created_at": ha_now().isoformat(timespec="seconds"),
            "updated_at": ha_now().isoformat(timespec="seconds"),
            "strategy": str(payload.get("strategy") or "balanced"),
            "updates": updates,
            "slot_validations": (
                deepcopy(payload.get("slot_validations"))
                if isinstance(payload.get("slot_validations"), dict)
                else {}
            ),
            "slot_results": {},
            "labels": [str(value) for value in payload.get("labels", []) if value is not None][:24],
        }
        approved_at = self.future_plan["created_at"]
        selected_keys = {
            str(update.get("slot_key") or "")
            for update in updates
            if isinstance(update, dict)
        }
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
        self.notify_update()

    async def async_cancel_future_plan(self, reason: str = "Anulowano przez użytkownika") -> None:
        if not self.future_plan:
            return
        plan_date = str(self.future_plan.get("date") or ha_now().date().isoformat())
        for update in self.future_plan.get("updates", []):
            if isinstance(update, dict):
                self._set_plan_execution_lifecycle(
                    plan_date,
                    str(update.get("slot_key") or ""),
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
        self.notify_update()

    async def async_process_future_plan(self) -> None:
        """Revalidate and apply only the accepted slot that is starting now."""
        plan = self.future_plan
        if not plan or plan.get("status") not in {"scheduled", "partial"}:
            return
        today = ha_now().date().isoformat()
        plan_date = str(plan.get("date") or "")
        if plan_date > today:
            return
        if plan_date < today:
            await self.async_cancel_future_plan("Plan wygasł przed zastosowaniem")
            async with self._operation_lock:
                await self.async_apply_safe_defaults("Plan na jutro wygasł przed zastosowaniem")
            return
        current_time = ha_now()
        current_slot_key = f"{current_time.hour:02d}_{(current_time.hour + 1) % 24:02d}"
        profile_id = ""
        execution_stage = "validation"
        try:
            updates = self._validate_future_plan_updates(plan.get("updates"))
            slot_results = dict(plan.get("slot_results") or {})
            current_update = next(
                (item for item in updates if item.get("slot_key") == current_slot_key),
                None,
            )
            if current_update is None or current_slot_key in slot_results:
                return
            validation = (
                plan.get("slot_validations", {}).get(current_slot_key, {})
                if isinstance(plan.get("slot_validations"), dict)
                else {}
            )
            validation = validation if isinstance(validation, dict) else {}
            profile_id = str(validation.get("profile_id") or "")
            selling = current_update.get("mode") == MODE_SELLING_FIRST
            charging = current_update.get("mode") == "Charge"
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
            if selling_needing_soc and self.state_float_or_none(self.battery_soc_sensor) is None:
                raise RuntimeError("brak poprawnego odczytu SOC dla sprzedaży")
            if selling_needing_price and self.state_float_or_none(self.price_sensor) is None:
                raise RuntimeError("brak ceny sprzedaży")
            current_soc = self.state_float_or_none(self.battery_soc_sensor)
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
                raise RuntimeError("falownik lub wymagana encja sterująca jest niedostępna")
            if (
                charging
                and validation.get("charge_source") in ("grid", "pv_and_grid")
                and not self.entity_available(self.grid_power_sensor)
            ):
                raise RuntimeError("brak wiarygodnego odczytu stanu sieci dla ładowania")
            planned_power = self.safe_float(
                current_update.get("sell_power", validation.get("power_limit_w")),
                0,
            )
            allowed_power = self.safe_float(validation.get("power_limit_w"), 0)
            if allowed_power > 0 and planned_power > allowed_power + 1e-6:
                raise RuntimeError("moc slotu przekracza aktualny limit profilu lub falownika")
            effective_buy_price = None
            if charging:
                effective_buy_price = self.price_map(
                    self.buy_price_today_sensor
                ).get(current_time.hour)
                if effective_buy_price is None:
                    effective_buy_price = self.state_float_or_none(
                        self.buy_price_today_sensor
                    )
                maximum_effective_price = self.safe_float(
                    validation.get("maximum_effective_price"),
                    0,
                )
                if maximum_effective_price > 0:
                    if effective_buy_price is None:
                        raise RuntimeError("brak aktualnej ceny zakupu dla slotu ładowania")
                    tariff = self.tariff_context(current_time)
                    if not self.price_includes_distribution:
                        effective_buy_price += self.safe_float(
                            tariff.get("total_distribution_rate"),
                            0,
                        )
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
                current_update.get("mode") == "Charge"
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
            await self.async_apply_schedule_patch([current_update])
            self._set_plan_execution_lifecycle(
                plan_date,
                current_slot_key,
                deployment_status="deployed",
                deployed_at=current_time.isoformat(timespec="seconds"),
                deployment_reason=None,
            )
            slot_results[current_slot_key] = {
                "status": "completed",
                "validated_at": current_time.isoformat(timespec="seconds"),
            }
            pending = [
                item
                for item in updates
                if item.get("slot_key") not in slot_results
                and int(str(item.get("slot_key")).split("_", 1)[0]) > current_time.hour
            ]
            self.future_plan = {
                **plan,
                "status": (
                    "partial"
                    if any(item.get("status") == "blocked" for item in slot_results.values())
                    else "scheduled"
                    if pending
                    else "completed"
                ),
                "slot_results": slot_results,
                "updated_at": current_time.isoformat(timespec="seconds"),
            }
            await self.async_add_ai_analysis({
                "timestamp": int(ha_now().timestamp() * 1000),
                "event": "future_plan_slot_applied",
                "date": plan_date,
                "slot_key": current_slot_key,
            })
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
                    **dict(plan.get("slot_results") or {}),
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
        self.notify_update()

    async def async_clear_all_history(self) -> None:
        self.ai_history = []
        self.solcast_history = []
        self.solcast_tracking = {}
        self.learning_history = []
        self.learning_tracking = {}
        self.energy_samples = []
        self.daily_archive = []
        self.monthly_archive = []
        self.energy_counter_state = {}
        self.load_profile_7x24 = {}
        self.pv_learning_profile = {}
        self.profile_execution = []
        self.plan_execution_archive = []
        await self.async_save_ai_data()
        await self.async_save_solcast_history()
        await self.async_save_learning_history()
        await self.async_save_energy_history()
        self.notify_update()

    async def async_load_solcast_history(self) -> None:
        self._solcast_store = Store(self.hass, 1, f"{DOMAIN}_{self.entry_id}_solcast_history")
        raw = await self._solcast_store.async_load()
        data, migrated = migrate_solcast_payload(raw)
        history = data.get("history")
        tracking = data.get("tracking")
        self.solcast_history = history[:1825] if isinstance(history, list) else []
        self.solcast_tracking = tracking if isinstance(tracking, dict) else {}
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
        forecast = self.solcast_forecast_today_value()
        actual = max(0, self.state_float(self.daily_pv_production_sensor, 0))
        tracked_day = str(self.solcast_tracking.get("date") or "")
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
            error = previous_actual - previous_forecast
            error_percent = (error / previous_forecast * 100) if previous_forecast > 0 else 0
            accuracy = max(0, 100 - abs(error_percent)) if previous_forecast > 0 else 0
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
            await self.async_add_ai_analysis({
                "timestamp": int(now.timestamp() * 1000),
                "event": "daily_summary",
                "date": tracked_day,
                "forecast_kwh": round(previous_forecast, 3),
                "actual_kwh": round(previous_actual, 3),
                "accuracy_percent": round(accuracy, 1),
            })
            self.solcast_tracking = {}
        if not self.solcast_tracking:
            self.solcast_tracking = {
                "date": today,
                "forecast": forecast,
                "initial_forecast_kwh": forecast if forecast > 0 else None,
                "latest_forecast_kwh": forecast if forecast > 0 else None,
                "forecast_snapshots": [],
                "actual": actual,
            }
        else:
            if self.safe_float(self.solcast_tracking.get("initial_forecast_kwh"), 0) <= 0 and forecast > 0:
                self.solcast_tracking["initial_forecast_kwh"] = forecast
                self.solcast_tracking["forecast"] = forecast
            if forecast > 0:
                self.solcast_tracking["latest_forecast_kwh"] = forecast
            self.solcast_tracking["actual"] = actual
        snapshots = self.solcast_tracking.setdefault("forecast_snapshots", [])
        snapshot_hour = now.replace(minute=0, second=0, microsecond=0).isoformat()
        if forecast > 0 and not any(str(row.get("timestamp")) == snapshot_hour for row in snapshots if isinstance(row, dict)):
            snapshots.append({"timestamp": snapshot_hour, "forecast_kwh": round(forecast, 3)})
            self.solcast_tracking["forecast_snapshots"] = snapshots[-72:]
        if changed_day or now.minute % 15 == 0:
            await self.async_save_solcast_history()

    async def async_load_learning_history(self) -> None:
        self._learning_store = Store(self.hass, 1, f"{DOMAIN}_{self.entry_id}_learning_history")
        raw = await self._learning_store.async_load()
        data, migrated = migrate_learning_payload(raw)
        history = data.get("history")
        tracking = data.get("tracking")
        self.learning_history = history[:17520] if isinstance(history, list) else []
        self.learning_tracking = tracking if isinstance(tracking, dict) else {}
        self.load_profile_7x24 = data.get("load_profile_7x24") if isinstance(data.get("load_profile_7x24"), dict) else {}
        self.pv_learning_profile = data.get("pv_profile") if isinstance(data.get("pv_profile"), dict) else {}
        self.profile_execution = data.get("profile_execution")[:17520] if isinstance(data.get("profile_execution"), list) else []
        if migrated:
            self._rebuild_learning_profiles_from_history()
            await self.async_save_learning_history()

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

    async def async_save_learning_history(self) -> None:
        if self._learning_store is None:
            return
        await self._learning_store.async_save({
            "schema_version": HISTORY_SCHEMA_VERSION,
            "history": self.learning_history[:17520],
            "tracking": self.learning_tracking,
            "load_profile_7x24": self.load_profile_7x24,
            "pv_profile": self.pv_learning_profile,
            "profile_execution": self.profile_execution[:17520],
        })

    async def async_load_energy_history(self) -> None:
        self._samples_store = Store(self.hass, 1, f"{DOMAIN}_{self.entry_id}_energy_samples")
        raw = await self._samples_store.async_load()
        data, migrated = migrate_energy_payload(raw)
        self.energy_samples = data.get("samples", []) if isinstance(data.get("samples"), list) else []
        self.daily_archive = data.get("daily", []) if isinstance(data.get("daily"), list) else []
        self.monthly_archive = data.get("monthly", []) if isinstance(data.get("monthly"), list) else []
        self.energy_counter_state = data.get("counter_state") if isinstance(data.get("counter_state"), dict) else {}
        last = data.get("last_sample")
        try:
            self._last_energy_sample_at = datetime.fromisoformat(str(last)) if last else None
        except (TypeError, ValueError):
            self._last_energy_sample_at = None
        if migrated:
            await self.async_save_energy_history()

    async def async_save_energy_history(self) -> None:
        if self._samples_store is None:
            return
        await self._samples_store.async_save({
            "schema_version": HISTORY_SCHEMA_VERSION,
            "samples": self.energy_samples,
            "daily": self.daily_archive,
            "monthly": self.monthly_archive,
            "counter_state": self.energy_counter_state,
            "last_sample": self._last_energy_sample_at.isoformat() if self._last_energy_sample_at else None,
        })

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
        self.energy_samples.append(sample)
        self._last_energy_sample_at = now
        self._archive_energy_samples(now)
        await self.async_save_energy_history()

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

        errors: list[str] = []
        hourly: list[dict[str, Any]] = []
        daily: list[dict[str, Any]] = []
        try:
            hourly = await fetch_forecast("hourly")
        except Exception as err:  # Weather is optional and must never block inverter safety logic.
            errors.append(f"godzinowa: {err}")
        try:
            daily = await fetch_forecast("daily")
        except Exception as err:
            errors.append(f"dzienna: {err}")

        # Compatibility fallback for older weather entities exposing forecast as an attribute.
        if not hourly:
            state = self.hass.states.get(entity_id)
            fallback = state.attributes.get("forecast", []) if state is not None else []
            hourly = [row for row in fallback if isinstance(row, dict)] if isinstance(fallback, list) else []

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
        soc = self.state_float_or_none(self.battery_soc_sensor)
        flags = pv_quality_flags(
            battery_soc=soc,
            work_mode=self.state_text(self.work_mode_select),
            grid_available=self.entity_available(self.grid_power_sensor),
            actual_power_w=pv_measurement.get("value"),
            inverter_limit_w=finite_float(self.ai_settings.get("inverterPowerW")),
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

    async def async_update_learning_history(self) -> None:
        now = ha_now()
        hour_key = now.strftime("%Y-%m-%dT%H:00:00%z")
        archive_changed = False
        if self.learning_tracking.get("hour") != hour_key:
            if self.learning_tracking.get("hour"):
                completed = self._finalize_learning_hour(self.learning_tracking)
                self._attach_plan_execution_actual(completed)
                archive_changed = True
                self.learning_history = [
                    completed,
                    *[row for row in self.learning_history if row.get("hour") != completed["hour"]],
                ][:17520]
                self._record_profile_execution(completed)
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
            inverter_limit_w=finite_float(self.ai_settings.get("inverterPowerW")),
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
            self.notify_update()

    def learning_summary(self) -> dict[str, Any]:
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
        stage = learning_stage(completed_days)

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
        current_forecast = self.safe_float(self.solcast_tracking.get("forecast"), 0)
        current_actual = self.safe_float(self.solcast_tracking.get("actual"), 0)
        current_progress = min(100.0, current_actual / current_forecast * 100) if current_forecast > 0 else None
        latest = completed_rows[0] if completed_rows else {}
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
            "usable_hours": sum(
                1
                for row in rows
                if any(
                    item.get("usable_for_learning")
                    for item in (row.get("channel_quality") or {}).values()
                    if isinstance(item, dict)
                )
            ),
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
                "prices_today": len(self.price_map(self.price_sensor)),
                "prices_tomorrow": len(self.price_map(self.sell_price_tomorrow_sensor, False)),
                "weather": min(48, len(self.weather_forecast)),
            },
            "solcast_accuracy_avg": round(sum(accuracy_rows) / len(accuracy_rows), 1) if accuracy_rows else None,
            "solcast_correction_factor": round(sum(correction_rows) / len(correction_rows), 3) if correction_rows else None,
            "solcast_accuracy_days": len(accuracy_rows),
            "solcast_last_accuracy": latest.get("accuracy_percent"),
            "solcast_last_date": latest.get("date"),
            "current_forecast_progress": round(current_progress, 1) if current_progress is not None else None,
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
            "weather": self.weather_context(),
            "tariff": self.tariff_context(),
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
            forecast = self.safe_float(self.solcast_tracking.get("forecast"), 0)
            actual = self.safe_float(self.solcast_tracking.get("actual"), 0)
            grouped.setdefault(tracking_day, {"date": tracking_day}).update({
                "forecast_kwh": forecast,
                "actual_kwh": actual,
                "accuracy_percent": None,
                "forecast_progress_percent": min(100, actual / forecast * 100) if forecast > 0 else None,
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

    def solcast_forecast_today_value(self) -> float:
        """Return today's Solcast forecast, tolerating renamed source entities."""
        configured = max(0, self.state_float(self.solcast_forecast_today_sensor, 0))
        if configured > 0:
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
            value = max(0, self.safe_float(state.state, 0))
            unit = str(state.attributes.get("unit_of_measurement") or "").lower()
            if value > 0 and unit in ("kwh", "wh"):
                return value / 1000 if unit == "wh" else value

        actual = max(0, self.state_float(self.daily_pv_production_sensor, 0))
        remaining = max(0, self.state_float(self.solcast_remaining_today_sensor, 0))
        if remaining > 0:
            return actual + remaining
        return 0

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
        self.sold_energy_today = round(sum(self.safe_float(values.get("kwh"), 0) for values in hourly.values()), 4)
        self.sold_value_today = round(sum(self.safe_float(values.get("value"), 0) for values in hourly.values()), 4)
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
        soc = self.state_float_or_none(self.battery_soc_sensor)
        return soc is not None and 0 <= soc <= 100 and soc >= self.active_min_sell_soc

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
            soc = self.state_float_or_none(self.battery_soc_sensor)
            if soc is None or not 0 <= soc <= 100:
                return ("error", "Brak poprawnego odczytu SOC dla sprzedaży")
            if soc < self.active_min_sell_soc:
                return (
                    "blocked",
                    f"Sprzedaż wstrzymana: SOC {soc:.0f}% jest niższy od limitu "
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
            return MODE_ZERO_EXPORT
        if (
            self.control_mode == "Schedule"
            and self.active_slot.enabled
            and self.active_slot.mode == MODE_SELLING_FIRST
            and self._selling_slot_is_blocked()
        ):
            return self.default_work_mode
        if self.active_charge_slot:
            # Charge is a manager profile, not a fourth Deye work mode.  Keep
            # the user's selected default topology (e.g. Zero Export To CT).
            return self.default_work_mode
        if self.active_slot.enabled:
            if self.active_slot.mode == MODE_NORMAL_OPERATION:
                # Return the physical Deye mode stored in this slot instead of
                # the logical Normalna Praca label, which must never be sent
                # to the inverter select entity.
                return self.active_slot.physical_work_mode or self.default_work_mode
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
    def target_discharge_current(self) -> float:
        if self.control_mode == "Manual Sell":
            return self.manual_discharge_current
        if self.control_mode != "Schedule":
            return self.default_discharge_current
        if self.active_slot.enabled and self.active_slot.mode == MODE_SELLING_FIRST and self._selling_slot_is_blocked():
            return self.default_discharge_current
        if self.active_charge_slot:
            return self.active_slot.discharge_current
        return self.active_slot.discharge_current if self.active_slot.enabled else self.default_discharge_current

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

    @property
    def manager_status(self) -> str:
        if self.emergency_stop:
            return "EMERGENCY STOP"
        if not self.data_available:
            return "NO DATA"
        if self.mapping_error and self.control_mode == "Schedule":
            return "MAPPING ERROR"
        if self.control_mode == "Protect Battery":
            return "PROTECT BATTERY"
        if self.control_mode == "Manual Sell":
            return "MANUAL SELL"
        if self.control_mode == "Charge Battery":
            return "CHARGE BATTERY"
        if self.control_mode == "Stop Sell":
            return "STOPPED"
        if self.control_mode == "Schedule":
            if not self.scheduler_enabled:
                return "SCHEDULER OFF"
            if not self.active_slot.enabled:
                return "SLOT DISABLED"
            guard_issue = self._selling_slot_guard_issue()
            if guard_issue and guard_issue[0] == "blocked":
                return "SELL BLOCKED"
            if self.last_schedule_attempt.get("status") == "failed" and self.last_schedule_attempt.get("slot") == self.active_slot_key():
                return "SCHEDULE APPLY ERROR"
            if self.active_slot.mode == MODE_SELLING_FIRST and not self.soc_ok:
                return "SOC TOO LOW"
            if self.active_slot.mode == MODE_SELLING_FIRST and not self.price_ok:
                return "PRICE TOO LOW"
            if self.active_charge_slot:
                return "GRID CHARGE ACTIVE" if self.active_slot.charge_enabled else "PV CHARGE ACTIVE"
            if self.active_slot.mode == MODE_SELLING_FIRST:
                return "SELLING ACTIVE"
            if self.active_slot.mode == MODE_NORMAL_OPERATION:
                physical = self.active_slot.physical_work_mode
                if physical == MODE_ZERO_EXPORT_CT:
                    return "ZERO EXPORT CT ACTIVE"
                return "ZERO EXPORT LOAD ACTIVE"
            if self.active_slot.mode == MODE_ZERO_EXPORT_CT:
                return "ZERO EXPORT CT ACTIVE"
            if self.active_slot.mode == MODE_ZERO_EXPORT:
                return "ZERO EXPORT LOAD ACTIVE"
            return "WAITING"
        return "WAITING"

    async def async_set_work_mode(self, mode: str) -> None:
        await self.hass.services.async_call(
            "select", "select_option", {"entity_id": self.work_mode_select, "option": mode}, blocking=True
        )

    async def async_set_number(self, entity_id: str | None, value: float) -> None:
        if entity_id:
            await self.hass.services.async_call("number", "set_value", {"entity_id": entity_id, "value": value}, blocking=True)

    async def async_set_number_if_needed(self, entity_id: str | None, value: float) -> bool:
        """Write a number only when Deye does not already report that value."""
        state = self.hass.states.get(entity_id) if entity_id else None
        current = None if state is None else self.safe_float(state.state, float("nan"))
        if current is not None and math.isfinite(current) and math.isclose(current, float(value), abs_tol=0.1):
            return False
        await self.async_set_number(entity_id, value)
        return True

    async def async_set_work_mode_if_needed(self, mode: str) -> bool:
        """Avoid re-sending an unchanged select option during a schedule tick."""
        state = self.hass.states.get(self.work_mode_select)
        if state is not None and str(state.state) == mode:
            return False
        await self.async_set_work_mode(mode)
        return True

    async def async_set_switch(self, entity_id: str | None, value: bool) -> None:
        if entity_id:
            await self.hass.services.async_call(
                "switch", "turn_on" if value else "turn_off", {"entity_id": entity_id}, blocking=True
            )

    async def async_set_switch_if_needed(self, entity_id: str | None, value: bool) -> bool:
        """Write a switch only if its current state differs from the target."""
        state = self.hass.states.get(entity_id) if entity_id else None
        if state is not None and state.state == ("on" if value else "off"):
            return False
        await self.async_set_switch(entity_id, value)
        return True

    async def async_set_time(self, entity_id: str | None, value: str) -> None:
        if entity_id:
            time_value = value if len(value) == 8 else f"{value}:00"
            await self.hass.services.async_call("time", "set_value", {"entity_id": entity_id, "time": time_value}, blocking=True)

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
        if not entity_id or not entity_id.startswith("time."):
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

    def _validate_control_plan(
        self,
        mode: str,
        sell_power: float,
        discharge_current: float,
        charge_current: float,
        grid_charge_current: float,
    ) -> None:
        """Reject an invalid control plan before the first write to Deye."""
        if mode not in WORK_MODES:
            raise ValueError(f"Unsupported Deye work mode: {mode}")
        values = {
            "Max Sell Power": (sell_power, 0.0, 13000.0),
            "Maximum Battery Discharge Current": (discharge_current, 0.0, 240.0),
            "Maximum Battery Charge Current": (charge_current, 0.0, 240.0),
            "Maximum Battery Grid Charge Current": (grid_charge_current, 0.0, 240.0),
        }
        for label, (raw_value, minimum, maximum) in values.items():
            value = float(raw_value)
            if not math.isfinite(value) or not minimum <= value <= maximum:
                raise ValueError(f"{label} must be between {minimum:g} and {maximum:g}")
        self._validate_select_entity("System Work Mode", self.work_mode_select, mode)
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
        self, mode: str | None, sell_power: float, discharge_current: float,
        charge_current: float, grid_charge_current: float,
    ) -> list[str]:
        """Read the current control state once, without writing it again.

        Some Deye integrations publish the requested values several seconds
        after the service call.  Re-sending a mode during that interval can
        undo a perfectly valid in-flight change, therefore delayed polling is
        handled by the pending transaction instead of this verifier.
        """
        expected_numbers = {
            self.max_sell_power_number: ("Max Sell Power", float(sell_power)),
            self.discharge_current_number: ("Maximum Battery Discharge Current", float(discharge_current)),
        }
        if self.charge_current_number:
            expected_numbers[self.charge_current_number] = ("Maximum Battery Charge Current", float(charge_current))
        if self.grid_charge_current_number:
            expected_numbers[self.grid_charge_current_number] = ("Maximum Battery Grid Charge Current", float(grid_charge_current))
        unconfirmed: list[str] = []
        if mode is not None:
            mode_state = self.hass.states.get(self.work_mode_select)
            if mode_state is None or str(mode_state.state) != mode:
                actual_mode = "brak" if mode_state is None else str(mode_state.state)
                unconfirmed.append(f"System Work Mode={actual_mode} (oczekiwano {mode})")
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
                self.max_sell_power_number,
                self.discharge_current_number,
                self.charge_current_number,
                self.grid_charge_current_number,
            )
            if entity_id
        ]

    def _start_schedule_input_listener(self) -> None:
        """Re-evaluate a price/SOC guard promptly, without parallel writes."""
        if self.unsub_input_listener:
            return
        entities = [entity_id for entity_id in (self.battery_soc_sensor, self.price_sensor) if entity_id]
        if not entities:
            return

        @callback
        def _on_input_change(_event: Any) -> None:
            if not self.scheduler_enabled or self.control_mode != "Schedule" or self.unsub_input_debounce:
                return

            @callback
            def _on_debounce(_now: datetime) -> None:
                self.unsub_input_debounce = None
                self.hass.async_create_task(self.async_tick())

            self.unsub_input_debounce = async_track_point_in_time(
                self.hass, _on_debounce, ha_now() + timedelta(seconds=1)
            )

        self.unsub_input_listener = async_track_state_change_event(
            self.hass, entities, _on_input_change
        )

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
        self, expected: dict[str, Any], stage: str, *, started: bool = False
    ) -> bool | None:
        """Confirm an in-flight write, or leave it pending without re-writing.

        ``True`` means confirmed, ``False`` means the 12-second confirmation
        window expired and defaults were restored, and ``None`` means that the
        caller must perform the first write.
        """
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
            float(expected.get("Max Sell Power", 0)),
            float(expected.get("Prąd rozładowania", 0)),
            float(expected.get("Prąd ładowania baterii", 0)),
            float(expected.get("Prąd ładowania z sieci", 0)),
        )
        if not unconfirmed:
            self._clear_pending_control_transaction()
            self.record_schedule_attempt("applied", "potwierdzenie", expected, "Potwierdzono pełny zestaw ustawień slotu")
            self._clear_slot_failure_latch()
            self.last_action = f"Applied {self.control_mode}"
            self.last_error = ""
            self.mark_settings_applied()
            self.notify_update()
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
            self.notify_update()
            return True

        self._clear_pending_control_transaction()
        reason = f"Niepotwierdzone ustawienia po {int(self.control_confirmation_timeout)} s: {'; '.join(unconfirmed)}"
        return await self._async_handle_slot_failure(reason, "potwierdzenie falownika", expected)

    async def async_apply_safe_defaults(self, reason: str) -> bool:
        """Apply user defaults as the single fail-safe path without forced zeroes."""
        mode = self.default_work_mode
        failures: list[str] = []
        try:
            self._validate_control_plan(
                mode,
                self.default_sell_power,
                self.default_discharge_current,
                self.default_charge_current,
                self.default_grid_charge_current,
            )
        except Exception as err:
            failures.append(str(err))

        operations = (
            ("Max Sell Power", self.async_set_number, (self.max_sell_power_number, self.default_sell_power)),
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
            ("System Work Mode", self.async_set_work_mode, (mode,)),
        )
        if not failures:
            for label, writer, args in operations:
                try:
                    await writer(*args)
                except Exception as err:
                    failures.append(f"{label}: {err}")

        if not failures:
            failures.extend(
                await self.async_verify_control_values(
                    mode,
                    self.default_sell_power,
                    self.default_discharge_current,
                    self.default_charge_current,
                    self.default_grid_charge_current,
                )
            )

        if failures:
            try:
                await self.async_set_work_mode(self.default_work_mode)
            except Exception as err:
                failures.append(f"System Work Mode: {err}")
            self.last_action = "Nie udało się w pełni zastosować ustawień domyślnych — sprawdź falownik."
            self.last_error = (
                f"KRYTYCZNY błąd częściowego zapisu ({reason}). "
                f"Niepotwierdzone wartości: {'; '.join(failures)}"
            )
            self.notify_update()
            return False

        self.last_action = f"{reason}. Zastosowano ustawienia domyślne."
        self.last_error = self.last_action
        self.notify_update()
        return True

    def _tou_entity(self, idx: int, kind: str) -> str:
        if kind == "start":
            return f"time.deye_inverter_time_of_use_{idx}_start"
        if kind == "soc":
            return f"number.deye_inverter_time_of_use_{idx}_soc"
        if kind == "grid":
            return f"switch.deye_inverter_time_of_use_{idx}_grid_charge"
        return ""

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

    def _compress_schedule_segments(self) -> list[dict[str, Any]]:
        segments: list[dict[str, Any]] = []
        for _key, _label, start, end in SLOTS:
            slot = self.slots[_key]
            mode = slot.mode if slot.enabled else MODE_ZERO_EXPORT
            charge_slot = bool(slot.enabled and slot.mode == MODE_CHARGE)
            # The profile is copied into a slot when Charge is selected.  From
            # then on this slot is authoritative and may be edited independently.
            grid_charge = bool(charge_slot and slot.charge_enabled)
            grid_charge_current = float(
                slot.grid_charge_current
                if charge_slot
                else (
                    slot.grid_charge_current
                    if slot.grid_charge_current > 0
                    else self.default_grid_charge_current
                )
            )
            data = {
                "start": start,
                "end": end if end < 24 else 0,
                "mode": mode,
                "sell_power": float(slot.sell_power if slot.enabled and not charge_slot else 0),
                "discharge_current": float(slot.discharge_current if slot.enabled else 0),
                "charge_current": float(slot.charge_current if slot.enabled else 0),
                "grid_charge_current": grid_charge_current if charge_slot else 0,
                # This is the only SOC written to physical Deye TOU.  The
                # Selling First eligibility threshold is never used here.
                "tou_soc": slot.tou_soc,
                "grid_charge": grid_charge,
            }
            comparable = {"tou_soc": data["tou_soc"], "grid_charge": data["grid_charge"]}
            previous = (
                {"tou_soc": segments[-1]["tou_soc"], "grid_charge": segments[-1]["grid_charge"]}
                if segments
                else None
            )
            if segments and previous == comparable:
                segments[-1]["end"] = data["end"]
            else:
                segments.append(data)
        while len(segments) < 6:
            split_index = -1
            longest = 0
            for index, segment in enumerate(segments):
                segment_end = 24 if segment["end"] == 0 else int(segment["end"])
                duration = segment_end - int(segment["start"])
                if duration > longest and duration > 1:
                    longest = duration
                    split_index = index
            if split_index < 0:
                break
            segment = segments[split_index]
            segment_end = 24 if segment["end"] == 0 else int(segment["end"])
            middle = int(segment["start"]) + (segment_end - int(segment["start"])) // 2
            first = {**segment, "end": middle}
            second = {**segment, "start": middle}
            segments[split_index : split_index + 1] = [first, second]
        return segments

    def _tou_grid_state_matches(self, segments: list[dict[str, Any]]) -> bool:
        """Return whether physical TOU Grid Charge switches match the plan.

        The cached map signature avoids unnecessary writes, but it must never
        turn ``Grid: nie`` into merely a visual setting.  If an inverter or a
        user changed a physical Grid Charge switch after the previous write,
        the next tick writes the intended value again.
        """
        for idx in range(1, 7):
            item = segments[idx - 1] if idx <= len(segments) else None
            expected = "on" if item and item["grid_charge"] else "off"
            if self.state_text(self._tou_entity(idx, "grid")) != expected:
                return False
        return True

    async def async_apply_time_of_use_map(self) -> bool:
        self._last_tou_write_started = False
        segments = self._compress_schedule_segments()
        missing_soc = [
            self.slots[key].label
            for key, _label, _start, _end in SLOTS
            if self.slots[key].tou_soc is None
        ]
        if missing_soc:
            self.last_error = (
                "SOC baterii Deye (TOU) wymaga potwierdzenia dla slotów: "
                + ", ".join(missing_soc)
            )
            self.notify_update()
            return False
        if len(segments) > 6:
            self.last_action = f"Time Of Use map skipped: {len(segments)} segments"
            self.last_error = f"Mapowanie wymaga {len(segments)} zakresów; Deye obsługuje maksymalnie 6"
            self.notify_update()
            return False

        missing = self.tou_mapping_errors()
        if missing:
            self._last_tou_signature = ""
            self.last_error = "Brak wymaganych encji Deye Time Of Use: " + ", ".join(missing)
            self.notify_update()
            return False

        signature = "|".join(
            f"{item['start']}-{item['end']}:{item['grid_charge']}:{item['tou_soc']}"
            for item in segments
        )
        if signature == self._last_tou_signature and self._tou_grid_state_matches(segments):
            return True

        try:
            # Validate the whole physical map before its first write.  A
            # missing later TOU entity must not leave the earlier ranges
            # partially updated.
            self._validate_switch_entity(
                "Deye Time Of Use", "switch.deye_inverter_time_of_use"
            )
            for idx in range(1, 7):
                item = segments[idx - 1] if idx <= len(segments) else None
                if item is None:
                    self._validate_switch_entity(
                        f"TOU {idx} Grid Charge", self._tou_entity(idx, "grid")
                    )
                    continue
                start_value = f"{int(item['start']):02d}:00"
                self._validate_time_entity(f"TOU {idx} start", self._tou_entity(idx, "start"), start_value)
                self._validate_number_entity(f"TOU {idx} SOC", self._tou_entity(idx, "soc"), float(item["tou_soc"]))
                self._validate_switch_entity(f"TOU {idx} Grid Charge", self._tou_entity(idx, "grid"))
                if item["grid_charge"]:
                    self._validate_number_entity(
                        "Maximum Battery Grid Charge Current",
                        self.grid_charge_current_number,
                        item["grid_charge_current"],
                    )

            self._last_tou_write_started = True
            await self.async_set_switch("switch.deye_inverter_time_of_use", True)
            for idx in range(1, 7):
                item = segments[idx - 1] if idx <= len(segments) else None
                if item is None:
                    await self.async_set_switch(self._tou_entity(idx, "grid"), False)
                    continue
                start_value = f"{int(item['start']):02d}:00"
                await self.async_set_time(self._tou_entity(idx, "start"), start_value)
                await self.async_set_number(self._tou_entity(idx, "soc"), float(item["tou_soc"]))
                await self.async_set_switch(self._tou_entity(idx, "grid"), bool(item["grid_charge"]))
                if item["grid_charge"]:
                    await self.async_set_number(self.grid_charge_current_number, item["grid_charge_current"])
        except Exception as err:
            self._last_tou_signature = ""
            self.last_error = f"Błąd zapisu Deye Time Of Use: {err}"
            self.notify_update()
            return False
        self._last_tou_signature = signature
        return True

    async def async_apply_slot_grid_charge(self, slot_key: str) -> bool:
        """Apply the current schedule after a per-slot Grid Charge change."""
        if slot_key not in self.slots:
            raise ValueError(f"Unknown schedule slot: {slot_key}")
        slot = self.slots[slot_key]
        if slot.mode != MODE_CHARGE:
            slot.charge_enabled = False
        self._last_tou_signature = ""
        self._clear_slot_failure_latch()
        self.mark_config_saved()
        self.notify_update()
        return bool(await self.async_tick())

    async def async_apply_schedule_patch(self, updates: list[dict[str, Any]]) -> None:
        """Validate and apply a group of logical slot changes as one operation."""
        if not isinstance(updates, list) or not updates:
            raise ValueError("Schedule patch must contain at least one slot")

        numeric_limits = {
            "sell_power": (0.0, 13000.0),
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
            "charge_enabled",
            "force_copy_normal_profile",
            "force_copy_charge_profile",
            *numeric_limits,
        }

        async with self._operation_lock:
            previous_slots = {key: replace(slot) for key, slot in self.slots.items()}
            previous_scheduler = self.scheduler_enabled
            self._clear_pending_control_transaction()
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
                    if "enabled" in update:
                        slot.enabled = bool(update["enabled"])
                    previous_mode = slot.mode
                    force_copy = bool(update.get("force_copy_normal_profile"))
                    force_copy_charge = bool(update.get("force_copy_charge_profile"))
                    if "mode" in update:
                        mode = str(update["mode"])
                        if mode not in SLOT_MODES:
                            raise ValueError(f"Unsupported slot mode: {mode}")
                        slot.mode = mode
                        if mode == MODE_NORMAL_OPERATION and (previous_mode != MODE_NORMAL_OPERATION or force_copy):
                            slot.enabled = True
                            if previous_mode == MODE_CHARGE:
                                slot.charge_enabled = False
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
                        elif mode == MODE_CHARGE:
                            slot.enabled = True
                            if previous_mode != MODE_CHARGE or force_copy_charge:
                                slot.charge_current = self.charge_profile_charge_current
                                slot.discharge_current = self.charge_profile_discharge_current
                                slot.grid_charge_current = self.charge_profile_grid_charge_current
                                slot.tou_soc = self.charge_profile_target_soc
                                slot.charge_enabled = self.charge_profile_grid_enabled
                        elif previous_mode == MODE_CHARGE:
                            slot.charge_enabled = False
                        elif previous_mode == MODE_NORMAL_OPERATION:
                            slot.physical_work_mode = None
                    if "charge_enabled" in update:
                        slot.charge_enabled = bool(update["charge_enabled"]) if slot.mode == MODE_CHARGE else False
                    for field_name, (minimum, maximum) in numeric_limits.items():
                        if field_name not in update:
                            continue
                        value = float(update[field_name])
                        if not math.isfinite(value) or not minimum <= value <= maximum:
                            raise ValueError(
                                f"{field_name} for {slot_key} must be between {minimum:g} and {maximum:g}"
                            )
                        setattr(slot, field_name, value)

                if any(slot.enabled for slot in self.slots.values()):
                    self.scheduler_enabled = True
                self._last_slot_failure_signature = ""
                if self.mapping_error:
                    raise ValueError(
                        f"Mapowanie wymaga {len(self._compress_schedule_segments())} zakresów; "
                        "Deye obsługuje maksymalnie 6"
                    )
                applied = await self._async_tick_impl()
                if not applied:
                    raise RuntimeError(self.last_error or "Nie udało się zastosować harmonogramu")
                self.mark_config_saved()
            except Exception as err:
                self.slots = previous_slots
                self.scheduler_enabled = previous_scheduler
                # ``_async_tick_impl`` already restores the full defaults when
                # an active slot fails.  Do not repeat the same inverter
                # transaction from this outer patch handler.  A mapping
                # rejected during preflight has not touched Deye at all, so it
                # must only roll back the logical schedule.
                self.notify_update()
                raise

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
        async with self._operation_lock:
            if mode == MODE_SELLING_FIRST and not self.sell_allowed:
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
                await self.async_apply_safe_defaults(f"Nieprawidłowy plan ustawień: {err}")
                raise
            try:
                await self.async_set_number(self.charge_current_number, charge_current)
                await self.async_set_number(
                    self.grid_charge_current_number,
                    effective_grid_charge_current,
                )
                await self.async_set_number(self.max_sell_power_number, sell_power)
                await self.async_set_number(self.discharge_current_number, discharge_current)
                unconfirmed = await self.async_verify_control_values(
                    None,
                    sell_power,
                    discharge_current,
                    charge_current,
                    effective_grid_charge_current,
                )
                if unconfirmed:
                    raise RuntimeError(f"Niepotwierdzone wartości: {'; '.join(unconfirmed)}")
                await self.async_set_work_mode(mode)
                unconfirmed = await self.async_verify_control_values(
                    mode,
                    sell_power,
                    discharge_current,
                    charge_current,
                    effective_grid_charge_current,
                )
                if unconfirmed:
                    raise RuntimeError(f"Niepotwierdzone wartości końcowe: {'; '.join(unconfirmed)}")
            except Exception as err:
                await self.async_apply_safe_defaults(f"Błąd bezpośredniego zapisu ustawień: {err}")
                raise
            self.last_action = "Zastosowano ustawienia bezpośrednie"
            self.last_error = ""
            self.mark_settings_applied()
            self.notify_update()

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
        slot_data = (
            slot.key, slot.enabled, slot.mode, slot.sell_power,
            slot.discharge_current, slot.charge_current,
            slot.grid_charge_current,
            slot.minimum_sell_soc, slot.tou_soc, slot.min_sell_price,
            slot.charge_enabled,
        )
        return repr((self.control_mode, slot_data, tuple(availability), tuple(sensor_states), self.mapping_error))

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
        required = len(self._compress_schedule_segments())
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
        expected = {"System Work Mode": target_mode, "Max Sell Power": target_sell_power, "Prąd rozładowania": target_discharge_current, "Prąd ładowania baterii": target_charge_current, "Prąd ładowania z sieci": grid_charge_current}
        pending_result = await self._async_confirm_or_wait_for_control(expected, "potwierdzenie falownika")
        if pending_result is not None:
            return pending_result
        if sell_block_reason:
            block_signature = self._sell_block_fingerprint(sell_block_reason)
            if block_signature == self._last_sell_block_signature:
                unconfirmed = await self.async_verify_control_values(
                    expected["System Work Mode"],
                    float(expected["Max Sell Power"]),
                    float(expected["Prąd rozładowania"]),
                    float(expected["Prąd ładowania baterii"]),
                    float(expected["Prąd ładowania z sieci"]),
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
        self.record_schedule_attempt("pending", stage, expected)
        try:
            self._validate_control_plan(target_mode, target_sell_power, target_discharge_current, target_charge_current, grid_charge_current)
            stage = "mapowanie Deye Time Of Use"
            if self.control_mode == "Schedule" and not await self.async_apply_time_of_use_map():
                raise RuntimeError(self.last_error or "Błąd zapisu mapowania TOU")
            stage = "wartości liczbowe"
            await self.async_set_number_if_needed(self.charge_current_number, target_charge_current)
            if self.control_mode == "Schedule" and self.active_charge_slot:
                await self.async_set_switch_if_needed("switch.deye_inverter_time_of_use", True)
            await self.async_set_number_if_needed(self.grid_charge_current_number, grid_charge_current)
            await self.async_set_number_if_needed(self.max_sell_power_number, target_sell_power)
            await self.async_set_number_if_needed(self.discharge_current_number, target_discharge_current)
            stage = "tryb pracy"
            await self.async_set_work_mode_if_needed(target_mode)
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
        return bool(await self._async_confirm_or_wait_for_control(expected, stage, started=True))

    async def async_apply_default_values(self, reason: str = "Defaults applied") -> None:
        self._validate_control_plan(
            self.default_work_mode,
            self.default_sell_power,
            self.default_discharge_current,
            self.default_charge_current,
            self.default_grid_charge_current,
        )
        try:
            await self.async_set_number(self.max_sell_power_number, self.default_sell_power)
            await self.async_set_number(self.discharge_current_number, self.default_discharge_current)
            await self.async_set_number(self.charge_current_number, self.default_charge_current)
            await self.async_set_number(self.grid_charge_current_number, self.default_grid_charge_current)
            unconfirmed = await self.async_verify_control_values(
                None,
                self.default_sell_power,
                self.default_discharge_current,
                self.default_charge_current,
                self.default_grid_charge_current,
            )
            if unconfirmed:
                raise RuntimeError(f"Niepotwierdzone ustawienia domyślne: {'; '.join(unconfirmed)}")
            await self.async_set_work_mode(self.default_work_mode)
            unconfirmed = await self.async_verify_control_values(
                self.default_work_mode,
                self.default_sell_power,
                self.default_discharge_current,
                self.default_charge_current,
                self.default_grid_charge_current,
            )
            if unconfirmed:
                raise RuntimeError(f"Niepotwierdzone ustawienia końcowe: {'; '.join(unconfirmed)}")
        except Exception as err:
            await self.async_apply_safe_defaults(f"Błąd ręcznego przywracania ustawień: {err}")
            raise
        self.last_action = reason
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
        self._validate_select_entity("System Work Mode", self.work_mode_select, physical_mode)
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
        fields = {
            "default_sell_power": self.safe_float(values.get("sell_power"), float("nan")),
            "default_discharge_current": self.safe_float(values.get("discharge_current"), float("nan")),
            "default_charge_current": self.safe_float(values.get("charge_current"), float("nan")),
            "default_grid_charge_current": self.safe_float(values.get("grid_charge_current"), float("nan")),
        }
        default_entities = {
            "default_sell_power": ("Max Sell Power", self.max_sell_power_number),
            "default_discharge_current": ("Maximum Battery Discharge Current", self.discharge_current_number),
            "default_charge_current": ("Maximum Battery Charge Current", self.charge_current_number),
            "default_grid_charge_current": ("Maximum Battery Grid Charge Current", self.grid_charge_current_number),
        }
        self._validate_select_entity("System Work Mode", self.work_mode_select, mode)
        for key, value in fields.items():
            self._validate_number_entity(*default_entities[key], value)
        self.default_work_mode = mode
        for key, value in fields.items():
            setattr(self, key, value)
        self.mark_config_saved()
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
            applied = await self._async_tick_impl()
            if not applied:
                raise RuntimeError(self.last_error or "Nie udało się zastosować bieżącego slotu harmonogramu")
            self.last_action = "Włączono Manager i harmonogram"
            self.last_error = ""
            self.mark_config_saved()
            self.notify_update()

    async def async_emergency_stop(self) -> None:
        async with self._operation_lock:
            self._clear_pending_control_transaction()
            self.emergency_stop = True
            self.control_mode = "Stop Sell"
            await self.async_apply_safe_defaults("Zatrzymanie awaryjne")

    async def _async_tick_impl(self, *_args: Any) -> bool:
        previous_sold_energy = self.sold_energy_today
        previous_sold_value = self.sold_value_today
        await self.async_update_sold_energy_today()
        await self.async_update_solcast_history()
        await self.async_update_learning_history()
        await self.async_update_energy_sample()
        if not self.weather_last_updated or ha_now().minute == 0:
            await self.async_update_weather_forecast()

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
                await self.async_apply_default_values("Defaults applied by inactive slot")

        if self.sold_energy_today != previous_sold_energy or self.sold_value_today != previous_sold_value:
            self.notify_update()
        return result

    async def async_tick(self, *_args: Any) -> None:
        if self._tariff_catalog_manager is not None and self._tariff_catalog_manager.refresh_due():
            await self._tariff_catalog_manager.async_refresh()
            self.notify_update()
        await self.async_process_future_plan()
        async with self._operation_lock:
            try:
                await self._async_tick_impl(*_args)
            except Exception as err:
                await self.async_apply_safe_defaults(f"Nieudana transakcja sterująca: {type(err).__name__}: {err}")
                raise
        if self.ai_api_config.get("enabled"):
            self.schedule_ai_api_analysis()

    async def async_start(self) -> None:
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
        await self.async_update_learning_history()
        await self.async_load_energy_history()
        await self.async_update_energy_sample()
        await self.async_update_weather_forecast()
        self._start_schedule_input_listener()
        self.unsub_timer = async_track_time_interval(self.hass, self.async_tick, timedelta(minutes=1))
        if self._tariff_catalog_manager.refresh_due():
            self.hass.async_create_task(self.async_refresh_tariff_catalog())

    async def async_unload(self) -> None:
        self._clear_pending_control_transaction()
        if self._ai_api_task is not None and not self._ai_api_task.done():
            self._ai_api_task.cancel()
        self._ai_api_task = None
        if self.unsub_input_listener:
            self.unsub_input_listener()
            self.unsub_input_listener = None
        if self.unsub_input_debounce:
            self.unsub_input_debounce()
            self.unsub_input_debounce = None
        if self.unsub_timer:
            self.unsub_timer()
            self.unsub_timer = None
        await self.async_save_sales_stats()
        await self.async_save_ai_data()
        await self.async_save_solcast_history()
        await self.async_save_learning_history()
        await self.async_save_energy_history()

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
            self.notify_update()

    def set_work_mode_for_slot(self, slot_key: str, mode: str) -> None:
        if mode in SLOT_MODES:
            slot = self.slots[slot_key]
            previous_mode = slot.mode
            slot.mode = mode
            if mode == MODE_NORMAL_OPERATION and previous_mode != MODE_NORMAL_OPERATION:
                slot.enabled = True
                self.scheduler_enabled = True
                if previous_mode == MODE_CHARGE:
                    slot.charge_enabled = False
                # Copy the normal profile template once into this slot.
                # Later changes to the template do not affect existing slots.
                if self.normal_profile_physical_work_mode in PHYSICAL_NORMAL_MODES:
                    slot.physical_work_mode = self.normal_profile_physical_work_mode
                if math.isfinite(self.normal_profile_sell_power) and 0 <= self.normal_profile_sell_power <= 13000:
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
            elif previous_mode == MODE_CHARGE:
                slot.charge_enabled = False
            elif previous_mode == MODE_NORMAL_OPERATION:
                slot.physical_work_mode = None
            self._clear_slot_failure_latch()
            self.notify_update()

    def set_default_work_mode(self, mode: str) -> None:
        if mode in WORK_MODES:
            self.default_work_mode = mode
            self.notify_update()
