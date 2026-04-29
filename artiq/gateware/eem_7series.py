from artiq.gateware import eem
from artiq.gateware.rtio.phy import ttl_simple, ttl_serdes_7series, edge_counter


def peripheral_dio(module, peripheral, **kwargs):
    ttl_classes = {
        "input": ttl_serdes_7series.InOut_8X,
        "output": ttl_serdes_7series.Output_8X,
        "clkgen": ttl_simple.ClockGen
    }
    if peripheral["edge_counter"]:
        edge_counter_cls = edge_counter.SimpleEdgeCounter
    else:
        edge_counter_cls = None
    has_second_port = len(peripheral["ports"]) == 2
    if peripheral.get("board", "") != "RJ45_LVDS":
        if has_second_port:
            raise ValueError("wrong number of ports")
        eem.DIO.add_std(module,
                        peripheral["ports"][0],
                        ttl_classes[peripheral["bank_direction_low"]],
                        ttl_classes[peripheral["bank_direction_high"]],
                        edge_counter_cls = edge_counter_cls,
                        **kwargs)
    else:
        dio_directions = peripheral["ch_direction_0_3"] + peripheral["ch_direction_4_7"] + peripheral.get("ch_direction_8_11", []) + peripheral.get("ch_direction_12_15", [])
        dio_cls_list = [ttl_classes[name] for name in dio_directions]
        eem.DIO.add_rj45_lvds(module,
                              peripheral["ports"][0],
                              peripheral["ports"][1] if has_second_port else None,
                              dio_cls_list,
                              edge_counter_cls = edge_counter_cls,
                              **kwargs)


def peripheral_dio_spi(module, peripheral, **kwargs):
    if peripheral.get("board", "") != "RJ45_LVDS" and len(peripheral["ports"]) != 1:
        raise ValueError("wrong number of ports")
    defined_channels = []
    spi = [(s["clk"], s.get("mosi"), s.get("miso"), s.get("cs", []))
           for s in peripheral["spi"]]
    for clk, mosi, miso, cs in spi:
        defined_channels.append(clk)
        if mosi is not None:
            defined_channels.append(mosi)
        if miso is not None:
            defined_channels.append(miso)
        defined_channels.extend(cs)

    dio_config = peripheral.get("dio", {})
    if dio_config.get("edge_counter", False):
        edge_counter_cls = edge_counter.SimpleEdgeCounter
    else:
        edge_counter_cls = None
    input_channels = [(pin, ttl_serdes_7series.InOut_8X, edge_counter_cls) for pin in dio_config.get("input_channels", [])]
    output_channels = [(pin, ttl_serdes_7series.Output_8X, None) for pin in dio_config.get("output_channels", [])]
    clkgen_channels = [(pin, ttl_simple.ClockGen, None) for pin in dio_config.get("clkgen_channels", [])]
    defined_channels.extend([ch for ch, _, _ in input_channels + output_channels + clkgen_channels])

    for channel in range(8 * len(peripheral["ports"])):
        if channel not in defined_channels:
            raise ValueError("missing dio channel: ch{}, dio_spi on EEM{}".format(channel, peripheral["ports"][0]))
    eem.DIO_SPI.add_std(module,
                        peripheral["ports"][0],
                        peripheral["ports"][1] if len(peripheral["ports"]) == 2 else None,
                        spi,
                        input_channels + output_channels + clkgen_channels,
                        **kwargs)


def peripheral_urukul(module, peripheral, **kwargs):
    if len(peripheral["ports"]) == 1:
        port, port_aux = peripheral["ports"][0], None
    elif len(peripheral["ports"]) == 2:
        port, port_aux = peripheral["ports"]
    else:
        raise ValueError("wrong number of ports")
    if peripheral["synchronization"]:
        sync_gen_cls = ttl_simple.ClockGen
    else:
        sync_gen_cls = None
    eem.Urukul.add_std(module, port, port_aux, ttl_serdes_7series.Output_8X,
        peripheral["dds"], peripheral["proto_rev"], sync_gen_cls, **kwargs)


def peripheral_sampler(module, peripheral, **kwargs):
    if len(peripheral["ports"]) == 1:
        port, port_aux = peripheral["ports"][0], None
    elif len(peripheral["ports"]) == 2:
        port, port_aux = peripheral["ports"]
    else:
        raise ValueError("wrong number of ports")
    eem.Sampler.add_std(module, port, port_aux, ttl_serdes_7series.Output_8X,
        **kwargs)


