from artiq.experiment import *
from numpy import int64, int32
from artiq.coredevice.core import Core

class AD9910(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.core:Core
        self.ad9910_0=self.get_device("urukul0_ch0") 

        self.setattr_argument("Enable_RF", BooleanValue(default=False))
        self.setattr_argument("Frequency", NumberValue(default=350.0, unit="MHz", min=0.0, max=400.0))
        self.setattr_argument("Attenuation", NumberValue(default=11.8, unit="dB", min=0.0, max=31.5))

    @kernel
    def run(self):
        self.core.reset()
        self.core.break_realtime()

        self.ad9910_0.sw.on()

        self.ad9910_0.cpld.init(blind=True)
        self.ad9910_0.init()
        
        self.ad9910_0.set_att(self.Attenuation)    #limit  : -31.5
        self.ad9910_0.set(frequency=self.Frequency * MHz)

        if self.Enable_RF:
            self.ad9910_0.sw.on()
        else:
            self.ad9910_0.sw.off()

        # for i in range(10):
        #     self.ad9910_0.sw.on()
        #     delay(1000*ms)
        #     self.ad9910_0.sw.off()
        #     delay(1000*ms)

        # for i in range(10):
        #     self.ad9910_0.set(frequency=39 * MHz, amplitude=1.0)
        #     delay(1000*ms)
        #     self.ad9910_0.set(frequency=41 * MHz, amplitude=1.0)
        #     delay(1000*ms)

        print("AD9910 test is done!")