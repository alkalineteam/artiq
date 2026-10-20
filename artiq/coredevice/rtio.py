from numpy import int32, int64

from artiq.language.core import compile, extern, kernel


@extern
def rtio_output(target: int32, data: int32):
    raise NotImplementedError("syscall not simulated")


@extern
def rtio_output_wide(target: int32, data: list[int32]):
    raise NotImplementedError("syscall not simulated")


@extern
def rtio_input_timestamp(timeout_mu: int64, channel: int32) -> int64:
    raise NotImplementedError("syscall not simulated")


@extern
def rtio_input_data(channel: int32) -> int32:
    raise NotImplementedError("syscall not simulated")


@extern
def rtio_input_timestamped_data(timeout_mu: int64,
                                channel: int32) -> tuple[int64, int32]:
    """Wait for an input event up to ``timeout_mu`` on the given channel, and
    return a tuple of timestamp and attached data, or (-1, 0) if the timeout is
    reached."""
    raise NotImplementedError("syscall not simulated")


@extern
def rtio_batch_start():
    raise NotImplementedError("syscall not simulated")


@extern
def rtio_batch_end():
    raise NotImplementedError("syscall not simulated")


@compile
class RTIOBatch:
    """Context manager for batching RTIO events.

    All output RTIO events within the context will be buffered
    on the core device and executed immediately after leaving the context.

    This feature is available only on Zynq devices such as Kasli-SoC,
    ZC706 and EBAZ4205 with ACP Kernel Initiator enabled.
    """
    def __init__(self, dmgr, core_device="core"):
        # since this is just a syscall wrapper for semantics,
        # nothing has to be done in init
        pass

    @kernel
    def __enter__(self):
        rtio_batch_start()

    @kernel
    def __exit__(self):
        rtio_batch_end()
