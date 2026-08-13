"""GPU memory, read from `nvidia-smi`.

Answers the question the inventory could not: will this model fit?

Deliberately shells out instead of taking a binding as a dependency — the
cockpit stays installable on a machine with no GPU, and a missing or failing
`nvidia-smi` simply means "unknown", never a wrong number.
"""

from __future__ import annotations

import logging
import shutil
import subprocess

from app.schemas import GpuMemory

logger = logging.getLogger("llm_cockpit.gpu")

_QUERY = "memory.total,memory.used,memory.free"
_TIMEOUT_S = 2.0
MIB = 1024 * 1024

# A model needs room for its weights plus a working margin (KV cache, context,
# whatever else already sits on the card). Reported as a separate verdict
# rather than folded into the numbers, so the raw figures stay honest.
HEADROOM_BYTES = 1024 * MIB


def _run_nvidia_smi() -> str | None:
    executable = shutil.which("nvidia-smi")
    if executable is None:
        return None
    try:
        completed = subprocess.run(
            [executable, f"--query-gpu={_QUERY}", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_S,
            check=True,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        logger.warning("nvidia-smi unusable: %s", exc)
        return None
    return completed.stdout


def parse_output(raw: str) -> GpuMemory | None:
    """First GPU of the report, or None when the output is not usable.

    Multi-GPU is out of scope: Ollama picks its own device, and reporting a
    card the model will not land on would be worse than reporting nothing.
    """
    for line in (raw or "").splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != 3:
            continue
        try:
            total, used, free = (int(p) for p in parts)
        except ValueError:
            continue
        if total <= 0:
            # A card reporting no memory at all is a broken reading, not a
            # fact. Returning it would divide by zero in the usage bar.
            continue
        return GpuMemory(
            total_bytes=total * MIB,
            used_bytes=used * MIB,
            free_bytes=free * MIB,
        )
    return None


def read_memory() -> GpuMemory | None:
    """Current GPU memory, or None when it cannot be established."""
    raw = _run_nvidia_smi()
    if raw is None:
        return None
    return parse_output(raw)


def fit_verdict(size_bytes: int | None, gpu: GpuMemory | None) -> str | None:
    """How a model of `size_bytes` compares to what the card can offer.

    Returns None when either number is unknown — an absent verdict is correct,
    an invented one is not.

    The model size on disk is an approximation of its memory footprint, which
    is why `fits` keeps a headroom margin and the wording stays cautious.
    """
    if size_bytes is None or gpu is None or gpu.total_bytes <= 0:
        return None
    if size_bytes + HEADROOM_BYTES > gpu.total_bytes:
        return "too_large"
    if size_bytes + HEADROOM_BYTES > gpu.free_bytes:
        return "tight"
    return "fits"
