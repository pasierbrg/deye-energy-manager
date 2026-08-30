from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import ACCEPTED_SLOT_MODES, CONTROL_MODES, DOMAIN, normalize_manager_mode, PHYSICAL_NORMAL_MODES, SLOTS, SLOT_MODES, WORK_MODES
from .entity import DeyeEnergyManagerEntity
from .inverter_provider import (
    normal_profile_mode_label_to_key,
    normal_profile_mode_metadata,
    normal_profile_mode_options,
    physical_normal_option_to_key,
)


class DeyeControlModeSelect(DeyeEnergyManagerEntity, SelectEntity, RestoreEntity):
    def __init__(self, runtime):
        super().__init__(runtime, "control_mode", "Control mode")

    @property
    def options(self):
        return CONTROL_MODES

    @property
    def current_option(self):
        return self.runtime.control_mode

    async def async_added_to_hass(self):
        if (last_state := await self.async_get_last_state()) is not None and last_state.state in CONTROL_MODES:
            self.runtime.control_mode = last_state.state

    async def async_select_option(self, option: str):
        self.runtime.set_control_mode(option)
        self.runtime.mark_config_saved()
        await self.runtime.async_tick()


class DeyeDefaultWorkModeSelect(DeyeEnergyManagerEntity, SelectEntity, RestoreEntity):
    def __init__(self, runtime):
        super().__init__(runtime, "default_work_mode", "Default work mode")

    @property
    def options(self):
        return WORK_MODES

    @property
    def current_option(self):
        return self.runtime.default_work_mode

    async def async_added_to_hass(self):
        if (last_state := await self.async_get_last_state()) is not None:
            normalized = normalize_manager_mode(last_state.state)
            if normalized in WORK_MODES:
                self.runtime.default_work_mode = normalized

    async def async_select_option(self, option: str):
        self.runtime.set_default_work_mode(option)
        self.runtime.mark_config_saved()


class DeyeNormalProfileModeSelect(DeyeEnergyManagerEntity, SelectEntity, RestoreEntity):
    def __init__(self, runtime):
        super().__init__(runtime, "normal_profile_mode", "Normal profile Deye mode")

    @property
    def options(self):
        # Show Polish labels; the technical provider option is translated only
        # when writing to the inverter.
        return normal_profile_mode_options(self.runtime.data)

    @property
    def current_option(self):
        # Missing Custom mappings are unavailable, not guessed technical values.
        return next(
            (
                row["label"]
                for row in normal_profile_mode_metadata(self.runtime.data)
                if row["available"]
                and row["value"] == self.runtime.normal_profile_physical_work_mode
            ),
            None,
        )

    async def async_added_to_hass(self):
        if (last_state := await self.async_get_last_state()) is not None:
            state = str(last_state.state)
            # Accept either the new Polish label or the legacy technical option.
            key = normal_profile_mode_label_to_key(self.runtime.data, state)
            if key is None:
                key = physical_normal_option_to_key(self.runtime.data, state)
            if key in PHYSICAL_NORMAL_MODES:
                self.runtime.normal_profile_physical_work_mode = key

    async def async_select_option(self, option: str):
        key = normal_profile_mode_label_to_key(self.runtime.data, option)
        if key not in PHYSICAL_NORMAL_MODES:
            raise ValueError(f"Nieznany tryb normalny: {option}")
        await self.runtime.async_save_normal_profile({
            "physical_work_mode": key,
        })
        self.runtime.mark_config_saved()


class DeyeSlotModeSelect(DeyeEnergyManagerEntity, SelectEntity, RestoreEntity):
    def __init__(self, runtime, slot_key, label):
        super().__init__(runtime, f"slot_{slot_key}_mode", f"Mode {label}")
        self.slot_key = slot_key

    @property
    def options(self):
        return SLOT_MODES

    @property
    def current_option(self):
        return self.runtime.slots[self.slot_key].mode

    @property
    def extra_state_attributes(self):
        return {
            "ai_sell_power_only": bool(
                self.runtime.slots[self.slot_key].ai_sell_power_only
            )
        }

    async def async_added_to_hass(self):
        if (last_state := await self.async_get_last_state()) is not None:
            normalized = normalize_manager_mode(last_state.state)
            if normalized in ACCEPTED_SLOT_MODES:
                await self.runtime.async_restore_slot_mode(
                    self.slot_key,
                    normalized,
                    ai_sell_power_only=bool(
                        last_state.attributes.get("ai_sell_power_only", False)
                    ),
                )

    async def async_select_option(self, option: str):
        # An explicit mode selection is a manual schedule decision.
        self.runtime.slots[self.slot_key].ai_sell_power_only = False
        self.runtime.set_work_mode_for_slot(self.slot_key, option)
        self.runtime.mark_config_saved()
        await self.runtime.async_tick()


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    runtime = hass.data[DOMAIN][entry.entry_id]
    entities = [
        DeyeControlModeSelect(runtime),
        DeyeDefaultWorkModeSelect(runtime),
        DeyeNormalProfileModeSelect(runtime),
    ]
    entities.extend(DeyeSlotModeSelect(runtime, key, label) for key, label, *_ in SLOTS)
    async_add_entities(entities)
