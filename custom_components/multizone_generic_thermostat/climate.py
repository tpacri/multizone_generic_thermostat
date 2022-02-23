"""Adds support for multizone generic thermostat units."""
import asyncio
import logging
from copy import deepcopy

from .binary_sensor import IsWindowOpenSensor

import voluptuous as vol

from datetime import timedelta
from datetime import datetime

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
    STATE_UNKNOWN
)

from homeassistant.core import DOMAIN as HA_DOMAIN, CoreState, callback
from homeassistant.helpers import condition
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import async_generate_entity_id
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
CONF_TEMP_SENSORS = "target_sensors"
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
CONF_REPORT_ZONE_NAME_INSTEAD_OF_PRESET_NAME="report_zone_name_instead_preset_name"
CONF_DELTA_TEMP="delta_temp"
CONF_MIN_DELTA_TIME="min_delta_time"
CONF_DELTA_TIME="delta_time"
CONF_OPEN_WINDOW="open_window"
CONF_ZONE_REACT_DELAY="zone_react_delay"

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE

OPEN_WINDIW_SCHEMA = vol.Schema(
        {
            vol.Required(CONF_DELTA_TEMP): vol.Coerce(float),
            vol.Required(CONF_DELTA_TIME): cv.time_period,
            vol.Optional(CONF_MIN_DELTA_TIME): cv.time_period,
            vol.Optional(CONF_ZONE_REACT_DELAY): cv.time_period,
        }
    )

ZONE_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Optional(ATTR_FRIENDLY_NAME): cv.string,
            vol.Optional(CONF_SENSOR): cv.entity_id,
            vol.Optional(CONF_TEMP_SENSORS, default=[]): vol.All(cv.ensure_list, [cv.entity_id]),
            vol.Optional(CONF_TARGET_TEMP): vol.Coerce(float),
            vol.Optional(CONF_TARGET_TEMP_SENSOR): cv.entity_id,
            vol.Optional(CONF_OPEN_WINDOW): vol.Schema(OPEN_WINDIW_SCHEMA)
        }
    ),
#    cv.has_at_least_one_key(CONF_SENSOR, CONF_TEMP_SENSORS),
#    cv.has_at_most_one_key(CONF_SENSOR, CONF_TEMP_SENSORS),
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
            vol.Optional(CONF_REPORT_ZONE_NAME_INSTEAD_OF_PRESET_NAME): cv.boolean,
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
        vol.Optional(CONF_TEMP_SENSORS, default=[]): vol.All(cv.ensure_list, [cv.entity_id]),
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
        vol.Optional(CONF_OPEN_WINDOW): vol.Schema(OPEN_WINDIW_SCHEMA)
    },
#    cv.has_at_most_one_key(CONF_SENSOR, CONF_TEMP_SENSORS)
    ))


def is_temp_valid(temp)->bool:
    return temp is not None and temp not in (
                STATE_UNAVAILABLE,
                STATE_UNKNOWN,
                'unavailable',
                ''
            )

class TempWithTime():
    def __init__(self, temp, temp_timestamp):
        self._temp = temp
        self._temp_timestamp = temp_timestamp

