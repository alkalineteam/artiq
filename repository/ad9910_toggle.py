from numpy import int32

from artiq.experiment import *
from artiq.coredevice.core import Core
from artiq.coredevice.ad9910 import AD9910


@compile
class AD9910Toggle(EnvExperiment):
    core: KernelInvariant[Core]
    dds: KernelInvariant[AD9910[Auto]]
    frequency: KernelInvariant[float]
    attenuation: KernelInvariant[float]
    cycles: KernelInvariant[int32]
    on_time: KernelInvariant[float]
    off_time: KernelInvariant[float]

    def build(self):
        self.setattr_device("core")
        channels = [name for name, desc in self.get_device_db().items()
                    if isinstance(desc, dict) and desc.get("class") == "AD9910"]
        self.setattr_argument("channel", EnumerationValue(channels, "urukul0_ch0"))
        self.setattr_argument("frequency", NumberValue(90*MHz, unit="MHz", min=0., max=400*MHz))
        self.setattr_argument("attenuation", NumberValue(0., unit="dB", min=0., max=31.5))
        self.setattr_argument("cycles", NumberValue(500, precision=0, step=1, min=1, type="int"))
        self.setattr_argument("on_time", NumberValue(1000*ms, unit="ms", min=1*us))
        self.setattr_argument("off_time", NumberValue(1000*ms, unit="ms", min=1*us))
        self.dds = self.get_device(self.channel)

    @kernel
    def run(self):
        self.core.reset()
        self.core.break_realtime()
        self.dds.cpld.init()
        self.dds.init()
        # init() reads back from the chip and waits for PLL lock, so get fresh
        # slack before the next output (otherwise RTIOUnderflow)
        self.core.break_realtime()

        self.dds.sw.unwrap().off()
        self.dds.set(self.frequency)
        self.dds.set_att(self.attenuation)

        for _ in range(self.cycles):
            self.dds.sw.unwrap().on()
            # wait for the switch to actually turn on, so the message is in sync
            self.core.wait_until_mu(now_mu())
            print_rpc("AD9910 is on")
            self.core.delay(self.on_time)
            self.dds.sw.unwrap().off()
            self.core.delay(self.off_time)

        # Stay in the kernel until the last switch event has actually happened
        self.core.wait_until_mu(now_mu())
