# Utilities for integration with Home Assistant
# Thanks to molobrakos

import logging
from datetime import datetime
from skodaconnect.utilities import camel2slug

_LOGGER = logging.getLogger(__name__)

class Instrument:
    def __init__(self, component, attr, name, icon=None):
        self.attr = attr
        self.component = component
        self.name = name
        self.vehicle = None
        self.icon = icon
        self.callback = None

    def __repr__(self):
        return self.full_name

    def configurate(self, **args):
        pass

    @property
    def slug_attr(self):
        return camel2slug(self.attr.replace(".", "_"))

    def setup(self, vehicle, **config):
        self.vehicle = vehicle
        try:
            if not self.is_supported:
                return False
        except:
            return False

        self.configurate(**config)
        return True

    @property
    def vehicle_name(self):
        return self.vehicle.vin

    @property
    def full_name(self):
        return f"{self.vehicle_name} {self.name}"

    @property
    def is_mutable(self):
        raise NotImplementedError("Must be set")

    @property
    def str_state(self):
        return self.state

    @property
    def state(self):
        if hasattr(self.vehicle, self.attr):
            return getattr(self.vehicle, self.attr)
        else:
            _LOGGER.debug(f'Could not find attribute "{self.attr}"')
        return self.vehicle.get_attr(self.attr)

    @property
    def attributes(self):
        return {}

    @property
    def is_supported(self):
        supported = 'is_' + self.attr + "_supported"
        if hasattr(self.vehicle, supported):
            return getattr(self.vehicle, supported)
        else:
            return False


class Sensor(Instrument):
    def __init__(self, attr, name, icon, unit=None, device_class=None):
        super().__init__(component="sensor", attr=attr, name=name, icon=icon)
        self.device_class = device_class
        self.unit = unit
        self.convert = False

    def configurate(self, **config):
        if self.unit and config.get('miles', False) is True:
            if "km" == self.unit:
                self.unit = "mi"
                self.convert = True
            elif "km/h" == self.unit:
                self.unit = "mi/h"
                self.convert = True
            elif "l/100 km" == self.unit:
                self.unit = "mpg"
                self.convert = True
            elif "kWh/100 km" == self.unit:
                self.unit = "kWh/100 mi"
                self.convert = True
        elif self.unit and config.get('scandinavian_miles', False) is True:
            if "km" == self.unit:
                self.unit = "mil"
            elif "km/h" == self.unit:
                self.unit = "mil/h"
            elif "l/100 km" == self.unit:
                self.unit = "l/mil"
            elif "kWh/100 km" == self.unit:
                self.unit = "kWh/mil"

        # Init placeholder for parking heater duration
        config.get('parkingheater', 30)
        if "pheater_duration" == self.attr:
            setValue = config.get('climatisation_duration', 30)
            self.vehicle.pheater_duration = setValue

    @property
    def is_mutable(self):
        return False

    @property
    def str_state(self):
        if self.unit:
            return f'{self.state} {self.unit}'
        else:
            return f'{self.state}'

    @property
    def state(self):
        val = super().state
        if val and self.unit and "mi" in self.unit and self.convert is True:
            return int(round(val / 1.609344))
        elif val and self.unit and "mi/h" in self.unit and self.convert is True:
            return int(round(val / 1.609344))
        elif val and self.unit and "mpg" in self.unit and self.convert is True:
            return round(val * 235.215, 1)
        elif val and self.unit and "kWh/100 mi" in self.unit and self.convert is True:
            return round(val * 0.4251438, 1)
        elif val and self.unit and "°F" in self.unit and self.convert is True:
            temp = round((val * 9 / 5) + 32, 1)
            return temp
        elif val and self.unit in ['mil', 'mil/h', 'l/mil', 'kWh/mil']:
            return val / 10
        else:
            return val


class BinarySensor(Instrument):
    def __init__(self, attr, name, device_class, icon='', reverse_state=False):
        super().__init__(component="binary_sensor", attr=attr, name=name, icon=icon)
        self.device_class = device_class
        self.reverse_state = reverse_state

    @property
    def is_mutable(self):
        return False

    @property
    def str_state(self):
        if self.device_class in ["door", "window"]:
            return "Closed" if self.state else "Open"
        if self.device_class == "lock":
            return "Locked" if self.state else "Unlocked"
        if self.device_class == "safety":
            return "Warning!" if self.state else "OK"
        if self.device_class == "plug":
            return "Connected" if self.state else "Disconnected"
        if self.state is None:
            _LOGGER.error(f"Can not encode state {self.attr} {self.state}")
            return "?"
        return "On" if self.state else "Off"

    @property
    def state(self):
        val = super().state

        if isinstance(val, (bool, list)):
            if self.reverse_state:
                if bool(val):
                    return False
                else:
                    return True
            else:
                return bool(val)
        elif isinstance(val, str):
            return val != "Normal"
        return val

    @property
    def is_on(self):
        return self.state


class Switch(Instrument):
    def __init__(self, attr, name, icon):
        super().__init__(component="switch", attr=attr, name=name, icon=icon)

    @property
    def is_mutable(self):
        return True

    @property
    def str_state(self):
        return "On" if self.state else "Off"

    def is_on(self):
        return self.state

    def turn_on(self):
        pass

    def turn_off(self):
        pass

    @property
    def assumed_state(self):
        return True


