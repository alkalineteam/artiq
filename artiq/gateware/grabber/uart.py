from migen import *
from misoc.interconnect.csr import *
from misoc.interconnect import stream


class GrabberUART(Module, AutoCSR):
    def __init__(self, phy, tx_fifo_depth=8, rx_fifo_depth=8):
        self._rx = CSR(8)
        self._tx = CSR(8)
        self._txfull = CSRStatus()
        self._rxempty = CSRStatus()

        # # #

        # TX
        tx_fifo = stream.SyncFIFO([("data", 8)], tx_fifo_depth)
        self.submodules += tx_fifo

        self.comb += [
            tx_fifo.sink.stb.eq(self._tx.re),
            tx_fifo.sink.data.eq(self._tx.r),
            self._txfull.status.eq(~tx_fifo.sink.ack),
            tx_fifo.source.connect(phy.sink),
        ]

        # RX
        rx_fifo = stream.SyncFIFO([("data", 8)], rx_fifo_depth)
        self.submodules += rx_fifo

        self.comb += [
            phy.source.connect(rx_fifo.sink),
            self._rxempty.status.eq(~rx_fifo.source.stb),
            self._rx.w.eq(rx_fifo.source.data),
            rx_fifo.source.ack.eq(self._rx.re)
        ]
