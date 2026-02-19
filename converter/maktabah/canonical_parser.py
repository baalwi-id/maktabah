"""
maktabah/canonical_parser.py — Canonical.txt → AST

Parses canonical format text files into Document AST.
Follows grammar spec in CANONICAL_GRAMMAR.md
"""
from __future__ import annotations
import re
import yaml
from typing import Optional, List, Tuple
from pathlib import Path

from .ast_nodes import (
    Document, FrontmatterBlock,
    Heading, Paragraph, PoemTable, PoemRow,
    DataTable, DataTableRow,
    Footnote, FootnoteRef, Figure,
    TextSpan, QCFSpan, UnicodeQuranSpan, PageBreak,
)
from .report import ParseReport, C


class CanonicalParser:
    """Parse canonical.txt → Document AST"""
    
    def __init__(self):
        self.current_file = ""
        self.lines = []
        self.line_idx = 0
        self.footnotes = {}
        
    def parse(self, canonical_path: str, report: ParseReport) -> Optional[Document]:
        """Main entry point: parse canonical file"""
        path = Path(canonical_path)
        report.info(C.I001, f"Parsing canonical: {path.name}")
        self.current_file = str(path)

        # Reset semua state per-parse — memastikan instance bisa dipakai ulang
        # (dan aman jika suatu saat dipakai dari beberapa thread secara bergantian,
        # meski saat ini engine hanya single-threaded)
        self.lines = []
        self.line_idx = 0
        self.footnotes = {}

        try:
            with open(path, 'r', encoding='utf-8') as f:
                text = f.read()
        except Exception as e:
            report.fatal(C.F003, f"Cannot read file: {e}")
            return None

        self.lines = text.split('\n')
        
        # Phase 1: Parse YAML header
        metadata = self._parse_yaml_header(report)
        if metadata is None:
            return None  # Fatal error
        
        # Phase 2: Parse frontmatter
        frontmatter = self._parse_frontmatter(report)
        if frontmatter is None:
            return None  # Fatal error
        
        # Phase 3: Parse body
        body = self._parse_body(report)
        
        # Phase 4: Validate footnotes
        self._validate_footnotes(report, body)
        
        doc = Document(
            frontmatter=FrontmatterBlock(metadata=metadata, lines=frontmatter),
            body=body,
            footnotes=self.footnotes
        )
        
        report.info(C.I003, f"Parsed {len(body)} body blocks, {len(self.footnotes)} footnotes")
        return doc
    
    # ══════════════════════════════════════════════════════════════════════
    # YAML HEADER
    # ══════════════════════════════════════════════════════════════════════
    
    def _parse_yaml_header(self, report: ParseReport) -> Optional[dict]:
        """Parse YAML header (between --- delimiters)"""
        if not self._current_line() == '---':
            report.fatal(C.F010, "Missing YAML header (expected '---' at start)")
            return None
        
        self.line_idx += 1
        yaml_lines = []
        
        while self.line_idx < len(self.lines):
            line = self._current_line()
            if line == '---':
                self.line_idx += 1
                break
            yaml_lines.append(line)
            self.line_idx += 1
        else:
            report.fatal(C.F011, "YAML header not closed (missing closing '---')")
            return None
        
        yaml_text = '\n'.join(yaml_lines)
        try:
            metadata = yaml.safe_load(yaml_text) or {}
            return metadata
        except yaml.YAMLError as e:
            report.fatal(C.F012, f"Malformed YAML: {e}")
            return None
    
    # ══════════════════════════════════════════════════════════════════════
    # FRONTMATTER
    # ══════════════════════════════════════════════════════════════════════
    
    def _parse_frontmatter(self, report: ParseReport) -> Optional[List[str]]:
        """Parse frontmatter block (:::frontmatter ... :::)"""
        # Skip blank lines
        while self.line_idx < len(self.lines) and self._current_line().strip() == '':
            self.line_idx += 1
        
        if not self._current_line() == ':::frontmatter':
            report.fatal(C.F013, "Missing :::frontmatter block")
            return None
        
        self.line_idx += 1
        fm_lines = []
        
        while self.line_idx < len(self.lines):
            line = self._current_line()
            if line == ':::':
                self.line_idx += 1
                break
            fm_lines.append(line)
            self.line_idx += 1
        else:
            report.fatal(C.F014, "Frontmatter block not closed (missing ':::')")
            return None
        
        return fm_lines
    
    # ══════════════════════════════════════════════════════════════════════
    # BODY PARSING (State Machine)
    # ══════════════════════════════════════════════════════════════════════
    
    def _parse_body(self, report: ParseReport) -> List:
        """Parse body blocks (headings, paragraphs, poems, tables, figures, page breaks)"""
        body = []
        
        while self.line_idx < len(self.lines):
            line = self._current_line()
            
            # Skip blank lines
            if line.strip() == '':
                self.line_idx += 1
                continue
            
            # Page break (standalone)
            if self._is_page_break(line):
                body.append(self._parse_page_break(line))
                self.line_idx += 1
                continue
            
            # Heading
            if line.startswith('#'):
                body.append(self._parse_heading(line, report))
                self.line_idx += 1
                continue
            
            # Poem
            if line.startswith('>'):
                poem = self._parse_poem(report)
                if poem:
                    body.append(poem)
                continue
            
            # Table
            if line.startswith('::table'):
                table = self._parse_table(report)
                if table:
                    body.append(table)
                continue
            
            # Figure
            if line.startswith('::figure'):
                fig = self._parse_figure(report)
                if fig:
                    body.append(fig)
                continue
            
            # Footnote definition (collect, don't emit as block)
            if line.startswith('[^') and ']:' in line:
                self._parse_footnote_definition(line, report)
                self.line_idx += 1
                continue
            
            # Otherwise: paragraph
            para = self._parse_paragraph(report)
            if para and not para.is_empty:
                body.append(para)
        
        return body
    
    # ══════════════════════════════════════════════════════════════════════
    # PAGE BREAK
    # ══════════════════════════════════════════════════════════════════════
    
    def _is_page_break(self, line: str) -> bool:
        """Check if line is standalone page break {P N}"""
        return bool(re.match(r'^\{P\s+\d+\}$', line.strip()))
    
    def _parse_page_break(self, line: str) -> PageBreak:
        """Parse page break {P N}"""
        match = re.search(r'\{P\s+(\d+)\}', line)
        page_num = int(match.group(1)) if match else 0
        return PageBreak(source='page_field', page_num=page_num)
    
    # ══════════════════════════════════════════════════════════════════════
    # HEADING
    # ══════════════════════════════════════════════════════════════════════
    
    def _parse_heading(self, line: str, report: ParseReport) -> Heading:
        """Parse heading # text"""
        if line.startswith('###'):
            level = 3
            text = line[3:].strip()
        elif line.startswith('##'):
            level = 2
            text = line[2:].strip()
        else:
            level = 1
            text = line[1:].strip()

        # Heading adalah plain text — tidak ada inline marker yang relevan.
        # Tidak perlu parse→flatten→stringify; langsung bungkus sebagai TextSpan.
        return Heading(level=level, inlines=[TextSpan(text=text)])
    
    # ══════════════════════════════════════════════════════════════════════
    # PARAGRAPH
    # ══════════════════════════════════════════════════════════════════════
    
    def _parse_paragraph(self, report: ParseReport) -> Optional[Paragraph]:
        """Parse paragraph (until blank line or end of block)"""
        para_lines = []
        
        while self.line_idx < len(self.lines):
            line = self._current_line()
            
            # Stop at blank line
            if line.strip() == '':
                self.line_idx += 1
                break
            
            # Stop at next block marker
            if (line.startswith('#') or line.startswith('>') or 
                line.startswith('::') or self._is_page_break(line)):
                break
            
            # Stop at footnote definition
            if line.startswith('[^') and ']:' in line:
                break
            
            para_lines.append(line)
            self.line_idx += 1
        
        if not para_lines:
            return None
        
        # Join lines (soft breaks within paragraph)
        full_text = ' '.join(para_lines)
        
        # Parse into sentences
        sentences = self._parse_sentences(full_text, report)
        
        # Flatten ke inlines untuk backward compatibility (renderer.py, parser.py, dll)
        flat_inlines = []
        for sentence in sentences:
            flat_inlines.extend(sentence)
        
        # Simpan juga sentences langsung — dipakai json_renderer tanpa re-segmentasi
        return Paragraph(inlines=flat_inlines, sentences=sentences)
    
    def _parse_sentences(self, text: str, report: ParseReport) -> List[List]:
        """
        Parse text into sentences.

        Sentence boundaries:
        1. Single period (.) — titik MELEKAT ke teks sebelumnya beserta spasi
           setelahnya. Jika period muncul setelah {Q} (current_sentence kosong),
           period dilampirkan ke sentence quran sebelumnya agar tidak hilang.
           Contoh: "نص. نص ثانٍ"  → [TextSpan("نص. "), TextSpan("نص ثانٍ")]
           Contoh: "{Q ref}. نص"  → [QCFSpan, TextSpan(". نص")]  ← period ke quran
        2. Multi-dot (.. atau ...) — BUKAN sentence boundary; dilampirkan ke
           kalimat saat ini sebagai punctuation biasa.
        3. Quran marker {Q ...} atau {Qt ...} — standalone sentence.

        Returns: List of sentences, each sentence is list of inline elements.
        """
        sentences = []
        current_sentence = []
        i = 0

        def flush(suffix: str = ""):
            """Flush current_sentence ke sentences.
            suffix (mis. '. ' atau '.') ditempel ke TextSpan terakhir jika ada,
            atau ke sentence terakhir yang sudah selesai jika current kosong
            (kasus: period/spasi tepat setelah {Q} marker)."""
            nonlocal current_sentence
            if suffix:
                if current_sentence:
                    # Ada kalimat aktif — tempel suffix ke TextSpan terakhirnya
                    if isinstance(current_sentence[-1], TextSpan):
                        current_sentence[-1].text += suffix
                    else:
                        current_sentence.append(TextSpan(text=suffix))
                elif sentences:
                    # current kosong tapi sudah ada sentence sebelumnya (mis. habis {Q})
                    # Tempel suffix ke sentence terakhir itu
                    last_sent = sentences[-1]
                    if last_sent and isinstance(last_sent[-1], TextSpan):
                        last_sent[-1].text += suffix
                    else:
                        last_sent.append(TextSpan(text=suffix))
                    return  # tidak ada current untuk di-flush
            if current_sentence:
                sentences.append(current_sentence)
                current_sentence = []

        while i < len(text):
            ch = text[i]

            # ── Quran / PageBreak markers ─────────────────────────────────
            if ch == '{':
                marker, end_idx = self._try_parse_quran_marker(text, i, report)
                if marker:
                    # Quran = sentence boundary: flush current, then standalone
                    flush()
                    sentences.append([marker])
                    i = end_idx
                    continue

                pb, end_idx = self._try_parse_page_break_inline(text, i)
                if pb:
                    current_sentence.append(pb)
                    i = end_idx
                    continue

                # Literal '{' yang bukan marker
                self._append_char(current_sentence, ch)
                i += 1
                continue

            # ── Footnote ref ──────────────────────────────────────────────
            if ch == '[':
                fn_ref, end_idx = self._try_parse_footnote_ref(text, i)
                if fn_ref:
                    current_sentence.append(fn_ref)
                    i = end_idx
                    continue

            # ── Period — cek single vs multi-dot ─────────────────────────
            if ch == '.':
                # Hitung berapa titik berturut-turut
                j = i
                while j < len(text) and text[j] == '.':
                    j += 1
                dot_count = j - i  # 1 = titik biasa, 2+ = ellipsis/trailing dots

                if dot_count >= 2:
                    # Multi-dot: bukan sentence boundary — lampirkan ke kalimat ini
                    self._append_char(current_sentence, '.' * dot_count)
                    i = j
                else:
                    # Single period: sentence boundary.
                    # Kumpulkan spasi setelah titik — ikutkan ke sentence ini
                    # sehingga rekonstruksi teks (join sentences) menghasilkan
                    # spasi yang benar tanpa perlu logika di consumer.
                    j = i + 1
                    trailing = ''
                    while j < len(text) and text[j] in ' \t':
                        trailing += text[j]
                        j += 1
                    flush(suffix='.' + trailing)
                    i = j
                continue

            # ── Regular character ─────────────────────────────────────────
            self._append_char(current_sentence, ch)
            i += 1

        # Sisa kalimat (tanpa titik di akhir) — tetap simpan apa adanya
        if current_sentence:
            sentences.append(current_sentence)

        # Buang sentence yang benar-benar kosong (tidak ada karakter apapun).
        # Filter HANYA untuk sentence yang semua span-nya berisi teks kosong/whitespace saja.
        # Punctuation bermakna (., ؟, !, dsb.) TIDAK dibuang — bisa jadi konten nyata
        # antara dua {Q} marker.
        def _is_empty_sentence(sent):
            for span in sent:
                if not isinstance(span, TextSpan):
                    return False   # ada non-TextSpan (Quran, PageBreak, dll) — tidak kosong
                if span.text.replace('\xa0', '').replace(' ', '').replace('\t', ''):
                    return False   # ada karakter non-whitespace — tidak kosong
            return True

        return [s for s in sentences if s and not _is_empty_sentence(s)]
    
    def _append_char(self, sentence: List, ch: str):
        """Append karakter ke TextSpan terakhir atau buat TextSpan baru."""
        if sentence and isinstance(sentence[-1], TextSpan):
            sentence[-1].text += ch
        else:
            sentence.append(TextSpan(text=ch))

    # ══════════════════════════════════════════════════════════════════════
    # INLINE HELPERS
    # ══════════════════════════════════════════════════════════════════════

    def _try_parse_quran_marker(self, text: str, start_idx: int, report: ParseReport) -> Tuple[Optional[object], int]:
        """Try to parse {Q ...} or {Qt ...} at position"""
        # {Q surah:ayah:word-word}
        match = re.match(r'\{Q\s+([\d:]+(?:-[\d:]+)?)\}', text[start_idx:])
        if match:
            ref = match.group(1)
            if self._validate_quran_ref(ref):
                return (QCFSpan(font_code="", decoded=ref, preview=""), start_idx + match.end())
            else:
                report.warning(C.W006, f"Invalid Quran ref: {{{match.group(0)}}}")
                return (TextSpan(text=match.group(0)), start_idx + match.end())
        
        # {Qt text}
        match = re.match(r'\{Qt\s+([^}]+)\}', text[start_idx:])
        if match:
            qt_text = match.group(1).strip()
            if not qt_text:
                report.error(C.E002, "Empty {Qt} marker")
                return (TextSpan(text="{Qt}"), start_idx + match.end())
            return (UnicodeQuranSpan(text=qt_text), start_idx + match.end())
        
        return (None, start_idx)
    
    def _try_parse_page_break_inline(self, text: str, start_idx: int) -> Tuple[Optional[PageBreak], int]:
        """Try to parse {P N} at position"""
        match = re.match(r'\{P\s+(\d+)\}', text[start_idx:])
        if match:
            page_num = int(match.group(1))
            return (PageBreak(source='page_field', page_num=page_num), start_idx + match.end())
        return (None, start_idx)
    
    def _try_parse_footnote_ref(self, text: str, start_idx: int) -> Tuple[Optional[FootnoteRef], int]:
        """Try to parse [^N] at position"""
        match = re.match(r'\[\^(\d+)\]', text[start_idx:])
        if match:
            num = int(match.group(1))
            return (FootnoteRef(number=num), start_idx + match.end())
        return (None, start_idx)
    
    def _validate_quran_ref(self, ref: str) -> bool:
        """Validate Quran reference format.

        Format yang valid (dari qcf_decoder.format_coord):
          s:a          → surah:ayah (jarang, tapi valid)
          s:a:w        → surah:ayah:word
          s:a:w:p      → surah:ayah:word:part  (muncul saat satu kata punya beberapa bagian)
          s:a:w-s:a:w  → span antar-word
          s:a:w:p-s:a:w:p → span antar-part
          (juga kombinasi asimetris, mis. s:a:w-s:a:w:p)
        """
        # Satu komponen referensi: s:a, s:a:w, atau s:a:w:p
        _single = r'\d+:\d+(?::\d+(?::\d+)?)?'
        pattern = rf'^{_single}(?:-{_single})?$'
        return bool(re.match(pattern, ref))
    
    # ══════════════════════════════════════════════════════════════════════
    # POEM
    # ══════════════════════════════════════════════════════════════════════
    
    def _parse_poem(self, report: ParseReport) -> Optional[PoemTable]:
        """Parse poem (lines starting with >)"""
        rows = []
        
        while self.line_idx < len(self.lines):
            line = self._current_line()
            
            if line.strip() == '':
                self.line_idx += 1
                break
            
            if not line.startswith('>'):
                break
            
            cols = [c.strip() for c in line[1:].split('::')]
            rows.append(PoemRow(cols=cols))
            self.line_idx += 1
        
        if not rows:
            return None
        
        return PoemTable(rows=rows)
    
    # ══════════════════════════════════════════════════════════════════════
    # TABLE
    # ══════════════════════════════════════════════════════════════════════
    
    def _parse_table(self, report: ParseReport) -> Optional[DataTable]:
        """Parse table (::table ... ::)"""
        header_line = self._current_line()
        self.line_idx += 1
        
        style_match = re.search(r'style=(\w+)', header_line)
        style = style_match.group(1) if style_match else None
        
        rows = []
        while self.line_idx < len(self.lines):
            line = self._current_line()
            
            if line.strip() == '::':
                self.line_idx += 1
                break
            
            if line.strip().startswith('|'):
                cells = [c.strip() for c in line.strip().split('|')[1:-1]]
                rows.append(DataTableRow(cells=cells))
            
            self.line_idx += 1
        
        if not rows:
            report.warning(C.W007, "Empty table")
            return None
        
        max_cols = max(len(row.cells) for row in rows)
        for row in rows:
            while len(row.cells) < max_cols:
                row.cells.append("")
        
        if len(set(len(row.cells) for row in rows)) > 1:
            report.warning(C.W008, f"Table normalized to {max_cols} columns")
        
        return DataTable(rows=rows, style_id=style or "DataTable")
    
    # ══════════════════════════════════════════════════════════════════════
    # FIGURE
    # ══════════════════════════════════════════════════════════════════════
    
    def _parse_figure(self, report: ParseReport) -> Optional[Figure]:
        """Parse figure (::figure ... ::)"""
        header_line = self._current_line()
        self.line_idx += 1
        
        id_match = re.search(r'id=([^\s]+)', header_line)
        src_match = re.search(r'src=([^\s]+)', header_line)
        
        if not id_match or not src_match:
            report.error(C.E003, "Figure missing id= or src=")
            while self.line_idx < len(self.lines):
                if self._current_line().strip() == '::':
                    self.line_idx += 1
                    break
                self.line_idx += 1
            return None
        
        fig_id = id_match.group(1)
        src = src_match.group(1)
        
        alt = ""
        if self.line_idx < len(self.lines):
            alt_line = self._current_line()
            if alt_line.startswith('alt:'):
                alt = alt_line[4:].strip()
                self.line_idx += 1
        
        while self.line_idx < len(self.lines):
            if self._current_line().strip() == '::':
                self.line_idx += 1
                break
            self.line_idx += 1
        
        return Figure(figure_id=fig_id, alt=alt, src=src)
    
    # ══════════════════════════════════════════════════════════════════════
    # FOOTNOTE
    # ══════════════════════════════════════════════════════════════════════
    
    def _parse_footnote_definition(self, line: str, report: ParseReport):
        """Parse footnote definition [^N]: text"""
        match = re.match(r'\[\^(\d+)\]:\s*(.+)', line)
        if match:
            num = int(match.group(1))
            text = match.group(2)
            self.footnotes[num] = Footnote(number=num, inlines=[TextSpan(text=text)])
    
    def _validate_footnotes(self, report: ParseReport, body: list):
        """Cek konsistensi footnote dua arah:
        - Ref [^N] di body tapi tidak ada definisi [^N]: → ERROR
        - Definisi [^N]: ada tapi tidak pernah direferens di body → WARNING (orphan)
        """
        from .ast_nodes import FootnoteRef

        # Kumpulkan semua nomor ref yang muncul di body.
        # Scan lewat node.inlines (bukan node.sentences) karena _parse_paragraph
        # sudah mem-flatten sentences → inlines (baris 275-277), sehingga semua
        # FootnoteRef dari dalam sentences sudah tercakup di sini.
        # Jangan "perbaiki" ini dengan scan ke sentences — inlines sudah cukup.
        referenced: set[int] = set()
        for node in body:
            for span in getattr(node, 'inlines', []):
                if isinstance(span, FootnoteRef):
                    referenced.add(span.number)

        defined: set[int] = set(self.footnotes.keys())

        for num in sorted(referenced - defined):
            report.error(C.E001,
                f"Footnote ref [^{num}] tidak ada definisinya.",
                location=f"footnote {num}")
        for num in sorted(defined - referenced):
            report.warning(C.W003,
                f"Footnote {num} didefinisikan tapi tidak pernah direferens (orphan).",
                location=f"footnote {num}")
    
    # ══════════════════════════════════════════════════════════════════════
    # UTILS
    # ══════════════════════════════════════════════════════════════════════
    
    def _current_line(self) -> str:
        """Get current line (or empty if past end)"""
        if self.line_idx < len(self.lines):
            return self.lines[self.line_idx]
        return ""
