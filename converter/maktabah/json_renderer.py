"""
maktabah/json_renderer.py — AST → JSON

Renders Document AST to JSON format with compact per-line formatting.
"""
from __future__ import annotations
import json
from typing import Any, Dict, List

from .ast_nodes import (
    Document, FrontmatterBlock,
    Heading, Paragraph, PoemTable, PoemRow,
    DataTable, DataTableRow, UnknownTable,
    Footnote, FootnoteRef, Figure,
    TextSpan, QCFSpan, UnicodeQuranSpan, PageBreak,
)


class JSONRenderer:
    """Render Document AST → JSON"""
    
    def render(self, doc: Document) -> str:
        """
        Render document to JSON string.
        
        Uses compact per-line formatting:
        - Top-level keys: readable
        - Body nodes: one per line
        - Small arrays: inline
        """
        data = self._build_json_dict(doc)
        return self._format_compact_json(data)
    
    def _build_json_dict(self, doc: Document) -> Dict[str, Any]:
        """Build JSON dictionary from Document AST"""
        return {
            "id": doc.frontmatter.metadata.get("id") or "",
            "metadata": doc.frontmatter.metadata,
            "frontmatter": doc.frontmatter.lines,
            "body": [self._serialize_node(node) for node in doc.body],
            "footnotes": {str(k): self._footnote_text(v) for k, v in doc.footnotes.items()}
        }
    
    def _footnote_text(self, footnote: Footnote) -> str:
        """Extract text from footnote inlines"""
        return ''.join(
            inline.text if isinstance(inline, TextSpan) else str(inline)
            for inline in footnote.inlines
        )
    
    def _serialize_node(self, node) -> Dict[str, Any]:
        """Serialize AST node to JSON dict"""
        
        if isinstance(node, PageBreak):
            return {
                "type": "page_break",
                "page_num": node.page_num
            }
        
        if isinstance(node, Heading):
            return {
                "type": "heading",
                "level": node.level,
                "text": node.text
            }
        
        if isinstance(node, Paragraph):
            # Gunakan sentences yang sudah dihitung canonical_parser jika tersedia.
            # Fallback ke _segment_into_sentences hanya jika datang langsung dari
            # docx parser (sentences=None), di mana canonical_parser tidak terlibat.
            if node.sentences is not None:
                sentences = [
                    [self._serialize_inline(span) for span in sent]
                    for sent in node.sentences
                ]
            else:
                sentences = self._segment_into_sentences(node.inlines)
            
            return {
                "type": "paragraph",
                "sentences": sentences
            }
        
        if isinstance(node, PoemTable):
            return {
                "type": "poem",
                "lines": [{"cols": row.cols} for row in node.rows]
            }
        
        if isinstance(node, DataTable):
            return {
                "type": "table",
                "rows": [{"cells": row.cells} for row in node.rows]
            }
        
        if isinstance(node, UnknownTable):
            return {
                "type": "table",
                "style": "unknown",
                "rows": [{"cells": row.cells} for row in node.rows]
            }
        
        if isinstance(node, Figure):
            return {
                "type": "figure",
                "id": node.figure_id,
                "src": node.src,
                "alt": node.alt
            }
        
        # Fallback
        return {"type": "unknown"}
    
    def _serialize_inline(self, inline) -> Dict[str, Any]:
        """Serialize inline element to JSON dict"""
        
        if isinstance(inline, TextSpan):
            return {"type": "text", "text": inline.text}
        
        if isinstance(inline, QCFSpan):
            # type "quran": referensi terstruktur dengan koordinat (surah:ayah:word).
            # Bisa di-lookup ke mushaf, di-link, atau di-index.
            return {
                "type": "quran",
                "ref": inline.decoded,
                "text": inline.preview or ""
            }
        
        if isinstance(inline, UnicodeQuranSpan):
            # type "unicode_quran": teks Unicode mentah tanpa koordinat.
            # Muncul ketika naskah memakai font KFGQPC (bukan QCF glyph font),
            # sehingga tidak bisa di-decode ke referensi surah:ayah:word.
            # Consumer harus perlakukan ini sebagai teks biasa, bukan referensi Quran.
            return {
                "type": "unicode_quran",
                "text": inline.text
            }
        
        if isinstance(inline, FootnoteRef):
            return {
                "type": "footnote_ref",
                "number": inline.number
            }
        
        if isinstance(inline, PageBreak):
            return {
                "type": "page_break",
                "page_num": inline.page_num
            }

        # Fallback
        return {"type": "text", "text": str(inline)}
    
    # ══════════════════════════════════════════════════════════════════════
    # SENTENCE SEGMENTATION (fallback — hanya untuk docx parser path)
    # ══════════════════════════════════════════════════════════════════════
    
    def _segment_into_sentences(self, inlines: List) -> List[List[Dict]]:
        """
        Fallback segmentation untuk paragraf yang datang dari docx parser
        (node.sentences is None). Untuk alur canonical → JSON, segmentasi
        sudah dilakukan oleh canonical_parser._parse_sentences.

        Aturan:
        - Titik (.) MELEKAT ke teks kalimat sebelumnya, tidak jadi token tersendiri.
          Contoh: "هذا نص." → [{"type":"text","text":"هذا نص."}]
        - Quran marker (QCFSpan, UnicodeQuranSpan) = sentence boundary, standalone.
        - PageBreak dipertahankan inline di dalam sentence.

        Returns: List of sentences, each sentence is list of inline dicts.
        """
        sentences: List[List[Dict]] = []
        current: List = []  # list of AST inline nodes (belum di-serialize)

        def flush_current():
            """Serialize dan simpan current sentence jika tidak kosong."""
            if current:
                sentences.append([self._serialize_inline(s) for s in current])
                current.clear()

        def attach_period_and_flush():
            """Tempel titik ke TextSpan terakhir (atau buat baru), lalu flush."""
            if current and isinstance(current[-1], TextSpan):
                current[-1] = TextSpan(text=current[-1].text + '.')
            else:
                # Akhiran bukan TextSpan (misal PageBreak/FootnoteRef) — buat span titik
                current.append(TextSpan(text='.'))
            flush_current()

        for inline in inlines:
            # Quran marker = sentence boundary
            if isinstance(inline, (QCFSpan, UnicodeQuranSpan)):
                flush_current()
                sentences.append([self._serialize_inline(inline)])
                continue

            # TextSpan yang mungkin mengandung titik
            if isinstance(inline, TextSpan) and '.' in inline.text:
                # Pecah pada titik; titik dilampirkan ke bagian kiri
                parts = inline.text.split('.')
                for idx, part in enumerate(parts):
                    is_last_part = (idx == len(parts) - 1)

                    if is_last_part:
                        # Sisa setelah titik terakhir — lanjut ke sentence berikutnya
                        if part:
                            current.append(TextSpan(text=part))
                    else:
                        # Ada titik di sini: tempel ke part, flush
                        if part:
                            current.append(TextSpan(text=part))
                        attach_period_and_flush()
                continue

            # Semua inline lain (FootnoteRef, PageBreak, dll.) — tambah ke current
            current.append(inline)

        # Sisa kalimat tanpa titik penutup
        flush_current()

        # Buang sentence yang semua teks-nya kosong
        return [
            s for s in sentences
            if any(
                e.get('text', '').strip() or e.get('type') not in ('text',)
                for e in s
            )
        ]
    
    # ══════════════════════════════════════════════════════════════════════
    # COMPACT FORMATTING
    # ══════════════════════════════════════════════════════════════════════
    
    def _format_compact_json(self, data: Dict) -> str:
        """
        Format JSON with compact per-line style.
        
        Example output:
        {
          "id": "kitab_001",
          "metadata": {"title": "...", "author": "..."},
          "body": [
            {"type": "heading", "level": 1, "text": "..."},
            {"type": "paragraph", "sentences": [[...], [...]]},
            ...
          ],
          "footnotes": {"1": "text..."}
        }
        """
        lines = ["{"]
        
        # ID
        lines.append(f'  "id": {json.dumps(data["id"], ensure_ascii=False)},')
        
        # Metadata (inline)
        metadata_json = json.dumps(data["metadata"], ensure_ascii=False)
        lines.append(f'  "metadata": {metadata_json},')
        
        # Frontmatter (inline)
        frontmatter_json = json.dumps(data["frontmatter"], ensure_ascii=False)
        lines.append(f'  "frontmatter": {frontmatter_json},')
        
        # Body (one node per line)
        lines.append('  "body": [')
        for i, node in enumerate(data["body"]):
            comma = "," if i < len(data["body"]) - 1 else ""
            node_json = json.dumps(node, ensure_ascii=False)
            lines.append(f'    {node_json}{comma}')
        lines.append('  ],')
        
        # Footnotes (inline)
        footnotes_json = json.dumps(data["footnotes"], ensure_ascii=False)
        lines.append(f'  "footnotes": {footnotes_json}')
        
        lines.append("}")
        
        return "\n".join(lines)
