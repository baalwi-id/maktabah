"""
maktabah/report.py - Sistem pelaporan parse: FATAL, ERROR, WARNING, INFO.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional
import json


class Severity(str, Enum):
    FATAL   = "FATAL"
    ERROR   = "ERROR"
    WARNING = "WARNING"
    INFO    = "INFO"


@dataclass
class ReportItem:
    code: str
    severity: Severity
    message: str
    location: Optional[str] = None

    def __str__(self):
        loc = f" [{self.location}]" if self.location else ""
        return f"[{self.severity.value}] {self.code}{loc}: {self.message}"

    def to_dict(self):
        d = {"code": self.code, "severity": self.severity.value, "message": self.message}
        if self.location:
            d["location"] = self.location
        return d


class ParseReport:
    def __init__(self, input_path: str):
        self.input_path = input_path
        self.items: list[ReportItem] = []

    def fatal(self, code, message, location=None):
        self.items.append(ReportItem(code, Severity.FATAL, message, location))

    def error(self, code, message, location=None):
        self.items.append(ReportItem(code, Severity.ERROR, message, location))

    def warning(self, code, message, location=None):
        self.items.append(ReportItem(code, Severity.WARNING, message, location))

    def info(self, code, message, location=None):
        self.items.append(ReportItem(code, Severity.INFO, message, location))

    @property
    def has_fatal(self):
        return any(i.severity == Severity.FATAL for i in self.items)

    @property
    def has_error(self):
        return any(i.severity == Severity.ERROR for i in self.items)

    def to_text(self):
        lines = [
            "Maktabah Parse Report",
            f"Input : {self.input_path}",
            "=" * 60,
        ]
        for sev in Severity:
            group = [i for i in self.items if i.severity == sev]
            if group:
                lines.append(f"\n{sev.value} ({len(group)})")
                lines.append("-" * 40)
                for item in group:
                    lines.append(str(item))
        counts = {s: sum(1 for i in self.items if i.severity == s) for s in Severity}
        lines += [
            "",
            "=" * 60,
            f"Total: {counts[Severity.FATAL]} fatal, {counts[Severity.ERROR]} error, "
            f"{counts[Severity.WARNING]} warning, {counts[Severity.INFO]} info",
        ]
        return "\n".join(lines)

    def to_json(self):
        counts = {s.value: sum(1 for i in self.items if i.severity == s) for s in Severity}
        return json.dumps({
            "input": self.input_path,
            "summary": counts,
            "items": [i.to_dict() for i in self.items],
        }, ensure_ascii=False, indent=2)


class C:
    # Fatal — parsing tidak bisa dilanjutkan
    F001 = "F001"   # File tidak ditemukan
    F002 = "F002"   # Bukan .docx
    F003 = "F003"   # File tidak bisa dibuka/dibaca
    F004 = "F004"   # File terlalu besar (>100 MB)
    # Fatal — canonical parser
    F010 = "F010"   # YAML header tidak ada
    F011 = "F011"   # YAML header tidak ditutup
    F012 = "F012"   # YAML malformed
    F013 = "F013"   # Frontmatter tidak ada
    F014 = "F014"   # Frontmatter tidak ditutup

    # Error
    E001 = "E001"   # Footnote ref tidak ada definisinya
    E002 = "E002"   # {Qt} kosong
    E003 = "E003"   # Figure malformed (id= atau src= hilang)
    E005 = "E005"   # Tidak ada heading dalam dokumen

    # Warning
    W003 = "W003"   # Footnote orphan (definisi ada tapi tidak direferens)
    W005 = "W005"   # Frontmatter kosong
    W006 = "W006"   # Referensi Quran format tidak valid
    W007 = "W007"   # Tabel kosong
    W008 = "W008"   # Kolom tabel tidak seragam (dinormalisasi)
    W009 = "W009"   # Heading loncat level
    W010 = "W010"   # Heading pertama bukan H1
    W012 = "W012"   # Style tabel tidak dikenali

    # Info
    I001 = "I001"   # Mulai parsing (docx atau canonical)
    I002 = "I002"   # Statistik elemen hasil parsing
    I003 = "I003"   # Waktu selesai / jumlah block
    I004 = "I004"   # Info komentar PAGE: ditemukan (mode akurat aktif)
