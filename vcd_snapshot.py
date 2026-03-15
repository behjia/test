from __future__ import annotations

import re
from pathlib import Path
from typing import Dict

__all__ = ["snapshot_signal_states"]

_UNIT_TO_NS: Dict[str, float] = {
    "s": 1e9,
    "ms": 1e6,
    "us": 1e3,
    "ns": 1.0,
    "ps": 1e-3,
    "fs": 1e-6,
}


def snapshot_signal_states(
    vcd_path: str | Path, target_timestamp_ns: float
) -> Dict[str, str]:
    """Return a dict of all signal names and their binary states at ``target_timestamp_ns``.

    The implementation is intentionally lightweight so it can run without
    dependencies, but it follows the same VCD conventions that a `pyvcd`
    parser would consume. The returned dictionary is ready to be embedded as
    JSON for the Critic Agent’s prompt.
    """

    path = Path(vcd_path)
    if not path.exists():
        raise FileNotFoundError(f"{path} does not exist")

    def _parse_timescale(line: str) -> float:
        match = re.search(r"\$timescale\s+([\d\.]+)\s*(s|ms|us|ns|ps|fs)\s*\$end", line)
        if not match:
            return 1.0
        magnitude = float(match.group(1))
        unit = match.group(2).lower()
        return magnitude * _UNIT_TO_NS.get(unit, 1.0)

    def _normalize_signal_name(scope: list[str], reference: str) -> str:
        scope = [s for s in scope if s]
        name_parts = scope + [reference]
        return ".".join(name_parts)

    def _snapshot_state(states: Dict[str, str]) -> Dict[str, str]:
        return {identifier_map[ident]: states.get(ident, "U") for ident in identifier_map}

    target_ns = float(target_timestamp_ns)
    timescale_ns = 1.0
    scope_stack: list[str] = []
    identifier_map: Dict[str, str] = {}
    last_values: Dict[str, str] = {}
    definitions_done = False
    in_dumpvars = False
    current_time_units = 0
    snapshot: Dict[str, str] | None = None

    def _time_in_ns(units: int) -> float:
        return units * timescale_ns

    def _maybe_capture(prev_units: int, next_units: int) -> bool:
        nonlocal snapshot
        if snapshot is not None:
            return True
        prev_ns = _time_in_ns(prev_units)
        next_ns = _time_in_ns(next_units)
        if prev_ns <= target_ns < next_ns:
            snapshot = _snapshot_state(last_values)
            return True
        return False

    def _parse_value(line: str) -> tuple[str, str] | None:
        if not line:
            return None
        if line[0] in {"b", "B"}:
            parts = line.split()
            if len(parts) >= 2:
                value = parts[0][1:]
                ident = parts[1]
            else:
                value = line[1:-1]
                ident = line[-1]
            return ident, value
        if line[0].lower() in {"0", "1", "x", "z"}:
            return line[1:], line[0].lower()
        return None

    def _process_var_declaration(buffer: str):
        tokens = buffer.split()
        if len(tokens) < 6:
            return
        ident = tokens[3]
        reference = " ".join(tokens[4:-1])
        full_name = _normalize_signal_name(scope_stack, reference)
        identifier_map[ident] = full_name
        last_values.setdefault(ident, "U")

    with path.open("r", errors="ignore") as handle:
        header_mode: str | None = None
        header_buffer = ""
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue

            if header_mode:
                header_buffer = f"{header_buffer} {line}".strip()
                if "$end" in line:
                    if header_mode == "timescale":
                        timescale_ns = _parse_timescale(header_buffer)
                    elif header_mode == "var":
                        _process_var_declaration(header_buffer)
                    header_mode = None
                    header_buffer = ""
                continue

            if not definitions_done:
                if line.startswith("$timescale"):
                    if "$end" in line:
                        timescale_ns = _parse_timescale(line)
                    else:
                        header_mode = "timescale"
                        header_buffer = line
                    continue
                if line.startswith("$scope"):
                    parts = line.split()
                    if len(parts) >= 3:
                        scope_stack.append(parts[2])
                    continue
                if line.startswith("$upscope"):
                    if scope_stack:
                        scope_stack.pop()
                    continue
                if line.startswith("$var"):
                    if "$end" in line:
                        _process_var_declaration(line)
                    else:
                        header_mode = "var"
                        header_buffer = line
                    continue
                if line.startswith("$enddefinitions"):
                    definitions_done = True
                    continue
                continue

            if line == "$dumpvars":
                in_dumpvars = True
                continue
            if in_dumpvars and line == "$end":
                in_dumpvars = False
                continue

            if line.startswith("#"):
                next_units = int(line[1:])
                if _maybe_capture(current_time_units, next_units):
                    break
                current_time_units = next_units
                continue

            value_entry = _parse_value(line)
            if value_entry:
                ident, value = value_entry
                if ident in last_values:
                    last_values[ident] = value
                continue

    if snapshot is None:
        snapshot = _snapshot_state(last_values)

    return snapshot
