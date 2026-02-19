# PARSER SPECIFICATION v1.0
## DOCX to Canonical Text Converter

**Document Version:** 1.0  
**Date:** February 16, 2026  
**Target:** Maktabah Digital Library Platform  
**Canonical Standard:** v1.1

---

## TABLE OF CONTENTS

1. [SCOPE & PHILOSOPHY](#1-scope--philosophy)
2. [INPUT REQUIREMENTS](#2-input-requirements)
3. [PREPROCESSING VALIDATION](#3-preprocessing-validation)
4. [PARSING RULES](#4-parsing-rules)
5. [ERROR HANDLING](#5-error-handling)
6. [OUTPUT GENERATION](#6-output-generation)
7. [VALIDATION & TESTING](#7-validation--testing)
8. [IMPLEMENTATION NOTES](#8-implementation-notes)

---

## 1. SCOPE & PHILOSOPHY

### 1.1 What This Parser Does

**Primary Function:**
> Convert structured DOCX files into Canonical Text format for the Maktabah Digital Library.

**Key Principles:**

**1. Deterministic Parsing (NOT Heuristic)**
```
❌ WRONG: "This looks like poetry, maybe it's a poem"
✅ RIGHT: "This table has style='Poem', therefore it IS poetry"
```

The parser **NEVER guesses** or **interprets**. It only reads explicit structural markers (Word styles, fonts, table styles).

**2. Fail-Fast Philosophy**
```
❌ WRONG: "I'll guess this is a heading and continue"
✅ RIGHT: "This has no recognized style → REJECT document"
```

When encountering ambiguity or invalid structure, the parser **rejects the document** with a clear error message, rather than making assumptions.

**3. Editor Responsibility**
```
Structure comes from DOCX styles, not parser intelligence.
If document structure is wrong → Editor fixes DOCX → Re-upload
```

The parser is a **mechanical transcriber**, not an intelligent analyzer.

---

### 1.2 What This Parser Does NOT Do

❌ **Does NOT:**
- Interpret semantic meaning of text
- Classify content (e.g., "this is a muqaddimah")
- Correct typos or grammatical errors
- Normalize spelling or diacritics
- Guess missing information
- Apply heuristics or machine learning
- Make editorial decisions

✅ **Only:**
- Reads explicit Word styles
- Detects specific font patterns (QCF, KFGQPC)
- Extracts structural elements as-is
- Validates structure consistency
- Reports errors when structure is ambiguous

---

### 1.3 Success Criteria

Parser succeeds when:
```
✅ Every structural element in DOCX → Canonical representation
✅ Zero interpretation or guessing required
✅ Output is 100% reproducible (same input = same output)
✅ Errors are caught early and clearly reported
✅ Editor can fix errors without parser knowledge
```

---

## 2. INPUT REQUIREMENTS

### 2.1 DOCX Format

**Supported Versions:**
- Microsoft Word 2016 or later (`.docx` format)
- LibreOffice Writer 6.0+ (saved as `.docx`)
- Google Docs (exported as `.docx`)

**Required Components:**
- Valid DOCX structure (ZIP archive with `word/document.xml`)
- UTF-8 or UTF-16 text encoding
- Standard Word styles (Heading 1/2/3, Normal)

**Maximum Limits:**
- File size: 100 MB
- Pages: 2,000 pages
- Images: 200 images
- Footnotes: 5,000 footnotes

**Rationale:**
- File size (100 MB): Covers most books with images (typical 500-page book ≈ 5-20 MB)
- Pages (2,000): Accommodates large single-volume works
- Images (200): Generous buffer for illustrated texts
- Footnotes (5,000): Sufficient for heavily annotated works

---

### 2.2 Required Word Styles

**Recognized Styles:**

| Word Style | Canonical Output | Purpose |
|------------|-----------------|---------|
| `Heading 1` | `# Text` | Chapter (Bab) |
| `Heading 2` | `## Text` | Section (Fasal) |
| `Heading 3` | `### Text` | Subsection (Fara') |
| `Normal` | Plain paragraph | Body text |
| `Footnote Text` | `[^n]: Text` | Footnote content |
| **ALL OTHER STYLES** | **Plain paragraph** | **Treated as Normal** |

**Important Notes:**
- **ONLY** Heading 1/2/3 are recognized as structural elements
- Title, Subtitle, Quote, Emphasis, and **all custom styles** are treated as Normal
- This keeps parsing simple and unambiguous
- Parser extracts text content regardless of style name
- Frontmatter boundary = first Heading 1/2/3

**Table Styles:**

| Table Style | Canonical Output | Purpose |
|-------------|-----------------|---------|
| `Poem` | `> col :: col` | Poetry (Shi'r) |
| `DataTable` | `::table ... ::` | Scientific tables |
| *(no style)* | `::table style=unknown` | Generic table (user classifies in web editor) |

---

### 2.3 Required Fonts

**For Qur'an References (QCF Glyphs):**

Pattern: `QCF4_Hafs_XX` or `QCF4_Hafs_XX_W`
- Where `XX` = 01 to 47 (font number, not surah number)
- Total: 47 font files covering all 114 surahs
- Source: King Fahd Glorious Quran Printing Complex
- Official app: Quran for Publisher (https://nashr.qurancomplex.gov.sa/)
- Example: `QCF4_Hafs_02`, `QCF4_Hafs_15_W`

**For Qur'an Text (Unicode):**

Exact font name: `KFGQPC_HAFS_Uthmanic_Script_H`
- Only this specific font is accepted
- Source: King Fahd Glorious Quran Printing Complex
- From Quran for Publisher application
- No variants or alternatives accepted

**Font Detection:**
```python
import re

def is_qcf_font(fontname):
    """Detect QCF glyph font (47 fonts total)"""
    if not fontname:
        return False
    pattern = r'QCF4_Hafs_(\d{2})(_W)?'
    return bool(re.match(pattern, fontname, re.IGNORECASE))

def is_unicode_quran_font(fontname):
    """Detect Unicode Qur'an font (exact match only)"""
    if not fontname:
        return False
    return fontname == 'KFGQPC_HAFS_Uthmanic_Script_H'
```

---

### 2.4 Document Structure Assumptions

**Expected Structure:**
```
1. Frontmatter (optional)
   - Everything before first Heading 1/2/3
   - All styles treated as Normal (Title, Subtitle, etc. ignored)
   - Used for metadata extraction
   
2. Body (required)
   - Starts with first Heading 1/2/3
   - MUST contain at least one heading
   - Hierarchical headings (H1 > H2 > H3)
   - Paragraphs, poetry, tables, figures, footnotes
   
3. Page markers (optional)
   - From header/footer page numbers
```

**Frontmatter Boundary:**
> Everything before the first Heading 1/2/3 = frontmatter

**Rules:**
- **At least ONE heading (H1/H2/H3) is REQUIRED**
- If no headings exist → ERROR E005 (reject)
- If first element is heading → No frontmatter (valid)
- All paragraph styles in frontmatter treated as Normal

**Rationale for Required Headings:**
- Islamic scholarly texts always have structure (Bab, Fasal, etc.)
- Without headings, cannot create navigation or table of contents
- In canonical format, all paragraphs look identical without `#` markers
- Easier to identify structure in DOCX (visual cues: bold, size, color)
- Even short texts should have at least a title heading
- Quality control: No headings likely means user forgot to apply styles

**Example:**

```
DOCX:
┌────────────────────────────────┐
│ المجموع شرح المهذب             │ ← Normal (frontmatter)
│ للإمام النووي                 │ ← Normal (frontmatter)
│ دار الفكر - بيروت             │ ← Normal (frontmatter)
│                                │
│ كتاب الطهارة                   │ ← Heading 1 (body starts here)
│ فصل الماء                      │ ← Heading 2
│ اعلم أن العبد...              │ ← Normal (body content)
└────────────────────────────────┘

Canonical:
:::frontmatter
المجموع شرح المهذب
للإمام النووي
دار الفكر - بيروت
:::

# كتاب الطهارة

## فصل الماء

اعلم أن العبد...
```

---

## 3. PREPROCESSING VALIDATION

### 3.1 File Integrity Checks

**Before parsing, validate:**

```python
def validate_docx_file(filepath):
    """
    Validate DOCX file integrity before parsing.
    """
    errors = []
    
    # Check file exists
    if not filepath.exists():
        errors.append("FATAL: File not found")
        return errors
    
    # Check file extension
    if filepath.suffix.lower() != '.docx':
        errors.append("FATAL: File must be .docx format")
        return errors
    
    # Check file size
    file_size = filepath.stat().st_size
    if file_size > 100 * 1024 * 1024:  # 100 MB
        errors.append("FATAL: File too large (max 100 MB)")
        return errors
    
    # Check if valid ZIP (DOCX is ZIP archive)
    try:
        with zipfile.ZipFile(filepath, 'r') as zip_file:
            # Check for required DOCX components
            required_files = ['word/document.xml', '[Content_Types].xml']
            for req_file in required_files:
                if req_file not in zip_file.namelist():
                    errors.append(f"FATAL: Invalid DOCX structure (missing {req_file})")
    except zipfile.BadZipFile:
        errors.append("FATAL: Corrupted ZIP archive")
    except Exception as e:
        errors.append(f"FATAL: Cannot read file ({str(e)})")
    
    return errors
```

**Error Actions:**
- If ANY FATAL error → **Stop immediately**, report error, reject file
- No partial parsing attempts

---

### 3.2 Document Structure Validation

**After loading DOCX, before parsing:**

```python
def validate_document_structure(doc):
    """
    Validate document structure before parsing.
    Returns: (is_valid, errors, warnings)
    """
    errors = []
    warnings = []
    
    # 1. Check if document is empty
    if len(doc.paragraphs) == 0:
        errors.append("ERROR: Document contains no text")
        return (False, errors, warnings)
    
    # 2. Check heading level sequence
    heading_errors = validate_heading_sequence(doc)
    errors.extend(heading_errors)
    
    # 3. Check for required fonts if Qur'an content present
    quran_warnings = validate_quran_fonts(doc)
    warnings.extend(quran_warnings)
    
    # 4. Check footnote integrity
    footnote_errors = validate_footnotes(doc)
    errors.extend(footnote_errors)
    
    # 5. Check table styles
    table_errors = validate_table_styles(doc)
    errors.extend(table_errors)
    
    is_valid = len(errors) == 0
    return (is_valid, errors, warnings)
```

---

### 3.3 Heading Level Validation

**Rules:**

**RULE 1: At least one heading REQUIRED**
- Document with NO headings at all → ERROR E005 (reject)
- Rationale: Islamic texts require structure; cannot create navigation without headings
- User must apply Heading 1/2/3 styles in Word before upload

**RULE 2: Cannot skip heading levels**
- H1 → H3 (skipping H2) → WARNING W009 (allow web editor fix)
- Can go back up (H3 → H1 is OK)
- Rationale: Easy to fix in web editor (change level or insert missing)

**RULE 3: First heading should be H1**
- Document starts with H2/H3 → WARNING W010 (allow web editor fix)
- Rationale: User can promote all headings in web editor

```python
def validate_heading_sequence(doc):
    """
    Validate heading structure.
    
    Returns: (is_valid, errors, warnings)
    """
    errors = []
    warnings = []
    headings = []
    
    # Extract all headings with positions
    # ONLY recognize Heading 1/2/3 (all other styles treated as Normal)
    for i, para in enumerate(doc.paragraphs):
        style_name = para.style.name if para.style else None
        if style_name in ['Heading 1', 'Heading 2', 'Heading 3']:
            level = int(style_name.split()[-1])
            headings.append({
                'index': i,
                'level': level,
                'text': para.text[:50]
            })
    
    # RULE 1: At least one heading REQUIRED
    if len(headings) == 0:
        errors.append({
            'code': 'E005',
            'level': 'ERROR',
            'message': 'No headings detected',
            'detail': 'Document contains only Normal style paragraphs',
            'suggestion': (
                'Islamic scholarly texts require structure. '
                'Apply Heading 1/2/3 styles in Microsoft Word:\n'
                '1. Select chapter titles → Apply "Heading 1"\n'
                '2. Select section titles → Apply "Heading 2"\n'
                '3. Select subsections → Apply "Heading 3"\n\n'
                'Even short texts should have at least a title (Heading 1).\n\n'
                'Why required:\n'
                '- Cannot create navigation without headings\n'
                '- In canonical format, all text looks identical\n'
                '- Easier to identify structure in Word (bold, size, color)'
            )
        })
        return (False, errors, warnings)
    
    # RULE 2: Cannot skip levels
    prev_level = headings[0]['level']
    for h in headings[1:]:
        if h['level'] > prev_level + 1:
            warnings.append({
                'code': 'W009',
                'level': 'WARNING',
                'message': 'Heading level skip detected',
                'detail': f"Heading {prev_level} followed by Heading {h['level']} at paragraph {h['index']}: '{h['text']}'",
                'suggestion': f"Insert Heading {prev_level + 1} or change to Heading {prev_level + 1}"
            })
        prev_level = h['level']
    
    # RULE 3: First heading should be H1
    if headings[0]['level'] != 1:
        warnings.append({
            'code': 'W010',
            'level': 'WARNING',
            'message': 'First heading is not H1',
            'detail': f"Document starts with Heading {headings[0]['level']} at paragraph {headings[0]['index']}",
            'suggestion': 'Review in web editor: promote all headings or confirm intentional'
        })
    
    is_valid = len(errors) == 0
    return (is_valid, errors, warnings)
```

---

### 3.4 Table Style Validation

**Rule:** Tables with style "Poem" or "DataTable" are processed. Tables without style are **preserved as generic tables** for user classification in web editor.

```python
def validate_table_styles(doc):
    """
    Validate table styles.
    
    Tables without style are preserved with style=unknown.
    User can classify them in web editor (poetry/data/paragraphs).
    
    Returns: (errors, warnings)
    """
    errors = []
    warnings = []
    
    for i, table in enumerate(doc.tables):
        style_name = table.style.name if table.style else None
        
        if not style_name or style_name not in ['Poem', 'DataTable']:
            warnings.append({
                'code': 'W012',
                'level': 'WARNING',
                'message': f'Table {i+1} has no Poem or DataTable style',
                'detail': f"Table has style: '{style_name or '(none)'}'",
                'suggestion': (
                    'Table will be preserved as generic table (style=unknown). '
                    'Review in web editor to convert to Poetry, Data Table, or Paragraphs.'
                )
            })
    
    # No FATAL errors for tables
    return errors, warnings
```

---

## 4. PARSING RULES

### 4.1 Metadata Extraction

**Source:** Frontmatter paragraphs (content before first Heading 1/2/3)

**Algorithm: Deterministic by Line Position**

```python
def extract_metadata_from_frontmatter(frontmatter_paragraphs):
    """
    Deterministic metadata extraction from frontmatter.
    
    Expected structure (after skipping empty lines):
    Line 0: Title (required)
    Line 1+: Subtitle (until "تأليف" keyword)
    After "تأليف": Author name
    Line with "المتوفى" or "المتوفي": Extract death_hijri
    Lines AFTER author with "دار" or "مكتبة": publisher
    Lines AFTER author with "YYYY م": edition_year
    Lines AFTER author with "حقوق": rights
    """
    
    metadata = {
        'title': None,
        'subtitle': None,
        'author': None,
        'author_full': None,
        'author_death_hijri': None,
        'edition': None,
        'edition_year': None,
        'publisher': None,
        'rights': None,
        'language': 'ar'  # Default Arabic
    }
    
    if not frontmatter_paragraphs:
        return metadata
    
    # STEP 1: Filter out empty paragraphs
    non_empty_paras = [p for p in frontmatter_paragraphs if p.text.strip()]
    
    if not non_empty_paras:
        return metadata
    
    idx = 0
    
    # STEP 2: Line 0 = Title (REQUIRED)
    if idx < len(non_empty_paras):
        metadata['title'] = non_empty_paras[idx].text.strip()
        idx += 1
    
    # STEP 3: Lines until "تأليف" = Subtitle
    subtitle_lines = []
    while idx < len(non_empty_paras):
        text = non_empty_paras[idx].text.strip()
        if 'تأليف' in text:
            idx += 1  # Skip "تأليف" line
            break
        subtitle_lines.append(text)
        idx += 1
    
    if subtitle_lines:
        metadata['subtitle'] = ' '.join(subtitle_lines)
    
    # STEP 4: Author lines (until death year or publisher marker)
    author_lines = []
    author_end_idx = idx  # Track where author section ends
    
    while idx < len(non_empty_paras):
        text = non_empty_paras[idx].text.strip()
        
        # Check for death year marker (any line with المتوفى/المتوفي)
        if 'المتوفى' in text or 'المتوفي' in text:
            # Extract year: any number before هـ
            match = re.search(r'(\d+)\s*هـ', text)
            if match:
                metadata['author_death_hijri'] = int(match.group(1))
            idx += 1
            author_end_idx = idx
            break
        
        # Check for publisher marker (stop collecting author)
        if 'دار' in text or 'مكتبة' in text:
            author_end_idx = idx
            break
        
        author_lines.append(text)
        idx += 1
        author_end_idx = idx
    
    if author_lines:
        # Full name with titles from frontmatter
        metadata['author_full'] = ' '.join(author_lines)
        # Short author name must be filled manually
        # (no heuristic extraction)
        metadata['author'] = None
    
    # STEP 5: Publisher and edition info (ONLY in lines AFTER author)
    publication_lines = non_empty_paras[author_end_idx:]
    
    for para in publication_lines:
        text = para.text.strip()
        
        # Publisher (contains دار or مكتبة)
        if ('دار' in text or 'مكتبة' in text) and not metadata.get('publisher'):
            # Extract publisher name (before dash or comma)
            parts = re.split(r'[\-\،]', text)
            metadata['publisher'] = parts[0].strip()
            metadata['edition'] = parts[0].strip()  # Same as publisher for now
        
        # Edition year (4-digit year + م)
        year_match = re.search(r'(\d{4})\s*م', text)
        if year_match and not metadata.get('edition_year'):
            metadata['edition_year'] = int(year_match.group(1))
        
        # Rights (line starts with حقوق)
        if text.startswith('حقوق'):
            if 'محفوظة' in text:
                metadata['rights'] = 'copyrighted'
            elif 'مجانية' in text or 'عامة' in text:
                metadata['rights'] = 'public_domain'
            else:
                metadata['rights'] = 'unknown'
    
    return metadata
```

**Required Fields (must be present or filled manually):**
- `id` - Generated from title or filled manually
- `title` - Extracted from line 0
- `author` - Extracted or filled manually
- `edition` - Extracted or filled manually
- `edition_year` - Extracted or filled manually
- `publisher` - Extracted or filled manually
- `language` - Default 'ar' or filled manually
- `rights` - Extracted or filled manually

---

### 4.2 Frontmatter Detection

**Algorithm:**

```python
def detect_frontmatter(doc):
    """
    Frontmatter = everything before first Heading 1/2/3.
    
    Simple rule: First heading = body starts.
    All other styles (Title, Subtitle, etc.) are treated as Normal.
    
    Returns: (frontmatter_paragraphs, body_paragraphs)
    """
    first_heading_index = None
    
    for i, para in enumerate(doc.paragraphs):
        style_name = para.style.name if para.style else None
        
        # ONLY recognize Heading 1/2/3
        if style_name in ['Heading 1', 'Heading 2', 'Heading 3']:
            first_heading_index = i
            break
    
    # No headings found → caught by validation (E005)
    if first_heading_index is None:
        # This should never happen (validation runs first)
        return None, doc.paragraphs
    
    # First element is heading → no frontmatter
    if first_heading_index == 0:
        return None, doc.paragraphs
    
    # Split at first heading
    frontmatter_paras = doc.paragraphs[:first_heading_index]
    body_paras = doc.paragraphs[first_heading_index:]
    
    return frontmatter_paras, body_paras
```

**Notes:**
- All paragraph styles in frontmatter are treated as Normal
- Parser extracts text content regardless of style name (Title, Subtitle, etc. ignored)
- No special handling for built-in styles
- This keeps logic simple and unambiguous

**Output:**
```
:::frontmatter
المجموع شرح المهذب
للإمام النووي
دار الفكر - بيروت
:::
```

---

### 4.3 Heading Parsing

**Mapping:**

```python
HEADING_MAP = {
    'Heading 1': '#',
    'Heading 2': '##',
    'Heading 3': '###'
}

def parse_heading(paragraph):
    """
    Convert Word heading to canonical format.
    """
    style_name = paragraph.style.name if paragraph.style else None
    
    if style_name not in HEADING_MAP:
        return None  # Not a heading
    
    marker = HEADING_MAP[style_name]
    text = paragraph.text.strip()
    
    return f"{marker} {text}"
```

**Output Rules:**
- Blank line before heading (except first heading in file)
- Blank line after heading
- Heading text preserved as-is (no normalization)

**Example:**
```
# كتاب الطهارة

## فصل الماء

### فرع في النية
```

---

### 4.4 Paragraph Parsing

**Algorithm:**

```python
def parse_paragraph(paragraph):
    """
    Extract paragraph text.
    
    Rules:
    - Preserve paragraph breaks
    - Newlines within paragraph → spaces
    - Trim leading/trailing whitespace
    - Preserve Arabic diacritics
    """
    text = paragraph.text
    
    # Replace internal newlines with space
    text = ' '.join(text.split())
    
    # Trim whitespace
    text = text.strip()
    
    return text if text else None
```

**Output:**
```
اعلم أن العبد لا ينجو إلا برحمة الله، وأن الأصل في العبادات التوقيف.

فدل مجموع ذلك على أن العبادة مبناها على الاتباع.
```

---

### 4.5 Qur'an Reference Parsing ({Q})

**Source:** QCF glyph fonts with markers F8E0 (start) and F8E1 (end)

**Algorithm:**

```python
def parse_quran_references(doc, mushaf_decoder):
    """
    Extract Qur'an references from QCF glyph fonts.
    
    CRITICAL: Font must be detected for EACH run, not once per paragraph.
    Different ayahs in same paragraph may use different fonts.
    
    Process:
    1. Detect QCF font runs
    2. Find F8E0 (begin) marker
    3. Decode glyphs between markers using current font code
    4. Find F8E1 (end) marker
    5. Generate coordinate range
    
    Universal Markers (same across all 47 fonts):
    - F8E0: Begin ayah
    - F8E1: End ayah
    
    Font-Specific Glyphs:
    - Each of 47 fonts covers different surahs
    - Decoder key: {font_code}:{glyph_hex}
    - Returns: [surah, ayah, word, part, preview]
    """
    
    QCF_BEGIN = '\uF8E0'  # Begin ayah marker
    QCF_END = '\uF8E1'    # End ayah marker
    
    quran_refs = []
    
    for para in doc.paragraphs:
        current_ayah = None
        current_font_code = None
        
        for run in para.runs:
            # ALWAYS check font for EACH run
            fontname = run.font.name
            if not is_qcf_font(fontname):
                continue
            
            # Extract font code for THIS run (01-47)
            match = re.search(r'QCF4_Hafs_(\d{2})', fontname)
            if not match:
                continue
            
            font_code = match.group(1)  # May differ from previous run!
            
            for char in run.text:
                hex_code = format(ord(char), '04X')
                
                # Begin ayah marker (universal)
                if hex_code == 'F8E0':
                    current_ayah = []
                    current_font_code = font_code
                    continue
                
                # End ayah marker (universal)
                if hex_code == 'F8E1':
                    if current_ayah:
                        # Generate reference
                        ref = generate_quran_reference(current_ayah)
                        quran_refs.append({
                            'paragraph': para,
                            'reference': ref
                        })
                    current_ayah = None
                    current_font_code = None
                    continue
                
                # Inside ayah - decode glyph (font-specific)
                if current_ayah is not None:
                    decoder_key = f"{font_code}:{hex_code}"
                    if decoder_key in mushaf_decoder:
                        surah, ayah, word, part, preview = mushaf_decoder[decoder_key]
                        current_ayah.append({
                            'surah': surah,
                            'ayah': ayah,
                            'word': word,
                            'part': part,
                            'preview': preview
                        })
    
    return quran_refs

def generate_quran_reference(ayah_data):
    """
    Generate reference from decoded glyph data.
    
    Format: {Q surah:ayah:word[:part]-surah:ayah:word[:part]}
    
    Part is OPTIONAL - only included if exists:
    - With part: {Q 2:21:1:1-2:21:4:2}
    - Without part: {Q 2:21:1-2:21:4}
    """
    if not ayah_data:
        return None
    
    first = ayah_data[0]
    last = ayah_data[-1]
    
    # Format start coordinate
    start = f"{first['surah']}:{first['ayah']}:{first['word']}"
    if first.get('part'):  # Only add if part exists
        start += f":{first['part']}"
    
    # Format end coordinate
    end = f"{last['surah']}:{last['ayah']}:{last['word']}"
    if last.get('part'):  # Only add if part exists
        end += f":{last['part']}"
    
    return f"{{Q {start}-{end}}}"
```

**Output:**
```
قال تعالى:
{Q 2:21:1-2:21:4}

والدليل {Q 112:1:1-112:2:4} واضح.
```

---

### 4.6 Qur'an Text Parsing ({Qt})

**Source:** Unicode Qur'an fonts with markers FD5F (start) and FD5E (end)

**Algorithm:**

```python
def parse_quran_unicode_text(doc):
    """
    Extract Unicode Qur'an text from KFGQPC fonts.
    
    Markers (RTL display):
    - Start: U+FD5F ﵟ
    - End: U+FD5E ﵞ
    """
    
    UNICODE_BEGIN = '\uFD5F'  # ﵟ
    UNICODE_END = '\uFD5E'    # ﵞ
    
    quran_texts = []
    
    for para in doc.paragraphs:
        current_text = None
        
        for run in para.runs:
            fontname = run.font.name
            
            # Check if Unicode Qur'an font
            if not is_unicode_quran_font(fontname):
                continue
            
            for char in run.text:
                # Begin marker
                if char == UNICODE_BEGIN:
                    current_text = []
                    continue
                
                # End marker
                if char == UNICODE_END:
                    if current_text:
                        text = ''.join(current_text).strip()
                        quran_texts.append({
                            'paragraph': para,
                            'text': text
                        })
                    current_text = None
                    continue
                
                # Inside Qur'an text
                if current_text is not None:
                    current_text.append(char)
    
    return quran_texts
```

**Output:**
```
قال تعالى:
{Qt يَا أَيُّهَا النَّاسُ اعْبُدُوا رَبَّكُمْ}

والدليل {Qt قُلْ هُوَ اللَّهُ أَحَدٌ} واضح.
```

---

### 4.7 Poetry Parsing

**Source:** Tables with style "Poem"

**Algorithm:**

```python
def parse_poetry_table(table):
    """
    Parse poetry table to canonical format.
    
    Rules:
    - Each row = one line of poetry
    - Skip columns with only separator symbols (*, -, |)
    - Skip empty columns
    - Join text columns with ' :: '
    - Prefix each line with '> '
    """
    
    SEPARATOR_PATTERN = re.compile(r'^[\*\-\|]+$')
    
    lines = []
    
    for row in table.rows:
        text_cells = []
        
        for cell in row.cells:
            text = cell.text.strip()
            
            # Skip empty cells
            if not text:
                continue
            
            # Skip separator-only cells
            if SEPARATOR_PATTERN.match(text):
                continue
            
            text_cells.append(text)
        
        # Generate line
        if text_cells:
            if len(text_cells) == 1:
                lines.append(f"> {text_cells[0]}")
            else:
                joined = ' :: '.join(text_cells)
                lines.append(f"> {joined}")
    
    return '\n'.join(lines)
```

**Examples:**

```
DOCX Table (3 columns):
┌────────────┬───┬──────────────┐
│ العلم نور  │ * │ والجهل ظلام  │
└────────────┴───┴──────────────┘

Output:
> العلم نور :: والجهل ظلام


DOCX Table (1 column):
┌──────────────────────────────┐
│ بيت كامل في satu kolom       │
└──────────────────────────────┘

Output:
> بيت كامل في satu kolom


DOCX Table (5 columns with separators):
┌────────┬───┬────────┬───┬────────┐
│ صدر    │ * │ وسط    │ * │ عجز    │
└────────┴───┴────────┴───┴────────┘

Output:
> صدر :: وسط :: عجز
```

---

### 4.8 Scientific Table Parsing

**Source:** Tables with style "DataTable"

**Algorithm:**

```python
def parse_data_table(table):
    """
    Parse scientific table to Markdown-style table.
    
    Output format:
    ::table
    | col1 | col2 | col3 |
    | val1 | val2 | val3 |
    ::
    """
    
    lines = ['::table']
    
    for row in table.rows:
        cells = []
        for cell in row.cells:
            # Clean cell text
            text = cell.text.strip()
            # Replace newlines with space
            text = ' '.join(text.split())
            cells.append(text)
        
        # Format row
        row_text = '| ' + ' | '.join(cells) + ' |'
        lines.append(row_text)
    
    lines.append('::')
    
    return '\n'.join(lines)
```

**Output:**
```
::table
| اليوم | الارتفاع | الميل |
| الأحد | 12 | 5 |
| الاثنين | 13 | 6 |
| الثلاثاء | 14 | 6.5 |
::
```

---

### 4.8 Table Parsing (Without Style)

**For tables without "Poem" or "DataTable" style:**

**Strategy: PRESERVE STRUCTURE**

Tables without recognized style are preserved as generic tables with `style=unknown`.
Structure is maintained for later classification in web editor.

**Algorithm:**

```python
def parse_table_without_style(table, table_index):
    """
    Preserve table structure for later classification.
    
    Output: Generic table that can be converted in web editor to:
    - Poetry (one-click conversion)
    - Data table (one-click attribute change)
    - Paragraphs (one-click extraction)
    """
    
    lines = [f'::table id=table_{table_index:03d} style=unknown']
    
    for row in table.rows:
        cells = []
        for cell in row.cells:
            # Clean cell text
            text = cell.text.strip()
            # Replace newlines with space
            text = ' '.join(text.split())
            cells.append(text)
        
        # Format row
        row_text = '| ' + ' | '.join(cells) + ' |'
        lines.append(row_text)
    
    lines.append('::')
    
    return '\n'.join(lines)
```

**Output:**
```
::table id=table_001 style=unknown
| Cell 1A | Cell 1B |
| Cell 2A | Cell 2B |
::
```

**Web Editor Actions:**

User can convert table to appropriate format:

1. **Convert to Poetry** (one-click):
   ```
   > Cell 1A :: Cell 1B
   > Cell 2A :: Cell 2B
   ```
   ⚠️ Irreversible - table structure lost

2. **Mark as Data Table** (one-click):
   ```
   ::table id=table_001 style=data
   | Cell 1A | Cell 1B |
   | Cell 2A | Cell 2B |
   ::
   ```
   ✓ Reversible - only changes style attribute

3. **Extract as Paragraphs** (one-click):
   ```
   Cell 1A Cell 1B
   
   Cell 2A Cell 2B
   ```
   ⚠️ Irreversible - table structure lost

4. **No Action** (leave as generic table):
   - Renders as plain HTML table
   - Valid output format
   - No conversion needed if generic table is appropriate

**Classification Level:**
- INFO (not WARNING or ERROR)
- Document accepted, no blocking issue
- Optional user review in web editor
- Generic table is a valid format (e.g., for table of contents)

**Why Preserve Structure:**
- Maintains row/column organization (structure, not layout)
- Enables easy conversion in web editor (simpler than Word)
- Avoids data loss from premature extraction to paragraphs
- One-way conversions are acceptable (structure → text, but not text → structure)


---

### 4.10 Figure Parsing

**Detection:** Images in document (any InlineShape or Picture)

**Algorithm:**

```python
def parse_figures(doc, book_id):
    """
    Extract figures from document.
    
    Process:
    1. Find all images
    2. Generate figure ID (sequential)
    3. Extract image file
    4. Extract caption (if present)
    5. Generate canonical markup
    """
    
    figures = []
    figure_counter = 1
    
    for para in doc.paragraphs:
        # Check if paragraph contains image
        for run in para.runs:
            # Check for inline shapes (images)
            if hasattr(run._element, 'inline'):
                for inline in run._element.inline:
                    # Extract image
                    image_data = extract_image_from_inline(inline)
                    
                    if image_data:
                        # Generate figure ID
                        figure_id = f"figure_{figure_counter:03d}"
                        
                        # Generate filename
                        ext = get_image_extension(image_data['content_type'])
                        filename = f"{book_id}_{figure_id}.{ext}"
                        filepath = f"figures/{filename}"
                        
                        # Extract caption (next paragraph or alt text)
                        caption = extract_figure_caption(doc, para)
                        
                        figures.append({
                            'id': figure_id,
                            'filename': filename,
                            'filepath': filepath,
                            'image_data': image_data['bytes'],
                            'caption': caption,
                            'paragraph': para
                        })
                        
                        figure_counter += 1
    
    return figures

def extract_figure_caption(doc, image_para):
    """
    Extract caption for figure.
    
    Heuristic: Next paragraph after image (if short)
    Or: Alt text from image properties
    """
    # Try to find next paragraph
    para_index = doc.paragraphs.index(image_para)
    if para_index + 1 < len(doc.paragraphs):
        next_para = doc.paragraphs[para_index + 1]
        text = next_para.text.strip()
        
        # If short text (< 200 chars) → likely caption
        if text and len(text) < 200:
            # Check for caption markers
            if any(marker in text for marker in ['شكل', 'رسم', 'صورة', 'Figure']):
                return text
    
    return None

def generate_figure_markup(figure):
    """
    Generate canonical figure markup.
    """
    markup = f"::figure id={figure['id']} src={figure['filepath']}"
    
    if figure.get('caption'):
        markup += f"\nalt: {figure['caption']}"
    
    markup += "\n::"
    
    return markup
```

**Output:**
```
::figure id=figure_001 src=figures/majmu_nawawi_figure_001.png
alt: شكل آلة الأسطرلاب
::
```

**File Extraction:**
- Save images to: `/media/figures/{book_id}_{figure_id}.{ext}`
- Supported formats: PNG, JPG, GIF
- Maximum size: 10 MB per image

---

### 4.11 Footnote Parsing

**Source:** Word footnotes (accessed via `python-docx` footnote API)

**Algorithm:**

```python
def parse_footnotes(doc):
    """
    Extract footnotes from document.
    
    Format:
    - References: [^n] inline in text
    - Definitions: [^n]: text (after paragraph)
    """
    
    footnotes = {}
    
    # Extract all footnotes
    for para in doc.paragraphs:
        # Scan for footnote references in runs
        for run in para.runs:
            # Check if run contains footnote reference
            if hasattr(run._element, 'footnoteReference'):
                footnote_id = run._element.footnoteReference.get('id')
                
                # Get footnote content
                footnote_text = get_footnote_text(doc, footnote_id)
                
                if footnote_text:
                    footnotes[footnote_id] = {
                        'paragraph': para,
                        'number': footnote_id,
                        'text': footnote_text
                    }
    
    return footnotes

def get_footnote_text(doc, footnote_id):
    """
    Extract footnote text from Word document.
    """
    # Access footnotes part
    footnotes_part = doc.part.footnotes_part
    if not footnotes_part:
        return None
    
    # Find footnote by ID
    for footnote_elem in footnotes_part.element.findall('.//w:footnote', namespaces):
        if footnote_elem.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}id') == footnote_id:
            # Extract text from footnote paragraphs
            texts = []
            for para_elem in footnote_elem.findall('.//w:p', namespaces):
                para_text = get_text_from_element(para_elem)
                if para_text:
                    texts.append(para_text)
            return '\n'.join(texts)
    
    return None
```

**Output Format:**

```
Inline reference:
وقال الشافعي: من تعلم القرآن عظمت قيمته[^1][^2].

After paragraph:
[^1]: أي الرحمة الخاصة بالمؤمنين
[^2]: شرح الثانية
```

**Validation:**
- Every `[^n]` reference must have `[^n]:` definition
- Definitions placed immediately after paragraph containing references
- Preserve footnote numbering from source document

---

### 4.11 Page Marker Parsing

**Source:** Page numbers in document headers/footers

**Note on Volume Markers:**
Volume markers `{V n}` are NOT auto-detected in MVP.
Users can add volume markers manually in web editor (Phase 2 feature).

**Algorithm:**

```python
def extract_page_markers(doc):
    """
    Extract page numbers from headers/footers.
    
    Strategy:
    1. Check each section's header/footer
    2. Look for numeric page numbers
    3. Map to document paragraphs
    """
    
    page_markers = []
    
    for section_idx, section in enumerate(doc.sections):
        # Check header
        if section.header:
            page_num = extract_page_number(section.header)
            if page_num:
                page_markers.append({
                    'section_index': section_idx,
                    'page': page_num,
                    'source': 'header'
                })
        
        # Check footer
        if section.footer:
            page_num = extract_page_number(section.footer)
            if page_num:
                # Prefer footer over header
                page_markers.append({
                    'section_index': section_idx,
                    'page': page_num,
                    'source': 'footer'
                })
    
    return page_markers

def extract_page_number(header_or_footer):
    """
    Extract numeric page number from header/footer text.
    """
    text = ''
    for para in header_or_footer.paragraphs:
        text += para.text + ' '
    
    # Look for standalone digits
    match = re.search(r'\b(\d+)\b', text)
    if match:
        return int(match.group(1))
    
    return None

def map_page_markers_to_paragraphs(doc, page_markers):
    """
    Map page markers to paragraph positions.
    
    Heuristic: Section breaks ≈ page breaks
    """
    marked_paragraphs = []
    
    # Map sections to paragraphs
    section_starts = get_section_start_paragraphs(doc)
    
    for marker in page_markers:
        section_idx = marker['section_index']
        if section_idx < len(section_starts):
            para_idx = section_starts[section_idx]
            marked_paragraphs.append({
                'paragraph_index': para_idx,
                'page_number': marker['page']
            })
    
    return marked_paragraphs
```

**Output Placement:**

```
Block-level (if page break at paragraph boundary):

{P 43}

اعلم أن العبد...


Inline (if page break mid-paragraph):

اعلم أن العبد لا ينجو إلا برحمة الله، {P 44} وأن الأصل...
```

**Fallback:** If no page numbers in headers/footers → No `{P}` markers generated (valid)

---

## 5. ERROR HANDLING

### 5.1 Error Classification

**FATAL** - Stop immediately, reject document
**ERROR** - Reject document, user must fix
**WARNING** - Accept document, flag for review
**INFO** - Log only, proceed normally

---

### 5.2 Error Catalog

#### **FATAL ERRORS**

| Code | Condition | Message | Action |
|------|-----------|---------|--------|
| F001 | File not found | "FATAL: File does not exist at path {path}" | Stop |
| F002 | Wrong extension | "FATAL: File must be .docx format" | Stop |
| F003 | File too large | "FATAL: File exceeds 100 MB limit" | Stop |
| F004 | Corrupted file | "FATAL: File is corrupted or not a valid DOCX" | Stop |
| F005 | Empty document | "FATAL: Document contains no content" | Stop |

#### **ERROR (Reject)**

| Code | Condition | Message | Action |
|------|-----------|---------|--------|
| E001 | Footnote orphan | "ERROR: Footnote reference [^{n}] has no definition" | Reject |
| E005 | No headings | "ERROR: No headings detected. Document must have at least one Heading 1/2/3 style. Apply heading styles in Word and re-upload." | Reject |

#### **WARNING (Accept, flag for review in web editor)**

| Code | Condition | Message | Action |
|------|-----------|---------|--------|
| W009 | Heading level skip | "WARNING: Heading level skip detected. H{prev} → H{curr} at paragraph {idx}. Review in web editor." | Flag for review |
| W010 | First heading not H1 | "WARNING: Document starts with Heading {level}. Review in web editor to promote headings." | Flag for review |
| W003 | Unicode Qur'an no brackets | "WARNING: KFGQPC font detected but no FD5F/FD5E markers" | Flag for review |
| W004 | Non-sequential footnotes | "WARNING: Footnotes not sequential: {sequence}" | Flag for review |
| W005 | Empty frontmatter | "WARNING: Frontmatter section is empty" | Flag for review |
| W012 | Table no style | "WARNING: Table {n} has no Poem or DataTable style. Preserved as generic table (style=unknown). Review in web editor to convert if needed." | Flag for review |

#### **INFO (Log only, no review needed)**

| Code | Condition | Message |
|------|-----------|---------|
| I001 | Parsing started | "INFO: Started parsing {filename}" |
| I002 | Element counts | "INFO: Found {n} headings, {m} paragraphs, {k} figures" |
| I003 | Processing time | "INFO: Parsing completed in {seconds}s" |
| I005 | No page numbers | "INFO: No page numbers detected in headers/footers. {P} markers will not be generated." |
| I006 | Large document | "INFO: Document exceeds 1000 pages" |
| I007 | Many images | "INFO: Document contains {count} images (>100)" |

---

### 5.3 Error Reporting Format

**JSON Error Report:**

```json
{
  "success": false,
  "status": "ERROR",
  "errors": [
    {
      "code": "E001",
      "level": "ERROR",
      "message": "Heading level skip detected",
      "detail": "Heading 1 followed by Heading 3 at paragraph 45",
      "location": {
        "paragraph": 45,
        "text": "فرع في النية"
      },
      "suggestion": "Insert Heading 2 before this, or change to Heading 2"
    }
  ],
  "warnings": [
    {
      "code": "W001",
      "level": "WARNING",
      "message": "No page numbers found in document",
      "suggestion": "Add page numbers to headers/footers or ignore if not needed"
    }
  ],
  "info": {
    "file": "majmu_nawawi.docx",
    "size": "2.4 MB",
    "pages": 450,
    "processing_time": "3.2s"
  }
}
```

---

## 6. OUTPUT GENERATION

### 6.1 Canonical File Structure

```
---
id: majmu_nawawi_darfikr_1997
work_id: majmu_nawawi
title: المجموع شرح المهذب
language: ar
author: النووي
author_full: يحيى بن شرف النووي
author_death_hijri: 676
edition: دار الفكر
edition_year: 1997
editor: محمد نجيب المطيعي
publisher: Dar al-Fikr
rights: public_domain
---

:::frontmatter
المجموع شرح المهذب
للإمام النووي
دار الفكر - بيروت
الطبعة الأولى ١٩٩٧ م
:::

{P 1}

# كتاب الطهارة

## فصل الماء

اعلم أن...

[Rest of content]
```

---

### 6.2 Output File Rules

**Encoding:** UTF-8 (no BOM)
**Line Endings:** LF (Unix style)
**Indentation:** None (flat structure)
**File Extension:** `.txt`

**Spacing Rules:**
- Blank line before heading (except first)
- Blank line after heading
- Blank line between paragraphs
- Blank line before/after `::table`, `::figure`, `:::frontmatter`
- File ends with single newline

**Whitespace:**
- Trim trailing spaces on each line
- Normalize multiple spaces to single space
- Preserve spaces in poetry (between `::`)

---

### 6.3 Canonical Writer Implementation

```python
class CanonicalWriter:
    """
    Writes canonical text output.
    """
    
    def __init__(self, output_path):
        self.output_path = output_path
        self.lines = []
        self.last_was_blank = False
    
    def write_metadata(self, metadata):
        """Write YAML metadata block"""
        self.lines.append('---')
        for key, value in metadata.items():
            if value is not None:
                if isinstance(value, str):
                    self.lines.append(f'{key}: {value}')
                else:
                    self.lines.append(f'{key}: {value}')
        self.lines.append('---')
        self.add_blank_line()
    
    def write_frontmatter(self, paragraphs):
        """Write frontmatter block"""
        self.lines.append(':::frontmatter')
        for para in paragraphs:
            self.lines.append(para.text.strip())
        self.lines.append(':::')
        self.add_blank_line()
    
    def write_heading(self, level, text):
        """Write heading"""
        self.ensure_blank_line()
        marker = '#' * level
        self.lines.append(f'{marker} {text}')
        self.add_blank_line()
    
    def write_paragraph(self, text):
        """Write paragraph"""
        self.ensure_blank_line()
        self.lines.append(text)
        self.add_blank_line()
    
    def write_quran_ref(self, reference):
        """Write Qur'an reference"""
        self.lines.append(reference)
    
    def write_poetry(self, poetry_lines):
        """Write poetry block"""
        self.ensure_blank_line()
        for line in poetry_lines:
            self.lines.append(line)
        self.add_blank_line()
    
    def write_table(self, table_lines):
        """Write table block"""
        self.ensure_blank_line()
        self.lines.extend(table_lines)
        self.add_blank_line()
    
    def write_figure(self, markup):
        """Write figure block"""
        self.ensure_blank_line()
        self.lines.append(markup)
        self.add_blank_line()
    
    def write_footnote_definition(self, number, text):
        """Write footnote definition"""
        self.lines.append(f'[^{number}]: {text}')
    
    def write_page_marker(self, page_num):
        """Write page marker"""
        self.ensure_blank_line()
        self.lines.append(f'{{P {page_num}}}')
        self.add_blank_line()
    
    def add_blank_line(self):
        """Add blank line"""
        if not self.last_was_blank:
            self.lines.append('')
            self.last_was_blank = True
    
    def ensure_blank_line(self):
        """Ensure previous line was blank"""
        if self.lines and self.lines[-1] != '':
            self.add_blank_line()
    
    def save(self):
        """Save to file"""
        content = '\n'.join(self.lines)
        # Ensure file ends with single newline
        if not content.endswith('\n'):
            content += '\n'
        
        with open(self.output_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(content)
```

---

## 7. VALIDATION & TESTING

### 7.1 Unit Tests

**Test each parser module independently:**

```python
def test_heading_parser():
    # Test H1, H2, H3 conversion
    # Test blank line spacing
    # Test level skip detection

def test_quran_reference_parser():
    # Test QCF font detection
    # Test glyph decoding
    # Test coordinate generation
    # Test marker boundaries

def test_poetry_parser():
    # Test 1-column, 2-column, 3+ column
    # Test separator skip
    # Test empty cell skip

def test_metadata_extraction():
    # Test deterministic line parsing
    # Test author extraction
    # Test publisher detection
    # Test year extraction
```

---

### 7.2 Integration Tests

**Test complete DOCX → Canonical pipeline:**

```python
def test_simple_document():
    """
    Test minimal valid document:
    - Metadata in frontmatter
    - One H1
    - Few paragraphs
    """
    
def test_complex_document():
    """
    Test all features:
    - Frontmatter
    - H1/H2/H3 hierarchy
    - Paragraphs
    - Qur'an references
    - Poetry
    - Tables
    - Figures
    - Footnotes
    - Page markers
    """

def test_error_cases():
    """
    Test error handling:
    - Heading level skip
    - Missing footnote definition
    - Corrupted file
    """
```

---

### 7.3 Validation Fixtures

**Test Data:**

```
tests/
├── fixtures/
│   ├── valid/
│   │   ├── minimal.docx          # Simplest valid document
│   │   ├── full_features.docx    # All elements present
│   │   ├── arabic_only.docx      # Pure Arabic text
│   │   └── multi_volume.docx     # Volume markers
│   │
│   ├── invalid/
│   │   ├── heading_skip.docx     # H1 → H3 error
│   │   ├── orphan_footnote.docx  # Missing definition
│   │   ├── no_styles.docx        # No formatting
│   │   └── corrupted.docx        # Broken file
│   │
│   └── expected/
│       ├── minimal.txt           # Expected output
│       ├── full_features.txt
│       └── ...
```

---

## 8. IMPLEMENTATION NOTES

### 8.1 Recommended Libraries

**Python:**
```python
# Core DOCX parsing
python-docx==0.8.11

# XML processing (for advanced DOCX features)
lxml==4.9.3

# YAML metadata
PyYAML==6.0

# Validation
jsonschema==4.19.0

# Testing
pytest==7.4.3
```

---

### 8.2 Performance Considerations

**Expected Performance:**

| Document Size | Processing Time |
|---------------|----------------|
| 100 pages | < 5 seconds |
| 500 pages | < 20 seconds |
| 1000 pages | < 45 seconds |

**Optimization Tips:**
- Stream-process large documents (don't load all in memory)
- Cache decoded QCF glyphs
- Parallel image extraction
- Lazy paragraph parsing

---

### 8.3 Error Recovery

**NOT IMPLEMENTED:**

Parser does **NOT** attempt to recover from errors. This is intentional (fail-fast philosophy).

**Rationale:**
- Ambiguous recovery = unpredictable output
- Better to reject and get clean input
- Editor fixes source → Deterministic output

---

### 8.4 Logging Strategy

```python
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('parser.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('maktabah.parser')

# Usage
logger.info("Started parsing document: %s", filename)
logger.warning("W001: No page numbers found")
logger.error("E001: Heading level skip at paragraph %d", idx)
```

---

## APPENDIX A: QUICK REFERENCE

### Element Type → Parser Function

| Element | DOCX Source | Parser Function | Output |
|---------|-------------|----------------|--------|
| Metadata | Frontmatter paras | `extract_metadata()` | YAML block |
| Frontmatter | Pre-H1 content | `detect_frontmatter()` | `:::frontmatter ... :::` |
| Headings | Heading 1/2/3 | `parse_heading()` | `#`, `##`, `###` |
| Paragraphs | Normal style | `parse_paragraph()` | Plain text |
| Qur'an refs | QCF fonts + F8E0/F8E1 | `parse_quran_references()` | `{Q x:y:z-x:y:z}` |
| Qur'an text | KFGQPC + FD5F/FD5E | `parse_quran_unicode_text()` | `{Qt ...}` |
| Poetry | Table style=Poem | `parse_poetry_table()` | `> col :: col` |
| Tables | Table style=DataTable | `parse_data_table()` | `::table ... ::` |
| Figures | InlineShapes | `parse_figures()` | `::figure ... ::` |
| Footnotes | Word footnotes | `parse_footnotes()` | `[^n]`, `[^n]: ...` |
| Pages | Header/footer numbers | `extract_page_markers()` | `{P n}` |

---

## APPENDIX B: CHANGE LOG

**v1.0 (2026-02-17):**
- Initial specification release
- Deterministic parsing philosophy established
- All element types covered (headings, paragraphs, Qur'an, poetry, tables, figures, footnotes, pages)
- Complete error classification system
- Implementation guide with Python examples

**Key Design Decisions:**
1. **Style Handling:**
   - ONLY Heading 1/2/3 recognized as structural elements
   - ALL other styles (Title, Subtitle, Quote, custom styles) treated as Normal
   - Simple rule: First heading = frontmatter boundary
   - No ambiguity, no special cases

2. **Heading Requirements:**
   - At least ONE heading (H1/H2/H3) REQUIRED → E005 if none
   - Cannot skip levels (H1→H3) → W009 warning
   - First heading should be H1 → W010 warning
   - Rationale: Islamic texts always have structure; cannot navigate without headings

3. **QCF Fonts:** 
   - 47 fonts (not 114) from King Fahd Glorious Quran Printing Complex
   - Font detected PER RUN (not per paragraph)
   - Universal markers (F8E0/F8E1) + font-specific glyphs

4. **Unicode Qur'an:** 
   - Exact match only: `KFGQPC_HAFS_Uthmanic_Script_H`

5. **Coordinates:**
   - Include part only if exists (x:x:x or x:x:x:x)

6. **Metadata Extraction:**
   - Skip empty lines in frontmatter
   - Flexible death year pattern (any line with المتوفى)
   - Publisher/rights detection ONLY after author section
   - Frontmatter → author_full (short author filled manually, no heuristics)

7. **Table Without Style:**
   - PRESERVE as `::table style=unknown`
   - Classification: WARNING W012 (flag for review)
   - Web editor provides one-click conversions:
     * Convert to Poetry
     * Mark as Data Table
     * Extract as Paragraphs

8. **Volume Markers:**
   - NOT auto-detected in MVP
   - Manual placement in web editor (Phase 2)

9. **Error Codes:**
   - Removed: E002 (Invalid YAML - parser generates it, can't be invalid)
   - Removed: I004 (No Heading 1 - contradicted E005)
   - Removed: W006/W007 (moved to I006/I007)
   - Added: W012 (Table no style)
   - All warnings flag for review (except I006/I007 which are truly informational)

10. **Maximum Limits:**
    - File size: 100 MB
    - Pages: 2,000
    - Images: 200
    - Footnotes: 5,000

---

## APPENDIX C: REFERENCES

**Standards:**
- Canonical Text Standard v1.1
- UTF-8 Encoding (RFC 3629)
- YAML 1.2 Specification
- Microsoft Office Open XML (ECMA-376)

**Libraries:**
- python-docx documentation
- lxml documentation
- PyYAML documentation

---

*END OF SPECIFICATION*

**For questions or clarifications:**
- Review Canonical Text Standard v1.1
- Check error code definitions (Section 5.2)
- Refer to example implementations (Section 4)
- Consult test fixtures (Section 7.3)
