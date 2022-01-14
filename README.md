# Notice

The component is used to create a thermostat that can control temperature in different zones, with the ability to set multiple profiles. It is based on the built-in Generic Thermostat provided with Home assistant

## Why?

The Generic thermostat allows control of Heater only based on a single input temperature input, and basd on a single target temperature. Also profiles are not supported (except a single away temperature). I tried vaious other ways to achieve same efects with generic thermostat but i just could not, and I decided to make my own componenet based on that

## What?

This repository contains multiple files. No description provided as they are self explanatory.
Only the content of the custom_components is needed on Home Assistant. The rest are additional examples/info

File | Purpose
-- | --
`.devcontainer/*` | Used for development/testing with VSCODE, more info in the readme file in that dir.
`.github/ISSUE_TEMPLATE/feature_request.md` | Template for Feature Requests
`.github/ISSUE_TEMPLATE/issue.md` | Template for issues
`.github/settings.yml` | Probot settings to control the repository settings.
`.vscode/tasks.json` | Tasks for the devcontainer.
`custom_components/multizone_generic_thermostat/__init__.py` | The component file for the integration.
`custom_components/multizone_generic_thermostat/manifest.json` | A [manifest file](https://developers.home-assistant.io/docs/en/creating_integration_manifest.html) for Home Assistant.
`CONTRIBUTING.md` | Guidelines on how to contribute.
`example.png` | Screenshot that demonstrate how it might look in the UI.
`info.md` | An example on a info file (used by [hacs][hacs]).
`LICENSE` | The license file for the project.
`README.md` | The file you are reading now, should contain info about the integration, installation and configuration instructions.
`requirements.txt` | Python packages used by this integration.
`requirements_dev.txt` | Python packages used to provide [IntelliSense](https://code.visualstudio.com/docs/editor/intellisense)/code hints during development of this integration, typically includes packages in `requirements.txt` but may include additional packages
`requirements_text.txt` | Python packages required to run the tests for this integration, typically includes packages in `requirements_dev.txt` but may include additional packages

## How?

How multizone works:
Lets assume we have the zones in the picture below. You can see that each zone/room has different target temperatures set and in config you can see that threshold is set to 0.5 degrees C. In each zone I have a temperature sensor, and there is just one central heating switch. 
- The open window detection will be calculated on each temperature update for a zone, and if the temperature difference in time interval exceds the one defined in config, then that specific zone is marked with the "is window open" flag, and he binary_sensor exposed by the thermostat is set to on. If a zone is marked with "is window open" and has the zone_react_delay config field set, then this zone will be ignored as a trigger for the heater/cooler for the period specified in the zone_react_delay. Be aware that delta_temp:2 delta_time:00:02:00  represents the same steep as delta_temp:10 delta_time:00:10:00 (whic is one degree per minute) but in second case the "is_window_open" detector will watch over a longer time window (10 minutes instead of 2) and this will cause the "is_window_open" flag to be set to off later than in the first case (Ex: in the first case (with 2C, 2 mins), if room temp is 22 and someone opens the window and temperature drops in 1 minute to 21 the the "is_window_open" flag is set to on, the temperature will keep dropping to 18 within next 5 minutes and then will stay there. In this case, after temperature dropped to 18, afte 2 more meanutes because there drastic temperature change anymore then the "is window open" will become off.)
- The heat will be turned on when at least one of the zones will have its current temperature under the lower threshold limit, and heater will maintain that zone active until the temperature in that area is bigger than the upper threshold limit. In this time, the termostat doesn't care about the other zones, because it tries to heat up this zone which becomes the active-locked one. 
- When the temperature in this zne passes the upper threshold limit:
	- a) if there is no other zone that has its current temperature under the lower limit threshold, the heating will be turned off;
	- b) if there is any other zone that has its current temperature under the lower threshold limit, then the heating will still be maintained as on until condition a) is met

When the heating is off, the component will automatically select as active the zone that has the lowest current temperature compared to its target limit. For example you can see in the picture that "dining" zone has a temperature of 19.2 and its limit is 19.5, and is the active zone whic means that this is the zone with lowest temperature relative to its limit, and is most probably the fist zone that will trigger the heating.

I use this multizone_generic_thermostat in combination with the automations to set different temperatures or presets based on time. Durin night I maintain a confortable temperature in the bedrooms and the rest of the rooms are set to minimum, during day I set confortable temperature in the dinign room and gaming room and lower in the bedrooms as noone will use them during day.

So, acordingly to the picture below, the heater will start as soon as temperature in the dining zone probably will pass below 19.0 (lower threshold = target is 19.5 minus 0.5 threshold), and will stop when temperature in that room will pass over 20 (upper threshold = target is 19.5 plus 0.5 threshold)

***
README content if this was a published component:
***

# multizone_generic_thermostat

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![hacs][hacsbadge]][hacs]
![Project Maintenance][maintenance-shield]
[![BuyMeCoffee][buymecoffeebadge]][buymecoffee]

[![Discord][discord-shield]][discord]
[![Community Forum][forum-shield]][forum]

_Component to integrate with [multizone_generic_thermostat][multizone_generic_thermostat]._

**This component will set up the following platforms.**

Platform | Description
-- | --
`climate` | Keep temperature within the specified limits, and can do this for multiple zones with different target temperatures and source temperature sensors. Also multiple profiles are supported

![example][exampleimg]

## Installation

