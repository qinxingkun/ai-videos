"""Read GPU metrics via nvidia-smi."""

from __future__ import annotations

import asyncio
import csv
import io
import shutil
from typing import Any


async def query_gpus() -> list[dict[str, Any]]:
    if not shutil.which("nvidia-smi"):
        return []

    proc = await asyncio.create_subprocess_exec(
        "nvidia-smi",
        "--query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw,power.limit",
        "--format=csv,noheader,nounits",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        return [
            {
                "error": (stderr or stdout).decode("utf-8", errors="replace").strip()
                or "nvidia-smi failed"
            }
        ]

    text = stdout.decode("utf-8", errors="replace").strip()
    if not text:
        return []

    gpus: list[dict[str, Any]] = []
    reader = csv.reader(io.StringIO(text))
    for row in reader:
        if len(row) < 8:
            continue
        try:
            mem_used = float(row[3].strip())
            mem_total = float(row[4].strip())
            gpus.append(
                {
                    "index": int(row[0].strip()),
                    "name": row[1].strip(),
                    "utilization": float(row[2].strip()),
                    "memory_used_mb": mem_used,
                    "memory_total_mb": mem_total,
                    "memory_pct": round(100.0 * mem_used / mem_total, 1) if mem_total else 0.0,
                    "temperature_c": float(row[5].strip()),
                    "power_draw_w": _maybe_float(row[6]),
                    "power_limit_w": _maybe_float(row[7]),
                }
            )
        except ValueError:
            continue
    return gpus


def _maybe_float(value: str) -> float | None:
    value = value.strip()
    if not value or value.upper() == "N/A" or value == "[N/A]":
        return None
    try:
        return float(value)
    except ValueError:
        return None
