"""Step one Fastino DAC channel between two voltages: high for 500 ms, low for
500 ms, repeated 200 times (about 3 min 20 s). The timing is set by RTIO, not
by the PC.

    artiq_run repository/fastino_toggle.py
    artiq_run repository/fastino_toggle.py dac=5 high_voltage=2.0

Voltages are Fastino outputs (-10 to +10 V). On CASTOR they go through the HV
amplifier, which multiplies them by its gain (most likely 5x), so the default
1 V shows up as about 5 V on the IDC-MCX adapter. The channel is left at
low_voltage at the end.
"""

from numpy import int32

from artiq.experiment import *
from artiq.coredevice.core import Core
from artiq.coredevice.fastino import Fastino


@compile
class FastinoToggle(EnvExperiment):
    core: KernelInvariant[Core]
    fastino: KernelInvariant[Fastino]
    dac: KernelInvariant[int32]
    high_voltage: KernelInvariant[float]
    low_voltage: KernelInvariant[float]
    cycles: KernelInvariant[int32]
    on_time: KernelInvariant[float]
    off_time: KernelInvariant[float]

    def build(self):
        self.setattr_device("core")
        fastinos = [name for name, desc in self.get_device_db().items()
                    if isinstance(desc, dict) and desc.get("class") == "Fastino"]
        self.setattr_argument("device", EnumerationValue(fastinos, fastinos[0]))
        self.setattr_argument("dac", NumberValue(0, precision=0, step=1, min=0, max=31, type="int"))
        self.setattr_argument("high_voltage", NumberValue(1., unit="V", min=-10., max=10.))
        self.setattr_argument("low_voltage", NumberValue(0., unit="V", min=-10., max=10.))
        self.setattr_argument("cycles", NumberValue(200, precision=0, step=1, min=1, type="int"))
        self.setattr_argument("on_time", NumberValue(500*ms, unit="ms", min=1*us))
        self.setattr_argument("off_time", NumberValue(500*ms, unit="ms", min=1*us))
        self.fastino = self.get_device(self.device)

    @kernel
    def run(self):
        self.core.reset()
        self.core.break_realtime()
        self.fastino.init()  # does not change the other channels' voltages
        self.core.delay(1.*ms)
        self.fastino.set_dac(self.dac, self.low_voltage)
        self.core.delay(1.*ms)

        for _ in range(self.cycles):
            self.fastino.set_dac(self.dac, self.high_voltage)
            # wait for the output to actually change, so the message is in sync
            self.core.wait_until_mu(now_mu())
            print_rpc("Fastino channel is high")
            self.core.delay(self.on_time)
            self.fastino.set_dac(self.dac, self.low_voltage)
            self.core.delay(self.off_time)

        # Stay in the kernel until the last update has actually happened
        self.core.wait_until_mu(now_mu())
