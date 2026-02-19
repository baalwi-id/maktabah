"""
maktabah/parser.py — DOCX → Document AST
"""
from __future__ import annotations
import re, time, zipfile
from pathlib import Path
from typing import Optional
import docx as _docx
from lxml import etree as _etree

from .ast_nodes import (
    Document, FrontmatterBlock,
    Heading, Paragraph, PoemTable, PoemRow,
    DataTable, DataTableRow, UnknownTable,
    Footnote, FootnoteRef, Figure,
    TextSpan, QCFSpan, UnicodeQuranSpan, PageBreak,
)
from .qcf_decoder import QCFDecoder, BEGIN_AYAH, END_AYAH
from .report import ParseReport, C

NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
def W(tag): return f"{{{NS}}}{tag}"

HEADING_STYLE_IDS = {
    "Heading1": 1, "Heading2": 2, "Heading3": 3,
    "Title": 1, "Sub-Title": 2, "SubTitle": 2,   # legacy alias
}

POEM_STYLE      = "Poem"
DATATABLE_STYLE = "DataTable"
POEM_SEPARATORS = set("*-|●•·᛫")

# Unicode Qur'an bracket markers (U+FD5F / U+FD5E)
UNICODE_BEGIN = "\uFD5F"   # ﵟ
UNICODE_END   = "\uFD5E"   # ﵞ

_DEATH_RE   = re.compile(r"المتوف[يى].*?(\d+)\s*هـ")
_HIJRI_RE   = re.compile(r"(\d{3,4})\s*هـ")
_YEAR_AD_RE = re.compile(r"(\d{4})\s*م")
_PUB_KW     = ("دار", "مكتبة", "مؤسسة", "منشورات", "مطبعة")

def _extract_short_author(full: str) -> str:
    """
    Buang gelar-gelar di awal nama Arab.
    Logika:
    1. Cari kata 'بن' pertama
    2. Ambil kata tepat sebelum 'بن' pertama = kata pertama nama inti
    3. Buang semua kata sebelumnya (gelar)
    4. Dari 'بن' terakhir, ambil kata pertama setelahnya
       lalu buang semua kata berawalan ال- setelahnya (nisba)

    Contoh:
      الإمام العلامة السيد الشريف المحدث محمد بن علي خرد العلوي الحسيني التريمي
      → محمد بن علي خرد
    """
    if not full:
        return full
    words = full.split()
    if not words:
        return full

    # Cari index 'بن' pertama
    try:
        first_bin = next(i for i, w in enumerate(words) if w == "بن")
    except StopIteration:
        return full   # tidak ada 'بن' → kembalikan penuh

    # Kata pertama nama inti = kata sebelum 'بن' pertama
    name_start = max(0, first_bin - 1)

    # Cari index 'بن' terakhir
    last_bin = max(i for i, w in enumerate(words) if w == "بن")

    # Kumpulkan kata dari name_start sampai akhir,
    # tapi setelah kata pertama setelah 'بن' terakhir,
    # buang kata-kata berawalan ال-
    result = []
    first_word_after_last_bin_done = False
    after_last_bin = False

    for i, w in enumerate(words):
        if i < name_start:
            continue  # buang gelar di awal

        if i == last_bin + 1:
            # kata pertama setelah بن terakhir — selalu disertakan
            result.append(w)
            after_last_bin = True
            first_word_after_last_bin_done = True
            continue

        if after_last_bin and first_word_after_last_bin_done:
            # kata-kata berikutnya: buang jika berawalan ال-
            if w.startswith("ال"):
                continue
            result.append(w)
            continue

        result.append(w)

    return " ".join(result) if result else full