class Climate(Instrument):
    def __init__(self, attr, name, icon):
        super().__init__(component="climate", attr=attr, name=name, icon=icon)

    @property
    def hvac_mode(self):
        pass

    @property
    def target_temperature(self):
        pass

    def set_temperature(self, **kwargs):
        pass

    def set_hvac_mode(self, hvac_mode):
        pass


class ElectricClimatisationClimate(Climate):
    def __init__(self):
        super().__init__(attr="electric_climatisation", name="Electric Climatisation", icon="mdi:radiator")

    @property
    def hvac_mode(self):
        return self.vehicle.electric_climatisation

    @property
    def target_temperature(self):
        return self.vehicle.climatisation_target_temperature

    async def set_temperature(self, temperature):
        await self.vehicle.climatisation_target(temperature)

    async def set_hvac_mode(self, hvac_mode):
        if hvac_mode:
            await self.vehicle.climatisation('electric')
        else:
            await self.vehicle.climatisation('off')


class CombustionClimatisationClimate(Climate):
    def __init__(self):
        super().__init__(attr="pheater_heating", name="Parking Heater Climatisation", icon="mdi:radiator")

    def configurate(self, **config):
        self.spin = config.get('spin', '')
        self.duration = config.get('combustionengineheatingduration', 30)

    @property
    def hvac_mode(self):
        return self.vehicle.pheater_heating

    @property
    def target_temperature(self):
        return self.vehicle.climatisation_target_temperature

    async def set_temperature(self, temperature):
        await self.vehicle.setClimatisationTargetTemperature(temperature)

    async def set_hvac_mode(self, hvac_mode):
        if hvac_mode:
            await self.vehicle.pheater_climatisation(spin=self.spin, duration=self.duration, mode='heating')
        else:
            await self.vehicle.pheater_climatisation(spin=self.spin, mode='off')


class Position(Instrument):
    def __init__(self):
        super().__init__(component="device_tracker", attr="position", name="Position")

    @property
    def is_mutable(self):
        return False

    @property
    def state(self):
        state = super().state #or {}
        return (
            state.get("lat", "?"),
            state.get("lng", "?"),
            state.get("timestamp", None),
        )

    @property
    def str_state(self):
        state = super().state #or {}
        ts = state.get("timestamp", None)
        if isinstance(ts, str):
            time = str(datetime.strptime(ts,'%Y-%m-%dT%H:%M:%SZ').astimezone(tz=None))
        elif isinstance(ts, datetime):
            time = str(ts.astimezone(tz=None))
        else:
            time = None
        return (
            state.get("lat", "?"),
            state.get("lng", "?"),
            time,
        )


class DoorLock(Instrument):
    def __init__(self):
        super().__init__(component="lock", attr="door_locked", name="Door locked", icon="mdi:car-door-lock")

    def configurate(self, **config):
        self.spin = config.get('spin', '')

    @property
    def is_mutable(self):
        return True

    @property
    def str_state(self):
        return "Locked" if self.state else "Unlocked"

    @property
    def state(self):
        return self.vehicle.door_locked

    @property
    def is_locked(self):
        return self.state

    async def lock(self):
        try:
            response = await self.vehicle.set_lock('lock', self.spin)
            await self.vehicle.update()
            if self.callback is not None:
                self.callback()
            return response
        except Exception as e:
            _LOGGER.error(f"Lock failed: {e}")
            return False

    async def unlock(self):
        try:
            response = await self.vehicle.set_lock('unlock', self.spin)
            await self.vehicle.update()
            if self.callback is not None:
                self.callback()
            return response
        except Exception as e:
            _LOGGER.error(f"Unlock failed: {e}")
            return False

    @property
    def attributes(self):
        return {
            'last_result': self.vehicle.lock_action_status,
            'last_timestamp': self.vehicle.lock_action_timestamp
        }


class TrunkLock(Instrument):
    def __init__(self):
        super().__init__(component="lock", attr="trunk_locked", name="Trunk locked")

    @property
    def is_mutable(self):
        return True

    @property
    def str_state(self):
        return "Locked" if self.state else "Unlocked"

    @property
    def state(self):
        return self.vehicle.trunk_locked

    @property
    def is_locked(self):
        return self.state

    async def lock(self):
        return None

    async def unlock(self):
        return None

# Switches
class RequestHonkAndFlash(Switch):
    def __init__(self):
        super().__init__(attr="request_honkandflash", name="Start honking and flashing", icon="mdi:car-emergency")

    @property
    def state(self):
        return self.vehicle.request_honkandflash

    async def turn_on(self):
        await self.vehicle.set_honkandflash('honkandflash')
        await self.vehicle.update()
        if self.callback is not None:
            self.callback()

    async def turn_off(self):
        pass

    @property
    def assumed_state(self):
        return False

    @property
    def attributes(self):
        return {
            'last_result': self.vehicle.honkandflash_action_status,
            'last_timestamp': self.vehicle.honkandflash_action_timestamp
        }

