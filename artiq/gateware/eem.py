from types import SimpleNamespace

from migen import *
from migen.build.generic_platform import *
from migen.genlib.io import DifferentialOutput, DifferentialInput

from artiq.gateware import rtio
from artiq.gateware.rtio.phy import spi2, ad53xx_monitor, dds, grabber
from artiq.gateware.suservo import servo, pads as servo_pads
from artiq.gateware.rtio.phy import servo as rtservo, fastino, phaser


def _eem_signal(i):
    n = "d{}".format(i)
    if i == 0:
        n += "_cc"
    return n


def _eem_pin(eem, i, pol):
    return "eem{}:{}_{}".format(eem, _eem_signal(i), pol)


def default_iostandard(eem):
    return IOStandard("LVDS_25")


class _EEM:
    @classmethod
    def add_extension(cls, target, eem, *args, is_drtio_over_eem=False, **kwargs):
        name = cls.__name__
        target.platform.add_extension(cls.io(eem, *args, **kwargs))
        if is_drtio_over_eem:
            print("{} (EEM{}) starting at DRTIO channel 0x{:06x}"
                .format(name, eem, (len(target.gt_drtio.channels) + len(target.eem_drtio_channels) + 1) << 16))
        else:
            print("{} (EEM{}) starting at RTIO channel 0x{:06x}"
                .format(name, eem, len(target.rtio_channels)))


class DIO(_EEM):
    @staticmethod
    def io(eem0, eem1, iostandard):
        signals = []
        for i in range(8):
            signals.append(("dio{}".format(eem0), i,
                    Subsignal("p", Pins(_eem_pin(eem0, i, "p"))),
                    Subsignal("n", Pins(_eem_pin(eem0, i, "n"))),
                    iostandard(eem0)))
        if eem1 is not None:
            for i in range(8):
                signals.append(("dio{}".format(eem0), i+8,
                        Subsignal("p", Pins(_eem_pin(eem1, i, "p"))),
                        Subsignal("n", Pins(_eem_pin(eem1, i, "n"))),
                        iostandard(eem0)))
        return signals

    @classmethod
    def add_std(cls, target, eem, ttl03_cls, ttl47_cls, iostandard=default_iostandard,
            edge_counter_cls=None):
        cls.add_extension(target, eem, None, iostandard=iostandard)

        phys = []
        dci = iostandard(eem).name == "LVDS"
        for i in range(4):
            pads = target.platform.request("dio{}".format(eem), i)
            phy = ttl03_cls(pads.p, pads.n, dci=dci)
            phys.append(phy)
            target.submodules += phy
            target.rtio_channels.append(rtio.Channel.from_phy(phy))
        for i in range(4):
            pads = target.platform.request("dio{}".format(eem), 4+i)
            phy = ttl47_cls(pads.p, pads.n, dci=dci)
            phys.append(phy)
            target.submodules += phy
            target.rtio_channels.append(rtio.Channel.from_phy(phy))

        if edge_counter_cls is not None:
            for phy in phys:
                state = getattr(phy, "input_state", None)
                if state is not None:
                    counter = edge_counter_cls(state)
                    target.submodules += counter
                    target.rtio_channels.append(rtio.Channel.from_phy(counter))

    @classmethod
    def add_rj45_lvds(cls, target, eem0, eem1, dio_cls_list, iostandard=default_iostandard,
                       edge_counter_cls=None):
        cls.add_extension(target, eem0, eem1, iostandard=iostandard)

        phys = []
        dci = iostandard(eem0).name == "LVDS"
        for i, (dio_cls) in enumerate(dio_cls_list):
            pads = target.platform.request("dio{}".format(eem0), i)
            phy = dio_cls(pads.p, pads.n, dci=dci)
            phys.append(phy)
            target.submodules += phy
            target.rtio_channels.append(rtio.Channel.from_phy(phy))

        if edge_counter_cls is not None:
            for phy in phys:
                state = getattr(phy, "input_state", None)
                if state is not None:
                    counter = edge_counter_cls(state)
                    target.submodules += counter
                    target.rtio_channels.append(rtio.Channel.from_phy(counter))