class OpenWindowDef():
    def __init__(self, delta, timediff, mintimediff, zoneReactDelay):
        self._delta = abs(delta)
        self._timedelta = timediff
        self._mintimedelta = mintimediff
        self._zoneReactDelay = zoneReactDelay
        self._steep = delta/timediff.total_seconds()
        self._temperature_history = []
        self._is_open_window = False
        self._is_open_window_timestamp = None
        self._zone_react_timestamp = None
        self._zoneName = "not set yet"

    def add_temp(self, temp):
        if is_temp_valid(temp):
            self._temperature_history.append(TempWithTime(float(temp), datetime.now()))
            time_limit = datetime.now()-max(self._timedelta, self._mintimedelta if self._mintimedelta is not None else self._timedelta)

            is_open_window = self.calculate_is_openwindow()

            while len(self._temperature_history) > 0 and self._temperature_history[0]._temp_timestamp < time_limit:
                self._temperature_history.pop(0)

            if is_open_window != self._is_open_window:
                self._is_open_window = is_open_window
                self._is_open_window_timestamp =  datetime.now() if is_open_window else None
                self._zone_react_timestamp = (self._is_open_window_timestamp + self._zoneReactDelay) if (self._is_open_window_timestamp is not None and self._zoneReactDelay is not None) else None
                _LOGGER.warning("Is window open changed for %s to %s", self._zoneName, is_open_window)

    def calculate_is_openwindow(self)->bool:
        if len(self._temperature_history)<=1:
            return False
        temp_diff= self._temperature_history[0]._temp - self._temperature_history[len(self._temperature_history)-1]._temp
        time_diff=self._temperature_history[len(self._temperature_history)-1]._temp_timestamp - self._temperature_history[0]._temp_timestamp
        #_LOGGER.info("calculating calculate_is_openwindow len:%s Dtemp:%s DTime:%s DSeconds:%s Steep:%s TargetSteep:%s", len(self._temperature_history), temp_diff, time_diff, time_diff.total_seconds(), temp_diff/time_diff.total_seconds(), self._steep)
        time_limit = max(self._timedelta, self._mintimedelta if self._mintimedelta is not None else self._timedelta)
        
        result = True
        if temp_diff < 0 or time_diff.total_seconds() == 0 or temp_diff/time_diff.total_seconds() <= self._steep or (time_diff <time_limit):
            result = False

        if result != self._is_open_window:
            _LOGGER.info("calculate_is_openwindow %s len:%s Dtemp:%s DTime:%s DSeconds:%s Steep:%s TargetSteep:%s", self._zoneName, len(self._temperature_history), temp_diff, time_diff, time_diff.total_seconds(), temp_diff/time_diff.total_seconds(), self._steep)

        return result

class TempAggregator():
    def __init__(self, name):
        self._name = name
        self._cur_temp_per_sensor = {}
        self.last_valid_temp_per_sensor = {}
        self.active_sensor = None
        self.default_failuresLimit = 3

    def set_cur_temp(self, sender_sensor, cur_temp):
        self._cur_temp_per_sensor[sender_sensor] = cur_temp
        if (is_temp_valid(cur_temp)):
            _LOGGER.debug("TempAggregator: set_cur_temp is_temp_valid %s: %s - %s", self._name, sender_sensor, cur_temp)
            self.last_valid_temp_per_sensor[sender_sensor] = {'sensor': sender_sensor, 'time': datetime.now(), 'value': cur_temp, 'failures': 0}
        else:
            if sender_sensor not in self.last_valid_temp_per_sensor:
                _LOGGER.debug("TempAggregator: set_cur_temp not valid and new %s: %s - %s", self._name, sender_sensor, cur_temp)
                self.last_valid_temp_per_sensor[sender_sensor] = {'sensor': sender_sensor, 'time': datetime.now(), 'value': cur_temp, 'failures': 1}
            else:
                _LOGGER.debug("TempAggregator: set_cur_temp not valid and existing %s: %s - %s", self._name, sender_sensor, cur_temp)
                self.last_valid_temp_per_sensor[sender_sensor]['failures'] = self.last_valid_temp_per_sensor[sender_sensor]['failures'] + 1

    def is_timetemp_valid(self, timeTemp, failuresLimit):
        time_limit = datetime.now()-timedelta(minutes=15)
        if is_temp_valid(timeTemp['value']) and timeTemp['time']>=time_limit and timeTemp['failures']<=failuresLimit:
            return True
        return False

    def getValidTimeTemp(self, sensor_name):
        if sensor_name is None:
            return None

        if sensor_name not in self.last_valid_temp_per_sensor:
            return None
            
        timeTemp = self.last_valid_temp_per_sensor[sensor_name]
        if self.is_timetemp_valid(timeTemp, self.default_failuresLimit):
            return timeTemp
        
        return None

    def get_cur_temp(self):
        if self._cur_temp_per_sensor and all(self.is_timetemp_valid(x, 0) for x in self.last_valid_temp_per_sensor.values()):
            mxval = max(self._cur_temp_per_sensor.values())
            _LOGGER.debug("TempAggregator: get_cur_temp all valid %s: %s", self._name, mxval)
            return mxval
            
        current_sensor_timetemp = self.getValidTimeTemp(self.active_sensor)
        if current_sensor_timetemp is not None:
            _LOGGER.debug("TempAggregator: get_cur_temp current_sensor_timetemp %s: %s", self._name, current_sensor_timetemp['value'])
            return current_sensor_timetemp['value']

        validSensors = list(filter(lambda mappedTimeTemp: self.is_timetemp_valid(mappedTimeTemp, self.default_failuresLimit), self.last_valid_temp_per_sensor.values()))

        validSensors.sort(key=lambda x: x['time'], reverse=True)
        if validSensors:
            oldActiveSensor = self.active_sensor
            self.active_sensor = validSensors[0]['sensor']
            _LOGGER.info("Active sensor temp changed %s: from %s to %s(%s)", self._name, oldActiveSensor, self.active_sensor, validSensors[0])
            return validSensors[0]['value']

        _LOGGER.info("TempAggregator: get_cur_temp None %s %s", self._name, self.last_valid_temp_per_sensor.values())
        return None

