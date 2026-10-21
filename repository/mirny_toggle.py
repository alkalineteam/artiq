"""Switch one Mirny RF output on and off: on for 500 ms, off for 500 ms,
repeated 200 times (about 3 min 20 s). Uses the channel's RF switch, so the
timing is set by RTIO, not by the PC.

    artiq_run repository/mirny_toggle.py
    artiq_run repository/mirny_toggle.py channel='"mirny1_ch2"' frequency=1500e6

The output is left off at the end.
"""

from numpy import int32

from artiq.experiment import *
from artiq.coredevice.core import Core
from artiq.coredevice.adf5356 import ADF5356


MIRNY_CHANNELS = ["mirny{}_ch{}".format(m, c) for m in range(2) for c in range(4)]


@compile
class MirnyToggle(EnvExperiment):
    core: KernelInvariant[Core]
    mirny: KernelInvariant[ADF5356]
    frequency: KernelInvariant[float]
    attenuation: KernelInvariant[float]
    cycles: KernelInvariant[int32]
    on_time: KernelInvariant[float]
    off_time: KernelInvariant[float]

    def build(self):
        self.setattr_device("core")
        self.setattr_argument("channel", EnumerationValue(MIRNY_CHANNELS, "mirny0_ch0"))
        self.setattr_argument("frequency", NumberValue(1000*MHz, unit="MHz", min=53.125*MHz, max=6800*MHz))
        self.setattr_argument("attenuation", NumberValue(20., unit="dB", min=0., max=31.5))
        self.setattr_argument("cycles", NumberValue(200, precision=0, step=1, min=1, type="int"))
        self.setattr_argument("on_time", NumberValue(500*ms, unit="ms", min=1*ms))
        self.setattr_argument("off_time", NumberValue(500*ms, unit="ms", min=1*ms))
        self.mirny = self.get_device(self.channel)

    @kernel
    def run(self):
        self.core.reset()
        self.mirny.cpld.init()
        self.core.break_realtime()
        self.mirny.init()
        self.core.break_realtime()

        self.mirny.sw.off()
        self.mirny.set_att(self.attenuation)
        self.mirny.set_frequency(self.frequency)
        self.core.delay(10.*ms)  # let the PLL lock before the first pulse

        for _ in range(self.cycles):
            self.mirny.sw.on()
            # wait for the switch to actually turn on, so the message is in sync
            self.core.wait_until_mu(now_mu())
            print_rpc("Mirny is on")
            self.core.delay(self.on_time)
            self.mirny.sw.off()
            self.core.delay(self.off_time)

        # Stay in the kernel until the last switch event has actually happened
        self.core.wait_until_mu(now_mu())
