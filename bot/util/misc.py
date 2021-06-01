from typing import Any, Callable, Sequence, Tuple


def find_prefixed_funcs(obj: Any,
                        prefix: str) -> Sequence[Tuple[str, Callable]]:
    """Finds functions with symbol names matching the prefix on the given object."""

    results = []

    for sym in dir(obj):
        if sym.startswith(prefix):
            name = sym[len(prefix):]
            func = getattr(obj, sym)
            if not callable(func):
                continue

            results.append((name, func))

    return results


def human_readable_bytes(value: int,
                         digits: int = 2,
                         delim: str = "",
                         postfix: str = "") -> str:
    chosen_unit = "B"
    for unit in ("KiB", "MiB", "GiB", "TiB"):
        if value > 1000:
            value /= 1024
            chosen_unit = unit
        else:
            break
    return f"{value:.{digits}f}" + delim + chosen_unit + postfix
