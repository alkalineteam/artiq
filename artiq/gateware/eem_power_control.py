from migen import *
from misoc.interconnect.csr import *


class EEMPowerControl(Module, AutoCSR):
    def __init__(self, power_en, fault_n):
        self.sw_power_en = CSRStorage()
        self.power_fault = power_fault = CSR()
        self.sync += If(~fault_n, power_fault.w.eq(1)).Elif(power_fault.re, power_fault.w.eq(0))
        self.comb += power_en.eq(self.sw_power_en.storage & ~power_fault.w)