class RequestFlash(Switch):
    def __init__(self):
        super().__init__(attr="request_flash", name="Start flashing", icon="mdi:car-parking-lights")

    @property
    def state(self):
        return self.vehicle.request_flash

    async def turn_on(self):
        await self.vehicle.set_honkandflash('flash')
        await self.vehicle.update()
        if self.callback is not None:
            self.callback()

    async def turn_off(self):
        pass

    @property
    def assumed_state(self):
        return False

    @property
    def attributes(self):
        return {
            'last_result': self.vehicle.honkandflash_action_status,
            'last_timestamp': self.vehicle.honkandflash_action_timestamp
        }

class RequestUpdate(Switch):
    def __init__(self):
        super().__init__(attr="refresh_data", name="Force data refresh", icon="mdi:car-connected")

    @property
    def state(self):
        if self.vehicle.refresh_data is None:
            return False
        else:
            return self.vehicle.refresh_data

    async def turn_on(self):
        await self.vehicle.set_refresh()
        await self.vehicle.update()
        if self.callback is not None:
            self.callback()

    async def turn_off(self):
        pass

    @property
    def assumed_state(self):
        return False

    @property
    def attributes(self):
        return {
            'last_result': self.vehicle.refresh_action_status,
            'last_timestamp': self.vehicle.refresh_action_timestamp
        }

class ElectricClimatisation(Switch):
    def __init__(self):
        super().__init__(attr="electric_climatisation", name="Electric Climatisation", icon="mdi:radiator")

    @property
    def state(self):
        return self.vehicle.electric_climatisation

    async def turn_on(self):
        await self.vehicle.set_climatisation(mode = 'electric')
        await self.vehicle.update()

    async def turn_off(self):
        await self.vehicle.set_climatisation(mode = 'off')
        await self.vehicle.update()

    @property
    def assumed_state(self):
        return False

    @property
    def attributes(self):
        attrs = {}
        if self.vehicle.is_electric_climatisation_attributes_supported:
            attrs = self.vehicle.electric_climatisation_attributes
            attrs['last_result'] = self.vehicle.climater_action_status
            attrs['last_timestamp'] = self.vehicle.climater_action_timestamp
        else:
            attrs['last_result'] = self.vehicle.climater_action_status
            attrs['last_timestamp'] = self.vehicle.climater_action_timestamp
        return attrs

class AuxiliaryClimatisation(Switch):
    def __init__(self):
        super().__init__(attr="auxiliary_climatisation", name="Auxiliary Climatisation", icon="mdi:radiator")

    def configurate(self, **config):
        self.spin = config.get('spin', '')

    @property
    def state(self):
        return self.vehicle.auxiliary_climatisation

    async def turn_on(self):
        await self.vehicle.set_climatisation(mode = 'auxiliary', spin = self.spin)
        await self.vehicle.update()

    async def turn_off(self):
        await self.vehicle.set_climatisation(mode = 'off')
        await self.vehicle.update()

    @property
    def assumed_state(self):
        return False

    @property
    def attributes(self):
        return {
            'last_result': self.vehicle.climater_action_status,
            'last_timestamp': self.vehicle.climater_action_timestamp
        }

class Charging(Switch):
    def __init__(self):
        super().__init__(attr="charging", name="Charging", icon="mdi:battery")

    @property
    def state(self):
        return self.vehicle.charging

    async def turn_on(self):
        await self.vehicle.set_charger('start')
        await self.vehicle.update()

    async def turn_off(self):
        await self.vehicle.set_charger('stop')
        await self.vehicle.update()

    @property
    def assumed_state(self):
        return False

    @property
    def attributes(self):
        return {
            'last_result': self.vehicle.charger_action_status,
            'last_timestamp': self.vehicle.charger_action_timestamp
        }

class MaxChargeCurrent(Switch):
    def __init__(self):
        super().__init__(attr="charge_max_ampere", name="Max Charge Current", icon="mdi:battery-charging-outline")

    @property
    def state(self):
        # Check charge max ampere valuel. Return True if set to maximum
        # Return False (Off) for all other values
        value = self.vehicle.charge_max_ampere
        if isinstance(value, str):
            return True if value.lower() == 'maximum' else False
        elif isinstance(value, int):
            return True if value == 254 else False
        return False

    async def turn_on(self):
        await self.vehicle.set_charger_current('Maximum')
        await self.vehicle.update()

    async def turn_off(self):
        await self.vehicle.set_charger_current('Reduced')
        await self.vehicle.update()

    @property
    def assumed_state(self):
        return False

    @property
    def attributes(self):
        return {
            'charge_current': self.vehicle.charge_max_ampere,
            'last_result': self.vehicle.charger_action_status,
            'last_timestamp': self.vehicle.charger_action_timestamp
        }

class PlugAutoUnlock(Switch):
    def __init__(self):
        super().__init__(attr="plug_autounlock", name="Plug Auto Unlock", icon="mdi:battery-lock")

    @property
    def state(self):
        return self.vehicle.plug_autounlock

    async def turn_on(self):
        await self.vehicle.set_plug_autounlock('Permanent')
        await self.vehicle.update()

    async def turn_off(self):
        await self.vehicle.set_plug_autounlock('Off')
        await self.vehicle.update()

    @property
    def assumed_state(self):
        return False

    @property
    def attributes(self):
        return {
            'last_result': self.vehicle.charger_action_status,
            'last_timestamp': self.vehicle.charger_action_timestamp
        }