class DIO_SPI(_EEM):
    @staticmethod
    def io(eem0, eem1, spi, dio, iostandard):
        def get_port_and_pin(channel):
            if channel < 8:
                return eem0, channel
            elif eem1 is not None:
                return eem1, channel-8
            else:
                raise ValueError("cannot assign channel 8-15 with single EEM port")

        def spi_subsignals(clk, mosi, miso, cs, pol):
            signals = []
            port, pin = get_port_and_pin(clk)
            signals.append(Subsignal("clk", Pins(_eem_pin(port, pin, pol))))
            if mosi is not None:
                port, pin = get_port_and_pin(mosi)
                signals.append(Subsignal("mosi", Pins(_eem_pin(port, pin, pol))))
            if miso is not None:
                port, pin = get_port_and_pin(miso)
                signals.append(Subsignal("miso", Pins(_eem_pin(port, pin, pol))))
            if cs:
                cs_pins = []
                for cs_channel in cs:
                    port, pin = get_port_and_pin(cs_channel)
                    cs_pins.append(_eem_pin(port, pin, pol))
                signals.append(Subsignal("cs_n", Pins(*cs_pins)))
            return signals

        def dio_subsignals(dio, iostandard):
            signals = []
            for i, (channel0, _, _) in enumerate(dio):
                port, pin = get_port_and_pin(channel)
                signal_name = "dio{}".format(eem0)
                signal = (signal_name, i,
                          Subsignal("p", Pins(_eem_pin(port, pin, "p"))),
                          Subsignal("n", Pins(_eem_pin(port, pin, "n"))),
                          iostandard(eem0))
                signals.append(signal)
            return signals

        spi = [
            ("dio{}_spi{}_{}".format(eem0, i, pol), i,
             *spi_subsignals(clk, mosi, miso, cs, pol),
             iostandard(eem0))
            for i, (clk, mosi, miso, cs) in enumerate(spi) for pol in "pn"
        ]
        dio = dio_subsignals(dio, iostandard)
        return spi + dio

    @classmethod
    def add_std(cls, target, eem0, eem1, spi, dio, iostandard=default_iostandard):
        cls.add_extension(target, eem0, eem1, spi, dio, iostandard=iostandard)

        for i in range(len(spi)):
            phy = spi2.SPIMaster(
                target.platform.request("dio{}_spi{}_p".format(eem0, i)),
                target.platform.request("dio{}_spi{}_n".format(eem0, i))
            )
            target.submodules += phy
            target.rtio_channels.append(
                rtio.Channel.from_phy(phy, ififo_depth=4))

        dci = iostandard(eem0).name == "LVDS"
        for i, (_, dio_cls, edge_counter_cls) in enumerate(dio):
            pads = target.platform.request("dio{}".format(eem0), i)
            phy = dio_cls(pads.p, pads.n, dci=dci)
            target.submodules += phy
            target.rtio_channels.append(rtio.Channel.from_phy(phy))

            if edge_counter_cls is not None:
                state = getattr(phy, "input_state", None)
                if state is not None:
                    counter = edge_counter_cls(state)
                    target.submodules += counter
                    target.rtio_channels.append(rtio.Channel.from_phy(counter))


