"""
maktabah/qcf_decoder.py
========================
Decode glyph QCF → koordinat Qur'an.
Diadaptasi dari 3_mushaf_canonical_generator.py (proven).
"""
from __future__ import annotations
import re, json
from pathlib import Path
from typing import Optional

BEGIN_AYAH = "F8E0"
END_AYAH   = "F8E1"

_QCF_RE    = re.compile(r"QCF\d+_Hafs_(\d{2})", re.IGNORECASE)
UNICODE_QURAN_FONT = "KFGQPC_HAFS_Uthmanic_Script_H"


class QCFDecoder:
    def __init__(self, decoder_path):
        p = Path(decoder_path)
        if not p.exists():
            raise FileNotFoundError(f"Decoder tidak ditemukan: {p}")
        with open(p, encoding="utf-8") as f:
            self._data: dict = json.load(f)

    # ── font helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def extract_font_code(font_name: Optional[str]) -> Optional[str]:
        if not font_name: return None
        m = _QCF_RE.search(font_name)
        return m.group(1) if m else None

    @staticmethod
    def is_qcf_font(font_name: Optional[str]) -> bool:
        return bool(_QCF_RE.search(font_name or ""))

    @staticmethod
    def is_unicode_quran_font(font_name: Optional[str]) -> bool:
        return (font_name or "").strip() == UNICODE_QURAN_FONT

    @staticmethod
    def char_hex(c: str) -> str:
        return format(ord(c), "04X")

    # ── decode ───────────────────────────────────────────────────────────────

    def decode_glyph(self, font_code: str, glyph_char: str) -> Optional[tuple]:
        """Returns (surah, ayah, word, part, preview) or None."""
        key = f"{font_code}:{self.char_hex(glyph_char)}"
        entry = self._data.get(key)
        return tuple(entry) if entry else None

    # ── coordinate formatting ────────────────────────────────────────────────

    @staticmethod
    def format_coord(s, a, w, p) -> str:
        return f"{s}:{a}:{w}:{p}" if p else f"{s}:{a}:{w}"

    @staticmethod
    def format_span(start: tuple, end: tuple) -> str:
        s1 = QCFDecoder.format_coord(*start)
        s2 = QCFDecoder.format_coord(*end)
        return s1 if s1 == s2 else f"{s1}-{s2}"

    def process_ayah_unit(self, unit: list) -> Optional[tuple[str, str]]:
        """
        unit = [{"loc": (s,a,w,p), "preview": "..."}, ...]
        Returns (decoded_span, preview) or None.
        """
        if not unit:
            return None
        span = self.format_span(unit[0]["loc"], unit[-1]["loc"])
        preview = " ".join(t["preview"].strip() for t in unit if t["preview"].strip())
        preview = " ".join(preview.split())
        return span, preview
