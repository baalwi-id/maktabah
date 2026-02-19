# Panduan Template Dokumen Arab
## Maktabah Digital Library — `TEMPLATE_ARABIC_BOOK.docx`

**Versi:** 1.1 | **Tanggal:** Februari 2026

---

## Daftar Isi

1. [Persiapan](#1-persiapan)
2. [Struktur Dokumen](#2-struktur-dokumen)
3. [Frontmatter](#3-frontmatter)
4. [Heading Bab dan Fasal](#4-heading-bab-dan-fasal)
5. [Teks Biasa](#5-teks-biasa)
6. [Ayat Qur'an](#6-ayat-quran)
7. [Syair](#7-syair)
8. [Tabel Ilmiah](#8-tabel-ilmiah)
9. [Footnote](#9-footnote)
10. [Gambar dan Diagram](#10-gambar-dan-diagram)
11. [Sebelum Upload](#11-sebelum-upload)
12. [Referensi Cepat](#12-referensi-cepat)

---

## 1. Persiapan

### Font Arab

Template menggunakan **Scheherazade New** sebagai default. Tapi font Arab apapun boleh digunakan — pilihan font di DOCX **tidak mempengaruhi output canonical** sama sekali. Parser membaca struktur, bukan tampilan.

| Font | Keterangan | Cara Mendapatkan |
|------|-----------|-----------------|
| **Scheherazade New** *(default template)* | Open source, gaya kitab klasik | [SIL International](https://software.sil.org/scheherazade/) — gratis |
| **Adwa' Assalaf** *(rekomendasi asatidz)* | Paling mirip kitab kuning cetak | Repo Maktabah: `fonts/adwa-assalaf/` |
| Amiri | Modern, lengkap | [Google Fonts](https://fonts.google.com/specimen/Amiri) |
| Traditional Arabic | Bawaan Windows | Sudah tersedia di Windows |

---

### Font Qur'an

Disediakan oleh **King Fahd Glorious Quran Printing Complex** melalui aplikasi resmi:

**Nama aplikasi:** مصحف المدينة النبوية للنشر الحاسوبي  
**Unduh:** https://nashr.qurancomplex.gov.sa/

Font QCF dan KFGQPC terinstall **otomatis** bersama aplikasi. Tidak perlu install terpisah.

Kalau ingin install manual (tanpa aplikasi):
- Font QCF4_Hafs: repo Maktabah `fonts/qcf/`
- Font KFGQPC: repo Maktabah `fonts/kfgqpc/`

---

## 2. Struktur Dokumen

```
┌─────────────────────────────────────────┐
│  FRONTMATTER  (opsional)                │
│  Halaman judul, penulis, penerbit       │
│  Style: Normal                          │
├─────────────────────────────────────────┤  ← Heading pertama (H1/H2/H3)
│  BODY  (wajib)                          │
│  Isi kitab                              │
│  Style: Heading 1/2/3, Normal,          │
│         Poem table, DataTable           │
└─────────────────────────────────────────┘
```

**Satu aturan mutlak:** Dokumen **wajib** memiliki minimal satu Heading 1, 2, atau 3. Dokumen tanpa heading ditolak oleh parser.

---

## 3. Frontmatter

Frontmatter adalah semua paragraf **sebelum heading pertama**. Parser otomatis mendeteksi batasnya — tidak perlu penanda khusus.

### Urutan yang Disarankan

```
[1]  Judul kitab lengkap
[2]  تأليف                      ← kata kunci untuk deteksi penulis
[3]  Nama penulis lengkap
[4]  المتوفى سنة NNN هـ          ← kata kunci untuk tahun wafat
[5]  (baris kosong — opsional)
[6]  تحقيق: nama muhaqiq         ← opsional
[7]  Nama penerbit               ← idealnya mengandung دار atau مكتبة
[8]  Kota - negara               ← opsional
[9]  YYYY م                      ← tahun terbit Masehi
[10] حقوق ...                    ← status hak cipta
```

### Contoh

```
المجموع شرح المهذب
تأليف
الإمام المحدث يحيى بن شرف النووي
المتوفى سنة 676 هـ

تحقيق: محمد نجيب المطيعي
دار الفكر - بيروت
الطبعة الأولى ١٩٩٧ م
حقوق الطبع محفوظة
```

### Shift+Enter untuk Nama Panjang

Untuk keterbacaan, nama atau judul panjang boleh dibagi baris dengan **Shift+Enter** dalam satu paragraf:

```
الإمام المحدث[Shift+Enter]
يحيى بن شرف[Shift+Enter]
النووي
```
→ Parser membaca sebagai satu field: `الإمام المحدث يحيى بن شرف النووي`

> **Enter** = paragraf baru (field terpisah)  
> **Shift+Enter** = baris baru dalam paragraf yang sama (satu field)

### Style di Frontmatter

Gunakan style **Normal** untuk semua teks. Style Title, Subtitle, atau custom styles diabaikan oleh parser — hanya teks yang diekstrak.

---

## 4. Heading Bab dan Fasal

### Style yang Digunakan

| Style Word | Output Canonical | Penggunaan |
|-----------|-----------------|------------|
| **Heading 1** | `# judul` | Kitab / Bab (كتاب، باب) |
| **Heading 2** | `## judul` | Fasal (فصل) |
| **Heading 3** | `### judul` | Fara' (فرع) |

### Cara Menerapkan

1. Ketik atau pilih teks judul bab
2. Home → Styles → klik **Heading 1** (atau 2, atau 3)

### Aturan

- Minimal satu heading **wajib** ada di dokumen
- Tidak boleh loncat level: H1 langsung ke H3 (tanpa H2) → **peringatan W009**
- Sebaiknya mulai dari H1 → jika mulai dari H2 → **peringatan W010** (tetap diproses)
- Shift+Enter dalam heading boleh digunakan untuk teks panjang

### Contoh Benar ✅

```
# كِتَابُ الطَّهَارَةِ

## فَصْلٌ فِي الْمِيَاهِ

### فَرْعٌ فِي النِّيَّةِ

## فَصْلٌ فِي الأَوَانِي

# كِتَابُ الصَّلَاةِ
```

### Contoh Salah ❌

```
# كِتَابُ الطَّهَارَةِ
### فَرْعٌ   ← loncat dari H1 ke H3, H2 tidak ada
```

---

## 5. Teks Biasa

- Gunakan style **Normal**
- Di DOCX: bebas pakai Enter atau Space After Paragraph untuk memisahkan paragraf — dua-duanya valid
- **Parser** yang akan menghasilkan satu baris kosong antar paragraf di output canonical
- Shift+Enter dalam paragraf = baris baru dalam blok yang sama, bukan paragraf baru

---

## 6. Ayat Qur'an

Sumber: aplikasi **مصحف المدينة النبوية للنشر الحاسوبي** dari King Fahd Complex.

### Langkah Umum

1. Buka aplikasi
2. Atur: **البرنامج → Microsoft Word**
3. Pilih surah, ayat awal, dan ayat akhir
4. Pilih metode copy (Metode 1 atau 2 di bawah)
5. Klik **نسخ الاختيار** atau **نسخ النص المحدد**
6. Paste ke Word — font ikut otomatis

---

### Metode 1 — مخطوط بدوي (QCF Glyph) ← Direkomendasikan

Di aplikasi: pilih **"مخطوط بدوي"** di bagian النص القرآني

Font yang ikut ke Word: `QCF4_Hafs_XX`

Output canonical yang dihasilkan parser:
```
{Q 2:255:1-2:255:7}
{Q 112:1:1-112:4:3}
```

---

### Metode 2 — خط كمبيوتر يونيكود (Unicode)

Di aplikasi: pilih **"خط كمبيوتر يونيكود"** di bagian النص القرآني

Font yang ikut ke Word: `KFGQPC_HAFS_Uthmanic_Script_H`

Output canonical yang dihasilkan parser:
```
{Qt يَا أَيُّهَا الَّذِينَ آمَنُوا إِذَا قُمْتُمْ إِلَى الصَّلَاةِ}
```

---

### Perbandingan

| | مخطوط بدوي | يونيكود |
|-|-----------|---------|
| Font | QCF4_Hafs_XX | KFGQPC_HAFS_Uthmanic_Script_H |
| Output | Koordinat kata: `{Q s:a:w}` | Teks: `{Qt ...}` |
| Tampilan di Word | Glyph khusus mushaf Madinah | Teks Arab berharakat |
| Gunakan untuk | Referensi ilmiah presisi | Kutipan teks ayat |

---

## 7. Syair

Syair menggunakan **tabel Word dengan style "Poem"**.

### Cara Membuat

1. **Insert → Table** — pilih jumlah kolom
2. Klik di dalam tabel
3. Home → Styles → pilih **Poem**
4. Isi setiap sel

### Jumlah Kolom

| Jenis | Kolom | Keterangan |
|-------|-------|-----------|
| Bait penuh | 1 | Seluruh baris dalam satu sel |
| Dua hemistich | 2 | Kanan = صدر, kiri = عجز |
| Tiga bagian | 3 | صدر / وسط / عجز |
| Muwashshah, zajal | 4+ | Bebas sesuai struktur |

### Separator Visual (Boleh!)

Boleh menaruh simbol separator di kolom tengah untuk keterbacaan — akan ikut di output canonical:

```
Tabel: | الْعِلْمُ نُورٌ | ─── | وَالْجَهْلُ ظَلَامٌ |
Output: > الْعِلْمُ نُورٌ :: ─── :: وَالْجَهْلُ ظَلَامٌ
```

### Output Canonical

```
> الْعِلْمُ نُورٌ :: وَالْجَهْلُ ظَلَامٌ
> وَالْقَلْبُ بَيْتٌ :: وَالذِّكْرُ سُكَّانٌ
> مَنْ طَلَبَ الْعِلْمَ لِلَّهِ فَقَدْ أَفْلَحَ
```

---

## 8. Tabel Ilmiah

Untuk konten tabular ilmiah: falak, faraidh, nasab, hisab, dan sejenisnya.

### Cara Membuat

1. **Insert → Table**
2. Klik di dalam tabel
3. Home → Styles → pilih **DataTable**
4. Baris pertama = header kolom (opsional)

### Output Canonical

```
::table style=data
| اليوم | الارتفاع | الميل |
| الأحد | 12 | 5 |
| الاثنين | 13 | 6 |
::
```

### Tabel Tanpa Style

Tabel yang tidak diberi style Poem atau DataTable tetap diproses — disimpan sebagai `::table style=unknown`. Di web editor, tersedia tombol konversi satu klik: ke Syair, ke DataTable, atau ke Paragraf.

---

## 9. Footnote

### Cara Membuat

1. Letakkan kursor setelah kata yang ingin diberi catatan kaki
2. **References → Insert Footnote** (`Ctrl+Alt+F` di Windows)
3. Ketik isi catatan kaki di area bawah halaman

> Gunakan footnote **native Word** saja. Parser tidak mendeteksi footnote yang ditulis manual di body teks.

### Output Canonical

```
وَقَالَ الشَّافِعِيُّ: مَنْ تَعَلَّمَ الْقُرْآنَ عَظُمَتْ قِيمَتُهُ[^1].

[^1]: أي الرحمة الخاصة بالمؤمنين
```

---

## 10. Gambar dan Diagram

Untuk gambar yang merupakan **bagian isi kitab** (diagram ilmiah, bagan, ilustrasi).

### Cara Memasukkan

1. **Insert → Pictures** → pilih file
2. Klik kanan gambar → **Edit Alt Text**
3. Isi deskripsi Arab di kolom alt text

### Output Canonical

```
::figure id=astrolabe_01 src=figures/majmu_nawawi_darfikr_1997_astrolabe_01.png
alt: شَكْلُ آلَةِ الْأُسْطُرْلَابِ
::
```

> Jangan masukkan gambar dekoratif. Format didukung: PNG, JPG, JPEG.

---

## 11. Sebelum Upload

### Checklist

- [ ] Semua kotak instruksi `📝` dihapus
- [ ] Semua `[PLACEHOLDER]` diganti konten nyata
- [ ] Minimal satu Heading 1/2/3 ada
- [ ] Tidak ada heading yang loncat level (H1 → H3)
- [ ] Teks Qur'an pakai font QCF atau KFGQPC
- [ ] Syair pakai tabel ber-style **Poem**
- [ ] Tabel ilmiah pakai style **DataTable**
- [ ] Footnote dibuat via References → Insert Footnote
- [ ] Disimpan sebagai `.docx`

### Batasan File

| | Maksimum |
|-|----------|
| Ukuran file | 100 MB |
| Halaman | 2.000 |
| Gambar | 200 |
| Footnote | 5.000 |

---

## 12. Referensi Cepat

| Elemen | Style / Cara | Output Canonical |
|--------|-------------|-----------------|
| Bab (كتاب/باب) | Heading 1 | `# judul` |
| Fasal (فصل) | Heading 2 | `## judul` |
| Fara' (فرع) | Heading 3 | `### judul` |
| Teks biasa | Normal | Paragraf |
| Qur'an — مخطوط بدوي | Copy dari app → QCF4_Hafs_XX | `{Q s:a:w-s:a:w}` |
| Qur'an — يونيكود | Copy dari app → KFGQPC font | `{Qt teks arab}` |
| Syair | Tabel style=**Poem** | `> col :: col` |
| Tabel ilmiah | Tabel style=**DataTable** | `::table style=data ... ::` |
| Tabel tanpa style | (otomatis) | `::table style=unknown ... ::` |
| Footnote | References → Insert Footnote | `[^n]: teks` |
| Gambar | Insert Picture + alt text | `::figure id=... ::` |

---

*Maktabah Digital Library — Panduan Template v1.1*