class Urukul(_EEM):
    @staticmethod
    def io(eem, eem_aux, iostandard):
        ios = [
            ("urukul{}_spi_p".format(eem), 0,
                Subsignal("clk", Pins(_eem_pin(eem, 0, "p"))),
                Subsignal("mosi", Pins(_eem_pin(eem, 1, "p"))),
                Subsignal("miso", Pins(_eem_pin(eem, 2, "p"))),
                Subsignal("cs_n", Pins(
                    *(_eem_pin(eem, i + 3, "p") for i in range(3)))),
                iostandard(eem),
            ),
            ("urukul{}_spi_n".format(eem), 0,
                Subsignal("clk", Pins(_eem_pin(eem, 0, "n"))),
                Subsignal("mosi", Pins(_eem_pin(eem, 1, "n"))),
                Subsignal("miso", Pins(_eem_pin(eem, 2, "n"))),
                Subsignal("cs_n", Pins(
                    *(_eem_pin(eem, i + 3, "n") for i in range(3)))),
                iostandard(eem),
            ),
        ]
        ttls = [(6, eem, "io_update"),
                (7, eem, "dds_reset_sync_in", Misc("IOB=TRUE"))]
        if eem_aux is not None:
            ttls += [(0, eem_aux, "sync_clk"),
                     (1, eem_aux, "sync_out"),
                     (2, eem_aux, "io_update_ret"),
                     (3, eem_aux, "nu_mosi3"),
                     (4, eem_aux, "sw0"),
                     (5, eem_aux, "sw1"),
                     (6, eem_aux, "sw2"),
                     (7, eem_aux, "sw3")]
        for i, j, sig, *extra_args in ttls:
            ios.append(
                ("urukul{}_{}".format(eem, sig), 0,
                    Subsignal("p", Pins(_eem_pin(j, i, "p"))),
                    Subsignal("n", Pins(_eem_pin(j, i, "n"))),
                    iostandard(j), *extra_args
                ))
        return ios

    @staticmethod
    def io_qspi(eem0, eem1, use_miso, iostandard):
        spi_ios = [(0, "clk"),
                   (1, "mosi"),
                   (3, 4, "cs_n")]
        if use_miso:
            spi_ios.append((2, "miso"))
        ios = [
            (
                "urukul{}_spi_{}".format(eem0, pol),
                0,
                *[
                    Subsignal(sig_name, Pins(
                        *[ _eem_pin(eem0, pin_idx, pol) for pin_idx in pin_indices ]
                    )) for *pin_indices, sig_name in spi_ios
                ],
                iostandard(eem0),
            ) for pol in ("p", "n")
        ]
        ttls = [(6, eem0, "io_update"),
                # FIXME: Causes critical warning "[Place 30-722]" when
                # synchronization is disabled.
                # No practical issue since `dds_reset_sync_in` is tied to GND
                # constant in this situation.
                #
                # See the proposed resolution in #2757.
                (7, eem0, "dds_reset_sync_in", Misc("IOB=TRUE")),
                (4, eem1, "sw0"),
                (5, eem1, "sw1"),
                (6, eem1, "sw2"),
                (7, eem1, "sw3")]
        for i, j, sig, *extra_args in ttls:
            ios.append(
                ("urukul{}_{}".format(eem0, sig), 0,
                    Subsignal("p", Pins(_eem_pin(j, i, "p"))),
                    Subsignal("n", Pins(_eem_pin(j, i, "n"))),
                    iostandard(j), *extra_args
                ))
        qspi_ios = [ (i, eem1, "mosi{}".format(i)) for i in range(4) ]
        if use_miso:
            # SPI MISO squeezes out QSPI NU_CLK from EEM0[2]
            # QSPI CS needs to make way for NU_CLK
            qspi_ios.append((5, eem0, "clk"))
        else:
            qspi_ios += [(2, eem0, "clk"),
                         (5, eem0, "cs")]
        ios += [
            (
                "urukul{}_qspi_{}".format(eem0, pol),
                0,
                *[ Subsignal(sig_name, Pins(_eem_pin(eem, i, pol)),
                    iostandard(eem)) for i, eem, sig_name in qspi_ios
                ]
            ) for pol in ("p", "n")
        ]
        return ios

    @classmethod
    def add_std(cls, target, eem, eem_aux, ttl_out_cls, dds_type, proto_rev,
                sync_gen_cls=None, iostandard=default_iostandard):
        cls.add_extension(target, eem, eem_aux, iostandard=iostandard)

        spi_phy = spi2.SPIMaster(target.platform.request("urukul{}_spi_p".format(eem)),
            target.platform.request("urukul{}_spi_n".format(eem)))
        target.submodules += spi_phy
        target.rtio_channels.append(rtio.Channel.from_phy(spi_phy, ififo_depth=4))

        pads = target.platform.request("urukul{}_dds_reset_sync_in".format(eem))
        if dds_type == "ad9912":
            # DDS_RESET for AD9912 variant only
            target.specials += DifferentialOutput(0, pads.p, pads.n)
        elif sync_gen_cls is not None:  # AD9910 variant and SYNC_IN to EEM
            sync_phy = sync_gen_cls(pad=pads.p, pad_n=pads.n, ftw_width=4)
            target.submodules += sync_phy
            target.rtio_channels.append(rtio.Channel.from_phy(sync_phy))

        pads = target.platform.request("urukul{}_io_update".format(eem))
        io_upd_phy = ttl_out_cls(pads.p, pads.n)
        target.submodules += io_upd_phy
        target.rtio_channels.append(rtio.Channel.from_phy(io_upd_phy))

        dds_monitor = dds.UrukulMonitor(spi_phy, io_upd_phy, dds_type, proto_rev)
        target.submodules += dds_monitor
        spi_phy.probes.extend(dds_monitor.probes)

        if eem_aux is not None:
            for signal in "sw0 sw1 sw2 sw3".split():
                pads = target.platform.request("urukul{}_{}".format(eem, signal))
                phy = ttl_out_cls(pads.p, pads.n)
                target.submodules += phy
                target.rtio_channels.append(rtio.Channel.from_phy(phy))


