"""GPU memory reading and the fit verdict shown on every model row."""

from app.schemas import GpuMemory
from app.services import gpu

GIB = 1024 * 1024 * 1024


def _card(total_gib: float, free_gib: float) -> GpuMemory:
    return GpuMemory(
        total_bytes=int(total_gib * GIB),
        used_bytes=int((total_gib - free_gib) * GIB),
        free_bytes=int(free_gib * GIB),
    )


def test_parses_nvidia_smi_output():
    memory = gpu.parse_output("16303, 5540, 10293\n")
    assert memory is not None
    assert memory.total_bytes == 16303 * gpu.MIB
    assert memory.used_bytes == 5540 * gpu.MIB
    assert memory.free_bytes == 10293 * gpu.MIB


def test_keeps_only_the_first_gpu():
    memory = gpu.parse_output("16303, 5540, 10293\n24564, 100, 24464\n")
    assert memory is not None
    assert memory.total_bytes == 16303 * gpu.MIB


def test_unusable_output_is_none_rather_than_zero():
    # A wrong number is worse than no number.
    assert gpu.parse_output("") is None
    assert gpu.parse_output("no devices were found") is None
    assert gpu.parse_output("N/A, N/A, N/A") is None


def test_read_memory_is_none_without_nvidia_smi(monkeypatch):
    monkeypatch.setattr(gpu.shutil, "which", lambda _name: None)
    assert gpu.read_memory() is None


def test_read_memory_survives_a_failing_nvidia_smi(monkeypatch):
    def _boom(*_args, **_kwargs):
        raise OSError("driver not loaded")

    monkeypatch.setattr(gpu.shutil, "which", lambda _name: "/usr/bin/nvidia-smi")
    monkeypatch.setattr(gpu.subprocess, "run", _boom)
    assert gpu.read_memory() is None


def test_model_larger_than_the_card_is_too_large():
    # The real case: qwen2.5:32b at ~18.5 GiB on a 16 GiB card.
    assert gpu.fit_verdict(int(18.5 * GIB), _card(16, 16)) == "too_large"


def test_model_that_fits_the_card_but_not_the_free_memory_is_tight():
    assert gpu.fit_verdict(int(11 * GIB), _card(16, 10)) == "tight"


def test_model_fitting_the_free_memory_fits():
    assert gpu.fit_verdict(int(4.5 * GIB), _card(16, 10)) == "fits"


def test_headroom_is_kept_so_a_model_that_just_fills_the_card_is_refused():
    # Weights alone are not the whole footprint: KV cache and context follow.
    assert gpu.fit_verdict(16 * GIB, _card(16, 16)) == "too_large"


def test_no_verdict_without_a_size_or_without_a_gpu():
    assert gpu.fit_verdict(None, _card(16, 10)) is None
    assert gpu.fit_verdict(4 * GIB, None) is None
    assert gpu.fit_verdict(4 * GIB, _card(0, 0)) is None


# --- Régressions trouvées en revue ---------------------------------------


def test_a_card_reporting_zero_total_is_no_reading_at_all():
    # nvidia-smi can report zeros while a driver is resetting. Accepting that
    # divided by zero in the usage bar and returned HTTP 500 on the inventory.
    assert gpu.parse_output("0, 0, 0") is None
    assert gpu.parse_output("0, 0, 0\n16303, 5540, 10293") is not None


def test_reading_the_gpu_does_not_block_the_event_loop():
    """nvidia-smi is synchronous with a 2 s timeout.

    Called inline from an async endpoint it froze every other request, the
    gateway included. The endpoints must hand it to a thread.
    """
    import asyncio
    import time

    from app import main

    def _slow():
        time.sleep(0.25)
        return None

    async def scenario():
        ticks = 0

        async def ticker():
            nonlocal ticks
            while True:
                await asyncio.sleep(0.01)
                ticks += 1

        task = asyncio.create_task(ticker())
        await asyncio.sleep(0)
        main.gpu_service.read_memory = _slow
        try:
            await main._read_gpu()
        finally:
            task.cancel()
            main.gpu_service.read_memory = gpu.read_memory
        return ticks

    # The loop must keep running while the slow call is in flight.
    assert asyncio.run(scenario()) > 5
