"""
mpl115a2.py
===========

Implements support for the Freescale MPL115A2 barometric pressure sensor.

Copyright (c) 2014 by Kevin Houlihan
License: MIT, see LICENSE for more details.


Usage
=====

The main functionality of this module is contained in the Mpl115A2 class, which
wraps an I2C object from the pyb module to control an MPL115A2 device. The RST
and SHDN pins can also optionally be controlled via Pin objects.

The device must be instructed to convert its sensor data by calling the
initiate_conversion method. The readings should be ready after about 3ms.

    bus = I2C(1, I2C.MASTER)
    sensor = Mpl115A2(bus)
    sensor.initiate_conversion()
    pyb.delay(3)
    print(sensor.temperature)
    print(sensor.pressure)


Shutdown and Reset
==================

The device can be shut down when not required to save power. This is not done
via I2C, but is controlled by a GPIO pin. A Pin object or name can be passed to
the constructor to allow this state to be managed.

    sensor = Mpl115A2(bus, shutdown_pin='X9')
    sensor.shutdown = True

Another pin can be used to "reset" the device. That is Freescale's term, not mine,
and it is poorly documented, but apparently it shuts down the I2C interface.

    sensor = Mpl115A2(bus, reset_pin='X10')
    sensor.reset = True

When the device is awoken from a shutdown or reset state, it takes up to 5ms before
it is ready to respond to commands.

    sensor.shutdown = False
    pyb.delay(5)
    sensor.initiate_conversion()


Temperature and Pressure Scales/Units
=====================================

By default, the temperature is in celsius and the pressure is in kilopascals. 
If other scales/units are preferred, convertors can be provided to the constructor.
Fahrenheit and Kelvin convertor classes are included in this module for temperature.
The pressure convertors also allow an adjustment to be specified, which is intended
for adjusting the pressure to sea-level. As such, there is a convertor for
AdjustedKiloPascals, HectoPascals, Atmospheres, PSI and Bars.

    sensor = Mpl115A2(
        bus, 
        temperature_convertor=Fahrenheit(),
        pressure_convertor=HectoPascals(0.9)
    )

Custom convertors can be provided as objects with these signatures:

    class TemperatureScaleUnit(object):

        def convert_to(self, temperature):
            '''
            Convert TO the custom unit FROM celsius.
            '''
            ...
            return new_temp


    class PressureScaleUnit(object):

        def convert_to(self, pressure):
            '''
            Convert TO the custom unit FROM kPa.
            '''
            ...
            return new_pressure
"""

import pyb


def _parse_signed(msb, lsb):
    combined = msb << 8 | lsb
    negative = combined & 0x8000
    if negative:
        combined ^= 0xffff
        combined *= -1
    return combined


class Celsius(object):
    """
    Dummy convertor for celsius. Providing an instance of this convertor
    is the same as providing no convertor.
    """

    def convert_to(self, temperature):
        return temperature


class Fahrenheit(object):
    """
    Convertor for fahrenheit scale.
    """

    def convert_to(self, temperature):
        """
        Convert celsius input to fahrenheit
        """
        return (temperature * 1.8) + 32.0


class Kelvin(object):
    """
    Convertor for the kelvin temperature scale.
    """

    def convert_to(self, temperature):
        """
        Convert celsius input to kelvin.
        """
        return temperature + 273.15


class AdjustedKiloPascals(object):
    """
    Convertor for KiloPascals, adjusted by some amount (most usefully, to sea-level).
    """

    def __init__(self, adjustment=None):
        self.adjustment = adjustment

    def convert_to(self, pressure):
        """
        Convert kPa to... adjusted kPa.
        """
        if self.adjustment is None:
            return pressure
        return pressure + self.adjustment


class HectoPascals(AdjustedKiloPascals):
    """
    Pressure convertor for HectoPascals.
    """

    def __init__(self, adjustment=None):
        if adjustment is not None:
            adjustment /= 10.0
        super().__init__(adjustment)

    def convert_to(self, pressure):
        """
        Convert kPa to hPa.
        """
        adjusted = super().convert_to(pressure)
        return adjusted * 10.0


class Atmospheres(AdjustedKiloPascals):
    """
    Pressure convertor for Atmospheres.
    """

    def __init__(self, adjustment=None):
        if adjustment is not None:
            adjustment /= 0.009869233
        super().__init__(adjustment)

    def convert_to(self, pressure):
        """
        Convert kPa to Atm.
        """
        adjusted = super().convert_to(pressure)
        return adjusted * 0.009869233


class PSI(AdjustedKiloPascals):
    """
    Pressure convertor for PSI.
    """

    def __init__(self, adjustment=None):
        if adjustment is not None:
            adjustment /= 0.14503773801
        super().__init__(adjustment)

    def convert_to(self, pressure):
        """
        Convert kPa to PSI.
        """
        adjusted = super().convert_to(pressure)
        return adjusted * 0.14503773801


class Bars(AdjustedKiloPascals):
    """
    Pressure convertor for Bars.
    """

    def __init__(self, adjustment=None):
        if adjustment is not None:
            adjustment /= 0.01
        super().__init__(adjustment)

    def convert_to(self, pressure):
        """
        Convert kPa to Bars.
        """
        adjusted = super().convert_to(pressure)
        return adjusted * 0.01