class Sampler(_EEM):
    @staticmethod
    def io(eem, eem_aux, iostandard):
        ios = [
            ("sampler{}_adc_spi_p".format(eem), 0,
                Subsignal("clk", Pins(_eem_pin(eem, 0, "p"))),
                Subsignal("miso", Pins(_eem_pin(eem, 1, "p")), Misc("DIFF_TERM=TRUE")),
                iostandard(eem),
            ),
            ("sampler{}_adc_spi_n".format(eem), 0,
                Subsignal("clk", Pins(_eem_pin(eem, 0, "n"))),
                Subsignal("miso", Pins(_eem_pin(eem, 1, "n")), Misc("DIFF_TERM=TRUE")),
                iostandard(eem),
            ),
            ("sampler{}_pgia_spi_p".format(eem), 0,
                Subsignal("clk", Pins(_eem_pin(eem, 4, "p"))),
                Subsignal("mosi", Pins(_eem_pin(eem, 5, "p"))),
                Subsignal("miso", Pins(_eem_pin(eem, 6, "p")), Misc("DIFF_TERM=TRUE")),
                Subsignal("cs_n", Pins(_eem_pin(eem, 7, "p"))),
                iostandard(eem),
            ),
            ("sampler{}_pgia_spi_n".format(eem), 0,
                Subsignal("clk", Pins(_eem_pin(eem, 4, "n"))),
                Subsignal("mosi", Pins(_eem_pin(eem, 5, "n"))),
                Subsignal("miso", Pins(_eem_pin(eem, 6, "n")), Misc("DIFF_TERM=TRUE")),
                Subsignal("cs_n", Pins(_eem_pin(eem, 7, "n"))),
                iostandard(eem),
            ),
        ] + [
            ("sampler{}_{}".format(eem, sig), 0,
                Subsignal("p", Pins(_eem_pin(j, i, "p"))),
                Subsignal("n", Pins(_eem_pin(j, i, "n"))),
                iostandard(j)
            ) for i, j, sig in [
                (2, eem, "sdr"),
                (3, eem, "cnv")
            ]
        ]
        if eem_aux is not None:
            ios += [
                ("sampler{}_adc_data_p".format(eem), 0,
                    Subsignal("clkout", Pins(_eem_pin(eem_aux, 0, "p"))),
                    Subsignal("sdoa", Pins(_eem_pin(eem_aux, 1, "p"))),
                    Subsignal("sdob", Pins(_eem_pin(eem_aux, 2, "p"))),
                    Subsignal("sdoc", Pins(_eem_pin(eem_aux, 3, "p"))),
                    Subsignal("sdod", Pins(_eem_pin(eem_aux, 4, "p"))),
                    Misc("DIFF_TERM=TRUE"),
                    iostandard(eem_aux),
                ),
                ("sampler{}_adc_data_n".format(eem), 0,
                    Subsignal("clkout", Pins(_eem_pin(eem_aux, 0, "n"))),
                    Subsignal("sdoa", Pins(_eem_pin(eem_aux, 1, "n"))),
                    Subsignal("sdob", Pins(_eem_pin(eem_aux, 2, "n"))),
                    Subsignal("sdoc", Pins(_eem_pin(eem_aux, 3, "n"))),
                    Subsignal("sdod", Pins(_eem_pin(eem_aux, 4, "n"))),
                    Misc("DIFF_TERM=TRUE"),
                    iostandard(eem_aux),
                ),
            ]
        return ios

    @classmethod
    def add_std(cls, target, eem, eem_aux, ttl_out_cls, iostandard=default_iostandard):
        cls.add_extension(target, eem, eem_aux, iostandard=iostandard)

        phy = spi2.SPIMaster(
                target.platform.request("sampler{}_adc_spi_p".format(eem)),
                target.platform.request("sampler{}_adc_spi_n".format(eem)))
        target.submodules += phy
        target.rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=4))
        phy = spi2.SPIMaster(
                target.platform.request("sampler{}_pgia_spi_p".format(eem)),
                target.platform.request("sampler{}_pgia_spi_n".format(eem)))
        target.submodules += phy

        target.rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=4))
        pads = target.platform.request("sampler{}_cnv".format(eem))
        phy = ttl_out_cls(pads.p, pads.n)
        target.submodules += phy

        target.rtio_channels.append(rtio.Channel.from_phy(phy))
        sdr = target.platform.request("sampler{}_sdr".format(eem))
        target.specials += DifferentialOutput(1, sdr.p, sdr.n)


