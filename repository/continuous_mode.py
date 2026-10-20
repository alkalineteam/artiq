from artiq.experiment import *
from artiq.coredevice.core import Core
from artiq.coredevice.ttl import TTLOut
from artiq.coredevice.ad9912 import AD9912


@compile
class continuous_mode(EnvExperiment):
    core: KernelInvariant[Core]

    #TTLs
    BMOT_Shutter: KernelInvariant[TTLOut]
    RMOT_Shutter: KernelInvariant[TTLOut]
    ZS_Shutter: KernelInvariant[TTLOut]
    Probe_Shutter: KernelInvariant[TTLOut]
    Clock_shutter: KernelInvariant[TTLOut]
    Repump_shutter: KernelInvariant[TTLOut]

    #AD9912 (urukul1)
    BMOT_AOM: KernelInvariant[AD9912]
    ZS_AOM: KernelInvariant[AD9912]
    Probe_AOM: KernelInvariant[AD9912]

    BMOT_Frequency: KernelInvariant[float]
    BMOT_Attenuation: KernelInvariant[float]
    ZS_Frequency: KernelInvariant[float]
    ZS_Attenuation: KernelInvariant[float]
    Probe_Frequency: KernelInvariant[float]
    Probe_Attenuation: KernelInvariant[float]

    def build(self):
        self.setattr_device("core")

        #TTLs
        self.BMOT_Shutter = self.get_device("ttl4")
        self.RMOT_Shutter = self.get_device("ttl5")
        self.ZS_Shutter = self.get_device("ttl6")
        self.Probe_Shutter = self.get_device("ttl7")
        self.Clock_shutter = self.get_device("ttl8")
        self.Repump_shutter = self.get_device("ttl9")

        #AD9912 (urukul1)
        self.BMOT_AOM = self.get_device("urukul1_ch0")
        self.ZS_AOM = self.get_device("urukul1_ch1")
        self.Probe_AOM = self.get_device("urukul1_ch2")


        self.setattr_argument("BMOT_Frequency", NumberValue(default = 90.0))
        self.setattr_argument("BMOT_Attenuation", NumberValue(default = 0.0))
        self.setattr_argument("ZS_Frequency", NumberValue(default = 70.0))
        self.setattr_argument("ZS_Attenuation", NumberValue(default = 0.0))
        self.setattr_argument("Probe_Frequency", NumberValue(default = 205.0))
        self.setattr_argument("Probe_Attenuation", NumberValue(default = 0.0))

    @kernel
    def run(self):
        self.core.reset()
        self.core.break_realtime()

        # initialise the Urukul CPLD (all three AOMs share urukul1) and DDS chips
        self.BMOT_AOM.cpld.init()
        self.BMOT_AOM.init()
        self.ZS_AOM.init()
        self.Probe_AOM.init()
        self.core.break_realtime()


        # Switch on all DDS channels
        self.BMOT_AOM.sw.unwrap().on()
        self.ZS_AOM.sw.unwrap().on()
        self.Probe_AOM.sw.unwrap().on()

        self.BMOT_Shutter.on()
        self.ZS_Shutter.on()
        self.Probe_Shutter.on()

        # SPI writes on the same Urukul can't overlap, so these run sequentially
        self.BMOT_AOM.set(frequency= self.BMOT_Frequency * MHz)
        self.BMOT_AOM.set_att(self.BMOT_Attenuation)
        self.ZS_AOM.set(frequency=self.ZS_Frequency * MHz)
        self.ZS_AOM.set_att(self.ZS_Attenuation)
        self.Probe_AOM.set(frequency=self.Probe_Frequency * MHz)
        self.Probe_AOM.set_att(self.Probe_Attenuation)

        # for i in range(500):
        #     self.ZS_AOM.sw.unwrap().on()
        #     self.core.delay(1000.*ms)
        #     self.ZS_AOM.sw.unwrap().off()
        #     self.core.delay(1000.*ms)

        # for i in range(500):
        #     self.Probe_AOM.sw.unwrap().on()
        #     self.core.delay(5000.*ms)
        #     self.Probe_AOM.sw.unwrap().off()
        #     self.core.delay(2000.*ms)
        

        print_rpc("Parameters are set")