class Mpl115A2(object):
    """
    Reads temperature and pressure from a Freescale MPL115A2 sensor over I2C.

    See the module docstring for usage information.
    """

    def __init__(
        self,
        bus,
        shutdown_pin=None,
        reset_pin=None,
        temperature_convertor=None,
        pressure_convertor=None,
        **kwargs
    ):
        """
        Create the device on the specified bus. 

        The bus must be a pyb.I2C object in master mode, or an object implementing
        the same interface.

        pyb.Pin objects can be provided for controlling the shutdown and reset pins
        of the sensor. They must be in output mode. The pins can also be specified
        as strings (e.g. 'X9'), for which Pin objects will be created and configured.

        Temperature and pressure convertor objects can be passed which will convert
        from celsius and kilopascals as necessary if you want to work in a different scale.
        """
        # There doesn't seem to be a way to check this at present. The first
        # send or recv should throw an error instead if the mode is incorrect.
        #if not bus.in_master_mode():
        #    raise ValueError('bus must be in master mode')
        self.bus = bus
        self.address = 0x60
        self.shutdown_pin = shutdown_pin
        if self.shutdown_pin is not None:
            if isinstance(self.shutdown_pin, str):
                from pyb import Pin
                # Not sure what are the appropriate settings here...
                self.shutdown_pin = Pin(
                    self.shutdown_pin,
                    Pin.OUT_PP,
                    Pin.PULL_UP
                )
                if 'shutdown' in kwargs:
                    self.shutdown_pin.value(not kwargs['shutdown'])
                else:
                    self.shutdown_pin.high()
        self.reset_pin = reset_pin
        if self.reset_pin is not None:
            if isinstance(self.reset_pin, str):
                from pyb import Pin
                # Not sure what are the appropriate settings here...
                self.reset_pin = Pin(
                    self.reset_pin,
                    Pin.OUT_PP,
                    Pin.PULL_UP
                )
                if 'reset' in kwargs:
                    self.reset_pin.value(not kwargs['reset'])
                else:
                    self.reset_pin.high()
        self.temperature_convertor = temperature_convertor
        self.pressure_convertor = pressure_convertor

        # Coefficients for compensation calculations - will be set on first
        # attempt to read pressure or temperature
        self._a0 = None
        self._b1 = None
        self._b2 = None
        self._c12 = None

    def _send_command(self, command, value=None):
        bvals = bytearray()
        bvals.append(command)
        if value is not None:
            for val in value:
                bvals.append(val)
        self.bus.send(bvals, addr=self.address)
        self._last_command = command

    def _read_coefficients(self):
        self._send_command(0x04)
        coefficients = self.bus.recv(8, addr=self.address)
        self._a0 = float(_parse_signed(coefficients[0], coefficients[1])) / 8.0
        self._b1 = float(_parse_signed(coefficients[2], coefficients[3])) / 8192.0
        self._b2 = float(_parse_signed(coefficients[4], coefficients[5])) / 16384.0
        self._c12 = float(_parse_signed(coefficients[6], coefficients[7]) >> 2) / 4194304.0

    def _read_raw_pressure(self):
        self._send_command(0x00)
        rp = self.bus.recv(2, addr=self.address)
        return int((rp[0] << 8 | rp[1]) >> 6)

    def _read_raw_temperature(self):
        self._send_command(0x02)
        rt = self.bus.recv(2, addr=self.address)
        return int((rt[0] << 8 | rt[1]) >> 6)

    def initiate_conversion(self):
        self._send_command(0x12, (0x00,))

    @property
    def pressure(self):
        if self._a0 is None:
            self._read_coefficients()
        raw_pressure = self._read_raw_pressure()
        raw_temp = self._read_raw_temperature()
        compensated = (((self._b1 + (self._c12 * raw_temp)) * raw_pressure) + self._a0) + (self._b2 * raw_temp)
        kpa = (compensated * (65.0 / 1023.0)) + 50.0
        if self.pressure_convertor is None:
            return kpa
        return self.pressure_convertor.convert_to(kpa)

    @property
    def temperature(self):
        if self._a0 is None:
            self._read_coefficients()
        raw_temp = self._read_raw_temperature()
        celsius = ((float(raw_temp) - 498.0) / -5.35) + 25.0
        if self.temperature_convertor is None:
            return celsius
        return self.temperature_convertor.convert_to(celsius)

    def _set_shutdown(self, value):
        if self.shutdown_pin is None:
            raise Exception("No shutdown pin has been set")
        if not value:
            self._last_wake_millis = pyb.millis()
        self.shutdown_pin.value(not value)
    def _get_shutdown(self):
        if self.shutdown_pin is None:
            raise Exception("No shutdown pin has been set")
        return not self.shutdown_pin.value()
    shutdown = property(_get_shutdown, _set_shutdown)

    def _set_reset(self, value):
        if self.reset_pin is None:
            raise Exception("No reset pin has been set")
        if not value:
            self._last_wake_millis = pyb.millis()
        self.reset_pin.value(not value)
    def _get_reset(self):
        if self.reset_pin is None:
            raise Exception("No reset pin has been set")
        return not self.reset_pin.value()
    reset = property(_get_reset, _set_reset)