class Zotino(_EEM):
    @staticmethod
    def io(eem, iostandard):
        return [
            ("zotino{}_spi_p".format(eem), 0,
                Subsignal("clk", Pins(_eem_pin(eem, 0, "p"))),
                Subsignal("mosi", Pins(_eem_pin(eem, 1, "p"))),
                Subsignal("miso", Pins(_eem_pin(eem, 2, "p"))),
                Subsignal("cs_n", Pins(
                    _eem_pin(eem, 3, "p"), _eem_pin(eem, 4, "p"))),
                iostandard(eem),
            ),
            ("zotino{}_spi_n".format(eem), 0,
                Subsignal("clk", Pins(_eem_pin(eem, 0, "n"))),
                Subsignal("mosi", Pins(_eem_pin(eem, 1, "n"))),
                Subsignal("miso", Pins(_eem_pin(eem, 2, "n"))),
                Subsignal("cs_n", Pins(
                    _eem_pin(eem, 3, "n"), _eem_pin(eem, 4, "n"))),
                iostandard(eem),
            ),
        ] + [
            ("zotino{}_{}".format(eem, sig), 0,
                    Subsignal("p", Pins(_eem_pin(j, i, "p"))),
                    Subsignal("n", Pins(_eem_pin(j, i, "n"))),
                    iostandard(j)
            ) for i, j, sig in [
                (5, eem, "ldac_n"),
                (6, eem, "busy"),
                (7, eem, "clr_n"),
            ]
        ]

    @classmethod
    def add_std(cls, target, eem, ttl_out_cls, iostandard=default_iostandard):
        cls.add_extension(target, eem, iostandard=iostandard)

        spi_phy = spi2.SPIMaster(target.platform.request("zotino{}_spi_p".format(eem)),
            target.platform.request("zotino{}_spi_n".format(eem)))
        target.submodules += spi_phy
        target.rtio_channels.append(rtio.Channel.from_phy(spi_phy, ififo_depth=4))

        pads = target.platform.request("zotino{}_ldac_n".format(eem))
        ldac_phy = ttl_out_cls(pads.p, pads.n)
        target.submodules += ldac_phy
        target.rtio_channels.append(rtio.Channel.from_phy(ldac_phy))

        pads = target.platform.request("zotino{}_clr_n".format(eem))
        clr_phy = ttl_out_cls(pads.p, pads.n)
        target.submodules += clr_phy
        target.rtio_channels.append(rtio.Channel.from_phy(clr_phy))

        dac_monitor = ad53xx_monitor.AD53XXMonitor(spi_phy.rtlink, ldac_phy.rtlink)
        target.submodules += dac_monitor
        spi_phy.probes.extend(dac_monitor.probes)


class Grabber(_EEM):
    @staticmethod
    def io(eem, eem_aux, iostandard):
        ios = [
            ("grabber{}_video".format(eem), 0,
                Subsignal("clk_p", Pins(_eem_pin(eem, 0, "p"))),
                Subsignal("clk_n", Pins(_eem_pin(eem, 0, "n"))),
                Subsignal("sdi_p", Pins(*[_eem_pin(eem, i, "p") for i in range(1, 5)])),
                Subsignal("sdi_n", Pins(*[_eem_pin(eem, i, "n") for i in range(1, 5)])),
                iostandard(eem), Misc("DIFF_TERM=TRUE")
            ),
            ("grabber{}_cc0".format(eem), 0,
                Subsignal("p", Pins(_eem_pin(eem, 5, "p"))),
                Subsignal("n", Pins(_eem_pin(eem, 5, "n"))),
                iostandard(eem)
            ),
            ("grabber{}_cc1".format(eem), 0,
                Subsignal("p", Pins(_eem_pin(eem, 6, "p"))),
                Subsignal("n", Pins(_eem_pin(eem, 6, "n"))),
                iostandard(eem)
            ),
            ("grabber{}_cc2".format(eem), 0,
                Subsignal("p", Pins(_eem_pin(eem, 7, "p"))),
                Subsignal("n", Pins(_eem_pin(eem, 7, "n"))),
                iostandard(eem)
            ),
        ]
        if eem_aux is not None:
            ios += [
                ("grabber{}_video_m".format(eem), 0,
                    Subsignal("clk_p", Pins(_eem_pin(eem_aux, 0, "p"))),
                    Subsignal("clk_n", Pins(_eem_pin(eem_aux, 0, "n"))),
                    Subsignal("sdi_p", Pins(*[_eem_pin(eem_aux, i, "p") for i in range(1, 5)])),
                    Subsignal("sdi_n", Pins(*[_eem_pin(eem_aux, i, "n") for i in range(1, 5)])),
                    iostandard(eem_aux), Misc("DIFF_TERM=TRUE")
                ),
                ("grabber{}_serrx".format(eem), 0,
                    Subsignal("p", Pins(_eem_pin(eem_aux, 5, "p"))),
                    Subsignal("n", Pins(_eem_pin(eem_aux, 5, "n"))),
                    iostandard(eem_aux), Misc("DIFF_TERM=TRUE")
                ),
                ("grabber{}_sertx".format(eem), 0,
                    Subsignal("p", Pins(_eem_pin(eem_aux, 6, "p"))),
                    Subsignal("n", Pins(_eem_pin(eem_aux, 6, "n"))),
                    iostandard(eem_aux)
                ),
                ("grabber{}_cc3".format(eem), 0,
                    Subsignal("p", Pins(_eem_pin(eem_aux, 7, "p"))),
                    Subsignal("n", Pins(_eem_pin(eem_aux, 7, "n"))),
                    iostandard(eem_aux)
                ),
            ]
        return ios

    @classmethod
    def add_std(cls, target, eem, eem_aux, eem_aux2, ttl_out_cls, roi_engine_count,
            iostandard=default_iostandard):
        cls.add_extension(target, eem, eem_aux, iostandard=iostandard)

        pads = target.platform.request("grabber{}_video".format(eem))
        target.platform.add_period_constraint(pads.clk_p, 14.71)

        # Use dummy pads for 1-EEM mode Grabbers to ensure consistent CSRs
        # across the grabber CSR group.
        uart_pads = SimpleNamespace(tx=Signal(), rx=Signal())
        if eem_aux is not None:
            tx = target.platform.request("grabber{}_sertx".format(eem))
            rx = target.platform.request("grabber{}_serrx".format(eem))
            target.specials += [
                DifferentialOutput(uart_pads.tx, tx.p, tx.n),
                DifferentialInput(rx.p, rx.n, uart_pads.rx)
            ]

        phy = grabber.Grabber(pads, uart_pads, roi_engine_count=roi_engine_count, clk_freq=target.clk_freq)

        name = "grabber{}".format(len(target.grabber_csr_group))
        setattr(target.submodules, name, phy)

        target.platform.add_false_path_constraints(
            target.crg.cd_sys.clk, phy.deserializer.cd_cl.clk)
        # Avoid bogus s/h violations at the clock input being sampled
        # by the ISERDES. This uses dynamic calibration.
        target.platform.add_false_path_constraints(
            pads.clk_p, phy.deserializer.cd_cl7x.clk)

        target.grabber_csr_group.append(name)
        target.csr_devices.append(name)
        target.rtio_channels += [
            rtio.Channel(phy.config),
            rtio.Channel(phy.gate_data)
        ]

        if ttl_out_cls is not None:
            for signal in "cc0 cc1 cc2".split():
                pads = target.platform.request("grabber{}_{}".format(eem, signal))
                phy = ttl_out_cls(pads.p, pads.n)
                target.submodules += phy
                target.rtio_channels.append(rtio.Channel.from_phy(phy))
            if eem_aux is not None:
                pads = target.platform.request("grabber{}_cc3".format(eem))
                phy = ttl_out_cls(pads.p, pads.n)
                target.submodules += phy
                target.rtio_channels.append(rtio.Channel.from_phy(phy))


