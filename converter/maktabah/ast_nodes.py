"""
maktabah/ast_nodes.py - AST nodes antara DOCX dan canonical output.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TextSpan:
    text: str

@dataclass
class QCFSpan:
    font_code: str
    decoded: str      # "2:255:1-2:255:7"
    preview: Optional[str] = None

@dataclass
class UnicodeQuranSpan:
    text: str

@dataclass
class FootnoteRef:
    number: int


def _inline_to_str(inlines: list) -> str:
    parts = []
    for s in inlines:
        if isinstance(s, (TextSpan, UnicodeQuranSpan)):
            parts.append(s.text)
        elif isinstance(s, QCFSpan):
            parts.append(f"{{Q {s.decoded}}}")
        elif isinstance(s, FootnoteRef):
            parts.append(f"[^{s.number}]")
    # normalize multiple spaces → single space, but keep content
    result = "".join(parts)
    # collapse runs of spaces/nbsp to single space
    result = re.sub(r'[ \u00a0]{2,}', ' ', result)
    return result


@dataclass
class Heading:
    level: int
    inlines: list = field(default_factory=list)

    @property
    def text(self): return _inline_to_str(self.inlines)

@dataclass
class Paragraph:
    inlines: list = field(default_factory=list)
    sentences: Optional[list] = None   # list[list[inline]] — diisi canonical_parser, None jika dari docx parser

    @property
    def text(self): return _inline_to_str(self.inlines)

    @property
    def is_empty(self): return not self.text.strip()

@dataclass
class PoemRow:
    cols: list[str]

@dataclass
class PoemTable:
    rows: list[PoemRow] = field(default_factory=list)

@dataclass
class DataTableRow:
    cells: list[str]

@dataclass
class DataTable:
    rows: list[DataTableRow] = field(default_factory=list)
    style_id: str = "DataTable"

@dataclass
class UnknownTable:
    style_id: str = ""
    rows: list[DataTableRow] = field(default_factory=list)

@dataclass
class Footnote:
    number: int
    inlines: list = field(default_factory=list)

    @property
    def text(self): return _inline_to_str(self.inlines)

@dataclass
class Figure:
    figure_id: str
    alt: str = ""
    src: str = "PENDING"

@dataclass
class FrontmatterBlock:
    lines: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

@dataclass
class Document:
    frontmatter: FrontmatterBlock = field(default_factory=FrontmatterBlock)
    body: list = field(default_factory=list)
    footnotes: dict = field(default_factory=dict)

@dataclass
class PageBreak:
    """Penanda pergantian halaman — {P N} dihitung saat render.

    source: 'explicit'    = dari w:br type=page
            'lrpb'        = dari lastRenderedPageBreak
            'page_field'  = dari komentar PAGE:N (akurat 100%)
    page_num: int | None  = nomor halaman aktual (hanya untuk source='page_field')
    """
    source: str = 'lrpb'
    page_num: int = 0   # 0 = tidak diketahui (hitung via counter di renderer)