class ZoneDef():
    def __init__(self, friendly_name, sensor_entity_id, sensors_entity_id, target_entity_id, target_temp, name, openWindow):
        self._friendly_name = friendly_name or name
        self._sensors_entity_id = [sensor_entity_id] if sensor_entity_id is not None else sensors_entity_id
        self._target_entity_id = target_entity_id    
        self._name = name 
        self._target_temp = target_temp
        self._openWindow = openWindow
        if (self._openWindow):
            self._openWindow._zoneName = name
        self._saved_target_temp = None
        #if self._target_entity_id and (isinstance(self._target_entity_id, float) or isinstance(self._target_entity_id, int)):
        #    self._target_temp = float(self._target_entity_id);
        self._cur_temp_per_sensor = TempAggregator(name)

    def has_temp_sensor_defined(self):
        return self._sensors_entity_id is not None
        
    def get_sensors_entity_id_names(self):
        return (' '.join(self._sensors_entity_id)) if self._sensors_entity_id is not None else 'None'

    def is_cur_temp_valid(self):
        return is_temp_valid(self.get_cur_temp())

    def is_target_temp_valid(self):
        return is_temp_valid(self._target_temp)

    def get_cur_temp(self):
        return self._cur_temp_per_sensor.get_cur_temp()
        
    def set_cur_temp(self, sender_sensor, cur_temp):
        self._cur_temp_per_sensor.set_cur_temp(sender_sensor, cur_temp)
        if self._openWindow is not None:
            self._openWindow.add_temp(self.get_cur_temp())

    def is_zone_with_open_window(self) -> bool:
        if self._openWindow is None:
            return False
        return self._openWindow._is_open_window

class PresetDef():
    def __init__(self, friendly_name, zones, name, report_zone_name_instead_preset_name):
        self._friendly_name = friendly_name or name
        self._name = name 
        self._zones = zones
        self._report_zone_name_instead_preset_name = report_zone_name_instead_preset_name

    def get_zone_with_open_window(self):
        if (self._zones == None or len(self._zones)==0):
            return None
        return next((z._name for z in self._zones if z.is_zone_with_open_window()), None)