class SUServo(_EEM):
    @staticmethod
    def io(*eems, use_miso, iostandard):
        assert len(eems) in range(4, 12 + 1, 2)
        io = Sampler.io(*eems[0:2], iostandard=iostandard)
        for eem0, eem1 in zip(eems[2::2], eems[3::2]):
            io += Urukul.io_qspi(
                eem0, eem1, use_miso=use_miso, iostandard=iostandard)
        return io

    @classmethod
    def add_std(cls, target, eems_sampler, eems_urukul,
                t_rtt=4, clk=1, shift=11, profile=5,
                sync_gen_cls=None,
                use_miso=True,
                sysclks_per_clk=8,
                iostandard=default_iostandard):
        """Add a 8-channel Sampler-Urukul Servo

        :param t_rtt: upper estimate for clock round-trip propagation time from
            ``sck`` at the FPGA to ``clkout`` at the FPGA, measured in RTIO
            coarse cycles (default: 4). This is the sum of the round-trip
            cabling delay and the 8 ns max propagation delay on Sampler (ADC
            and LVDS drivers). Increasing ``t_rtt`` increases servo latency.
            With all other parameters at their default values, ``t_rtt`` values
            above 4 also increase the servo period (reduce servo bandwidth).
        :param clk: DDS SPI clock cycle half-width in RTIO coarse cycles
            (default: 1)
        :param shift: fixed-point scaling factor for IIR coefficients
            (default: 11)
        :param profile: log2 of the number of profiles for each DDS channel
            (default: 5)
        :param sysclks_per_clk: DDS "sysclk" cycles per RTIO clock cycle.
            Only the default (8) is supported. Other ratios can be supported
            provided that that I/O update of the DDSes are aligned to its own
            sysclk (default: 8)
        """
        cls.add_extension(
            target, *(eems_sampler + sum(eems_urukul, [])),
            use_miso=use_miso, iostandard=iostandard)
        eem_sampler = "sampler{}".format(eems_sampler[0])
        eem_urukul = ["urukul{}".format(i[0]) for i in eems_urukul]

        sampler_pads = servo_pads.SamplerPads(target.platform, eem_sampler)
        urukul_pads = servo_pads.UrukulPads(
            target.platform, sync_gen_cls is not None, *eem_urukul)
        target.submodules += sampler_pads, urukul_pads
        # timings in units of RTIO coarse period
        adc_p = servo.ADCParams(width=16, channels=8, lanes=4, t_cnvh=4,
                                # account for SCK DDR to CONV latency
                                # difference (4 cycles measured)
                                t_conv=57 - 4, t_rtt=t_rtt + 4)
        iir_p = servo.IIRWidths(state=25, coeff=18, adc=16, asf=14, word=16,
                                accu=48, shift=shift,
                                profile=profile, dly=8)
        dds_p = servo.DDSParams(width=8 + 32 + 16 + 16,
                                channels=4*len(eems_urukul), clk=clk)
        su = servo.Servo(sampler_pads, urukul_pads, adc_p, iir_p, dds_p, sysclks_per_clk)
        su = ClockDomainsRenamer("rio_phy")(su)
        # explicitly name the servo submodule to enable the migen namer to derive
        # a name for the adc return clock domain
        setattr(target.submodules, "suservo_eem{}".format(eems_sampler[0]), su)

        ctrls = [rtservo.RTServoCtrl(ctrl) for ctrl in su.iir.ctrl]
        target.submodules += ctrls
        target.rtio_channels.extend(
            rtio.Channel.from_phy(ctrl) for ctrl in ctrls)
        mem = rtservo.RTServoMem(iir_p, su, sysclks_per_clk)
        target.submodules += mem
        target.rtio_channels.append(rtio.Channel.from_phy(mem, ififo_depth=4))

        phy = spi2.SPIMaster(
            target.platform.request("{}_pgia_spi_p".format(eem_sampler)),
            target.platform.request("{}_pgia_spi_n".format(eem_sampler)))
        target.submodules += phy
        target.rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=4))

        for j, eem_urukuli in enumerate(eem_urukul):
            sync_pads = target.platform.request("{}_dds_reset_sync_in".format(eem_urukuli))

            if sync_gen_cls is not None:
                io_upd_phy = urukul_pads.ttl_rtio_phys[j]
                target.rtio_channels.append(rtio.Channel.from_phy(io_upd_phy))

                sync_phy = sync_gen_cls(pad=sync_pads.p, pad_n=sync_pads.n, ftw_width=4)
                target.submodules += sync_phy
                target.rtio_channels.append(rtio.Channel.from_phy(sync_phy))

            else:
                target.specials += DifferentialOutput(0, sync_pads.p, sync_pads.n)

            spi_p, spi_n = (
                target.platform.request("{}_spi_p".format(eem_urukuli)),
                target.platform.request("{}_spi_n".format(eem_urukuli)))

            phy = spi2.SPIMaster(spi_p, spi_n)
            target.submodules += phy
            target.rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=4))

            for i, signal in enumerate("sw0 sw1 sw2 sw3".split()):
                pads = target.platform.request("{}_{}".format(eem_urukuli, signal))
                target.specials += DifferentialOutput(
                    su.iir.ctrl[j*4 + i].en_out, pads.p, pads.n)