class WindowHeater(Switch):
    def __init__(self):
        super().__init__(attr="window_heater", name="Window Heater", icon="mdi:car-defrost-rear")

    @property
    def state(self):
        return self.vehicle.window_heater

    async def turn_on(self):
        await self.vehicle.set_window_heating('start')
        await self.vehicle.update()

    async def turn_off(self):
        await self.vehicle.set_window_heating('stop')
        await self.vehicle.update()

    @property
    def assumed_state(self):
        return False

    @property
    def attributes(self):
        return {
            'last_result': self.vehicle.climater_action_status,
            'last_timestamp': self.vehicle.climater_action_timestamp,
            "Front":self.vehicle.window_heater_attributes.get("Front", ''),
            "Rear": self.vehicle.window_heater_attributes.get("Rear", '')
        }

class WindowHeaterNew(Switch):
    def __init__(self):
        super().__init__(attr="window_heater_new", name="Window Heater", icon="mdi:car-defrost-rear")

    @property
    def state(self):
        return self.vehicle.window_heater_new

    async def turn_on(self):
        await self.vehicle.set_window_heating('start')
        await self.vehicle.update()

    async def turn_off(self):
        await self.vehicle.set_window_heating('stop')
        await self.vehicle.update()

    @property
    def assumed_state(self):
        return False

    @property
    def attributes(self):
        return {
            'last_result': self.vehicle.climater_action_status,
            'last_timestamp': self.vehicle.climater_action_timestamp,
            "Front":self.vehicle.window_heater_attributes.get("Front", ''),
            "Rear": self.vehicle.window_heater_attributes.get("Rear", '')
        }

class ClimatisationWindowHeat(Switch):
    def __init__(self):
        super().__init__(attr="climatisation_window_heat", name="Climatisation Window Heat", icon="mdi:car-defrost-rear")

    @property
    def state(self):
        return self.vehicle.climatisation_window_heat

    async def turn_on(self):
        await self.vehicle.set_window_heating('enabled')
        await self.vehicle.update()

    async def turn_off(self):
        await self.vehicle.set_window_heating('disabled')
        await self.vehicle.update()

    @property
    def assumed_state(self):
        return False

    @property
    def attributes(self):
        return {
            'last_result': self.vehicle.climater_action_status,
            'last_timestamp': self.vehicle.climater_action_timestamp,
            "Front":self.vehicle.window_heater_attributes.get("Front", ''),
            "Rear": self.vehicle.window_heater_attributes.get("Rear", '')
        }

class AuxHeaterDeparture(Switch):
    def __init__(self):
        super().__init__(attr="aux_heater_for_departure", name="Allow aux heater next departure", icon="mdi:car-defrost-rear")

    def configurate(self, **config):
        self.spin = config.get('spin', '')

    @property
    def state(self):
        return self.vehicle.aux_heater_for_departure

    async def turn_on(self):
        await self.vehicle.set_heatersource(source='automatic', spin=self.spin)
        await self.vehicle.update()

    async def turn_off(self):
        await self.vehicle.set_heatersource(source='electric')
        await self.vehicle.update()

    @property
    def assumed_state(self):
        return False

    @property
    def attributes(self):
        return {
            'last_result': self.vehicle.timer_action_status,
            'last_timestamp': self.vehicle.timer_action_timestamp,
        }

class SeatHeatingFrontLeft(Switch):
    def __init__(self):
        super().__init__(attr="seat_heating_front_left", name="Seat heating front left", icon="mdi:seat-recline-normal")

    @property
    def state(self):
        return self.vehicle.seat_heating_front_left

    async def turn_on(self):
        await self.vehicle.set_seat_heating('frontLeft', 'enable')
        await self.vehicle.update()

    async def turn_off(self):
        await self.vehicle.set_seat_heating('frontLeft', 'disable')
        await self.vehicle.update()

    @property
    def assumed_state(self):
        return False

    @property
    def attributes(self):
        return {
            'last_result': self.vehicle.aircon_action_status,
            'last_timestamp': self.vehicle.aircon_action_timestamp
        }

class SeatHeatingFrontRight(Switch):
    def __init__(self):
        super().__init__(attr="seat_heating_front_right", name="Seat heating front right", icon="mdi:seat-recline-normal")

    @property
    def state(self):
        return self.vehicle.seat_heating_front_right

    async def turn_on(self):
        await self.vehicle.set_seat_heating('frontRight', 'enable')
        await self.vehicle.update()

    async def turn_off(self):
        await self.vehicle.set_seat_heating('frontRight', 'disable')
        await self.vehicle.update()

    @property
    def assumed_state(self):
        return False

    @property
    def attributes(self):
        return {
            'last_result': self.vehicle.aircon_action_status,
            'last_timestamp': self.vehicle.aircon_action_timestamp
        }

class SeatHeatingRearLeft(Switch):
    def __init__(self):
        super().__init__(attr="seat_heating_rear_left", name="Seat heating rear left", icon="mdi:seat-recline-normal")

    @property
    def state(self):
        return self.vehicle.seat_heating_rear_left

    async def turn_on(self):
        await self.vehicle.set_seat_heating('rearLeft', 'enable')
        await self.vehicle.update()

    async def turn_off(self):
        await self.vehicle.set_seat_heating('rearLeft', 'disable')
        await self.vehicle.update()

    @property
    def assumed_state(self):
        return False

    @property
    def attributes(self):
        return {
            'last_result': self.vehicle.aircon_action_status,
            'last_timestamp': self.vehicle.aircon_action_timestamp
        }

