"""FRED observations client. Never include credential-bearing URLs in errors."""

import json
import socket
import ssl
import time
from dataclasses import dataclass
from datetime import date
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


class IngestionError(ValueError):
    """Safe, actionable ingestion failure."""


def validate_range(start: str, end: str | None) -> None:
    try:
        if date.fromisoformat(start).isoformat() != start:
            raise ValueError
        if end is not None:
            if date.fromisoformat(end).isoformat() != end or end < start:
                raise ValueError
    except (TypeError, ValueError):
        raise IngestionError("Use YYYY-MM-DD dates with start on or before end.") from None


@dataclass
class FredClient:
    api_key: str
    timeout: float = 30
    attempts: int = 3
    opener: object = urlopen
    sleeper: object = time.sleep

    def __post_init__(self):
        self.api_key = self.api_key.strip()
        if not self.api_key:
            raise IngestionError("Set FRED_API_KEY before ingestion.")
        if self.timeout <= 0 or self.attempts < 1:
            raise IngestionError("Timeout and retry attempts must be positive.")

    def _request(self, params: dict) -> dict:
        url = "https://api.stlouisfed.org/fred/series/observations?" + urlencode(
            {**params, "api_key": self.api_key, "file_type": "json"}
        )
        failure = "network connection failed; check connectivity and proxy settings"
        for attempt in range(self.attempts):
            try:
                with self.opener(url, timeout=self.timeout) as response:
                    payload = json.load(response)
                if not isinstance(payload, dict) or "error_code" in payload:
                    raise IngestionError("FRED returned an invalid or error response.")
                return payload
            except HTTPError as error:
                status = error.code
                error.close()
                if status != 429 and not 500 <= status <= 599:
                    raise IngestionError(
                        f"FRED HTTP {status}; check credentials and request parameters."
                    ) from None
                failure = f"FRED HTTP {status}; try again later"
            except (URLError, OSError) as error:
                reason = error.reason if isinstance(error, URLError) else error
                if isinstance(reason, ssl.SSLCertVerificationError):
                    raise IngestionError(
                        "TLS certificate verification failed. Repair Python's CA certificate "
                        "bundle; on python.org macOS installs, run Install Certificates.command "
                        "from your Python folder in /Applications."
                    ) from None
                if isinstance(reason, socket.gaierror):
                    failure = "DNS lookup failed; check internet connection and DNS settings"
                elif isinstance(reason, TimeoutError):
                    failure = "connection timed out; check connectivity or try again later"
                else:
                    failure = "network connection failed; check connectivity and proxy settings"
            except (ValueError, UnicodeError):
                raise IngestionError("FRED returned invalid JSON.") from None
            if attempt + 1 < self.attempts:
                self.sleeper(2**attempt)
        raise IngestionError(f"FRED request failed after bounded retries: {failure}.")

    def fetch_unrate(self, start: str, end: str | None = None) -> list[dict]:
        validate_range(start, end)
        params = {
            "series_id": "UNRATE", "observation_start": start,
            "sort_order": "asc", "units": "lin", "limit": 100000,
        }
        if end:
            params["observation_end"] = end
        pages, offset, expected_count = [], 0, None
        while True:
            payload = self._request({**params, "offset": offset})
            count, rows = payload.get("count"), payload.get("observations")
            if type(count) is not int or count < 0 or not isinstance(rows, list):
                raise IngestionError("FRED returned malformed pagination data.")
            if payload.get("offset") != offset:
                raise IngestionError("FRED returned an unexpected page offset.")
            if expected_count is not None and count != expected_count:
                raise IngestionError("FRED data changed during pagination; retry ingestion.")
            expected_count = count
            pages.append(payload)
            offset += len(rows)
            if offset > count or (offset < count and not rows):
                raise IngestionError("FRED returned incomplete or inconsistent pages.")
            if offset == count:
                return pages
