"""Generic pure dataclass merge — shared by BatteryReading (entities.py) and
StringReading (string_reading.py). No I/O, no framework imports."""

import dataclasses


def merge_dataclass(instance, patch: dict):
    """Recursively build a new dataclass instance with `patch` applied.

    Unknown keys are ignored (mirrors the BMS payload having fields we don't
    track). Never mutates `instance`.
    """
    if not patch:
        return instance
    updates = {}
    for key, value in patch.items():
        if not hasattr(instance, key):
            continue
        current = getattr(instance, key)
        if dataclasses.is_dataclass(current) and isinstance(value, dict):
            updates[key] = merge_dataclass(current, value)
        else:
            updates[key] = value
    return dataclasses.replace(instance, **updates) if updates else instance
