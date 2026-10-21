"""Health check for the CASTOR crate (DRTIO master + satellite).

Goes through every device in the device DB one by one, prints PASS/FAIL for
each, and ends with a summary. Run it from the directory holding the crate's
device_db.py:

    artiq_run repository/castor_check.py

Checks that need no extra equipment (CPLD/chip responses, register readbacks,
PLL lock) always run. Anything that changes a physical output is opt-in:

    rf_test_outputs=True    leave test tones on (Urukul 10-33 MHz, Mirny
                            1.1-1.23 GHz) for a scope / spectrum analyser
    pulse_ttl_outputs=True  pulse every TTL output 3 times

    artiq_run repository/castor_check.py rf_test_outputs=True

Running this re-initialises every Urukul and Mirny and turns their RF
switches off, so don't run it while an experiment needs stable RF. Fastino
voltages are never changed, because the HV amplifier is driven from it.

Status words: PASS = verified by readback, FAIL = error or wrong readback,
LOOK = commands sent but only your eyes can confirm (LEDs), SKIP = not tested.
"""

import re
import time

from numpy import int32

from artiq.experiment import *
from artiq.coredevice.core import Core
from artiq.coredevice.ttl import TTLOut
from artiq.coredevice.urukul import CPLD as UrukulCPLD
from artiq.coredevice.ad9910 import AD9910
from artiq.coredevice.fastino import Fastino
from artiq.coredevice.sampler import Sampler
from artiq.coredevice.mirny import Mirny
from artiq.coredevice.adf5356 import ADF5356


# Gains 0,1,2,3,0,1,2,3 on Sampler channels 0-7, packed as Sampler.set_gain_mu does
SAMPLER_GAIN_PATTERN = sum((i % 4) << (2*i) for i in range(8))

# Control lines driven by their own drivers, not tested as plain TTL outputs
CONTROL_TTL_ARGS = ("sw_device", "io_update_device", "cnv_device",
                    "ldac_device", "clr_device")


def natural_key(name):
    return [int(s) if s.isdigit() else s for s in re.split(r"(\d+)", name)]