class Mirny(_EEM):
    @staticmethod
    def io(eem, iostandard):
        ios = [
            ("mirny{}_spi_p".format(eem), 0,
                Subsignal("clk", Pins(_eem_pin(eem, 0, "p"))),
                Subsignal("mosi", Pins(_eem_pin(eem, 1, "p"))),
                Subsignal("miso", Pins(_eem_pin(eem, 2, "p")), Misc("DIFF_TERM=TRUE")),
                Subsignal("cs_n", Pins(_eem_pin(eem, 3, "p"))),
                iostandard(eem),
            ),
            ("mirny{}_spi_n".format(eem), 0,
                Subsignal("clk", Pins(_eem_pin(eem, 0, "n"))),
                Subsignal("mosi", Pins(_eem_pin(eem, 1, "n"))),
                Subsignal("miso", Pins(_eem_pin(eem, 2, "n")), Misc("DIFF_TERM=TRUE")),
                Subsignal("cs_n", Pins(_eem_pin(eem, 3, "n"))),
                iostandard(eem),
            ),
        ]
        for i in range(4):
            ios.append(
                ("mirny{}_io{}".format(eem, i), 0,
                    Subsignal("p", Pins(_eem_pin(eem, 4 + i, "p"))),
                    Subsignal("n", Pins(_eem_pin(eem, 4 + i, "n"))),
                    iostandard(eem)
                ))
        return ios

    @classmethod
    def add_std(cls, target, eem, ttl_out_cls, iostandard=default_iostandard):
        cls.add_extension(target, eem, iostandard=iostandard)

        phy = spi2.SPIMaster(
            target.platform.request("mirny{}_spi_p".format(eem)),
            target.platform.request("mirny{}_spi_n".format(eem)))
        target.submodules += phy
        target.rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=4))

        for i in range(4):
            pads = target.platform.request("mirny{}_io{}".format(eem, i))
            phy = ttl_out_cls(pads.p, pads.n)
            target.submodules += phy
            target.rtio_channels.append(rtio.Channel.from_phy(phy))


