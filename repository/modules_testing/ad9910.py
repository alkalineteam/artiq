from artiq.experiment import *
from numpy import int64, int32
from artiq.coredevice.core import Core

class AD9910(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.core:Core
        self.ad9910_0=self.get_device("urukul1_ch0") 

    @kernel
    def run(self):
        self.core.reset()
        self.core.break_realtime()

        self.ad9910_0.sw.on()

        self.ad9910_0.cpld.init()
        self.ad9910_0.init()
        
        self.ad9910_0.set_att(0.0)     #limit  : 31.5
        self.ad9910_0.set(frequency=10 * MHz, amplitude=1.0)

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