import artiq
from artiq.experiment import *
import numpy as np
import sys
import logging
from artiq.experiment import EnvExperiment
from artiq.experiment import StringValue, BooleanValue,NumberValue
from artiq.experiment import kernel
from artiq.experiment import rpc
import time

#print("Python executable:", sys.executable)

class ContinuousDDS0(EnvExperiment): # The name that appears in artiqdashboard
    def build(self): # defines all of the devices that the experiment (the program) will use
        self.setattr_device("core") # the kasli core device
        self.urukul0 = self.get_device("urukul0_cpld") # the controller on the 0th dds card

        self.n_dds = 4  # Set to 4 if you're using all DDS channels

        self.dds_channels = []
        for i in range(self.n_dds):
            self.dds_channels.append(self.get_device("urukul0_ch" + str(i))) # adds *n_dds* of dds outputs 

            # these are the defaults you will see in the dashboard 
            self.setattr_argument("frequency" + str(i),
                                  NumberValue(default=80*MHz if i == 0 else 200*MHz),
                                  group="Frequency") 
            self.setattr_argument("attenuation" + str(i),
                                  NumberValue(default=0.0),
                                  group="Attenuation")
            self.setattr_argument("amplitude" + str(i),
                                  NumberValue(default=0.1 if i == 0 else 0.7),
                                  group="Amplitude")
            self.setattr_argument("dds" + str(i) + "_enable",
                                  BooleanValue(default=True),
                                  group="Power Toggle")

    def prepare(self):
        self.freqs = []
        self.atts = []
        self.amps = []
        self.enables = []
        self.status_messages = []

        for i in range(self.n_dds): # these actually set the defaults (or whatever they are set to on the dashboard)
            self.freqs.append(getattr(self, "frequency" + str(i)))
            self.atts.append(getattr(self, "attenuation" + str(i)))
            self.amps.append(getattr(self, "amplitude" + str(i)))
            self.enables.append(getattr(self, "dds" + str(i) + "_enable"))

            # Precompute static strings for kernel print
            self.status_messages.append(("DDS channel " + str(i) + " enabled",
                                         "DDS channel " + str(i) + " disabled")) # this just preps the print statement it doesnt actually toggle on/off

    @kernel
    def run(self):
        self.core.reset()
        self.core.break_realtime()
        delay(500*ms) # good to add delays before initializing devices to avoid RTIO errors (idk why)

        self.urukul0.init() # initialises the card (NOT THE OUTPUTS)

        for i in range(self.n_dds):
            dds = self.dds_channels[i] # shorthand (unnecessary but makes the code cleaner)

            dds.init()
            dds.set_att(self.atts[i])
            dds.set(frequency=self.freqs[i], amplitude=self.amps[i])

            if self.enables[i]:
                dds.sw.on() # actually switches on output here
                print(self.status_messages[i][0])
            else:
                dds.sw.off() # here is where the toggle would actually switch off (NOTE THE CHANGES WILL BE MADE AND THEN IT WILL SWITCH OFF)
                print(self.status_messages[i][1])

# this is the same code but not in a for loop and for only two outputs, it is useful to understand how the above code works

    # @kernel
    # def run(self):
    #     self.core.reset()
    #     self.core.break_realtime()

    #     delay(500*ms)
        
    #     self.urukul0.init()
        
    #     self.dds0.init()
    #     self.dds0.set_att(self.attenuation0)
    #     self.dds0.set(frequency=self.frequency0, amplitude=self.amplitude0)

    #     if self.dds0_enable:
    #         self.dds0.sw.on()
    #         print("RF0 enabled")
    #     else:
    #         self.dds0.sw.off()
    #         print("RF0 disabled")
        
    #     self.dds1.init()
    #     self.dds1.set_att(self.attenuation1)
    #     self.dds1.set(frequency=self.frequency1, amplitude=self.amplitude1)

    #     if self.dds1_enable:
    #         self.dds1.sw.on()
    #         print("RF1 enabled")
    #     else:
    #         self.dds1.sw.off()
    #         print("RF1 disabled")
        