class MaktabahParser:

    def __init__(self, decoder: QCFDecoder):
        self.decoder = decoder
        self._fig_counter = 0
        self._current_docx_path = ""
        self._page_comments: dict = {}   # comment_id → page_num dari macro PAGE:N

    def parse(self, docx_path, report: ParseReport) -> Optional[Document]:
        t0 = time.time()
        path = Path(docx_path)
        report.info(C.I001, f"Memulai parsing: {path.name}")
        self._fig_counter = 0
        self._current_docx_path = str(path)

        if not path.exists():
            report.fatal(C.F001, f"File tidak ditemukan: {path}"); return None
        if path.suffix.lower() != ".docx":
            report.fatal(C.F002, f"Bukan .docx: {path.suffix}"); return None
        if path.stat().st_size > 100 * 1024 * 1024:
            report.fatal(C.F004, "File >100 MB"); return None
        try:
            doc_obj = _docx.Document(str(path))
        except Exception as e:
            report.fatal(C.F003, f"Tidak bisa dibuka: {e}"); return None

        fn_defs      = self._extract_footnote_defs(report)
        page_comments = self._load_page_comments()
        self._page_comments = page_comments   # dipakai di _collect_inlines
        if page_comments:
            report.info(C.I004, f"Ditemukan {len(page_comments)} komentar PAGE: — mode akurat aktif.")
        raw      = self._traverse_body(doc_obj.element.body, fn_defs, report)
        doc_ast  = self._split_frontmatter(raw, report)
        doc_ast.footnotes = fn_defs
        self._validate_headings(doc_ast.body, report)
        self._report_stats(doc_ast, report, time.time() - t0)
        return doc_ast

    # ══════════════════════════════════════════════════════════════════════
    # TRAVERSAL
    # ══════════════════════════════════════════════════════════════════════

    # ══════════════════════════════════════════════════════════════════════
    # PARAGRAPH
    # ══════════════════════════════════════════════════════════════════════

    def _parse_paragraph(self, p_elem, idx: int, fn_defs: dict, report: ParseReport):
        style_id = self._get_style_id(p_elem)
        inlines = self._collect_inlines(p_elem, idx, fn_defs, report)

        # PageBreak sudah inline dalam inlines list di posisi tepat.
        # Heading yang diawali PageBreak: [PageBreak, ...text...]
        # → traversal akan split menjadi [PageBreak node, Heading node]
        
        # Pisahkan leading PageBreaks dari inlines
        leading_pbs = []
        while inlines and isinstance(inlines[0], PageBreak):
            leading_pbs.append(inlines.pop(0))

        result_nodes = leading_pbs  # PageBreak sebelum konten

        if style_id in HEADING_STYLE_IDS:
            result_nodes.append(Heading(level=HEADING_STYLE_IDS[style_id], inlines=inlines))
        else:
            result_nodes.append(Paragraph(inlines=inlines))

        return result_nodes  # list, di-extend di _traverse_body

    def _traverse_body(self, body_elem, fn_defs: dict, report: ParseReport) -> list:
        nodes = []
        pi = ti = 0
        for child in body_elem:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if tag == "p":
                result = self._parse_paragraph(child, pi, fn_defs, report)
                if result:
                    nodes.extend(result)   # result is a list
                pi += 1
            elif tag == "tbl":
                result = self._parse_table(child, ti, report)
                if result is not None:
                    if isinstance(result, list):
                        nodes.extend(result)   # tabel terpotong oleh page break
                    else:
                        nodes.append(result)
                ti += 1

        # Dedup: hapus LRPB yang merupakan duplikat dari EXPLICIT sebelumnya.
        # Pola yang terjadi di Word: explicit trailing di para A + lrpb leading di para B
        # keduanya merepresentasikan SATU pergantian halaman → hapus yg lrpb.
        # Juga: dalam satu para heading (explicit+lrpb keduanya leading), hapus yg lrpb.
        return self._dedup_pagebreaks(nodes)

    def _dedup_pagebreaks(self, nodes: list) -> list:
        """
        Hapus PageBreak(lrpb) yang merupakan duplikat dari PageBreak(explicit)
        di depannya.

        Aturan: jika PageBreak(explicit) diikuti PageBreak(lrpb) — dengan atau tanpa
        Paragraph kosong di antaranya — hapus yang lrpb.

        Ini menangani dua pola Word:
        1. EXP trailing di para A, LRPB leading di para B berikutnya
           (termasuk para kosong di antara A dan B)
        2. EXP dan LRPB keduanya leading di para yang sama (heading)
        """
        from .ast_nodes import PageBreak, Paragraph

        result = []
        prev_was_explicit = False

        for node in nodes:
            if isinstance(node, PageBreak):
                if node.source == "page_field":
                    # Sumber akurat dari komentar VBA — selalu pertahankan, tidak pernah di-skip
                    result.append(node)
                    prev_was_explicit = False
                elif node.source == "explicit":
                    result.append(node)
                    prev_was_explicit = True
                else:  # lrpb
                    if prev_was_explicit:
                        pass  # skip — duplikat dari explicit
                    else:
                        result.append(node)
                        prev_was_explicit = False  # lrpb bukan trigger
            elif isinstance(node, Paragraph) and node.is_empty:
                # Paragraf kosong tidak mereset flag — explicit masih berlaku
                result.append(node)
            else:
                # Konten nyata: reset flag
                prev_was_explicit = False
                result.append(node)

        return result

    def _get_style_id(self, p_elem) -> Optional[str]:
        pPr = p_elem.find(W("pPr"))
        if pPr is None: return None
        ps = pPr.find(W("pStyle"))
        return ps.get(W("val")) if ps is not None else None

    # ══════════════════════════════════════════════════════════════════════
    # INLINE CONTENT
    # ══════════════════════════════════════════════════════════════════════

    def _collect_inlines(self, p_elem, para_idx: int, fn_defs: dict,
                         report: ParseReport) -> list:
        """Returns inlines list. PageBreak injected inline at exact position."""
        inlines = []
        qcf_unit = None
        qcf_font_code = None

        # State for Unicode Qur'an bracketing
        unicode_unit: Optional[list] = None   # collecting chars between ﵟ…ﵞ

        def flush_qcf_partial():
            """Flush QCF buffer yang sedang aktif menjadi QCFSpan parsial.
            
            Dipanggil saat PageBreak ditemukan di tengah glyph unit (antara
            BEGIN_AYAH dan END_AYAH). Tanpa ini, ayat panjang yang terpotong
            banyak halaman akan menghasilkan semua PageBreak menumpuk di depan
            satu QCFSpan raksasa di akhir — sehingga navigasi per halaman rusak.
            
            Setelah flush, qcf_unit direset ke [] (bukan None) agar akumulasi
            glyph di halaman berikutnya tetap berjalan sampai END_AYAH.
            """
            nonlocal qcf_unit, qcf_font_code
            if qcf_unit:
                result = self.decoder.process_ayah_unit(qcf_unit)
                if result:
                    span, preview = result
                    inlines.append(QCFSpan(font_code=qcf_font_code or "",
                                           decoded=span, preview=preview))
                qcf_unit = []   # reset buffer, BUKAN None — unit masih terbuka

        for elem in p_elem.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

            if tag == "footnoteReference":
                fn_id = elem.get(W("id"))
                if fn_id and fn_id not in ("-1", "0"):
                    num = int(fn_id)
                    inlines.append(FootnoteRef(number=num))
                    # definisi footnote di-handle di renderer setelah paragraf
                continue

            if tag == "commentReference":
                # Komentar PAGE:N dari macro InsertPageMarkers
                cid_str = elem.get(W("id"))
                if cid_str is not None:
                    try:
                        cid = int(cid_str)
                        page_num = self._page_comments.get(cid, 0)
                        if page_num > 0:
                            # Ganti PageBreak lrpb/explicit sebelumnya yang mungkin
                            # sudah di-append untuk posisi yang sama
                            # (komentar PAGE: selalu ada di paragraf yang sama dengan LRPB)
                            # → tandai dengan source='page_field' dan page_num aktual
                            # Cari PageBreak terakhir di inlines dan upgrade
                            upgraded = False
                            for ri in range(len(inlines) - 1, -1, -1):
                                if isinstance(inlines[ri], PageBreak):
                                    inlines[ri] = PageBreak(source="page_field", page_num=page_num)
                                    upgraded = True
                                    break
                            if not upgraded:
                                # Tidak ada PageBreak sebelumnya → sisipkan baru
                                inlines.append(PageBreak(source="page_field", page_num=page_num))
                    except (ValueError, TypeError):
                        pass
                continue

            if tag == "br":
                br_type = elem.get(W("type"), "")
                if br_type == "page":
                    # Flush QCF buffer parsial sebelum emit PageBreak, agar
                    # glyph yang sudah terkumpul di halaman ini tidak ikut
                    # "terseret" ke halaman berikutnya.
                    flush_qcf_partial()
                    inlines.append(PageBreak(source="explicit"))   # inline di posisi tepat
                else:
                    inlines.append(TextSpan(text=" "))
                continue

            # lastRenderedPageBreak → inline PageBreak di posisi tepat
            if tag == "lastRenderedPageBreak":
                # Flush QCF buffer parsial sebelum emit PageBreak — alasan sama
                # dengan explicit page break di atas.
                flush_qcf_partial()
                inlines.append(PageBreak(source="lrpb"))
                continue

            if tag == "drawing":
                self._fig_counter += 1
                fid = f"fig_{self._fig_counter:03d}"
                ns_draw = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
                docPr = elem.find(f".//{{{ns_draw}}}docPr")
                alt = docPr.get("descr", "") if docPr is not None else ""
                inlines.append(Figure(figure_id=fid, alt=alt, src="PENDING"))
                continue

            if tag != "t":
                continue

            run_elem = elem.getparent()
            if run_elem is None: continue

            font_name = self._get_run_font(run_elem)
            text = elem.text or ""
            if not text: continue

            # ── Unicode Qur'an (KFGQPC font) ─────────────────────────
            if QCFDecoder.is_unicode_quran_font(font_name):
                # FIX: process char-by-char to detect ﵟ…ﵞ brackets
                qcf_unit, qcf_font_code, unicode_unit = self._process_unicode_quran(
                    text, qcf_unit, qcf_font_code, unicode_unit, inlines
                )
                continue

            # ── QCF glyph font ────────────────────────────────────────
            font_code = QCFDecoder.extract_font_code(font_name)
            if font_code:
                # Close any open unicode unit before switching to QCF
                if unicode_unit is not None:
                    inlines.append(UnicodeQuranSpan(text="".join(unicode_unit)))
                    unicode_unit = None
                qcf_unit, qcf_font_code = self._process_qcf_run(
                    text, font_code, qcf_unit, qcf_font_code, inlines
                )
                continue

            # ── plain text ────────────────────────────────────────────
            # Close unicode unit if open
            if unicode_unit is not None:
                inlines.append(UnicodeQuranSpan(text="".join(unicode_unit)))
                unicode_unit = None
            if text:
                inlines.append(TextSpan(text=text))

        # Close unclosed units
        if unicode_unit is not None:
            inlines.append(UnicodeQuranSpan(text="".join(unicode_unit)))
        if qcf_unit:
            result = self.decoder.process_ayah_unit(qcf_unit)
            if result:
                span, preview = result
                inlines.append(QCFSpan(font_code=qcf_font_code or "", decoded=span, preview=preview))

        return inlines

    def _process_unicode_quran(self, text, qcf_unit, qcf_font_code,
                                unicode_unit, inlines):
        """
        BUG 6 fix: process KFGQPC text char-by-char.
        ﵟ (U+FD5F) = begin, ﵞ (U+FD5E) = end.
        Everything between markers → UnicodeQuranSpan with {Qt ...} wrapper.
        Text outside markers (in KFGQPC font) → plain TextSpan (e.g. " ").
        """
        for ch in text:
            if ch == UNICODE_BEGIN:
                unicode_unit = []
                continue
            if ch == UNICODE_END:
                if unicode_unit is not None:
                    content = "".join(unicode_unit).strip()
                    if content:
                        inlines.append(UnicodeQuranSpan(text=content))
                unicode_unit = None
                continue
            if unicode_unit is not None:
                unicode_unit.append(ch)
            else:
                # text in KFGQPC font but outside brackets = plain text (e.g. spaces)
                if ch.strip():
                    inlines.append(TextSpan(text=ch))
        return qcf_unit, qcf_font_code, unicode_unit

    def _process_qcf_run(self, text, font_code, qcf_unit, qcf_font_code, inlines):
        """
        Proses satu run teks QCF glyph font char-by-char.

        qcf_unit bisa dalam tiga state:
          None   = di luar ayah (belum ketemu BEGIN_AYAH atau sudah END_AYAH)
          []     = di dalam ayah, buffer kosong karena baru di-flush parsial
                   oleh flush_qcf_partial() saat ada PageBreak di tengah unit
          [...]  = di dalam ayah, ada glyph yang sudah terkumpul

        Perbedaan None vs [] penting:
          - None → glyph di luar ayah → buang (PUA) atau emit TextSpan
          - []   → masih di dalam ayah, glyph berikutnya tetap dikumpulkan
        """
        for ch in text:
            hexv = QCFDecoder.char_hex(ch)
            if hexv == BEGIN_AYAH:
                qcf_unit = []; qcf_font_code = font_code; continue
            if hexv == END_AYAH:
                if qcf_unit is not None:
                    # qcf_unit bisa [] jika semua glyph sudah di-flush parsial
                    # dan halaman terakhir kosong — process_ayah_unit([]) → None, aman.
                    result = self.decoder.process_ayah_unit(qcf_unit)
                    if result:
                        span, preview = result
                        inlines.append(QCFSpan(font_code=qcf_font_code or font_code,
                                               decoded=span, preview=preview))
                qcf_unit = None; qcf_font_code = None; continue
            if qcf_unit is None:
                # Di luar BEGIN_AYAH..END_AYAH — buang glyph PUA, emit non-PUA
                if not (0xE000 <= ord(ch) <= 0xF8FF):
                    inlines.append(TextSpan(text=ch))
                continue
            # qcf_unit is not None ([] atau [...]) → kumpulkan glyph
            decoded = self.decoder.decode_glyph(font_code, ch)
            if decoded:
                s, a, w, p, preview = decoded
                qcf_unit.append({"loc": (s, a, w, p), "preview": preview})
        return qcf_unit, qcf_font_code

    def _get_run_font(self, run_elem) -> Optional[str]:
        rPr = run_elem.find(W("rPr"))
        if rPr is None: return None
        rFonts = rPr.find(W("rFonts"))
        if rFonts is None: return None
        return (rFonts.get(W("cs")) or rFonts.get(W("ascii")) or rFonts.get(W("hAnsi")))

    # ══════════════════════════════════════════════════════════════════════
    # TABLE
    # ══════════════════════════════════════════════════════════════════════

    def _row_has_pagebreak(self, tr_elem) -> Optional[tuple]:
        """
        Cek apakah row tabel diawali page break.
        Mengembalikan (source, page_num) atau None.
          source: 'page_field' | 'explicit' | 'lrpb'
          page_num: nomor halaman aktual (hanya untuk 'page_field'), else 0

        Prioritas: commentReference PAGE:N (akurat) > explicit > lrpb.
        Hanya cek cell PERTAMA — itulah posisi PB yang disisipkan Word.
        """
        first_tc = tr_elem.find(W("tc"))
        if first_tc is None:
            return None
        first_p = first_tc.find(W("p"))
        if first_p is None:
            return None

        found_lrpb = False
        found_explicit = False

        for elem in first_p.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag == "commentReference":
                cid_str = elem.get(W("id"))
                if cid_str is not None:
                    try:
                        cid = int(cid_str)
                        page_num = self._page_comments.get(cid, 0)
                        if page_num > 0:
                            return ("page_field", page_num)
                    except (ValueError, TypeError):
                        pass
            elif tag == "lastRenderedPageBreak":
                found_lrpb = True
            elif tag == "br" and elem.get(W("type")) == "page":
                found_explicit = True

        if found_explicit:
            return ("explicit", 0)
        if found_lrpb:
            return ("lrpb", 0)
        return None

    def _parse_table(self, tbl_elem, idx: int, report: ParseReport):
        """Parse tabel, otomatis memotong di baris yang diawali page break."""
        style_id = self._get_table_style(tbl_elem)
        tr_elems = tbl_elem.findall(W("tr"))

        # Kumpulkan baris ke dalam chunk-chunk yang dipisah PageBreak
        # chunk = list of row data (list of cell strings)
        chunks: list[list[list[str]]] = []
        chunk_pbs: list[Optional[str]] = []   # source PB sebelum setiap chunk (kecuali pertama)
        current_chunk: list[list[str]] = []

        # Page break yang ada di row PERTAMA tabel (current_chunk masih kosong)
        # tidak bisa jadi pemisah antar-chunk, tapi harus disisipkan SEBELUM tabel.
        leading_pb: Optional[tuple] = None

        for tr in tr_elems:
            pb_result = self._row_has_pagebreak(tr)
            cells = self._extract_row_cells(tr)
            if not cells:
                continue
            if pb_result and current_chunk:
                # Page break di tengah tabel → potong jadi dua chunk
                chunks.append(current_chunk)
                chunk_pbs.append(pb_result)   # (source, page_num)
                current_chunk = [cells]
            else:
                if pb_result and not current_chunk:
                    # Page break di row pertama tabel → simpan sebagai leading PB
                    leading_pb = pb_result
                current_chunk.append(cells)

        if current_chunk:
            chunks.append(current_chunk)

        # Bangun nodes: [Table, PageBreak, Table, PageBreak, Table, ...]
        def _make_table(rows_data):
            if style_id == POEM_STYLE or self._looks_like_poem(rows_data):
                return PoemTable(rows=[PoemRow(cols=self._strip_poem_separator(r)) for r in rows_data])
            if style_id == DATATABLE_STYLE:
                return DataTable(rows=[DataTableRow(cells=r) for r in rows_data])
            report.warning(C.W012,
                f"Tabel style '{style_id or 'tidak ada'}' tidak dikenali.",
                location=f"tabel ke-{idx + 1}")
            return UnknownTable(style_id=style_id or "",
                                rows=[DataTableRow(cells=r) for r in rows_data])

        if len(chunks) == 1:
            tbl_node = _make_table(chunks[0])
            if leading_pb:
                pb_source, pb_page_num = leading_pb
                return [PageBreak(source=pb_source, page_num=pb_page_num), tbl_node]
            return tbl_node

        # Tabel terpotong: kembalikan list [Table, PB, Table, PB, Table, ...]
        nodes = []
        for i, chunk in enumerate(chunks):
            if i > 0:
                pb_source, pb_page_num = chunk_pbs[i - 1]
                nodes.append(PageBreak(source=pb_source, page_num=pb_page_num))
            nodes.append(_make_table(chunk))

        # Prepend leading PB jika ada
        if leading_pb:
            pb_source, pb_page_num = leading_pb
            nodes.insert(0, PageBreak(source=pb_source, page_num=pb_page_num))

        return nodes

    @staticmethod
    def _strip_poem_separator(cols: list[str]) -> list[str]:
        """
        BUG 4: hapus kolom yang berisi simbol separator atau kosong.
        [صدر, *, عجز] → [صدر, عجز]
        """
        return [c for c in cols if c.strip() and c.strip() not in POEM_SEPARATORS]

    @staticmethod
    def _looks_like_poem(rows_data: list[list[str]]) -> bool:
        """
        Cek apakah tabel ini adalah qasidah/syair.

        Pola baris yang diterima:
        - Baris penuh : 3 kolom, kolom tengah = simbol separator (*, -, dll)
                        → صدر | * | عجز
        - Baris penutup: 3 kolom tapi kolom 2&3 kosong (= bait ganjil di akhir)
                        → makhir | '' | ''

        Syarat lulus: minimal ada 1 baris penuh; tidak ada baris di luar kedua pola di atas.
        """
        if not rows_data: return False
        has_full_row = False
        for row in rows_data:
            non_empty = [c for c in row if c.strip()]
            if len(non_empty) == 0:
                continue  # baris kosong total, abaikan
            if len(non_empty) == 1:
                # baris penutup (bait tunggal) — boleh ada
                continue
            if len(row) == 3:
                mid = row[1].strip()
                if mid and len(mid) == 1 and mid in POEM_SEPARATORS:
                    has_full_row = True
                    continue
            # Pola lain (2-col, 3-col tanpa sep, >3-col) → bukan poem
            return False
        return has_full_row

    def _get_table_style(self, tbl_elem) -> Optional[str]:
        tblPr = tbl_elem.find(W("tblPr"))
        if tblPr is None: return None
        ts = tblPr.find(W("tblStyle"))
        return ts.get(W("val")) if ts is not None else None

    def _extract_row_cells(self, tr_elem) -> list[str]:
        """Extract cell strings dari satu row elemen."""
        cells = []
        for tc in tr_elem.findall(W("tc")):
            parts = []
            for p in tc.findall(W("p")):
                for elem in p.iter():
                    tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                    if tag == "t":
                        parts.append(elem.text or "")
                    elif tag == "br":
                        parts.append(" ")
            cells.append("".join(parts).strip())
        return cells if cells else []

    # ══════════════════════════════════════════════════════════════════════
    # PAGE COMMENTS — komentar PAGE:N dari macro VBA
    # ══════════════════════════════════════════════════════════════════════

    def _load_page_comments(self) -> dict:
        """
        Load komentar PAGE:N dari word/comments.xml.
        Return dict: {comment_id (int) → page_num (int)}

        Komentar dibuat oleh macro InsertPageMarkers.bas dengan format teks 'PAGE:N'.
        Parser menggunakan ini sebagai sumber nomor halaman yang akurat (100% sesuai Word).
        Jika tidak ada komentar PAGE: → dict kosong → parser fallback ke LRPB counter.
        """
        if not self._current_docx_path:
            return {}
        try:
            with zipfile.ZipFile(self._current_docx_path, 'r') as z:
                if 'word/comments.xml' not in z.namelist():
                    return {}
                xml = z.read('word/comments.xml')
        except Exception:
            return {}
        try:
            root = _etree.fromstring(xml)
        except Exception:
            return {}

        page_comments = {}
        for comment in root.findall(W('comment')):
            try:
                cid = int(comment.get(W('id'), '-1'))
            except ValueError:
                continue
            if cid < 0:
                continue
            # Gabungkan semua teks dalam komentar
            text = ''.join(t.text or '' for t in comment.iter(W('t'))).strip()
            if text.startswith('PAGE:'):
                try:
                    page_num = int(text[5:].strip())
                    page_comments[cid] = page_num
                except ValueError:
                    pass
        return page_comments

    # ══════════════════════════════════════════════════════════════════════
    # FOOTNOTES — via zipfile (python-docx API tidak konsisten)
    # ══════════════════════════════════════════════════════════════════════

    def _extract_footnote_defs(self, report: ParseReport) -> dict:
        footnotes = {}
        if not self._current_docx_path:
            return {}
        try:
            with zipfile.ZipFile(self._current_docx_path, 'r') as z:
                if 'word/footnotes.xml' not in z.namelist():
                    return {}
                fn_xml = z.read('word/footnotes.xml')
        except Exception:
            return {}
        try:
            root = _etree.fromstring(fn_xml)
        except Exception:
            return {}

        for fn in root.findall(W("footnote")):
            try:
                fn_id = int(fn.get(W("id"), "0"))
            except ValueError:
                continue
            if fn_id <= 0:
                continue
            inlines = []
            for p in fn.findall(W("p")):
                for elem in p.iter():
                    tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                    if tag == "t":
                        run_elem = elem.getparent()
                        font = self._get_run_font(run_elem) if run_elem is not None else None
                        text = elem.text or ""
                        if not text: continue
                        if QCFDecoder.is_unicode_quran_font(font):
                            inlines.append(UnicodeQuranSpan(text=text))
                        else:
                            inlines.append(TextSpan(text=text))
                    elif tag == "br":
                        inlines.append(TextSpan(text=" "))
            footnotes[fn_id] = Footnote(number=fn_id, inlines=inlines)
        return footnotes

    # ══════════════════════════════════════════════════════════════════════
    # FRONTMATTER + METADATA
    # ══════════════════════════════════════════════════════════════════════

    def _split_frontmatter(self, raw_nodes: list, report: ParseReport) -> Document:
        from .ast_nodes import PageBreak
        first_h = next((i for i, n in enumerate(raw_nodes) if isinstance(n, Heading)), None)
        if first_h is None:
            fm_nodes, body_nodes = raw_nodes, []
        else:
            # PageBreak yang ada tepat sebelum Heading pertama harus ikut ke body,
            # bukan frontmatter. Cari seberapa jauh ke belakang ada PB trailing.
            split_at = first_h
            while split_at > 0 and isinstance(raw_nodes[split_at - 1], PageBreak):
                split_at -= 1
            fm_nodes, body_nodes = raw_nodes[:split_at], raw_nodes[split_at:]

        fm_lines = []
        for node in fm_nodes:
            if isinstance(node, Paragraph) and not node.is_empty:
                text = node.text.strip()
                # FIX: jika المتوفي tersemat dalam baris yang lebih panjang,
                # pisahkan menjadi dua baris agar metadata author_death_hijri bisa diekstrak.
                if "المتوف" in text and len(text) > 30:
                    idx = text.index("المتوف")
                    before = text[:idx].strip()
                    death_part = text[idx:].strip()
                    if before:
                        fm_lines.append(before)
                    fm_lines.append(death_part)
                else:
                    fm_lines.append(text)

        if not fm_lines:
            report.warning(C.W005, "Frontmatter kosong.")

        meta = self._extract_metadata(fm_lines)
        return Document(frontmatter=FrontmatterBlock(lines=fm_lines, metadata=meta),
                        body=body_nodes)

    def _extract_metadata(self, lines: list[str]) -> dict:
        meta = {
            "title": None, "author": None, "author_full": None,
            "author_death_hijri": None, "edition": None,
            "edition_year": None, "publisher": None, "rights": None,
        }
        if not lines:
            return meta

        meta["title"] = lines[0].strip()

        for i, line in enumerate(lines):
            s = line.strip()
            if not s: continue

            # ── تأليف → nama penulis ──────────────────────────────────
            if s in ("تأليف", "تأليف:") and meta["author_full"] is None:
                parts = []
                for j in range(i + 1, len(lines)):
                    part = lines[j].strip()
                    if not part: break
                    if any(kw in part for kw in _PUB_KW): break
                    # FIX: jika baris mengandung المتوفي,
                    # ambil bagian SEBELUM المتوفي saja — sisanya bukan nama pengarang.
                    if "المتوف" in part:
                        before = part[:part.index("المتوف")].strip()
                        if before:
                            parts.append(before)
                        break
                    parts.append(part)
                if parts:
                    full = " ".join(parts)
                    meta["author_full"] = full
                    meta["author"] = _extract_short_author(full)
                continue

            # ── tahun wafat ───────────────────────────────────────────
            m = _DEATH_RE.search(s)
            if m and meta["author_death_hijri"] is None:
                meta["author_death_hijri"] = int(m.group(1))
                continue

            # ── hak cipta (cek dulu sebelum edition agar tidak ter-skip) ──
            # FIX: urutan cek penting — "حقوق" bisa muncul di baris yang sama dengan tahun.
            if "حقوق" in s:
                meta["rights"] = "copyrighted"

            # ── edition_year (edition dikosongkan) ────────────────────
            if meta["edition_year"] is None:
                if "الطبعة" in s or "طبع" in s:
                    m_h = _HIJRI_RE.search(s)
                    if m_h:
                        meta["edition_year"] = int(m_h.group(1))
                        continue
                # tahun hijri saja di baris terpisah
                m_h = _HIJRI_RE.search(s)
                if m_h and s.strip().startswith(m_h.group(1)):
                    meta["edition_year"] = int(m_h.group(1))
                    continue
                # tahun masehi
                m_ad = _YEAR_AD_RE.search(s)
                if m_ad:
                    meta["edition_year"] = int(m_ad.group(1))
                    continue

            # ── penerbit ──────────────────────────────────────────────
            if meta["publisher"] is None and any(kw in s for kw in _PUB_KW):
                meta["publisher"] = s; continue

        return meta

    # ══════════════════════════════════════════════════════════════════════
    # VALIDATION + STATS
    # ══════════════════════════════════════════════════════════════════════

    def _validate_headings(self, body: list, report: ParseReport):
        headings = [n for n in body if isinstance(n, Heading)]
        if not headings:
            report.error(C.E005, "Tidak ada heading dalam dokumen."); return
        if headings[0].level != 1:
            report.warning(C.W010, f"Heading pertama adalah H{headings[0].level}, bukan H1.",
                           location=f"'{headings[0].text[:50]}'")
        prev = 0
        for h in headings:
            if prev > 0 and h.level - prev > 1:
                report.warning(C.W009, f"Heading loncat H{prev}→H{h.level}.",
                               location=f"'{h.text[:50]}'")
            prev = h.level

    def _report_stats(self, doc: Document, report: ParseReport, elapsed: float):
        b = doc.body
        # Hitung Figure di dalam inlines paragraf juga
        fig_count = sum(1 for n in b if isinstance(n, Figure))
        for n in b:
            if isinstance(n, Paragraph):
                fig_count += sum(1 for s in n.inlines if isinstance(s, Figure))
        report.info(C.I002,
            f"Elemen: "
            f"{sum(1 for n in b if isinstance(n, Heading))} heading, "
            f"{sum(1 for n in b if isinstance(n, Paragraph))} paragraf, "
            f"{sum(1 for n in b if isinstance(n, PoemTable))} syair, "
            f"{sum(1 for n in b if isinstance(n, DataTable))} tabel, "
            f"{sum(1 for n in b if isinstance(n, UnknownTable))} tabel-unknown, "
            f"{sum(1 for n in b if isinstance(n, PageBreak))} page-break, "
            f"{len(doc.footnotes)} footnote, "
            f"{fig_count} gambar"
        )
        report.info(C.I003, f"Waktu: {elapsed:.2f}s")