def peripheral_suservo(module, peripheral, **kwargs):
    if len(peripheral["sampler_ports"]) != 2:
        raise ValueError("wrong number of Sampler ports")
    if "urukul_ports" in peripheral:
        urukul_ports = peripheral["urukul_ports"]
    else:
        urukul_ports = []
        if len(peripheral["urukul0_ports"]) != 2:
            raise ValueError("wrong number of Urukul #0 ports")
        urukul_ports.append(peripheral["urukul0_ports"])
        if "urukul1_ports" in peripheral:
            if len(peripheral["urukul1_ports"]) != 2:
                raise ValueError("wrong number of Urukul #1 ports")
            urukul_ports.append(peripheral["urukul1_ports"])
    if peripheral["synchronization"]:
        sync_gen_cls = ttl_simple.ClockGen
    else:
        sync_gen_cls = None
    use_miso = peripheral["proto_rev"] == 9

    eem.SUServo.add_std(module,
        peripheral["sampler_ports"],
        urukul_ports, sync_gen_cls=sync_gen_cls, use_miso=use_miso, **kwargs)


def peripheral_zotino(module, peripheral, **kwargs):
    if len(peripheral["ports"]) != 1:
        raise ValueError("wrong number of ports")
    eem.Zotino.add_std(module, peripheral["ports"][0],
        ttl_serdes_7series.Output_8X, **kwargs)


def peripheral_grabber(module, peripheral, **kwargs):
    if len(peripheral["ports"]) == 1:
        port = peripheral["ports"][0]
        port_aux = None
        port_aux2 = None
    elif len(peripheral["ports"]) == 2:
        port, port_aux = peripheral["ports"]
        port_aux2 = None
    elif len(peripheral["ports"]) == 3:
        port, port_aux, port_aux2 = peripheral["ports"]
    else:
        raise ValueError("wrong number of ports")

    eem.Grabber.add_std(
        module,
        port,
        port_aux,
        port_aux2,
        ttl_out_cls=None,
        roi_engine_count=peripheral["roi_engine_count"],
        **kwargs
    )


def peripheral_mirny(module, peripheral, **kwargs):
    if len(peripheral["ports"]) != 1:
        raise ValueError("wrong number of ports")
    eem.Mirny.add_std(module, peripheral["ports"][0],
        ttl_serdes_7series.Output_8X, **kwargs)


def peripheral_fastino(module, peripheral, **kwargs):
    if len(peripheral["ports"]) != 1:
        raise ValueError("wrong number of ports")
    eem.Fastino.add_std(module, peripheral["ports"][0],
        peripheral["log2_width"], **kwargs)


def peripheral_phaser(module, peripheral, **kwargs):
    if len(peripheral["ports"]) != 1:
        raise ValueError("wrong number of ports")
    eem.Phaser.add_std(module, peripheral["ports"][0],
        peripheral["mode"], **kwargs)


def peripheral_hvamp(module, peripheral, **kwargs):
    if len(peripheral["ports"]) != 1:
        raise ValueError("wrong number of ports")
    eem.HVAmp.add_std(module, peripheral["ports"][0],
        ttl_simple.Output, **kwargs)

def peripheral_drtio_over_eem(module, peripheral, **kwargs):
    if len(peripheral["ports"]) == 1:
        port = peripheral["ports"][0]
        port_aux = None
    elif len(peripheral["ports"]) == 2:
        port, port_aux = peripheral["ports"]
    else:
        raise ValueError("wrong number of ports")
    eem.DrtioOverEEM.add_std(module, port, port_aux, **kwargs)

peripheral_processors = {
    "dio": peripheral_dio,
    "dio_spi": peripheral_dio_spi,
    "urukul": peripheral_urukul,
    "sampler": peripheral_sampler,
    "suservo": peripheral_suservo,
    "zotino": peripheral_zotino,
    "grabber": peripheral_grabber,
    "mirny": peripheral_mirny,
    "fastino": peripheral_fastino,
    "phaser": peripheral_phaser,
    "phaser_drtio": peripheral_drtio_over_eem,
    "hvamp": peripheral_hvamp,
    "shuttler": peripheral_drtio_over_eem,
    "songbird": peripheral_drtio_over_eem,
}


def add_peripherals(module, peripherals, **kwargs):
    for peripheral in peripherals:
        peripheral_processors[peripheral["type"]](module, peripheral, **kwargs)