class Fastino(_EEM):
    @staticmethod
    def io(eem, iostandard):
        return [
            ("fastino{}_ser_{}".format(eem, pol), 0,
                Subsignal("clk", Pins(_eem_pin(eem, 0, pol))),
                Subsignal("mosi", Pins(*(_eem_pin(eem, i, pol)
                    for i in range(1, 7)))),
                Subsignal("miso", Pins(_eem_pin(eem, 7, pol)),
                          Misc("DIFF_TERM=TRUE")),
                iostandard(eem),
            ) for pol in "pn"]

    @classmethod
    def add_std(cls, target, eem, log2_width, iostandard=default_iostandard):
        cls.add_extension(target, eem, iostandard=iostandard)

        phy = fastino.Fastino(target.platform.request("fastino{}_ser_p".format(eem)),
            target.platform.request("fastino{}_ser_n".format(eem)),
            log2_width=log2_width)
        target.submodules += phy
        target.rtio_channels.append(rtio.Channel.from_phy(phy, ififo_depth=4))


class Phaser(_EEM):
    @staticmethod
    def io(eem, iostandard):
        return [
            ("phaser{}_ser_{}".format(eem, pol), 0,
                Subsignal("clk", Pins(_eem_pin(eem, 0, pol))),
                Subsignal("mosi", Pins(*(_eem_pin(eem, i, pol)
                    for i in range(1, 7)))),
                Subsignal("miso", Pins(_eem_pin(eem, 7, pol)),
                          Misc("DIFF_TERM=TRUE")),
                iostandard(eem),
            ) for pol in "pn"]

    @classmethod
    def add_std(cls, target, eem, mode="base", iostandard=default_iostandard):
        cls.add_extension(target, eem, iostandard=iostandard)

        if mode == "base":
            phy = phaser.Base(
                target.platform.request("phaser{}_ser_p".format(eem)),
                target.platform.request("phaser{}_ser_n".format(eem)))
            target.submodules += phy
            target.rtio_channels.extend([
                rtio.Channel.from_phy(phy, ififo_depth=4),
                rtio.Channel.from_phy(phy.ch0.frequency),
                rtio.Channel.from_phy(phy.ch0.phase_amplitude),
                rtio.Channel.from_phy(phy.ch1.frequency),
                rtio.Channel.from_phy(phy.ch1.phase_amplitude),
            ])
        elif mode == "miqro":
            phy = phaser.Miqro(
                target.platform.request("phaser{}_ser_p".format(eem)),
                target.platform.request("phaser{}_ser_n".format(eem)))
            target.submodules += phy
            target.rtio_channels.extend([
                rtio.Channel.from_phy(phy, ififo_depth=4),
                rtio.Channel.from_phy(phy.ch0),
                rtio.Channel.from_phy(phy.ch1),
            ])
        else:
            raise ValueError("invalid mode", mode)


class HVAmp(_EEM):
    @staticmethod
    def io(eem, iostandard):
        return [
            ("hvamp{}_out_en".format(eem), i,
                    Subsignal("p", Pins(_eem_pin(eem, i, "p"))),
                    Subsignal("n", Pins(_eem_pin(eem, i, "n"))),
                    iostandard(eem)
            ) for i in range(8)]

    @classmethod
    def add_std(cls, target, eem, ttl_out_cls, iostandard=default_iostandard):
        cls.add_extension(target, eem, iostandard=iostandard)

        for i in range(8):
            pads = target.platform.request("hvamp{}_out_en".format(eem), i)
            phy = ttl_out_cls(pads.p, pads.n)
            target.submodules += phy
            target.rtio_channels.append(rtio.Channel.from_phy(phy))


class DrtioOverEEM(_EEM):
    @staticmethod
    def io(eem, iostandard=default_iostandard):
        # Master: Pair 0~3 data IN, 4~7 OUT
        data_in = ("drtio_over_eem{}_rx".format(eem), 0,
            Subsignal("p", Pins("{} {} {} {}".format(*[
                _eem_pin(eem, i, "p") for i in range(4)
            ]))),
            Subsignal("n", Pins("{} {} {} {}".format(*[
                _eem_pin(eem, i, "n") for i in range(4)
            ]))),
            iostandard(eem),
            Misc("DIFF_TERM=TRUE"),
        )

        data_out = ("drtio_over_eem{}_tx".format(eem), 0,
            Subsignal("p", Pins("{} {} {} {}".format(*[
                _eem_pin(eem, i, "p") for i in range(4, 8)
            ]))),
            Subsignal("n", Pins("{} {} {} {}".format(*[
                _eem_pin(eem, i, "n") for i in range(4, 8)
            ]))),
            iostandard(eem),
        )

        return [data_in, data_out]

    @classmethod
    def add_std(cls, target, eem, eem_aux, iostandard=default_iostandard):
        cls.add_extension(target, eem, is_drtio_over_eem=True, iostandard=iostandard)
        target.eem_drtio_channels.append((target.platform.request("drtio_over_eem{}_rx".format(eem), 0), target.platform.request("drtio_over_eem{}_tx".format(eem), 0)))