@compile
class CastorCheck(EnvExperiment):
    core: KernelInvariant[Core]

    def build(self):
        self.setattr_device("core")
        self.setattr_argument("rf_test_outputs", BooleanValue(False),
                              tooltip="Leave a test tone on every Urukul and Mirny output")
        self.setattr_argument("pulse_ttl_outputs", BooleanValue(False),
                              tooltip="Pulse every TTL output 3 times (100 ms)")
        self.setattr_argument("drtio_timeout", NumberValue(10., unit="s", min=0., max=60.),
                              tooltip="How long to wait for satellites to come up")

        self.ddb = self.get_device_db()
        control_ttls = set()
        for desc in self.ddb.values():
            if isinstance(desc, dict):
                args = desc.get("arguments", {})
                control_ttls.update(args[k] for k in CONTROL_TTL_ARGS if k in args)

        self.leds = []
        self.ttl_outs = []
        self.urukul_cplds = []
        self.urukul_channels = []
        self.fastinos = []
        self.samplers = []
        self.mirny_cplds = []
        self.mirny_channels = []
        self.not_checked = []
        for name in sorted(self.ddb, key=natural_key):
            desc = self.ddb[name]
            if not isinstance(desc, dict) or desc["type"] != "local":
                continue
            kind = (desc["module"], desc["class"])
            if kind == ("artiq.coredevice.ttl", "TTLOut"):
                if name.startswith("led"):
                    self.leds.append(self.entry(name))
                elif name not in control_ttls:
                    self.ttl_outs.append(self.entry(name))
            elif kind == ("artiq.coredevice.urukul", "CPLD"):
                self.urukul_cplds.append(self.entry(name))
            elif kind == ("artiq.coredevice.ad9910", "AD9910"):
                self.urukul_channels.append(self.entry(name))
            elif kind == ("artiq.coredevice.fastino", "Fastino"):
                self.fastinos.append(self.entry(name))
            elif kind == ("artiq.coredevice.sampler", "Sampler"):
                self.samplers.append(self.entry(name))
            elif kind == ("artiq.coredevice.mirny", "Mirny"):
                self.mirny_cplds.append(self.entry(name))
            elif kind == ("artiq.coredevice.adf5356", "ADF5356"):
                self.mirny_channels.append(self.entry(name))
            elif kind in (("artiq.coredevice.ad9912", "AD9912"),
                          ("artiq.coredevice.zotino", "Zotino"),
                          ("artiq.coredevice.ttl", "TTLInOut")):
                self.not_checked.append(name)

        self.destinations = sorted(
            {dest for group in (self.leds, self.ttl_outs, self.urukul_cplds,
                                self.fastinos, self.samplers, self.mirny_cplds)
             for _, _, dest in group} - {0})

    def entry(self, name):
        return name, self.get_device(name), self.destination_of(name)

    def destination_of(self, name):
        """DRTIO destination of a device, found by following its device DB
        references down to an RTIO channel (destination = channel >> 16)."""
        desc = self.ddb[name]
        if isinstance(desc, str):  # alias
            return self.destination_of(desc)
        args = desc.get("arguments", {})
        for key in ("spi_device", "cpld_device", "spi_adc_device"):
            if key in args:
                return self.destination_of(args[key])
        return args.get("channel", 0) >> 16

    # ---- kernels -------------------------------------------------------

    @kernel
    def check_core(self):
        self.core.reset()

    @kernel
    def destination_up(self, destination: int32) -> bool:
        return self.core.get_rtio_destination_status(destination)

    @kernel
    def switches_off(self, switches: list[TTLOut]):
        self.core.break_realtime()
        for sw in switches:
            sw.off()
            self.core.delay(10.*us)
        self.core.wait_until_mu(now_mu())

    @kernel
    def blink(self, ttls: list[TTLOut]):
        self.core.break_realtime()
        for ttl in ttls:
            for _ in range(3):
                ttl.pulse(100.*ms)
                self.core.delay(100.*ms)
            self.core.delay(200.*ms)
        self.core.wait_until_mu(now_mu())

    @kernel
    def check_urukul_cpld(self, cpld: UrukulCPLD[Auto]) -> int32:
        self.core.break_realtime()
        cpld.init()  # raises on no response or proto_rev mismatch
        self.core.break_realtime()
        errors = 0
        for i in range(32):
            word = 1 << i
            cpld.set_all_att_mu(word)
            if cpld.get_att_mu() != word:
                errors += 1
            self.core.break_realtime()
        cpld.set_all_att_mu(0)  # all channels at maximum attenuation
        return errors

    @kernel
    def check_ad9910(self, channel: AD9910[Auto], frequency: float, rf_on: bool) -> float:
        self.core.break_realtime()
        channel.init()  # raises on chip ID mismatch or PLL lock timeout
        self.core.break_realtime()
        channel.set_att(31.5)
        channel.set(frequency)
        self.core.break_realtime()
        f_read, phase, amplitude = channel.get()
        if rf_on:
            self.core.break_realtime()
            channel.set_att(10.)
            channel.cfg_sw(True)
        return f_read

    @kernel
    def check_fastino(self, fastino: Fastino):
        self.core.break_realtime()
        fastino.init()  # does not change the DAC voltages
        self.core.delay(1.*ms)
        for i in range(8):
            fastino.set_leds(1 << i)
            self.core.delay(150.*ms)
        fastino.set_leds(0)
        self.core.wait_until_mu(now_mu())

    @rpc
    def store_sampler_voltages(self, voltages: list[float]):
        self.sampler_voltages = voltages

    @kernel
    def check_sampler(self, sampler: Sampler) -> int32:
        self.core.break_realtime()
        sampler.init()
        self.core.delay(5.*ms)
        for i in range(8):
            sampler.set_gain_mu(i, i % 4)
            self.core.delay(100.*us)
        gains = sampler.get_gains_mu()
        self.core.break_realtime()
        for i in range(8):
            sampler.set_gain_mu(i, 0)
            self.core.delay(100.*us)
        voltages = [0. for _ in range(8)]
        # The first conversion after power-up can read full scale; discard it
        sampler.sample(voltages)
        self.core.delay(1.*ms)
        sampler.sample(voltages)
        self.store_sampler_voltages(voltages)
        return gains

    @kernel
    def check_mirny_cpld(self, cpld: Mirny):
        self.core.break_realtime()
        cpld.init()  # raises on no response or PROTO_REV mismatch

    @kernel
    def check_adf5356(self, channel: ADF5356, frequency: float, rf_on: bool) -> bool:
        self.core.break_realtime()
        channel.init()  # raises if the MUXOUT line can't be read back
        self.core.break_realtime()
        channel.set_att(31.5)
        channel.set_frequency(frequency)
        self.core.delay(5.*ms)
        locked = channel.read_muxout()  # digital lock detect after init
        if rf_on:
            self.core.break_realtime()
            channel.set_att(15.)
            channel.sw.on()
        return locked

    # ---- host-side sequence --------------------------------------------

    def report(self, status, name, detail=""):
        self.results.append((status, name, detail))
        print("  [{}] {:22s} {}".format(status, name, detail))

    def attempt(self, name, kernel_fn, *args):
        """Run one kernel; a core-device exception becomes a FAIL line."""
        try:
            return True, kernel_fn(*args)
        except Exception as e:
            self.report("FAIL", name, "{}: {}".format(type(e).__name__, e))
            # Run the next kernel on a fresh connection. Reusing the session
            # after a failed kernel can halt the core device firmware
            # ("attempted to start kernel CPU when it is already running").
            self.core.comm.close()
            return False, None

    def reachable(self, group):
        """Drop devices behind a DRTIO destination that is down."""
        kept = []
        for name, dev, dest in group:
            if dest in self.down:
                self.report("SKIP", name, "satellite destination {} is down".format(dest))
            else:
                kept.append((name, dev, dest))
        return kept

    def run(self):
        self.results = []
        self.down = set()

        print("\n== Core device")
        ok, _ = self.attempt("core", self.check_core)
        if not ok:
            print("\nThe first kernel failed (see above); nothing else can be checked.")
            return self.summary()
        self.report("PASS", "core", "connected, RTIO reset")

        print("\n== DRTIO satellites")
        if not self.destinations:
            print("  (none in device DB)")
        for dest in self.destinations:
            deadline = time.monotonic() + self.drtio_timeout
            up = False
            while True:
                ok, up = self.attempt("destination {}".format(dest), self.destination_up, dest)
                if not ok or up or time.monotonic() > deadline:
                    break
                time.sleep(0.5)
            if up:
                self.report("PASS", "destination {}".format(dest), "link up")
            else:
                self.down.add(dest)
                if ok:
                    self.report("FAIL", "destination {}".format(dest),
                                "link not up after {:.0f} s: check the SFP cable/port "
                                "and the master's rtio_clock".format(self.drtio_timeout))

        # Safe state first: all RF switches off on reachable crates
        switches = []
        for name, dev, dest in self.urukul_channels:
            if dest not in self.down and dev.sw.is_some():
                switches.append(dev.sw.unwrap())
        for name, dev, dest in self.mirny_channels:
            if dest not in self.down:
                switches.append(dev.sw)
        if switches:
            self.attempt("RF switches", self.switches_off, switches)

        print("\n== Kasli user LEDs (each blinks 3x, in this order)")
        leds = self.reachable(self.leds)
        if leds:
            ok, _ = self.attempt("LEDs", self.blink, [dev for _, dev, _ in leds])
            for name, _, dest in leds:
                if ok:
                    self.report("LOOK", name, "blinked on the {} Kasli".format(
                        "master" if dest == 0 else "satellite {}".format(dest)))

        print("\n== Urukul CPLDs")
        failed_cplds = set()
        for name, dev, dest in self.reachable(self.urukul_cplds):
            ok, errors = self.attempt(name, self.check_urukul_cpld, dev)
            if not ok:
                failed_cplds.add(name)
            elif errors:
                failed_cplds.add(name)
                self.report("FAIL", name, "attenuator readback wrong in {}/32 bits".format(errors))
            else:
                self.report("PASS", name, "CPLD answered (proto_rev {}), attenuator readback 32/32"
                            .format(dev.proto_rev))

        print("\n== Urukul DDS channels")
        for n, (name, dev, dest) in enumerate(self.reachable(self.urukul_channels)):
            cpld_name = self.ddb[name]["arguments"]["cpld_device"]
            if cpld_name in failed_cplds:
                self.report("SKIP", name, "its CPLD ({}) failed".format(cpld_name))
                continue
            frequency = (10. * (n // 4 + 1) + n % 4) * MHz
            ok, f_read = self.attempt(name, self.check_ad9910, dev, frequency, self.rf_test_outputs)
            if not ok:
                continue
            if abs(f_read - frequency) < 1.:
                self.report("PASS", name, "chip ID + PLL lock OK, frequency readback {:.3f} MHz{}"
                            .format(f_read / MHz, " (RF ON)" if self.rf_test_outputs else ""))
            else:
                self.report("FAIL", name, "wrote {:.3f} MHz, read back {:.3f} MHz"
                            .format(frequency / MHz, f_read / MHz))

        print("\n== Fastino")
        for name, dev, dest in self.reachable(self.fastinos):
            ok, _ = self.attempt(name, self.check_fastino, dev)
            if ok:
                self.report("LOOK", name, "initialised; its 8 front-panel LEDs should have lit "
                            "one after another (Fastino has no readback)")

        print("\n== Sampler")
        for name, dev, dest in self.reachable(self.samplers):
            ok, gains = self.attempt(name, self.check_sampler, dev)
            if not ok:
                continue
            voltages = " ".join("{:+.2f}".format(v) for v in self.sampler_voltages)
            if gains & 0xffff == SAMPLER_GAIN_PATTERN:
                self.report("PASS", name, "gain register readback OK; inputs now read [V]: " + voltages)
            else:
                self.report("FAIL", name, "gain readback 0x{:04x}, expected 0x{:04x}"
                            .format(gains & 0xffff, SAMPLER_GAIN_PATTERN))

        print("\n== Mirny CPLDs")
        failed_cplds = set()
        for name, dev, dest in self.reachable(self.mirny_cplds):
            ok, _ = self.attempt(name, self.check_mirny_cpld, dev)
            if ok:
                self.report("PASS", name, "CPLD answered, PROTO_REV OK")
            else:
                failed_cplds.add(name)

        print("\n== Mirny PLL channels")
        for n, (name, dev, dest) in enumerate(self.reachable(self.mirny_channels)):
            cpld_name = self.ddb[name]["arguments"]["cpld_device"]
            if cpld_name in failed_cplds:
                self.report("SKIP", name, "its CPLD ({}) failed".format(cpld_name))
                continue
            frequency = (1000. + 100. * (n // 4 + 1) + 10. * (n % 4)) * MHz
            ok, locked = self.attempt(name, self.check_adf5356, dev, frequency, self.rf_test_outputs)
            if not ok:
                continue
            if locked:
                self.report("PASS", name, "MUXOUT readback OK, PLL locked at {:.0f} MHz{}"
                            .format(frequency / MHz, " (RF ON)" if self.rf_test_outputs else ""))
            else:
                self.report("FAIL", name, "PLL did not lock at {:.0f} MHz: check the MMCX "
                            "reference clock and refclk in the JSON".format(frequency / MHz))

        print("\n== TTL outputs")
        ttls = self.reachable(self.ttl_outs)
        if not self.pulse_ttl_outputs:
            for name, _, _ in ttls:
                self.report("SKIP", name, "not pulsed (run with pulse_ttl_outputs=True)")
        elif ttls:
            ok, _ = self.attempt("TTL outputs", self.blink, [dev for _, dev, _ in ttls])
            for name, _, _ in ttls:
                if ok:
                    self.report("LOOK", name, "pulsed 3x 100 ms (check scope / channel LED)")

        for name in self.not_checked:
            self.report("SKIP", name, "device type not covered by this check")

        self.summary()

    def summary(self):
        counts = {}
        for status, _, _ in self.results:
            counts[status] = counts.get(status, 0) + 1
        print("\n== Summary: " + ", ".join("{} {}".format(counts.get(s, 0), s)
                                         for s in ("PASS", "FAIL", "LOOK", "SKIP")))
        failures = [(name, detail) for status, name, detail in self.results if status == "FAIL"]
        if failures:
            print("Failed:")
            for name, detail in failures:
                print("  {:22s} {}".format(name, detail))
        else:
            print("No failures. Confirm the LOOK items by eye.")
