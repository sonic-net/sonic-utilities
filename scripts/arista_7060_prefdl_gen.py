from arista.components.eeprom import I2cEeprom
from arista.core.platform import loadPrerequisites
from arista.core.types import I2cBus

"""Read system information from EEPROM via I2C

This script reads system information from the EEPROM via I2C.

This script is only intended to be ran on Arista-7060-32S
  devices on or before the SONiC 202605 release.
"""


IDENT_BUS_NAME = 'SMBus PIIX4 adapter port 1 at 0b20'

loadPrerequisites()
eeprom = I2cEeprom(addr=I2cBus(IDENT_BUS_NAME).i2cAddr(0x52))
eeprom.setup()
pfdl = eeprom.readPrefdl()
pfdl.writeToFile("/host/.system-prefdl")
