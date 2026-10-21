"""Switch one TTL output on and off: high for 500 ms, low for 500 ms,
repeated 200 times (about 3 min 20 s). The timing is set by RTIO, not by
the PC.

    artiq_run repository/ttl_toggle.py
    artiq_run repository/ttl_toggle.py channel='"ttl5"' on_time=0.1

The output is left low at the end.
"""

import re

from numpy import int32

from artiq.experiment import *
from artiq.coredevice.core import Core
from artiq.coredevice.ttl import TTLOut


@compile
class TTLToggle(EnvExperiment):
    core: KernelInvariant[Core]
    ttl: KernelInvariant[TTLOut]
    cycles: KernelInvariant[int32]
    on_time: KernelInvariant[float]
    off_time: KernelInvariant[float]

    def build(self):
        self.setattr_device("core")
        ttls = sorted((name for name, desc in self.get_device_db().items()
                       if isinstance(desc, dict)
                       and desc.get("class") == "TTLOut"
                       and re.fullmatch(r"ttl\d+", name)),
                      key=lambda name: int(name[3:]))
        self.setattr_argument("channel", EnumerationValue(ttls, ttls[0]))
        self.setattr_argument("cycles", NumberValue(200, precision=0, step=1, min=1, type="int"))
        self.setattr_argument("on_time", NumberValue(500*ms, unit="ms", min=1*us))
        self.setattr_argument("off_time", NumberValue(500*ms, unit="ms", min=1*us))
        self.ttl = self.get_device(self.channel)

    @kernel
    def run(self):
        self.core.reset()
        self.ttl.off()
        self.core.delay(1.*ms)

        for _ in range(self.cycles):
            self.ttl.on()
            # wait for the output to actually go high, so the message is in sync
            self.core.wait_until_mu(now_mu())
            print_rpc("TTL is on")
            self.core.delay(self.on_time)
            self.ttl.off()
            self.core.delay(self.off_time)

        # Stay in the kernel until the last edge has actually happened
        self.core.wait_until_mu(now_mu())
