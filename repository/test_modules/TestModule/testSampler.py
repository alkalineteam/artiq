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

###### THIS SHOULD BE ABLE TO RUN AT SAMPLE DELAY = NUM SAMPLES

class Test_AD9910Signalling(EnvExperiment):
    def build(self):
        self.setattr_device("core")
        self.dds = self.get_device("urukul0_ch0")
        self.urukul0 = self.get_device("urukul0_cpld")
        self.sampler:Sampler = self.get_device("sampler0")
        self.setattr_argument("frequency", NumberValue(default = 1*MHz))
        self.setattr_argument("amplitude", NumberValue(default = 1.0))
        self.setattr_argument("sample_delay", NumberValue(default = 100*us, unit="us")) # min sample delay seems to be 15 us
        self.setattr_argument("num_samples", NumberValue(default = 1500)) # max value is about 37000

    @kernel
    def run(self):
        self.core.reset()
        self.core.break_realtime()

        delay(500*ms)
        
        self.urukul0.init()
        self.dds.init()
        self.sampler.init()
        self.dds.set_att(0.0)
        self.dds.set(frequency=self.frequency, amplitude=self.amplitude)
        self.dds.sw.on()
        num_samples = int(self.num_samples)

        delay(50*ms)  # Let the DDS output settle

        #sample_period = 1 / 30000   #25kHz sampling rate should give us enough data points
        #sampling_duration = 0.01     #30ms sampling time to allow for all the imaging slices to take place

        #num_samples = int32(sampling_duration/sample_period) # total number of datapoints
        

        samples = [[0.0 for i in range(8)] for i in range(num_samples)] # make an array for all of the channels that is as long as the dataset

        for i in range(num_samples):

            self.sampler.sample(samples[i]) # saves the ith reading from the sampler to the "samples" array

            delay(self.sample_delay)
            #self.core.break_realtime() # makes RTIO errors go away?
    
        # delay(sampling_duration*s)


        # self.dds.sw.off()

        samples_ch0 = [float(i[0]) for i in samples] # takes the 0th (channel 1) 2d array of the 3d sampler array (datapoints:time:channels)
        samples_ch1 = [float(i[1]) for i in samples]
        samples_ch2 = [float(i[2]) for i in samples]
        samples_ch3 = [float(i[3]) for i in samples]
        samples_ch4 = [float(i[4]) for i in samples]
        samples_ch5 = [float(i[5]) for i in samples] # takes data from channel 2
        samples_ch6 = [float(i[6]) for i in samples] # takes data        
        samples_ch7 = [float(i[7]) for i in samples] # takes datra from channel 8

        sample_index = list(range(int(num_samples))) # makes a x array (not neccesary unless plotting manually)

        self.set_dataset("sampler_signal0", samples_ch0, broadcast=True, archive=True) # makes the datasets and broadcasts them
        self.set_dataset("sampler_signal1", samples_ch1, broadcast=True, archive=True)
        self.set_dataset("sampler_signal2", samples_ch2, broadcast=True, archive=True)
        self.set_dataset("sampler_signal3", samples_ch3, broadcast=True, archive=True)
        self.set_dataset("sampler_signal4", samples_ch4, broadcast=True, archive=True)
        self.set_dataset("sampler_signal5", samples_ch5, broadcast=True, archive=True)
        self.set_dataset("sampler_signal6", samples_ch6, broadcast=True, archive=True)
        self.set_dataset("sampler_signal7", samples_ch7, broadcast=True, archive=True)

        self.set_dataset("sample_index", sample_index, broadcast=True, archive=True)

        print("Sampler Test Complete")
        delay(100*ms)  # Allow time for the datasets to be written before the experiment ends
        self.analyze

    def analyze(self):
    # Total sampling duration
        total_duration = self.num_samples * self.sample_delay
        print("Sample delay:", self.sample_delay)
        print("Number of samples:", self.num_samples)
        print("Total sampling duration:", total_duration*1E3,"ms")





