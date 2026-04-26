"""Internal utilities: rate limiting, retries, request shaping.

Nothing in this module is part of the public API; signatures may change
between minor versions.
"""

from __future__ import annotations

import asyncio
import base64
import time
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Iterable, Mapping, Sequence


class AsyncRateLimiter:
    """Token-bucket-style limiter capping requests over a sliding window.

    The Podpislon API allows 4 requests per second per API key. A naive
    ``asyncio.sleep`` between calls would either over- or under-shoot when
    requests come in bursts. Tracking timestamps in a deque gives us an exact
    sliding window: we sleep only as long as needed for the oldest request
    to fall outside it.
    """

    def __init__(self, rate: int, per: float = 1.0) -> None:
        if rate <= 0:
            raise ValueError("rate must be a positive integer")
        if per <= 0:
            raise ValueError("per must be a positive float (seconds)")
        self._rate = rate
        self._per = per
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        async with self._lock:
            now = time.monotonic()
            cutoff = now - self._per
            while self._timestamps and self._timestamps[0] <= cutoff:
                self._timestamps.popleft()

            if len(self._timestamps) >= self._rate:
                wait_for = self._per - (now - self._timestamps[0])
                if wait_for > 0:
                    await asyncio.sleep(wait_for)
                    now = time.monotonic()
                    cutoff = now - self._per
                    while self._timestamps and self._timestamps[0] <= cutoff:
                        self._timestamps.popleft()

            self._timestamps.append(time.monotonic())
        yield


def encode_file_to_base64(source: bytes | str | Path) -> str:
    """Encode a PDF file or raw bytes into the base64 form expected by the API."""

    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")
        data = path.read_bytes()
    elif isinstance(source, (bytes, bytearray)):
        data = bytes(source)
    else:
        raise TypeError(
            f"Unsupported file source: {type(source).__name__}; "
            "expected bytes, str path or pathlib.Path"
        )
    return base64.b64encode(data).decode("ascii")


def decode_base64_to_bytes(value: str) -> bytes:
    """Decode the base64 string that ``GET /get-file`` returns."""

    return base64.b64decode(value, validate=False)


def to_form_data(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Flatten a payload into ``application/x-www-form-urlencoded`` form.

    Pydantic / dict values that are themselves arrays or mappings are encoded
    using PHP-style bracket keys (``contacts[0][phone]``), which is the format
    Podpislon's PHP backend understands. ``None`` values are dropped so that
    optional fields don't accidentally clobber server-side defaults.
    """

    out: dict[str, Any] = {}
    for key, value in payload.items():
        if value is None:
            continue
        _flatten(key, value, out)
    return out


def _flatten(key: str, value: Any, out: dict[str, Any]) -> None:
    if isinstance(value, Mapping):
        for sub_key, sub_value in value.items():
            _flatten(f"{key}[{sub_key}]", sub_value, out)
    elif isinstance(value, (list, tuple, set)) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            _flatten(f"{key}[{index}]", item, out)
    elif isinstance(value, bool):
        # The API expects "Y" for boolean-like flags rather than "true"/"false".
        out[key] = "Y" if value else ""
    else:
        out[key] = value


def chunked(iterable: Sequence[Any], size: int) -> Iterable[Sequence[Any]]:
    """Yield successive ``size``-sized chunks of ``iterable``."""

    if size <= 0:
        raise ValueError("size must be a positive integer")
    for i in range(0, len(iterable), size):
        yield iterable[i : i + size]


def parse_int_header(headers: Mapping[str, str], name: str) -> int | None:
    """Read an integer header (used for pagination metadata).

    HTTP header names are case-insensitive but Python ``dict`` lookups are not,
    so we walk the keys ourselves.
    """

    raw = headers.get(name)
    if raw is None:
        target = name.lower()
        for key, value in headers.items():
            if key.lower() == target:
                raw = value
                break
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None
