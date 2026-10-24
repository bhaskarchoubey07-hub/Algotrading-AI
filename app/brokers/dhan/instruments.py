"""DhanHQ Instrument Master and Security Identifier Resolver."""

import csv
from dataclasses import dataclass
import io
import logging
import threading
from typing import Any
import requests
from app.brokers.dhan.exceptions import DhanSecurityNotFoundError

logger = logging.getLogger("algotrade.dhan.instruments")

# Pre-seeded master mapping for core NSE Cash & Index instruments
DEFAULT_SCRIP_MAPPING = {
    # NSE Equities
    ("RELIANCE", "NSE_EQ"): "2885",
    ("INFY", "NSE_EQ"): "1594",
    ("TCS", "NSE_EQ"): "11536",
    ("HDFCBANK", "NSE_EQ"): "1333",
    ("ICICIBANK", "NSE_EQ"): "4963",
    ("SBIN", "NSE_EQ"): "3045",
    ("BHARTIARTL", "NSE_EQ"): "10604",
    ("ITC", "NSE_EQ"): "1660",
    ("KOTAKBANK", "NSE_EQ"): "1922",
    ("LT", "NSE_EQ"): "11483",
    ("TATAMOTORS", "NSE_EQ"): "3456",
    # Indices
    ("NIFTY", "IDX_I"): "13",
    ("BANKNIFTY", "IDX_I"): "25",
    ("FINNIFTY", "IDX_I"): "27",
    ("MIDCPNIFTY", "IDX_I"): "51",
}


@dataclass
class ScripMetadata:
    symbol: str
    security_id: str
    exchange_segment: str
    instrument_type: str  # "EQUITY", "INDEX", "FUTSTK", "OPTSTK", "FUTIDX", "OPTIDX"
    lot_size: int = 1
    tick_size: float = 0.05
    expiry_date: str | None = None
    strike_price: float = 0.0
    option_type: str | None = None  # "CE" or "PE"


class DhanInstrumentManager:
    """Manages instrument master lookups, symbol resolution, and local caching."""

    COMPACT_CSV_URL = "https://images.dhan.co/api-data/api-scrip-master.csv"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._symbol_to_secid: dict[tuple[str, str], str] = dict(DEFAULT_SCRIP_MAPPING)
        self._secid_to_symbol: dict[tuple[str, str], str] = {
            (sec_id, seg): sym for (sym, seg), sec_id in DEFAULT_SCRIP_MAPPING.items()
        }
        self._metadata_cache: dict[str, ScripMetadata] = {}
        self._last_loaded_count = len(self._symbol_to_secid)

    def resolve_security_id(self, symbol: str, exchange_segment: str = "NSE_EQ") -> str:
        """Resolves a trading symbol to its Dhan security ID.

        Raises DhanSecurityNotFoundError if not found.
        """
        key = (symbol.upper().strip(), exchange_segment.upper().strip())
        with self._lock:
            sec_id = self._symbol_to_secid.get(key)
        if sec_id:
            return sec_id
        # Fallback search if segment differs
        for (sym, _), s_id in self._symbol_to_secid.items():
            if sym == key[0]:
                return s_id

        raise DhanSecurityNotFoundError(
            f"Could not resolve security ID for {symbol} on {exchange_segment}. "
            "Ensure the instrument is in Dhan's scrip master.",
            error_code="SCRIP_NOT_FOUND",
        )

    def resolve_symbol(self, security_id: str, exchange_segment: str = "NSE_EQ") -> str:
        """Resolves a Dhan security ID to trading symbol."""
        key = (str(security_id).strip(), exchange_segment.upper().strip())
        with self._lock:
            sym = self._secid_to_symbol.get(key)
        if sym:
            return sym
        for (sec, _), s_sym in self._secid_to_symbol.items():
            if sec == key[0]:
                return s_sym
        return f"SEC_{security_id}"

    def register_instrument(
        self,
        symbol: str,
        security_id: str,
        exchange_segment: str = "NSE_EQ",
        instrument_type: str = "EQUITY",
        lot_size: int = 1,
        tick_size: float = 0.05,
    ) -> None:
        """Manually registers an instrument into the in-memory master."""
        sym_upper = symbol.upper().strip()
        seg_upper = exchange_segment.upper().strip()
        sec_str = str(security_id).strip()

        with self._lock:
            self._symbol_to_secid[(sym_upper, seg_upper)] = sec_str
            self._secid_to_symbol[(sec_str, seg_upper)] = sym_upper
            self._metadata_cache[sec_str] = ScripMetadata(
                symbol=sym_upper,
                security_id=sec_str,
                exchange_segment=seg_upper,
                instrument_type=instrument_type,
                lot_size=lot_size,
                tick_size=tick_size,
            )

    def load_from_csv_content(self, csv_text: str) -> int:
        """Parses CSV text into in-memory dictionary."""
        reader = csv.DictReader(io.StringIO(csv_text))
        count = 0
        with self._lock:
            for row in reader:
                # Dhan scrip master CSV headers usually include SEM_TRADING_SYMBOL, SEM_SMST_SECURITY_ID, etc.
                sym = (
                    row.get("SEM_TRADING_SYMBOL")
                    or row.get("trading_symbol")
                    or row.get("symbol")
                    or ""
                ).strip()
                sec_id = (
                    row.get("SEM_SMST_SECURITY_ID")
                    or row.get("security_id")
                    or row.get("securityId")
                    or ""
                ).strip()
                seg = (
                    row.get("SEM_EXM_EXCH_ID")
                    or row.get("exchange_segment")
                    or row.get("exchange")
                    or "NSE_EQ"
                ).strip()

                if sym and sec_id:
                    self._symbol_to_secid[(sym, seg)] = sec_id
                    self._secid_to_symbol[(sec_id, seg)] = sym
                    count += 1
            self._last_loaded_count = len(self._symbol_to_secid)
        return count

    def refresh_scrip_master(self, timeout_sec: float = 10.0) -> dict[str, Any]:
        """Downloads latest scrip master from Dhan's official CDN."""
        try:
            resp = requests.get(self.COMPACT_CSV_URL, timeout=timeout_sec)
            if resp.status_code == 200:
                loaded = self.load_from_csv_content(resp.text)
                return {"status": "SUCCESS", "loaded_instruments": loaded}
            return {"status": "FAILED", "http_status": resp.status_code}
        except Exception as exc:
            logger.warning(f"Failed to refresh Dhan scrip master online: {exc}. Retaining cached master.")
            return {"status": "FALLBACK", "cached_count": len(self._symbol_to_secid), "error": str(exc)}

    def get_summary(self) -> dict[str, Any]:
        return {
            "total_instruments": len(self._symbol_to_secid),
            "sample_equities": list({sym for (sym, seg) in self._symbol_to_secid.keys() if seg == "NSE_EQ"})[:10],
            "sample_indices": list({sym for (sym, seg) in self._symbol_to_secid.keys() if seg == "IDX_I"}),
        }


instrument_manager = DhanInstrumentManager()
