"""Adds support for multizone generic thermostat units."""
import asyncio
import logging

import voluptuous as vol

from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateEntity
from homeassistant.components.climate.const import (
    ATTR_PRESET_MODE,
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_AWAY,
    PRESET_NONE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_TEMPERATURE,
    CONF_NAME,
    CONF_UNIQUE_ID,
    EVENT_HOMEASSISTANT_START,
    PRECISION_HALVES,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_OFF,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import DOMAIN as HA_DOMAIN, CoreState, callback
from homeassistant.helpers import condition
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.restore_state import RestoreEntity

from . import DOMAIN, PLATFORMS
from typing import Any, Dict

_LOGGER = logging.getLogger(__name__)

DEFAULT_TOLERANCE = 0.3
DEFAULT_NAME = "Multizone Generic Thermostat"

CONF_HEATER = "heater"
ZONES = "zones"
PRESETS = "presets"
CONF_SENSOR = "target_sensor"
CONF_MIN_TEMP = "min_temp"
CONF_MAX_TEMP = "max_temp"
CONF_TARGET_TEMP = "target_temp"
CONF_TARGET_TEMP_SENSOR = "target_temp_sensor"
CONF_AC_MODE = "ac_mode"
CONF_MIN_DUR = "min_cycle_duration"
CONF_COLD_TOLERANCE = "cold_tolerance"
CONF_HOT_TOLERANCE = "hot_tolerance"
CONF_KEEP_ALIVE = "keep_alive"
CONF_INITIAL_HVAC_MODE = "initial_hvac_mode"
CONF_AWAY_TEMP = "away_temp"
CONF_PRECISION = "precision"
ATTR_ONGOING_ZONE = "ongoing_zone"
ATTR_SELECTED_ZONE="selected_zone"
ATTR_SELECTED_PRESET="selected_preset"
ATTR_REPORT_ZONE_NAME_INSTEAD_OF_PRESET_NAME="report_zone_name_instead_preset_name"

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE

ZONE_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Optional(ATTR_FRIENDLY_NAME): cv.string,
            vol.Required(CONF_SENSOR): cv.entity_id,
            vol.Optional(CONF_TARGET_TEMP): vol.Coerce(float),
            vol.Optional(CONF_TARGET_TEMP_SENSOR): cv.entity_id
        }
    ),
    cv.has_at_least_one_key(CONF_TARGET_TEMP, CONF_TARGET_TEMP_SENSOR),
    cv.has_at_most_one_key(CONF_TARGET_TEMP, CONF_TARGET_TEMP_SENSOR))

PRESET_SCHEMA = vol.Schema({
    vol.Optional(ZONES): cv.schema_with_slug_keys(ZONE_SCHEMA),
})

PRESET_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Optional(ATTR_FRIENDLY_NAME): cv.string,
            vol.Required(ZONES): vol.All(cv.schema_with_slug_keys(ZONE_SCHEMA)),
            vol.Optional(ATTR_REPORT_ZONE_NAME_INSTEAD_OF_PRESET_NAME): cv.boolean,
        }
    ))

PLATFORM_SCHEMA = vol.All(
    cv.deprecated(CONF_AWAY_TEMP),
    PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HEATER): cv.entity_id,
        vol.Optional(ZONES): vol.All(cv.schema_with_slug_keys(ZONE_SCHEMA)),
        vol.Optional(PRESETS): vol.All(cv.schema_with_slug_keys(PRESET_SCHEMA)),
        vol.Optional(CONF_SENSOR): cv.entity_id,
        vol.Optional(CONF_AC_MODE): cv.boolean,
        vol.Optional(CONF_MAX_TEMP): vol.Coerce(float),
        vol.Optional(CONF_MIN_DUR): cv.positive_time_period,
        vol.Optional(CONF_MIN_TEMP): vol.Coerce(float),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_COLD_TOLERANCE, default=DEFAULT_TOLERANCE): vol.Coerce(float),
        vol.Optional(CONF_HOT_TOLERANCE, default=DEFAULT_TOLERANCE): vol.Coerce(float),
        vol.Optional(CONF_TARGET_TEMP): vol.Coerce(float),
        vol.Optional(CONF_KEEP_ALIVE): cv.positive_time_period,
        vol.Optional(CONF_INITIAL_HVAC_MODE): vol.In(
            [HVAC_MODE_COOL, HVAC_MODE_HEAT, HVAC_MODE_OFF]
        ),
        vol.Optional(CONF_AWAY_TEMP): vol.Coerce(float),
        vol.Optional(CONF_PRECISION): vol.In(
            [PRECISION_TENTHS, PRECISION_HALVES, PRECISION_WHOLE]
        ),
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
    ))


