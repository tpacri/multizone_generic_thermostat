import asyncio
import logging

import voluptuous as vol

from datetime import timedelta
from datetime import datetime

from homeassistant.components.binary_sensor import PLATFORM_SCHEMA, ENTITY_ID_FORMAT, DEVICE_CLASS_OPENING
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
        self._is_window_open = False

    @property
    def is_on(self):
        return self._is_window_open

    @property
    def device_class(self):
        """Return device_class."""
        return DEVICE_CLASS_OPENING

    @property
    def icon(self):
        """Return icon."""
        return "mdi:window-open" if self.is_on else "mdi:window-closed"

    @property
    def name(self):
        """Return name."""
        return self._name

    def set_is_window_open(self, value):
        if value != self._is_window_open:
            self._is_window_open = value
            self.async_write_ha_state()

#    @asyncio.coroutine
#    async def async_update(self):
#        pass