1. Using the tool of choice open the directory (folder) for your HA configuration (where you find `configuration.yaml`).
2. If you do not have a `custom_components` directory (folder) there, you need to create it.
3. In the `custom_components` directory (folder) create a new folder called `multizone_generic_thermostat`.
4. Download _all_ the files from the `custom_components/multizone_generic_thermostat/` directory (folder) in this repository.
5. Place the files you downloaded in the new directory (folder) you created.
6. Restart Home Assistant
7. In the HA UI go to "Configuration" -> "Integrations" click "+" and search for "multizone_generic_thermostat"

Using your HA configuration directory (folder) as a starting point you should now also have this:

```text
custom_components/multizone_generic_thermostat/__init__.py
custom_components/multizone_generic_thermostat/climate.py
custom_components/multizone_generic_thermostat/manifest.json
custom_components/multizone_generic_thermostat/services.yaml
```

## Configuration is done in configuration.yaml
```text
input_number:
  min_ambiental_temperature:
    name: Min ambiental temperature
    initial: 21
    min: 14
    max: 25
    step: 0.1
    
  min_dining_temperature:
    name: Min dining temperature
    initial: 20
    min: 14
    max: 25
    step: 0.1
    
  min_kitchen_temperature:
    name: Min kitchen temperature
    initial: 20
    min: 14
    max: 25
    step: 0.1
    
  min_fabians_bedroom_temperature:
    name: Min Fabian's bedroom temperature
    initial: 20
    min: 14
    max: 25
    step: 0.1     
    
  min_small_bedroom_temperature:
    name: Min small bedroom temperature
    initial: 18
    min: 14
    max: 25
    step: 0.1        
    
  min_ioanas_bedroom_temperature:
    name: Min Ioana's bedroom temperature
    initial: 21
    min: 14
    max: 25
    step: 0.1  
    
climate:
  - platform: multizone_generic_thermostat
    name: Thermostat
    heater: switch.heating 
    presets:
        none:
            report_zone_name_instead_preset_name: true
            zones:
                ambiental:
                    target_sensor: sensor.thermostat_ambiental_temperature
                    target_temp_sensor: input_number.min_ambiental_temperature
                ambiental2:
                    target_sensor: sensor.thermostat_ambiental_temperature2
                    target_temp_sensor: input_number.min_ambiental_temperature
                dining:
                    target_sensor: sensor.dining_room_temperature
                    target_temp_sensor: input_number.min_dining_temperature
                kitchen:
                    target_sensor: sensor.kitchen_temperature
                    target_temp_sensor: input_number.min_kitchen_temperature
                kids_bedroom:
                    friendly_name: kids bedroom
                    target_sensor: sensor.kids_bedroom_temperature
                    target_temp_sensor: input_number.min_kids_bedroom_temperature
                small_bedroom:
                    friendly_name: small bedroom
                    target_sensor: sensor.small_bedroom_temperature
                    target_temp_sensor: input_number.min_small_bedroom_temperature
                gaming_room:
                    friendly_name: gaming room
                    target_sensor: sensor.gaming_room_temperature
                    target_temp_sensor: input_number.min_gaming_room_temperature
                    open_window:
                        delta_temp: 2
                        delta_time: 100
                        zone_react_delay: 00:10:00                    
                test:
                    target_sensor: input_number.test_temperature
                    target_temp_sensor: input_number.min_test_temperature
                test2:
                    target_sensor: input_number.test_temperature2
                    target_temp_sensor: input_number.min_test_temperature2
    open_window:
        delta_temp: 2
        min_delta_time: 60
        delta_time: 180
        zone_react_delay: 00:10:00
    min_temp: 17
    max_temp: 25
    ac_mode: false
    #target_temp: 22.5
    cold_tolerance: 0.5
    hot_tolerance: 0.5
    min_cycle_duration:
      seconds: 10
    keep_alive:
      minutes: 3
    initial_hvac_mode: "heat"
    away_temp: 22
    precision: 0.1     
```	
<!---->

Additionally I added inside pyscript a script to be used with pyscript addon. This script can be used to automate much easier target temperatures per each room per each day of the week/per whatever time intervals you want.

For example, I want every weekday at 7 AM to heat up little bit my son's room to be warmer when he dresses for school.
At 7:40 when he should be gone to school already, I change it down back to lower temperature. Etc...

Install pyscript integration. Copy the pyscript/thermostatautomation.py onto your homeassistant pyscript folder (if folder is missing, create pyscript folder on the same level with your configuration.yaml smd place the thermostatautomation.py file inside this folder)

## Contributions are welcome!

If you want to contribute to this please read the [Contribution guidelines](CONTRIBUTING.md)

***

[multizone_generic_thermostat]: https://github.com/tpacri/multizone_generic_thermostat
[buymecoffee]: https://www.buymeacoffee.com/tpacri
[buymecoffeebadge]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=for-the-badge
[commits-shield]: https://img.shields.io/github/commit-activity/y/tpacri/multizone_generic_thermostat.svg?style=for-the-badge
[commits]: https://github.com/tpacri/multizone_generic_thermostat/commits/main
[hacs]: https://github.com/custom-components/hacs
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[discord]: https://discord.gg/Qa5fW2R
[discord-shield]: https://img.shields.io/discord/330944238910963714.svg?style=for-the-badge
[exampleimg]: example.png
[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg?style=for-the-badge
[forum]: https://community.home-assistant.io/
[license-shield]: https://img.shields.io/github/license/tpacri/multizone_generic_thermostat.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-tpacri-blue.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/tpacri/multizone_generic_thermostat.svg?style=for-the-badge
[releases]: https://github.com/tpacri/multizone_generic_thermostat/releases
