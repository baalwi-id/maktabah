"""
maktabah/renderer.py — AST → canonical text
"""
from __future__ import annotations
import re
from .ast_nodes import (
    Document, FrontmatterBlock,
    Heading, Paragraph, PoemTable, DataTable, UnknownTable,
    Footnote, FootnoteRef, Figure, PageBreak,
    UnicodeQuranSpan, QCFSpan, TextSpan,
)


class CanonicalRenderer:

    def render(self, doc: Document) -> str:
        parts = []
        parts.append(self._render_metadata(doc.frontmatter.metadata))
        fm = self._render_frontmatter(doc.frontmatter)
        if fm:
            parts.append(fm)

        body_parts = []

        self._page_num = 2
        for node in doc.body:
            # block-level PageBreak — hanya emit kalau ada page_num dari VBA comment
            if isinstance(node, PageBreak):
                if node.page_num > 0:
                    body_parts.append(f"{{P {node.page_num}}}")
                    self._page_num = node.page_num + 1
                else:
                    body_parts.append(f"{{P {self._page_num}}}")
                    self._page_num += 1
                continue

            if isinstance(node, Footnote):
                continue   # skip standalone footnote nodes

            r = self._render_node(node)
            if r:
                body_parts.append(r)
                # setelah paragraf: emit definisi footnote yang direferens di dalamnya
                if isinstance(node, (Paragraph, Heading)):
                    fn_defs = self._collect_footnote_refs(node, doc.footnotes)
                    for fn in fn_defs:
                        body_parts.append(f"[^{fn.number}]: {fn.text.strip()}")

        body_parts = self._dedup_page_breaks(body_parts)

        if body_parts:
            parts.append("\n\n".join(body_parts))

        return "\n\n".join(p for p in parts if p).rstrip() + "\n"

    # ── metadata ─────────────────────────────────────────────────────────────

    def _render_metadata(self, meta: dict) -> str:
        m = meta or {}
        def v(k): return str(m.get(k) or "")
        return "\n".join([
            "---",
            f"id: ",
            f"title: {v('title')}",
            f"language: ar",
            f"author: {v('author')}",
            f"author_full: {v('author_full')}",
            f"author_death_hijri: {v('author_death_hijri')}",
            f"edition: {v('edition')}",
            f"edition_year: {v('edition_year')}",
            f"publisher: {v('publisher')}",
            f"rights: {v('rights')}",
            "---",
        ])

    def _render_frontmatter(self, fm: FrontmatterBlock) -> str:
        if not fm.lines: return ""
        return ":::frontmatter\n" + "\n".join(fm.lines) + "\n:::"

    # ── nodes ─────────────────────────────────────────────────────────────────

    def _render_node(self, node) -> str | None:
        if isinstance(node, Heading):
            return "#" * node.level + " " + node.text
        if isinstance(node, Paragraph):
            return self._render_paragraph(node)
        if isinstance(node, PoemTable):
            return self._render_poem(node)
        if isinstance(node, DataTable):
            return self._render_table_rows(node.rows)
        if isinstance(node, UnknownTable):
            return self._render_unknown_table(node)
        if isinstance(node, Figure):
            return self._render_figure(node)
        return None

    def _render_paragraph(self, p: Paragraph) -> str | None:
        has_figure = any(isinstance(s, Figure) for s in p.inlines)
        if p.is_empty and not has_figure:
            return None
        parts = []
        pending_figure = None
        for span in p.inlines:
            if isinstance(span, TextSpan):
                parts.append(span.text)
            elif isinstance(span, UnicodeQuranSpan):
                parts.append(f"{{Qt {span.text}}}")
            elif isinstance(span, QCFSpan):
                parts.append(f"{{Q {span.decoded}}}")
            elif isinstance(span, FootnoteRef):
                parts.append(f"[^{span.number}]")
            elif isinstance(span, PageBreak):
                if span.page_num > 0:
                    parts.append(f"{{P {span.page_num}}}")
                    self._page_num = span.page_num + 1
                else:
                    parts.append(f"{{P {self._page_num}}}")
                    self._page_num += 1
            elif isinstance(span, Figure):
                pending_figure = span
        result = "".join(parts)
        if pending_figure:
            fig_block = self._render_figure(pending_figure)
            if result.strip():
                result = result + "\n\n" + fig_block
            else:
                result = fig_block
        return result if result.strip() else None

    def _render_poem(self, poem: PoemTable) -> str:
        lines = []
        for row in poem.rows:
            lines.append("> " + " :: ".join(col for col in row.cols if col.strip()))
        return "\n".join(lines)

    def _render_table_rows(self, rows) -> str:
        lines = ["::table"]
        for row in rows:
            lines.append("| " + " | ".join(row.cells) + " |")
        lines.append("::")
        return "\n".join(lines)

    def _render_unknown_table(self, tbl: UnknownTable) -> str:
        lines = ["::table style=unknown"]
        for row in tbl.rows:
            lines.append("| " + " | ".join(row.cells) + " |")
        lines.append("::")
        return "\n".join(lines)

    def _dedup_page_breaks(self, parts: list) -> list:
        """
        Hapus consecutive {P N} — kalau ada beberapa {P N} berturutan
        tanpa konten di antaranya, simpan hanya yang terakhir.
        """
        _PB_RE = re.compile(r'\{P \d+\}')

        # Pass 1: block-level dedup
        result = []
        i = 0
        while i < len(parts):
            if _PB_RE.fullmatch(parts[i].strip()):
                j = i
                while j < len(parts) and _PB_RE.fullmatch(parts[j].strip()):
                    j += 1
                result.append(parts[j - 1])
                i = j
            else:
                result.append(parts[i])
                i += 1

        # Pass 2: inline dedup dalam string
        deduped = []
        for part in result:
            cleaned = re.sub(r'(\{P \d+\}\s*)+\{P (\d+)\}', r'{P \2}', part)
            deduped.append(cleaned)

        return deduped

    def _collect_footnote_refs(self, node, footnotes: dict) -> list:
        """Kumpulkan definisi footnote yang direferens dalam node ini."""
        inlines = getattr(node, "inlines", [])
        result = []
        seen = set()
        for span in inlines:
            if isinstance(span, FootnoteRef) and span.number not in seen:
                seen.add(span.number)
                if span.number in footnotes:
                    result.append(footnotes[span.number])
        return result

    def _render_figure(self, fig: Figure) -> str:
        lines = [f"::figure id={fig.figure_id} src={fig.src}"]
        if fig.alt:
            lines.append(f"alt: {fig.alt}")
        lines.append("::")
        return "\n".join(lines)