class ZoneDef():
    def __init__(self, friendly_name, sensor_entity_id, target_entity_id, target_temp, name):
        self._friendly_name = friendly_name or name
        self._sensor_entity_id = sensor_entity_id
        self._target_entity_id = target_entity_id    
        self._name = name 
        self._target_temp = target_temp;
        self._saved_target_temp = None;
        #if self._target_entity_id and (isinstance(self._target_entity_id, float) or isinstance(self._target_entity_id, int)):
        #    self._target_temp = float(self._target_entity_id);
        self._cur_temp = None;

class PresetDef():
    def __init__(self, friendly_name, zones, name, report_zone_name_instead_preset_name):
        self._friendly_name = friendly_name or name
        self._name = name 
        self._zones = zones
        self._report_zone_name_instead_preset_name = report_zone_name_instead_preset_name

def parse_zones_dict(explicit_zones):
    zones = []
    try:
        if explicit_zones:
            for key, z in explicit_zones.items():
                zones.append(ZoneDef(z[ATTR_FRIENDLY_NAME] if (ATTR_FRIENDLY_NAME in z) else None, 
                    z[CONF_SENSOR], 
                    z[CONF_TARGET_TEMP_SENSOR] if (CONF_TARGET_TEMP_SENSOR in z) else None, 
                    z[CONF_TARGET_TEMP] if (CONF_TARGET_TEMP in z) else None, 
                    key))
    except ValueError as ex:
                _LOGGER.error("Unable to parse zones %s %s", explicit_zones, ex)
    except TypeError as ex:
                _LOGGER.error("Unable to parse zones %s %s", explicit_zones, ex)
    return zones

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the multizone generic thermostat platform."""
    _LOGGER.info("async_setup_platform. ")

    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)

    name = config.get(CONF_NAME)
    heater_entity_id = config.get(CONF_HEATER)
    explicit_zones = config.get(ZONES)
    explicit_presets = config.get(PRESETS)
    sensor_entity_id0 = config.get(CONF_SENSOR)
    min_temp = config.get(CONF_MIN_TEMP)
    max_temp = config.get(CONF_MAX_TEMP)
    target_temp0 = config.get(CONF_TARGET_TEMP)
    target_temp_sensor0 = config.get(CONF_TARGET_TEMP_SENSOR)
    ac_mode = config.get(CONF_AC_MODE)
    min_cycle_duration = config.get(CONF_MIN_DUR)
    cold_tolerance = config.get(CONF_COLD_TOLERANCE)
    hot_tolerance = config.get(CONF_HOT_TOLERANCE)
    keep_alive = config.get(CONF_KEEP_ALIVE)
    initial_hvac_mode = config.get(CONF_INITIAL_HVAC_MODE)
    away_temp = config.get(CONF_AWAY_TEMP)
    precision = config.get(CONF_PRECISION)
    unit = hass.config.units.temperature_unit
    unique_id = config.get(CONF_UNIQUE_ID)

    global_zone = list(filter(lambda z: (not z._sensor_entity_id is None) and (not z._target_entity_id is None), [ZoneDef("Global", sensor_entity_id0, target_temp_sensor0, target_temp0, "GlobalZone")]))

    zones = global_zone + parse_zones_dict(explicit_zones)

    presets = list(filter(lambda p: len(p._zones) > 0, [PresetDef(PRESET_NONE, zones, PRESET_NONE, False)]))

    try:
        if explicit_presets:
            for key, p in explicit_presets.items():
                presets.append(PresetDef(p[ATTR_FRIENDLY_NAME] if (ATTR_FRIENDLY_NAME in p) else None, parse_zones_dict(p[ZONES]), key, p[ATTR_REPORT_ZONE_NAME_INSTEAD_OF_PRESET_NAME] if (ATTR_REPORT_ZONE_NAME_INSTEAD_OF_PRESET_NAME in p) else None))
    except ValueError as ex:
                _LOGGER.error("Unable to parse presets %s %s", explicit_presets, ex)
    except TypeError as ex:
                _LOGGER.error("Unable to parse presets %s %s", explicit_presets, ex)

    if len(presets) == 0:
        _LOGGER.error("No zones nor presets defined")

    for p in presets:
        _LOGGER.info("Preset: %s %s %s", p._name, p._friendly_name, p._report_zone_name_instead_preset_name)
        for z in p._zones:
            _LOGGER.info("Zone: %s %s SensorId:%s Target:%s", z._name, z._friendly_name, z._sensor_entity_id, z._target_entity_id)

    async_add_entities(
        [
            MultizoneGenericThermostat(
                name,
                heater_entity_id,
                presets,
                min_temp,
                max_temp,
                ac_mode,
                min_cycle_duration,
                cold_tolerance,
                hot_tolerance,
                keep_alive,
                initial_hvac_mode,
                away_temp,
                precision,
                unit,
                unique_id,
            )
        ]
    )

class MultizoneGenericThermostat(ClimateEntity, RestoreEntity):
    """Representation of a Multizone Generic Thermostat device."""

    def __init__(
        self,
        name,
        heater_entity_id,
        presets,
        min_temp,
        max_temp,
        ac_mode,
        min_cycle_duration,
        cold_tolerance,
        hot_tolerance,
        keep_alive,
        initial_hvac_mode,
        away_temp,
        precision,
        unit,
        unique_id,
    ):
        """Initialize the thermostat."""
        _LOGGER.info("__init__. ")

        self._name = name
        self.heater_entity_id = heater_entity_id
        self._presets = presets
        self._selected_preset = self._presets[0]
        self._selected_zone = self._selected_preset._zones[0]
        self._ongoing_zone = None
        self.ac_mode = ac_mode
        self.min_cycle_duration = min_cycle_duration
        self._cold_tolerance = cold_tolerance
        self._hot_tolerance = hot_tolerance
        self._keep_alive = keep_alive
        self._hvac_mode = initial_hvac_mode
        for z in self._selected_preset._zones:
            z._saved_target_temp = z._target_temp or away_temp
        self._temp_precision = precision
        if self.ac_mode:
            self._hvac_list = [HVAC_MODE_COOL, HVAC_MODE_OFF]
        else:
            self._hvac_list = [HVAC_MODE_HEAT, HVAC_MODE_OFF]
        self._active = False
        self._cur_temp = None
        self._temp_lock = asyncio.Lock()
        self._min_temp = min_temp
        self._max_temp = max_temp
        self._unit = unit
        self._unique_id = unique_id
        self._support_flags = SUPPORT_FLAGS
        if away_temp:
            self._support_flags = SUPPORT_FLAGS | SUPPORT_PRESET_MODE
        self._away_temp = away_temp
        self._is_away = False

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        _LOGGER.info("async_added_to_hass. ")

        # Add listener
        for z in self._selected_preset._zones:
            if z._sensor_entity_id:
                self.async_on_remove(
                    async_track_state_change_event(
                        self.hass, [z._sensor_entity_id], self._async_sensor_changed
                    )
                )

            if z._target_entity_id:
                self.async_on_remove(
                    async_track_state_change_event(
                        self.hass, [z._target_entity_id], self._async_target_changed
                    )
            )

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self.heater_entity_id], self._async_switch_changed
            )
        )

        if self._keep_alive:
            self.async_on_remove(
                async_track_time_interval(
                    self.hass, self._async_control_heating, self._keep_alive
                )
            )

        @callback
        def _async_startup(*_):
            """Init on startup."""
            _LOGGER.info("_async_startup. ")

            for z in self._selected_preset._zones:
                sensor_state = self.hass.states.get(z._sensor_entity_id)
                if sensor_state and sensor_state.state not in (
                    STATE_UNAVAILABLE,
                    STATE_UNKNOWN,
                ):
                    self._async_update_temp(z, sensor_state)
                    self.async_write_ha_state()

                if z._target_entity_id:
                    sensor_state = self.hass.states.get(z._target_entity_id)
                    if sensor_state and sensor_state.state not in (
                        STATE_UNAVAILABLE,
                        STATE_UNKNOWN,
                    ):
                        self._async_update_target_temp(z, sensor_state)
                        self.async_write_ha_state()

        if self.hass.state == CoreState.running:
            _async_startup()
        else:
            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, _async_startup)

        # Check If we have an old state
        old_state = await self.async_get_last_state()
        if old_state is not None:
            # If we have no initial temperature, restore
            #for z in self._selected_preset._zones:
            #    if z._target_temp is None:
            #        # If we have a previously saved temperature
            #        if old_state.attributes.get(ATTR_TEMPERATURE+z._name) is None:
            #            if self.ac_mode:
            #                z._target_temp = self.max_temp
            #            else:
            #                z._target_temp = self.min_temp
            #            _LOGGER.warning(
            #                "Undefined target temperature, falling back %s to %s",
            #                z._name, z._target_temp,
            #            )
            #        else:
            #            z._target_temp = float(old_state.attributes[ATTR_TEMPERATURE+z._name])

            if old_state.attributes.get(ATTR_PRESET_MODE) == PRESET_AWAY:
                self._is_away = True
            if not self._hvac_mode and old_state.state:
                self._hvac_mode = old_state.state

        else:
            # No previous state, try and restore defaults
            for z in self._selected_preset._zones:
                if z._target_temp is None:
                    if self.ac_mode:
                        z._target_temp = self.max_temp
                    else:
                        z._target_temp = self.min_temp
                _LOGGER.warning(
                    "No previously saved temperature, setting %s to %s", z._name, z._target_temp
                )

        # Set default state to off
        if not self._hvac_mode:
            self._hvac_mode = HVAC_MODE_OFF

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def name(self):
        """Return the name of the thermostat."""
        return self._name

    @property
    def selected_zone_name(self):
        """Return the name of the selected zone (with worst temperature)."""
        return self._selected_zone._name

    @property
    def ongoing_zone_name(self):
        """Return the name of the zone that is curently being heated or cooled."""
        if self._ongoing_zone is None:
            return None
        return self._ongoing_zone._name

    @property
    def unique_id(self):
        """Return the unique id of this thermostat."""
        return self._unique_id

    @property
    def precision(self):
        """Return the precision of the system."""
        if self._temp_precision is not None:
            return self._temp_precision
        return super().precision

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        # Since this integration does not yet have a step size parameter
        # we have to re-use the precision as the step size for now.
        return self.precision

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def current_temperature(self):
        """Return the sensor temperature."""
        return (self._ongoing_zone or self._selected_zone)._cur_temp

    @property
    def hvac_mode(self):
        """Return current operation."""
        return self._hvac_mode

    @property
    def hvac_action(self):
        """Return the current running hvac operation if supported.

        Need to be one of CURRENT_HVAC_*.
        """
        if self._hvac_mode == HVAC_MODE_OFF:
            return CURRENT_HVAC_OFF
        if not self._is_device_active:
            return CURRENT_HVAC_IDLE
        if self.ac_mode:
            return CURRENT_HVAC_COOL
        return CURRENT_HVAC_HEAT

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return (self._ongoing_zone or self._selected_zone)._target_temp

    @property
    def hvac_modes(self):
        """List of available operation modes."""
        return self._hvac_list

    @property
    def preset_mode(self):
        """Return the current preset mode, e.g., home, away, temp."""
        if self._selected_preset._report_zone_name_instead_preset_name == True:
            return self._selected_zone._friendly_name
        return PRESET_AWAY if self._is_away else self._selected_preset._name # PRESET_AWAY if self._is_away else PRESET_NONE

    @property
    def preset_modes(self):
        """Return a list of available preset modes or PRESET_NONE if _away_temp is undefined."""
        #return [PRESET_NONE, PRESET_AWAY] if self._away_temp else PRESET_NONE
        return list(p._name for p in self._presets) + list([PRESET_AWAY] if self._away_temp else [])

    async def async_set_hvac_mode(self, hvac_mode):
        """Set hvac mode."""
        if hvac_mode == HVAC_MODE_HEAT:
            self._hvac_mode = HVAC_MODE_HEAT
            await self._async_control_heating(force=True)
        elif hvac_mode == HVAC_MODE_COOL:
            self._hvac_mode = HVAC_MODE_COOL
            await self._async_control_heating(force=True)
        elif hvac_mode == HVAC_MODE_OFF:
            self._hvac_mode = HVAC_MODE_OFF
            if self._is_device_active:
                await self._async_heater_turn_off()
        else:
            _LOGGER.error("Unrecognized hvac mode: %s", hvac_mode)
            return
        # Ensure we update the current operation after changing the mode
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""

        temperature = kwargs.get(ATTR_TEMPERATURE)
        _LOGGER.info("async_set_temperature. %s", temperature)

        if temperature is None:
            return
        (self._ongoing_zone or self._selected_zone)._target_temp = temperature
        await self._async_control_heating(force=True)
        self.async_write_ha_state()

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        if self._min_temp is not None:
            return self._min_temp

        # get default temp from super class
        return super().min_temp

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        if self._max_temp is not None:
            return self._max_temp

        # Get default temp from super class
        return super().max_temp

    async def _async_target_changed(self, event):
        """Handle target temperature changes."""
        sender = event.data.get("entity_id")
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return
        
        _LOGGER.info("_async_target_changed. %s", new_state.state)

        for p in self._presets:
            for z in p._zones:
                if z._target_entity_id == sender:
                    self._async_update_target_temp(z, new_state)
                    _LOGGER.info("zone target value updated. %s: %s<%s", z._name, z._target_temp, z._cur_temp)
        await self._async_control_heating()
        self.async_write_ha_state()

    async def _async_sensor_changed(self, event):
        """Handle temperature changes."""
        sender = event.data.get("entity_id")
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return
        
        _LOGGER.info("_async_sensor_changed. %s", new_state.state)

        for p in self._presets:
            for z in p._zones:
                if z._sensor_entity_id == sender:
                    self._async_update_temp(z, new_state)
                    _LOGGER.info("zone sensor value updated. %s: %s<%s", z._name, z._target_temp, z._cur_temp)
        await self._async_control_heating()
        self.async_write_ha_state()

    @callback
    def _async_switch_changed(self, event):
        """Handle heater switch state changes."""
        new_state = event.data.get("new_state")
        if new_state is None:
            return

        _LOGGER.info("_async_switch_changed. %s", new_state.state)

        self.async_write_ha_state()

        if new_state.state == STATE_OFF:
            self._ongoing_zone = None

    @callback
    def _async_update_target_temp(self, zone, state):
        """Update thermostat with latest state from target sensor."""
        try:
            zone._target_temp = float(state.state)
        except ValueError as ex:
            _LOGGER.error("Unable to update target temp %s from sensor: %s", z._name, ex)

    @callback
    def _async_update_temp(self, zone, state):
        """Update thermostat with latest state from sensor."""
        try:
            zone._cur_temp = float(state.state)
        except ValueError as ex:
            _LOGGER.error("Unable to update %s from sensor: %s", z._name, ex)

    def select_worst_zone(self):
        if not self._ongoing_zone is None: 
            self._selected_zone = self._ongoing_zone
            return

        sortedZones =list(sorted(filter(lambda z: (not z._cur_temp is None) and (not z._target_temp is None), self._selected_preset._zones), key=lambda z: z._cur_temp  - z._target_temp))
        if len(sortedZones) > 0:
            selected_zone = sortedZones[0]
        else:
            selected_zone = self._selected_preset._zones[0]

        if self._selected_zone != selected_zone:
            _LOGGER.info("Selected zone changed from %s -> %s", self._selected_zone._name, selected_zone._name)
            self._selected_zone = selected_zone

    async def _async_control_heating(self, time=None, force=False):
        """Check if we need to turn heating on or off."""
        async with self._temp_lock:
            self.select_worst_zone()
            if not self._active and None not in (self._selected_zone._cur_temp, self._selected_zone._target_temp):
                self._active = True
                _LOGGER.info(
                    "Obtained current and target temperature. "
                    "Multizone generic thermostat active. %s, %s",
                    self._selected_zone._cur_temp,
                    self._selected_zone._target_temp,
                )

            if not self._active or self._hvac_mode == HVAC_MODE_OFF:
                return

            if not force and time is None:
                # If the `force` argument is True, we
                # ignore `min_cycle_duration`.
                # If the `time` argument is not none, we were invoked for
                # keep-alive purposes, and `min_cycle_duration` is irrelevant.
                if self.min_cycle_duration:
                    if self._is_device_active:
                        current_state = STATE_ON
                    else:
                        current_state = HVAC_MODE_OFF
                    long_enough = condition.state(
                        self.hass,
                        self.heater_entity_id,
                        current_state,
                        self.min_cycle_duration,
                    )
                    if not long_enough:
                        return

            too_cold = self._selected_zone._target_temp >= self._selected_zone._cur_temp + self._cold_tolerance
            too_hot = self._selected_zone._cur_temp >= self._selected_zone._target_temp + self._hot_tolerance
            if self._is_device_active:
                if (self.ac_mode and too_cold) or (not self.ac_mode and too_hot):
                    _LOGGER.info("Turning off heater %s %s", self._selected_zone._name, self.heater_entity_id)
                    self._ongoing_zone = None
                    self.select_worst_zone()
                    new_too_cold = self._selected_zone._target_temp >= self._selected_zone._cur_temp + self._cold_tolerance
                    new_too_hot = self._selected_zone._cur_temp >= self._selected_zone._target_temp + self._hot_tolerance
                    if (self.ac_mode and not new_too_hot) or (not self.ac_mode and not new_too_cold):
                        await self._async_heater_turn_off()
                    else:
                        _LOGGER.info("Not turning off heater because there is another zone too cold")
                elif time is not None:
                    # The time argument is passed only in keep-alive case
                    _LOGGER.info(
                        "Keep-alive - Turning on heater heater %s",
                        self.heater_entity_id,
                    )

                    self._ongoing_zone = self._selected_zone
                    await self._async_heater_turn_on()
            else:
                if (self.ac_mode and too_hot) or (not self.ac_mode and too_cold):
                    _LOGGER.info("Turning on heater %s %s", self._selected_zone._name, self.heater_entity_id)

                    self._ongoing_zone = self._selected_zone
                    await self._async_heater_turn_on()
                elif time is not None:
                    # The time argument is passed only in keep-alive case
                    _LOGGER.info(
                        "Keep-alive - Turning off heater %s", self.heater_entity_id
                    )
                    self._ongoing_zone = None
                    await self._async_heater_turn_off()

    @property
    def _is_device_active(self):
        """If the toggleable device is currently active."""
        return self.hass.states.is_state(self.heater_entity_id, STATE_ON)

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._support_flags

    async def _async_heater_turn_on(self):
        """Turn heater toggleable device on."""
        data = {ATTR_ENTITY_ID: self.heater_entity_id}
        await self.hass.services.async_call(
            HA_DOMAIN, SERVICE_TURN_ON, data, context=self._context
        )

    async def _async_heater_turn_off(self):
        """Turn heater toggleable device off."""
        data = {ATTR_ENTITY_ID: self.heater_entity_id}
        await self.hass.services.async_call(
            HA_DOMAIN, SERVICE_TURN_OFF, data, context=self._context
        )

    async def async_set_preset_mode(self, preset_mode: str):
        """Set new preset mode."""

        if preset_mode in self._presets:
            self._selected_preset = self._presets[preset_mode]
            self._ongoing_zone = None
            await self._async_control_heating(force=True)
        else: 
            if preset_mode == PRESET_AWAY and not self._is_away:
                self._is_away = True
                for z in self._selected_preset._zones:
                    z._saved_target_temp = z._target_temp
                    z._target_temp = self._away_temp
                self._ongoing_zone = None
                await self._async_control_heating(force=True)
            elif preset_mode == PRESET_NONE and self._is_away:
                self._is_away = False
                for z in self._selected_preset._zones:
                    z._target_temp = z._saved_target_temp
                self._ongoing_zone = None
                await self._async_control_heating(force=True)

        self.async_write_ha_state()

    @ClimateEntity.state_attributes.getter
    def state_attributes(self) -> Dict[str, Any]:
        data = super().state_attributes
        data[ATTR_ONGOING_ZONE] = self._ongoing_zone._name if self._ongoing_zone else None
        data[ATTR_SELECTED_ZONE] = self._selected_zone._name
        data[ATTR_SELECTED_PRESET] = self._selected_preset._name
        return data