class SeatHeatingRearRight(Switch):
    def __init__(self):
        super().__init__(attr="seat_heating_rear_right", name="Seat heating rear right", icon="mdi:seat-recline-normal")

    @property
    def state(self):
        return self.vehicle.seat_heating_rear_right

    async def turn_on(self):
        await self.vehicle.set_seat_heating('rearRight', 'enable')
        await self.vehicle.update()

    async def turn_off(self):
        await self.vehicle.set_seat_heating('rearRight', 'disable')
        await self.vehicle.update()

    @property
    def assumed_state(self):
        return False

    @property
    def attributes(self):
        return {
            'last_result': self.vehicle.aircon_action_status,
            'last_timestamp': self.vehicle.aircon_action_timestamp
        }

class AirConditionAtUnlock(Switch):
    def __init__(self):
        super().__init__(attr="aircon_at_unlock", name="Air-conditioning at unlock", icon="mdi:power-plug")

    @property
    def state(self):
        return self.vehicle.aircon_at_unlock

    async def turn_on(self):
        await self.vehicle.set_aircon_at_unlock(True)
        await self.vehicle.update()

    async def turn_off(self):
        await self.vehicle.set_aircon_at_unlock(False)
        await self.vehicle.update()

    @property
    def assumed_state(self):
        return False

    @property
    def attributes(self):
        return {
            'last_result': self.vehicle.aircon_action_status,
            'last_timestamp': self.vehicle.aircon_action_timestamp
        }

class BatteryClimatisation(Switch):
    def __init__(self):
        super().__init__(attr="climatisation_without_external_power", name="Climatisation from battery", icon="mdi:power-plug")

    @property
    def state(self):
        return self.vehicle.climatisation_without_external_power

    async def turn_on(self):
        await self.vehicle.set_battery_climatisation(True)
        await self.vehicle.update()

    async def turn_off(self):
        await self.vehicle.set_battery_climatisation(False)
        await self.vehicle.update()

    @property
    def assumed_state(self):
        return False

    @property
    def attributes(self):
        return {
            'last_result': self.vehicle.climater_action_status,
            'last_timestamp': self.vehicle.climater_action_timestamp
        }

class PHeaterHeating(Switch):
    def __init__(self):
        super().__init__(attr="pheater_heating", name="Parking Heater Heating", icon="mdi:radiator")

    def configurate(self, **config):
        self.spin = config.get('spin', '')
        self.duration = config.get('combustionengineheatingduration', 30)

    @property
    def state(self):
        return self.vehicle.pheater_heating

    async def turn_on(self):
        await self.vehicle.set_pheater(mode='heating', spin=self.spin)
        await self.vehicle.update()

    async def turn_off(self):
        await self.vehicle.set_pheater(mode='off', spin=self.spin)
        await self.vehicle.update()

    @property
    def assumed_state(self):
        return False

    @property
    def attributes(self):
        return {
            'last_result': self.vehicle.pheater_action_status,
            'last_timestamp': self.vehicle.pheater_action_timestamp
        }

class PHeaterVentilation(Switch):
    def __init__(self):
        super().__init__(attr="pheater_ventilation", name="Parking Heater Ventilation", icon="mdi:radiator")

    def configurate(self, **config):
        self.spin = config.get('spin', '')
        self.duration = config.get('combustionengineclimatisationduration', 30)

    @property
    def state(self):
        return self.vehicle.pheater_ventilation

    async def turn_on(self):
        await self.vehicle.set_pheater(mode='ventilation', spin=self.spin)
        await self.vehicle.update()

    async def turn_off(self):
        await self.vehicle.set_pheater(mode='off', spin=self.spin)
        await self.vehicle.update()

    @property
    def assumed_state(self):
        return False

    @property
    def attributes(self):
        return {
            'last_result': self.vehicle.pheater_action_status,
            'last_timestamp': self.vehicle.pheater_action_timestamp
        }

class DepartureTimer1(Switch):
    def __init__(self):
        super().__init__(attr="departure1", name="Departure timer 1", icon="mdi:radiator")

    def configurate(self, **config):
        self.spin = config.get('spin', '')

    @property
    def state(self):
        status1 = self.vehicle.departure1.get("timerProgrammedStatus", "")
        status2 = self.vehicle.departure1.get("enabled", False)
        if status1 == "programmed":
            return True
        elif status2 is True:
            return True
        else:
            return False

    async def turn_on(self):
        await self.vehicle.set_timer_active(id=1, action="on")
        await self.vehicle.update()

    async def turn_off(self):
        await self.vehicle.set_timer_active(id=1, action="off")
        await self.vehicle.update()

    @property
    def assumed_state(self):
        return False

    @property
    def attributes(self):
        return dict(self.vehicle.departure1)

