#!/usr/bin/env python3
"""Extract plain text + structure from a manuscript (epub, docx, pdf, txt, md).

Stdlib-only for epub/docx/txt/md. PDF needs pdfminer.six (or `pdftotext` on PATH).

Usage:
    python3 extract_book.py <book_path> [--out <workdir>]

Writes into <workdir> (default: ./.appraisal_work/<book_stem>/):
    full.txt       normalised plain text, blank-line separated paragraphs
    manifest.json  word count, paragraph offsets, detected section headings
"""

import argparse
import html
import json
import os
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

# ---------------------------------------------------------------- text utils

TAG_RE = re.compile(r"<[^>]+>")
BLOCK_END_RE = re.compile(r"</(p|div|h[1-6]|li|br|tr)\s*>|<br\s*/?>", re.I)
WS_RE = re.compile(r"[ \t ]+")


def html_to_text(markup: str) -> str:
    markup = re.sub(r"(?is)<(script|style|head)[^>]*>.*?</\1>", " ", markup)
    markup = BLOCK_END_RE.sub("\n\n", markup)
    text = TAG_RE.sub("", markup)
    return html.unescape(text)


def normalise(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("­", "")          # soft hyphen
    text = WS_RE.sub(" ", text)
    lines = [ln.strip() for ln in text.split("\n")]
    out, blank = [], False
    for ln in lines:
        if ln:
            out.append(ln)
            blank = False
        elif not blank:
            out.append("")
            blank = True
    return "\n".join(out).strip()


# ---------------------------------------------------------------- extractors


def extract_epub(path: Path) -> str:
    """Read the OPF spine so chapters come out in reading order."""
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        try:
            container = ET.fromstring(z.read("META-INF/container.xml"))
            rootfile = container.find(".//{*}rootfile").get("full-path")
        except Exception:
            cands = [n for n in names if n.lower().endswith(".opf")]
            if not cands:
                raise SystemExit("epub: no OPF package document found")
            rootfile = cands[0]

        opf = ET.fromstring(z.read(rootfile))
        base = os.path.dirname(rootfile)
        idmap = {
            item.get("id"): item.get("href")
            for item in opf.iterfind(".//{*}manifest/{*}item")
        }
        spine = [
            idmap.get(ref.get("idref"))
            for ref in opf.iterfind(".//{*}spine/{*}itemref")
        ]
        hrefs = [h for h in spine if h]
        if not hrefs:
            hrefs = [n for n in names if n.lower().endswith((".xhtml", ".html", ".htm"))]

        parts = []
        for href in hrefs:
            member = os.path.normpath(os.path.join(base, href)).replace(os.sep, "/")
            if member not in names:
                member = next((n for n in names if n.endswith(os.path.basename(href))), None)
                if member is None:
                    continue
            raw = z.read(member).decode("utf-8", "replace")
            chunk = normalise(html_to_text(raw))
            if chunk:
                parts.append(chunk)
    return "\n\n".join(parts)


def extract_docx(path: Path) -> str:
    W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(path) as z:
        doc = ET.fromstring(z.read("word/document.xml"))
    paras = []
    for p in doc.iter(f"{W}p"):
        runs = [t.text or "" for t in p.iter(f"{W}t")]
        line = "".join(runs).strip()
        style = p.find(f"{W}pPr/{W}pStyle")
        if line and style is not None and "Heading" in (style.get(f"{W}val") or ""):
            line = f"## {line}"
        if line:
            paras.append(line)
    return "\n\n".join(paras)


PDF_STR_ESCAPES = {"n": "\n", "r": "\n", "t": "\t", "b": "", "f": "",
                   "(": "(", ")": ")", "\\": "\\"}


def _pdf_unescape(raw: bytes) -> str:
    out, i = [], 0
    while i < len(raw):
        ch = raw[i:i + 1]
        if ch == b"\\" and i + 1 < len(raw):
            nxt = raw[i + 1:i + 2].decode("latin-1")
            if nxt.isdigit():                      # octal \ooo
                oct_digits = ""
                j = i + 1
                while j < len(raw) and len(oct_digits) < 3 and raw[j:j + 1].isdigit():
                    oct_digits += raw[j:j + 1].decode("latin-1")
                    j += 1
                out.append(chr(int(oct_digits, 8)))
                i = j
                continue
            out.append(PDF_STR_ESCAPES.get(nxt, nxt))
            i += 2
            continue
        out.append(ch.decode("latin-1"))
        i += 1
    return "".join(out)


def _pdf_stdlib(path: Path) -> str:
    """Last-resort PDF text extraction using only the standard library.

    Handles the common case — a PDF exported from a word processor, with
    FlateDecode streams and standard encodings. It does NOT handle scanned
    pages (no text to find) or subset fonts with custom CMaps (produces
    mojibake, which the caller detects and rejects).
    """
    import zlib

    data = path.read_bytes()
    chunks = []
    for m in re.finditer(rb"stream\r?\n?(.*?)endstream", data, re.S):
        raw = m.group(1)
        try:
            raw = zlib.decompress(raw)
        except zlib.error:
            try:
                raw = zlib.decompressobj().decompress(raw)   # truncated stream
            except zlib.error:
                continue
        if b"BT" not in raw:
            continue
        for tm in re.finditer(rb"\((?:[^()\\]|\\.)*\)|<[0-9A-Fa-f\s]+>|T[dDmJj*]|ET",
                              raw):
            tok = tm.group(0)
            if tok.startswith(b"("):
                chunks.append(_pdf_unescape(tok[1:-1]))
            elif tok.startswith(b"<"):
                hexes = re.sub(rb"\s", b"", tok[1:-1])
                if len(hexes) % 2 == 0:
                    try:
                        chunks.append(bytes.fromhex(hexes.decode()).decode(
                            "utf-16-be" if len(hexes) % 4 == 0 else "latin-1",
                            "replace"))
                    except ValueError:
                        pass
            elif tok in (b"Td", b"TD", b"T*", b"ET"):
                chunks.append("\n")
    return "".join(chunks)


def _looks_like_prose(text: str) -> bool:
    """Guard against returning mojibake as if it were a manuscript."""
    sample = text[:20000]
    if len(sample) < 200:
        return False
    letters = sum(c.isalpha() or c.isspace() or c in ".,;:'\"!?-—’“”" for c in sample)
    spaces = sample.count(" ")
    return letters / len(sample) > 0.85 and spaces / len(sample) > 0.08


def extract_pdf(path: Path) -> str:
    text = ""
    try:
        from pdfminer.high_level import extract_text  # type: ignore
        text = extract_text(str(path)) or ""
    except ImportError:
        pass
    except Exception:
        text = ""
    if not _looks_like_prose(text):
        import shutil
        import subprocess
        if shutil.which("pdftotext"):
            try:
                text = subprocess.run(["pdftotext", "-layout", str(path), "-"],
                                      capture_output=True, text=True,
                                      check=True).stdout
            except subprocess.SubprocessError:
                text = ""
    if not _looks_like_prose(text):
        text = _pdf_stdlib(path)
    if not _looks_like_prose(text):
        raise SystemExit(
            "UNREADABLE PDF — no usable text could be pulled from this file.\n"
            "This usually means the PDF is a scan (pictures of pages, not text),\n"
            "or it uses embedded fonts that cannot be decoded.\n"
            "What to do: ask the author to send the original Word (.docx) or\n"
            "EPUB file instead. That is the normal fix and it always works."
        )
    return text


RTF_CONTROL_RE = re.compile(r"\\'([0-9a-fA-F]{2})|\\([a-zA-Z]+)-?\d* ?|[{}]|\\\n")


def extract_rtf(path: Path) -> str:
    raw = path.read_text("latin-1", errors="replace")

    def sub(m):
        if m.group(1):                                  # \'xx escaped byte
            return bytes([int(m.group(1), 16)]).decode("cp1252", "replace")
        word = m.group(2)
        if word in ("par", "line", "pard"):
            return "\n\n"
        if word in ("tab",):
            return "\t"
        if word in ("emdash",):
            return "—"
        if word in ("lquote", "rquote"):
            return "’"
        if word in ("ldblquote", "rdblquote"):
            return '"'
        return ""

    # drop font/colour/stylesheet tables wholesale before unescaping
    raw = re.sub(r"\{\\\*?\\(?:fonttbl|colortbl|stylesheet|info)[^{}]*"
                 r"(?:\{[^{}]*\}[^{}]*)*\}", " ", raw)
    return RTF_CONTROL_RE.sub(sub, raw)


def extract_txt(path: Path) -> str:
    return path.read_text("utf-8", errors="replace")


def read_metadata(path: Path) -> dict:
    """Declared title/author from the container, where the format has them."""
    meta = {"title": None, "author": None, "source": None}
    ext = path.suffix.lower()
    try:
        if ext == ".epub":
            with zipfile.ZipFile(path) as z:
                opf_name = next((n for n in z.namelist()
                                 if n.lower().endswith(".opf")), None)
                if opf_name:
                    opf = ET.fromstring(z.read(opf_name))
                    t = opf.find(".//{http://purl.org/dc/elements/1.1/}title")
                    a = opf.find(".//{http://purl.org/dc/elements/1.1/}creator")
                    meta["title"] = t.text.strip() if t is not None and t.text else None
                    meta["author"] = a.text.strip() if a is not None and a.text else None
                    meta["source"] = "epub OPF metadata"
        elif ext == ".docx":
            with zipfile.ZipFile(path) as z:
                if "docProps/core.xml" in z.namelist():
                    core = ET.fromstring(z.read("docProps/core.xml"))
                    t = core.find("{http://purl.org/dc/elements/1.1/}title")
                    a = core.find("{http://purl.org/dc/elements/1.1/}creator")
                    meta["title"] = t.text.strip() if t is not None and t.text else None
                    meta["author"] = a.text.strip() if a is not None and a.text else None
                    meta["source"] = "docx core properties"
    except Exception:
        pass  # metadata is a nicety; never let it break extraction
    return meta


EXTRACTORS = {
    ".epub": extract_epub, ".docx": extract_docx, ".pdf": extract_pdf,
    ".rtf": extract_rtf, ".txt": extract_txt, ".md": extract_txt,
    ".markdown": extract_txt,
}

# plain-language guidance for formats we cannot read, aimed at the reader
# rather than at a developer
UNSUPPORTED = {
    ".doc": "This is the old Word format (Word 97–2003). Ask the author to open it "
            "and use File > Save As > Word Document (.docx), then resend.",
    ".pages": "This is an Apple Pages document. Ask the author to use "
              "File > Export To > Word, then resend.",
    ".odt": "This is a LibreOffice/OpenOffice document. Ask the author to save it "
            "as .docx, then resend.",
    ".zip": "This is a zip archive. Unzip it first and use the document inside.",
}


def check_readable(src: Path) -> None:
    """Fail early, in language a submissions reader can act on."""
    ext = src.suffix.lower()
    if ext in UNSUPPORTED:
        raise SystemExit(f"CANNOT READ {ext} FILES\n{UNSUPPORTED[ext]}")
    if ext not in EXTRACTORS:
        raise SystemExit(
            f"CANNOT READ {ext or 'this'} FILES\n"
            f"Readable formats: {', '.join(sorted(EXTRACTORS))}.\n"
            "Ask the author to resend as .docx or .epub — both always work.")
    # a .docx that is really a .doc renamed is a common and confusing case
    if ext in (".docx", ".epub") and src.read_bytes()[:4] != b"PK\x03\x04":
        raise SystemExit(
            f"THIS FILE IS NOT REALLY A {ext.upper()[1:]}\n"
            "It has the right name but the wrong contents — usually an old .doc "
            "that was renamed. Ask the author to re-save it properly as .docx.")


def find_book(folder: Path) -> Path:
    """Pick the manuscript out of a folder of uploads: the largest readable file."""
    cands = [p for p in folder.rglob("*")
             if p.is_file() and p.suffix.lower() in EXTRACTORS]
    if not cands:
        raise SystemExit(f"no readable manuscript file found in {folder}")
    return max(cands, key=lambda p: p.stat().st_size)

# ---------------------------------------------------------------- structure

HEADING_RE = re.compile(
    r"^(##\s+.+|(?:chapter|part|book|prologue|epilogue|interlude)\b.{0,60}|"
    r"[IVXLC]{1,7}|\d{1,3})$",
    re.I,
)


def find_headings(paras, cum_words):
    out = []
    for i, p in enumerate(paras):
        if len(p) <= 70 and HEADING_RE.match(p.strip()):
            out.append({"paragraph": i, "word_offset": cum_words[i],
                        "text": p.strip().lstrip("# ")})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("book")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    src = Path(args.book).expanduser()
    if src.is_dir():
        src = find_book(src)
    if not src.exists():
        raise SystemExit(f"not found: {src}")
    check_readable(src)
    ext = src.suffix.lower()

    text = normalise(EXTRACTORS[ext](src))
    paras = [p for p in text.split("\n\n") if p.strip()]
    words = [len(p.split()) for p in paras]
    total = sum(words)

    if total < 2000:
        sys.stderr.write(
            f"WARNING: only {total} words extracted. If this is a scanned PDF it "
            "needs OCR first (e.g. ocrmypdf) — do not appraise from this.\n"
        )

    cum, run = [], 0
    for w in words:
        cum.append(run)
        run += w

    out_dir = Path(args.out) if args.out else Path(".appraisal_work") / src.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "full.txt").write_text("\n\n".join(paras), "utf-8")

    meta = read_metadata(src)
    if not meta["title"]:
        # fall back to the first short standalone line, which is usually the title
        for p in paragraphs[:5]:
            if 2 <= len(p.split()) <= 15 and not p.endswith((".", ",", "!", "?")):
                meta["title"] = p.strip("# ")
                meta["source"] = "first line of text (guess)"
                break

    manifest = {
        "source": str(src.resolve()),
        "format": ext.lstrip("."),
        "metadata": meta,
        "total_words": total,
        "paragraphs": len(paras),
        "paragraph_word_offsets": cum,
        "headings": find_headings(paras, cum)[:400],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), "utf-8")

    print(json.dumps({
        "workdir": str(out_dir), "total_words": total,
        "paragraphs": len(paras), "headings_found": len(manifest["headings"]),
    }, indent=2))


if __name__ == "__main__":
    main()
