import asyncio
import logging

import voluptuous as vol

from datetime import timedelta
from datetime import datetime

from homeassistant.components.binary_sensor import PLATFORM_SCHEMA, ENTITY_ID_FORMAT, BinarySensorDeviceClass
from homeassistant.helpers.entity import async_generate_entity_id

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


try:
    from homeassistant.components.binary_sensor import BinarySensorEntity
except ImportError:
    from homeassistant.components.binary_sensor import (
        BinarySensorDevice as BinarySensorEntity,
    )
from . import DOMAIN, PLATFORMS
from typing import Any, Dict

_LOGGER = logging.getLogger(__name__)


class IsWindowOpenSensor(BinarySensorEntity):
    def __init__(self, hass, name):
        uid = f"{name}_is_window_open"
        self.entity_id = async_generate_entity_id(ENTITY_ID_FORMAT, uid, hass=hass)
        self._name = uid
        self.zone_with_window_open = None
        self.custom_attributes = {}

    @property
    def is_on(self):
        return self.zone_with_window_open != None
        
    @property
    def zone_name(self):
        return self.zone_with_window_open
        
    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {'zone': self.zone_with_window_open}        

    @property
    def device_class(self):
        """Return device_class."""
        return BinarySensorDeviceClass.OPENING

    @property
    def icon(self):
        """Return icon."""
        return "mdi:window-open" if self.is_on else "mdi:window-closed"

    @property
    def name(self):
        """Return name."""
        return self._name

    def set_zone_with_window_open(self, zone):
        if zone != self.zone_with_window_open:
            self.zone_with_window_open = zone           
            
            self.async_write_ha_state()
#    @asyncio.coroutine
#    async def async_update(self):
#        pass
