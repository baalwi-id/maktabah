#!/usr/bin/env python3
"""
maktabah_convert.py
====================
CLI untuk mengkonversi DOCX → canonical text dan canonical → JSON.

Usage:
    # DOCX → Canonical
    python maktabah_convert.py to-canonical kitab.docx
    python maktabah_convert.py to-canonical kitab.docx --output output/
    
    # Canonical → JSON
    python maktabah_convert.py to-json kitab.txt
    python maktabah_convert.py to-json canonical/*.txt --output api-data/
"""
import sys
import argparse
from pathlib import Path

# Pastikan package bisa diimport
sys.path.insert(0, str(Path(__file__).parent))

from maktabah import MaktabahParser, QCFDecoder, CanonicalRenderer
from maktabah.canonical_parser import CanonicalParser
from maktabah.json_renderer import JSONRenderer
from maktabah.report import ParseReport, Severity


DEFAULT_DECODER = Path(__file__).parent / "maktabah" / "mushaf_decoder.json"


def cmd_to_canonical(args):
    input_path = Path(args.input)
    decoder_path = Path(args.decoder) if args.decoder else DEFAULT_DECODER
    output_dir = Path(args.output) if args.output else input_path.parent

    # ── validasi decoder ──────────────────────────────────────────────
    if not decoder_path.exists():
        print(f"[FATAL] Decoder tidak ditemukan: {decoder_path}", file=sys.stderr)
        print("  Letakkan mushaf_decoder.json di folder maktabah/,")
        print("  atau gunakan --decoder path/ke/decoder.json", file=sys.stderr)
        sys.exit(1)

    # ── init ──────────────────────────────────────────────────────────
    report = ParseReport(str(input_path))
    try:
        decoder = QCFDecoder(decoder_path)
    except Exception as e:
        print(f"[FATAL] Gagal load decoder: {e}", file=sys.stderr)
        sys.exit(1)

    parser   = MaktabahParser(decoder)
    renderer = CanonicalRenderer()

    # ── parse ─────────────────────────────────────────────────────────
    doc_ast = parser.parse(input_path, report)

    # ── output paths ──────────────────────────────────────────────────
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = input_path.stem
    canonical_path = output_dir / f"{stem}.txt"
    report_path    = output_dir / f"{stem}.report.txt"

    # ── tulis report dulu (selalu ditulis, termasuk saat fatal) ───────
    report_text = report.to_text()
    report_path.write_text(report_text, encoding="utf-8")

    # ── fatal → stop ──────────────────────────────────────────────────
    if report.has_fatal or doc_ast is None:
        print(f"\n✗ Parsing gagal (FATAL error).")
        _print_summary(report)
        print(f"\nLihat detail: {report_path}")
        sys.exit(1)

    # ── render canonical ──────────────────────────────────────────────
    canonical_text = renderer.render(doc_ast)
    canonical_path.write_text(canonical_text, encoding="utf-8")

    # ── print summary ─────────────────────────────────────────────────
    print(f"\n✓ Selesai: {input_path.name}")
    print(f"  canonical : {canonical_path}")
    print(f"  report    : {report_path}")
    _print_summary(report)

    # Exit code 1 jika ada ERROR (tapi bukan fatal)
    if report.has_error:
        sys.exit(1)


def _print_summary(report: ParseReport):
    fatals   = [i for i in report.items if i.severity == Severity.FATAL]
    errors   = [i for i in report.items if i.severity == Severity.ERROR]
    warnings = [i for i in report.items if i.severity == Severity.WARNING]
    infos    = [i for i in report.items if i.severity == Severity.INFO]

    print()
    for item in fatals:
        print(f"  {item}")
    for item in errors:
        print(f"  {item}")
    for item in warnings:
        print(f"  {item}")

    # Hanya print INFO yang penting (counts + timing)
    for item in infos:
        if item.code in ("I002", "I003"):
            print(f"  {item}")


def cmd_to_json(args):
    """Convert canonical.txt → JSON"""
    input_paths = [Path(p) for p in args.inputs]
    output_dir = Path(args.output) if args.output else Path.cwd()
    output_dir.mkdir(parents=True, exist_ok=True)
    
    parser = CanonicalParser()
    renderer = JSONRenderer()
    
    success_count = 0
    fail_count = 0
    
    for canonical_path in input_paths:
        if not canonical_path.exists():
            print(f"✗ File not found: {canonical_path}", file=sys.stderr)
            fail_count += 1
            continue
        
        print(f"Processing: {canonical_path.name}")
        report = ParseReport(str(canonical_path))
        
        # Parse canonical → AST
        doc_ast = parser.parse(canonical_path, report)
        
        if doc_ast is None:
            print(f"✗ Parse failed: {canonical_path.name}")
            fail_count += 1
            continue
        
        # Render AST → JSON
        json_output = renderer.render(doc_ast)
        
        # Save JSON
        output_name = canonical_path.stem + '.json'
        output_path = output_dir / output_name
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(json_output)
        
        print(f"✓ Created: {output_path}")
        success_count += 1
    
    print()
    print(f"Summary: {success_count} success, {fail_count} failed")


def main():
    parser = argparse.ArgumentParser(
        prog="maktabah_convert",
        description="Maktabah Digital Library — Converter"
    )
    sub = parser.add_subparsers(dest="command")

    # to-canonical subcommand (renamed from convert)
    p_docx = sub.add_parser("to-canonical", help="Convert DOCX → canonical text")
    p_docx.add_argument("input", help="Path to .docx file")
    p_docx.add_argument("--output", "-o", help="Output directory (default: same as input)")
    p_docx.add_argument("--decoder", "-d", help="Path to mushaf_decoder.json")
    
    # to-json subcommand
    p_json = sub.add_parser("to-json", help="Convert canonical text → JSON")
    p_json.add_argument("inputs", nargs="+", help="Path(s) to canonical text file(s)")
    p_json.add_argument("--output", "-o", help="Output directory (default: current directory)")

    args = parser.parse_args()

    if args.command == "to-canonical":
        cmd_to_canonical(args)
    elif args.command == "to-json":
        cmd_to_json(args)
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