class DepartureTimer2(Switch):
    def __init__(self):
        super().__init__(attr="departure2", name="Departure timer 2", icon="mdi:radiator")

    def configurate(self, **config):
        self.spin = config.get('spin', '')

    @property
    def state(self):
        status1 = self.vehicle.departure2.get("timerProgrammedStatus", "")
        status2 = self.vehicle.departure2.get("enabled", False)
        if status1 == "programmed":
            return True
        elif status2 is True:
            return True
        else:
            return False

    async def turn_on(self):
        await self.vehicle.set_timer_active(id=2, action="on")
        await self.vehicle.update()

    async def turn_off(self):
        await self.vehicle.set_timer_active(id=2, action="off")
        await self.vehicle.update()

    @property
    def assumed_state(self):
        return False

    @property
    def attributes(self):
        return dict(self.vehicle.departure2)

class DepartureTimer3(Switch):
    def __init__(self):
        super().__init__(attr="departure3", name="Departure timer 3", icon="mdi:radiator")

    def configurate(self, **config):
        self.spin = config.get('spin', '')

    @property
    def state(self):
        status1 = self.vehicle.departure3.get("timerProgrammedStatus", "")
        status2 = self.vehicle.departure3.get("enabled", False)
        if status1 == "programmed":
            return True
        elif status2 is True:
            return True
        else:
            return False

    async def turn_on(self):
        await self.vehicle.set_timer_active(id=3, action="on")
        await self.vehicle.update()

    async def turn_off(self):
        await self.vehicle.set_timer_active(id=3, action="off")
        await self.vehicle.update()

    @property
    def assumed_state(self):
        return False

    @property
    def attributes(self):
        return dict(self.vehicle.departure3)


class RequestResults(Sensor):
    def __init__(self):
        super().__init__(attr="request_results", name="Request results", icon="mdi:chat-alert", unit=None)

    @property
    def state(self):
        if self.vehicle.request_results.get('state', False):
            return self.vehicle.request_results.get('state')
        return 'N/A'

    @property
    def assumed_state(self):
        return False

    @property
    def attributes(self):
        return dict(self.vehicle.request_results)

class ChargingPower(Sensor):
    def __init__(self):
        super().__init__(attr="charging_power", name="Charging Power", icon="mdi:flash", unit="W", device_class="power")

    @property
    def state(self):
        return self.vehicle.charging_power

    @property
    def assumed_state(self):
        return False

    @property
    def attributes(self):
        values = {
            "max_power": self.vehicle.max_charging_power
        }
        return values

class CarInfo(Sensor):
    def __init__(self):
        super().__init__(attr="model", name="Car Info", icon="mdi:information-outline", unit=None)

    @property
    def state(self):
        return self.vehicle.vin

    @property
    def assumed_state(self):
        return False

    @property
    def attributes(self):
        values = {}
        if self.vehicle.is_engine_capacity_supported:
            values['engine'] = {
                "type": self.vehicle.engine_type,
                "power_in_kw": self.vehicle.engine_power,
                "capacity_in_liter": self.vehicle.engine_capacity
            }
        else:
            if self.vehicle.is_battery_capacity_supported:
                values['engine'] = {
                    "engine_type": self.vehicle.engine_type,
                    "power_in_kw": self.vehicle.engine_power,
                    "battery_capacity_kwh": self.vehicle.battery_capacity
                }
            else:
                values['engine'] = {
                    "engine_type": self.vehicle.engine_type,
                    "power_in_kw": self.vehicle.engine_power
                }

        values['model'] = {
            "model": self.vehicle.model,
            "manufactured": self.vehicle.model_year
        }
        if self.vehicle.is_model_image_large_supported:
            values['model']['image_url_large'] = self.vehicle.model_image_large
        if self.vehicle.is_model_image_small_supported:
            values['model']['image_url_small'] = self.vehicle.model_image_small

        return values