def parse_openwindow(config):
    if config is None:
        return None
    delta = config[CONF_DELTA_TEMP]
    deltaTime = config[CONF_DELTA_TIME]
    minDeltaTime = config[CONF_MIN_DELTA_TIME] if CONF_MIN_DELTA_TIME in config else None
    zoneReactDelay = config[CONF_ZONE_REACT_DELAY] if CONF_ZONE_REACT_DELAY in config else None
    
    return OpenWindowDef(delta, deltaTime, minDeltaTime, zoneReactDelay)

def parse_zones_dict(explicit_zones, default_openwindow):
    zones = []
    try:
        if explicit_zones:
            for key, z in explicit_zones.items():
                zones.append(ZoneDef(z[ATTR_FRIENDLY_NAME] if (ATTR_FRIENDLY_NAME in z) else None, 
                    z[CONF_SENSOR] if (CONF_SENSOR in z) else None, 
                    z[CONF_TEMP_SENSORS] if (CONF_TEMP_SENSORS in z) else None, 
                    z[CONF_TARGET_TEMP_SENSOR] if (CONF_TARGET_TEMP_SENSOR in z) else None, 
                    z[CONF_TARGET_TEMP] if (CONF_TARGET_TEMP in z) else None, 
                    key,
                    parse_openwindow(z[CONF_OPEN_WINDOW]) if (CONF_OPEN_WINDOW in z) else deepcopy(default_openwindow)))
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
    sensors_entity_id0 = config.get(CONF_TEMP_SENSORS)
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
    
    default_openwindow= parse_openwindow(config[CONF_OPEN_WINDOW]) if (CONF_OPEN_WINDOW in config) else None
    global_zone = list(filter(lambda z: (z.has_temp_sensor_defined()) and (not z._target_entity_id is None), [ZoneDef("Global", sensor_entity_id0, sensors_entity_id0, target_temp_sensor0, target_temp0, "GlobalZone", default_openwindow)]))

    zones = global_zone + parse_zones_dict(explicit_zones, default_openwindow)

    presets = list(filter(lambda p: len(p._zones) > 0, [PresetDef(PRESET_NONE, zones, PRESET_NONE, False)]))

    try:
        if explicit_presets:
            for key, p in explicit_presets.items():
                presets.append(PresetDef(p[ATTR_FRIENDLY_NAME] if (ATTR_FRIENDLY_NAME in p) else None, parse_zones_dict(p[ZONES], default_openwindow), key, p[CONF_REPORT_ZONE_NAME_INSTEAD_OF_PRESET_NAME] if (CONF_REPORT_ZONE_NAME_INSTEAD_OF_PRESET_NAME in p) else None))
    except ValueError as ex:
                _LOGGER.error("Unable to parse presets %s %s", explicit_presets, ex)
    except TypeError as ex:
                _LOGGER.error("Unable to parse presets %s %s", explicit_presets, ex)

    if len(presets) == 0:
        _LOGGER.error("No zones nor presets defined")

    for p in presets:
        _LOGGER.info("Preset: %s %s %s", p._name, p._friendly_name, p._report_zone_name_instead_preset_name)
        for z in p._zones:
            _LOGGER.debug("Zone: %s %s SensorId:%s Target:%s", z._name, z._friendly_name, z.get_sensors_entity_id_names(), z._target_entity_id)

    thermostat = MultizoneGenericThermostat(
        hass,
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

    async_add_entities(
        [
            thermostat,
            thermostat._isWindowOpenBinarySensor
        ]
    )

class MultizoneGenericThermostat(ClimateEntity, RestoreEntity):
    """Representation of a Multizone Generic Thermostat device."""

    def __init__(
        self,
        hass,
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
        self._isWindowOpenBinarySensor = IsWindowOpenSensor(hass, name)


    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        _LOGGER.info("async_added_to_hass. ")

        # Add listener
        for z in self._selected_preset._zones:
            if z._sensors_entity_id:
                for ts in z._sensors_entity_id:
                    self.async_on_remove(
                        async_track_state_change_event(
                            self.hass, [ts], self._async_sensor_changed
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

            obj = type('', (), {})()

            #for z in self._selected_preset._zones:
            #    sensor_state = self.hass.states.get(z._sensor_entity_id)
            #    obj.state = sensor_state

            #    #self._async_update_temp(z, obj)
            #    self.async_write_ha_state()

            #    if z._target_entity_id:
            #        sensor_state = self.hass.states.get(z._target_entity_id)
            #        obj.state = sensor_state
                    #self._async_update_target_temp(z, obj)
            #        self.async_write_ha_state()
            #self.async_write_ha_state()
            
            _LOGGER.debug("Initial set of target temps")
            for p in self._presets:
                _LOGGER.debug("Initial set of target temps for preset %s", p._friendly_name)
                for z in p._zones:
                    _LOGGER.debug("Initial set of target temps for preset %s Zone: %s | Target sensor id:%s", p._friendly_name, z._friendly_name, z._target_entity_id)
                    target_value = self.hass.states.get(z._target_entity_id)
                    _LOGGER.debug("Initial set of target temp: %s Zone: %s Target:%s Target Value:%s", p._friendly_name, z._friendly_name, z._target_entity_id, target_value)
                    self._async_update_target_temp(z, target_value)
                      
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
        _LOGGER.debug("current_temperature +++ %s - %s", self._ongoing_zone._name if self._ongoing_zone else 'None', self._selected_zone._name if self._selected_zone else 'None')
        cur_temp = (self._ongoing_zone or self._selected_zone).get_cur_temp()
        _LOGGER.debug("current_temperature is %s - %s - %s", self._ongoing_zone._name if self._ongoing_zone else 'None', self._selected_zone._name if self._selected_zone else 'None', cur_temp)
        return float(cur_temp) if is_temp_valid(cur_temp) else None

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
        target_temp = (self._ongoing_zone or self._selected_zone)._target_temp
        return float(target_temp) if is_temp_valid(target_temp) else None

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
        _LOGGER.debug("async_set_temperature. %s", temperature)

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
        if new_state is None:
            return
        
        #_LOGGER.info("_async_target_changed. %s", new_state.state)

        for p in self._presets:
            for z in p._zones:
                if z._target_entity_id == sender:
                    _LOGGER.debug("zone target value updated. %s: %s<%s", z._name, z._target_temp, new_state.state)
                    self._async_update_target_temp(z, new_state)
        await self._async_control_heating()
        self.async_write_ha_state()

    async def _async_sensor_changed(self, event):
        """Handle temperature changes."""
        sender = event.data.get("entity_id")
        new_state = event.data.get("new_state")
        if new_state is None:
            return
        
        # _LOGGER.info("_async_sensor_changed. %s", new_state.state)

        for p in self._presets:
            for z in p._zones:
                for ts in z._sensors_entity_id:
                    if ts == sender:
                        _LOGGER.debug("zone sensor value updated. %s-%s: %s<%s", z._name, sender, z._target_temp, new_state.state)
                        self._async_update_temp(z, sender, new_state)
        self._isWindowOpenBinarySensor.set_zone_with_window_open(self._selected_preset.get_zone_with_open_window())
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
            zone._target_temp = state.state
            _LOGGER.debug("zone target value updated. %s: - set %s<%s", zone._name, zone._target_temp, zone.get_cur_temp())
        except ValueError as ex:
            _LOGGER.error("Unable to update target temp %s from sensor: %s", z._name, ex)

    @callback
    def _async_update_temp(self, zone, sender_sensor, state):
        """Update thermostat with latest state from sensor."""
        try:
            _LOGGER.debug("zone sensor value updated.. %s-%s: - set %s<%s", zone._name, sender_sensor, zone._target_temp, state.state)
            zone.set_cur_temp(sender_sensor, state.state)
        except ValueError as ex:
            _LOGGER.error("Unable to update %s from sensor: %s", zone._name, ex)

    def select_worst_zone(self):
        if not self._ongoing_zone is None: 
            self._selected_zone = self._ongoing_zone
            return

        sortedZones =list(sorted(filter(lambda z: (z.is_cur_temp_valid()) and (z.is_target_temp_valid()) and (z._openWindow is None or (z._openWindow._zone_react_timestamp is None or z._openWindow._zone_react_timestamp<=datetime.now())), self._selected_preset._zones), key=lambda z: float(z.get_cur_temp())  - float(z._target_temp)))
        if len(sortedZones) > 0:
            selected_zone = sortedZones[0]
        else:
            selected_zone = self._selected_preset._zones[0]

        if self._selected_zone != selected_zone:
            _LOGGER.info("Selected zone changed from %s -> %s (%s<%s)", self._selected_zone._name, selected_zone._name, selected_zone._target_temp, selected_zone.get_cur_temp())
            self._selected_zone = selected_zone

    async def _async_control_heating(self, time=None, force=False):
        """Check if we need to turn heating on or off."""
        async with self._temp_lock:
            self.select_worst_zone()
            if not self._active and (self._selected_zone.is_cur_temp_valid()) and (self._selected_zone.is_target_temp_valid()):
                self._active = True
                _LOGGER.debug(
                    "Obtained current and target temperature. "
                    "Multizone generic thermostat active. %s < %s",
                    self._selected_zone._target_temp,
                    self._selected_zone.get_cur_temp(),
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

            isValidTemp = (self._selected_zone.is_cur_temp_valid()) and (self._selected_zone.is_target_temp_valid())
            
            if not isValidTemp:
                self._ongoing_zone = None
                self.select_worst_zone()
                _LOGGER.debug("_async_control_heating skipped because temps are invalid Zone:%s CurTemp:%s TargetTemp:%s", self._selected_zone._name, self._selected_zone.get_cur_temp(), self._selected_zone._target_temp)
                return
                
            target_temp_value = float(self._selected_zone._target_temp)
            cur_temp_value = float(self._selected_zone.get_cur_temp())

            too_cold = isValidTemp and (target_temp_value >= cur_temp_value + self._cold_tolerance)
            too_hot = isValidTemp and (cur_temp_value >= target_temp_value + self._hot_tolerance)
            if self._is_device_active:
                if (self.ac_mode and too_cold) or (not self.ac_mode and too_hot):
                    _LOGGER.info("Turning off heater %s %s (%s<%s)", self._selected_zone._name, self.heater_entity_id, target_temp_value, cur_temp_value)
                    self._ongoing_zone = None
                    self.select_worst_zone()
                    new_too_cold = target_temp_value >= cur_temp_value + self._cold_tolerance
                    new_too_hot = cur_temp_value >= target_temp_value + self._hot_tolerance
                    if (self.ac_mode and not new_too_hot) or (not self.ac_mode and not new_too_cold):
                        await self._async_heater_turn_off()
                    else:
                        _LOGGER.info("Not turning off heater because there is another zone too cold")
                elif time is not None:
                    # The time argument is passed only in keep-alive case
                    _LOGGER.debug(
                        "Keep-alive - Turning on heater heater %s",
                        self.heater_entity_id,
                    )

                    self._ongoing_zone = self._selected_zone
                    await self._async_heater_turn_on()
            else:
                if (self.ac_mode and too_hot) or (not self.ac_mode and too_cold):
                    _LOGGER.info("Turning on heater %s %s (%s<%s)", self._selected_zone._name, self.heater_entity_id, target_temp_value, cur_temp_value)

                    self._ongoing_zone = self._selected_zone
                    await self._async_heater_turn_on()
                elif time is not None:
                    # The time argument is passed only in keep-alive case
                    _LOGGER.debug(
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

        _LOGGER.info("async_set_preset_mode %s %s", self.heater_entity_id, preset_mode)

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
