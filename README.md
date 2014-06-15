micropython-mpl115a2
====================

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