def create_instruments():
    return [
        Position(),
        DoorLock(),
        TrunkLock(),
        RequestFlash(),
        RequestHonkAndFlash(),
        RequestUpdate(),
        PlugAutoUnlock(),
        AuxHeaterDeparture(),
        WindowHeater(),
        WindowHeaterNew(),
        ClimatisationWindowHeat(),
        SeatHeatingFrontLeft(),
        SeatHeatingFrontRight(),
        SeatHeatingRearLeft(),
        SeatHeatingRearRight(),
        AirConditionAtUnlock(),
        BatteryClimatisation(),
        ElectricClimatisation(),
        AuxiliaryClimatisation(),
        PHeaterVentilation(),
        PHeaterHeating(),
        #ElectricClimatisationClimate(),
        #CombustionClimatisationClimate(),
        CarInfo(),
        Charging(),
        MaxChargeCurrent(),
        RequestResults(),
        ChargingPower(),
        DepartureTimer1(),
        DepartureTimer2(),
        DepartureTimer3(),
        Sensor(
            attr="distance",
            name="Odometer",
            icon="mdi:speedometer",
            unit="km",
            device_class="distance"
        ),
        Sensor(
            attr="battery_level",
            name="Battery level",
            icon="mdi:battery",
            unit="%",
            device_class="battery"
        ),
        Sensor(
            attr="min_charge_level",
            name="Minimum charge level",
            icon="mdi:battery-positive",
            unit="%",
            device_class="battery"
        ),
        Sensor(
            attr="adblue_level",
            name="Adblue level",
            icon="mdi:fuel",
            unit="km",
        ),
        Sensor(
            attr="fuel_level",
            name="Fuel level",
            icon="mdi:fuel",
            unit="%",
        ),
        Sensor(
            attr="service_inspection",
            name="Service inspection days",
            icon="mdi:garage",
            unit="days",
        ),
        Sensor(
            attr="service_inspection_distance",
            name="Service inspection distance",
            icon="mdi:garage",
            unit="km",
        ),
        Sensor(
            attr="oil_inspection",
            name="Oil inspection days",
            icon="mdi:oil",
            unit="days",
        ),
        Sensor(
            attr="oil_inspection_distance",
            name="Oil inspection distance",
            icon="mdi:oil",
            unit="km",
        ),
        Sensor(
            attr="last_connected",
            name="Last connected",
            icon="mdi:clock",
            device_class="timestamp"
        ),
        Sensor(
            attr="parking_time",
            name="Parking time",
            icon="mdi:clock",
            device_class="timestamp"
        ),
        Sensor(
            attr="charging_time_left",
            name="Charging time left",
            icon="mdi:battery-charging-100",
            unit="h",
            device_class="duration"
        ),
        Sensor(
            attr="charge_rate",
            name="Charging rate",
            icon="mdi:battery-heart",
            unit="km/h"
        ),
        Sensor(
            attr="electric_range",
            name="Electric range",
            icon="mdi:car-electric",
            unit="km",
            device_class="distance"
        ),
        Sensor(
            attr="combustion_range",
            name="Combustion range",
            icon="mdi:car",
            unit="km",
            device_class="distance"
        ),
        Sensor(
            attr="combined_range",
            name="Combined range",
            icon="mdi:car",
            unit="km",
            device_class="distance"
        ),
        Sensor(
            attr="charge_max_ampere",
            name="Charger max ampere",
            icon="mdi:flash",
            unit="A",
            device_class="current"
        ),
        Sensor(
            attr="climatisation_target_temperature",
            name="Climatisation target temperature",
            icon="mdi:thermometer",
            unit="°C",
            device_class="temperature"
        ),
        Sensor(
            attr="climatisation_time_left",
            name="Climatisation time left",
            icon="mdi:clock",
            unit="h",
            device_class="duration"
        ),
        Sensor(
            attr="trip_last_average_speed",
            name="Last trip average speed",
            icon="mdi:speedometer",
            unit="km/h",
        ),
        Sensor(
            attr="trip_last_average_electric_consumption",
            name="Last trip average electric consumption",
            icon="mdi:car-battery",
            unit="kWh/100 km",
        ),
        Sensor(
            attr="trip_last_average_fuel_consumption",
            name="Last trip average fuel consumption",
            icon="mdi:fuel",
            unit="l/100 km",
        ),
        Sensor(
            attr="trip_last_duration",
            name="Last trip duration",
            icon="mdi:clock",
            unit="min",
        ),
        Sensor(
            attr="trip_last_length",
            name="Last trip length",
            icon="mdi:map-marker-distance",
            unit="km",
        ),
        Sensor(
            attr="trip_last_recuperation",
            name="Last trip recuperation",
            icon="mdi:battery-plus",
            unit="kWh/100 km",
        ),
        Sensor(
            attr="trip_last_average_recuperation",
            name="Last trip average recuperation",
            icon="mdi:battery-plus",
            unit="kWh/100 km",
        ),
        Sensor(
            attr="trip_last_average_auxillary_consumption",
            name="Last trip average auxillary consumption",
            icon="mdi:flash",
            unit="kWh/100 km",
        ),
        Sensor(
            attr="trip_last_average_aux_consumer_consumption",
            name="Last trip average auxillary consumer consumption",
            icon="mdi:flash",
            unit="kWh/100 km",
        ),
        Sensor(
            attr="trip_last_total_electric_consumption",
            name="Last trip total electric consumption",
            icon="mdi:car-battery",
            unit="kWh/100 km",
        ),
        Sensor(
            attr="trip_last_start_mileage",
            name="Last trip start mileage",
            icon="mdi:map-marker-distance",
            unit="km",
        ),
        Sensor(
            attr="trip_longterm_average_speed",
            name="Longterm average speed",
            icon="mdi:speedometer",
            unit="km/h",
        ),
        Sensor(
            attr="trip_longterm_average_electric_consumption",
            name="Longterm average electric consumption",
            icon="mdi:car-battery",
            unit="kWh/100 km",
        ),
        Sensor(
            attr="trip_longterm_average_fuel_consumption",
            name="Longterm average fuel consumption",
            icon="mdi:fuel",
            unit="l/100 km",
        ),
        Sensor(
            attr="trip_longterm_duration",
            name="Longterm duration",
            icon="mdi:clock",
            unit="min",
        ),
        Sensor(
            attr="trip_longterm_length",
            name="Longterm distance",
            icon="mdi:map-marker-distance",
            unit="km",
        ),
        Sensor(
            attr="trip_longterm_recuperation",
            name="Longterm recuperation",
            icon="mdi:battery-plus",
            unit="kWh/100 km",
        ),
        Sensor(
            attr="trip_longterm_average_recuperation",
            name="Longterm average recuperation",
            icon="mdi:battery-plus",
            unit="kWh/100 km",
        ),
        Sensor(
            attr="trip_longterm_average_auxillary_consumption",
            name="Longterm average auxillary consumption",
            icon="mdi:flash",
            unit="kWh/100 km",
        ),
        Sensor(
            attr="trip_longterm_average_aux_consumer_consumption",
            name="Longterm average auxillary consumer consumption",
            icon="mdi:flash",
            unit="kWh/100 km",
        ),
        Sensor(
            attr="trip_longterm_total_electric_consumption",
            name="Longterm total electric consumption",
            icon="mdi:car-battery",
            unit="kWh/100 km",
        ),
        Sensor(
            attr="trip_longterm_start_mileage",
            name="Longterm start mileage",
            icon="mdi:map-marker-distance",
            unit="km",
        ),
        Sensor(
            attr="model_image_large",
            name="Model image URL (Large)",
            icon="mdi:file-image",
        ),
        Sensor(
            attr="model_image_small",
            name="Model image URL (Small)",
            icon="mdi:file-image",
        ),
        Sensor(
            attr="pheater_status",
            name="Parking Heater heating/ventilation status",
            icon="mdi:radiator",
        ),
        Sensor(
            attr="pheater_duration",
            name="Parking Heater heating/ventilation duration",
            icon="mdi:timer",
            unit="minutes",
        ),
        Sensor(
            attr="outside_temperature",
            name="Outside temperature",
            icon="mdi:thermometer",
            unit="°C",
            device_class="temperature"
        ),
        Sensor(
            attr="requests_remaining",
            name="Requests remaining",
            icon="mdi:chat-alert",
            unit=""
        ),
        BinarySensor(
            attr="external_power",
            name="External power",
            device_class="power"
        ),
        BinarySensor(
            attr="energy_flow",
            name="Energy flow",
            device_class="power"
        ),
        BinarySensor(
            attr="parking_light",
            name="Parking light",
            device_class="light",
            icon="mdi:car-parking-lights"
        ),
        BinarySensor(
            attr="door_locked",
            name="Doors locked",
            device_class="lock",
            reverse_state=False,
            icon="mdi:car-door-lock"
        ),
        BinarySensor(
            attr="door_closed_left_front",
            name="Door closed left front",
            device_class="door",
            reverse_state=False,
            icon="mdi:car-door"
        ),
        BinarySensor(
            attr="door_closed_right_front",
            name="Door closed right front",
            device_class="door",
            reverse_state=False,
            icon="mdi:car-door"
        ),
        BinarySensor(
            attr="door_closed_left_back",
            name="Door closed left back",
            device_class="door",
            reverse_state=False,
            icon="mdi:car-door"
        ),
        BinarySensor(
            attr="door_closed_right_back",
            name="Door closed right back",
            device_class="door",
            reverse_state=False,
            icon="mdi:car-door"
        ),
        BinarySensor(
            attr="trunk_locked",
            name="Trunk locked",
            device_class="lock",
            reverse_state=False
        ),
        BinarySensor(
            attr="trunk_closed",
            name="Trunk closed",
            device_class="door",
            reverse_state=False
        ),
        BinarySensor(
            attr="hood_closed",
            name="Hood closed",
            device_class="door",
            reverse_state=False
        ),
        BinarySensor(
            attr="charging_cable_connected",
            name="Charging cable connected",
            device_class="plug",
            reverse_state=False
        ),
        BinarySensor(
            attr="charging_cable_locked",
            name="Charging cable locked",
            device_class="lock",
            reverse_state=False
        ),
        BinarySensor(
            attr="sunroof_closed",
            name="Sunroof closed",
            device_class="window",
            reverse_state=False
        ),
        BinarySensor(
            attr="windows_closed",
            name="Windows closed",
            device_class="window",
            reverse_state=False
        ),
        BinarySensor(
            attr="window_closed_left_front",
            name="Window closed left front",
            device_class="window",
            reverse_state=False
        ),
        BinarySensor(
            attr="window_closed_left_back",
            name="Window closed left back",
            device_class="window",
            reverse_state=False
        ),
        BinarySensor(
            attr="window_closed_right_front",
            name="Window closed right front",
            device_class="window",
            reverse_state=False
        ),
        BinarySensor(
            attr="window_closed_right_back",
            name="Window closed right back",
            device_class="window",
            reverse_state=False
        ),
        BinarySensor(
            attr="vehicle_moving",
            name="Vehicle Moving",
            device_class="moving"
        ),
        BinarySensor(
            attr="request_in_progress",
            name="Request in progress",
            device_class="connectivity"
        ),
        #BinarySensor(
        #    attr="seat_heating_front_left",
        #    name="Seat heating front left",
        #    device_class="heat"
        #),
        #BinarySensor(
        #    attr="seat_heating_front_right",
        #    name="Seat heating front right",
        #    device_class="heat"
        #),
        #BinarySensor(
        #    attr="seat_heating_rear_left",
        #    name="Seat heating rear left",
        #    device_class="heat"
        #),
        #BinarySensor(
        #    attr="seat_heating_rear_right",
        #    name="Seat heating rear right",
        #    device_class="heat"
        #),
        #BinarySensor(
        #    attr="aircon_at_unlock",
        #    name="Air-conditioning at unlock",
        #    device_class=None
        #),
    ]


class Dashboard:
    def __init__(self, vehicle, **config):
        self._config = config
        self.instruments = [
            instrument
            for instrument in create_instruments()
            if instrument.setup(vehicle, **config)
        ]
        _LOGGER.debug("Supported instruments: " + ", ".join(str(inst.attr) for inst in self.instruments))