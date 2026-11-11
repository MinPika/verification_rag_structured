"""K0: frozen, anchored text of a task's document corpus (handbook + any other policy-bearing documents).

Each document becomes a list of blocks {id, kind, level, section, text}; tables become one block per row with the
header attached. ``render`` produces anchored markdown that both the offline compiler and the online tools read, so
every compiled rule can cite block ids and quote text that lint checks verbatim.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import paths

DOC_EXT = (".pdf", ".docx", ".html", ".htm", ".md", ".txt")
POLICY_NAME = re.compile(r"sop|handbook|procedure|policy|manual|guideline|qa_review|templates?\b", re.I)
NUMBERED = re.compile(r"^(?:section\s+)?(\d+(?:\.\d+){0,4}|[A-Z](?:\.\d+){0,3}|appendix\s+[a-z0-9]+)[.):]?\s+\S", re.I)


@dataclass
class Block:
    id: str
    kind: str  # heading | para | item | row
    text: str
    level: int = 0
    section: str = ""
    header: list[str] = field(default_factory=list)


@dataclass
class Doc:
    name: str
    sha256: str
    fmt: str
    blocks: list[Block]


def _clean(s: str) -> str:
    s = s.replace("\u00a0", " ").replace("\u200b", "")
    return re.sub(r"[ \t]+", " ", s).strip()


def _heading_level(text: str) -> int:
    m = NUMBERED.match(text)
    if not m:
        return 0
    return m.group(1).count(".") + 1 if m.group(1)[0].isdigit() else 2


# ---- HTML -------------------------------------------------------------------------------------------------------

def parse_html(path: Path) -> list[tuple]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(path.read_bytes(), "lxml")
    for bad in soup(["script", "style", "nav"]):
        bad.decompose()
    out: list[tuple] = []
    body = soup.body or soup
    for el in body.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "table", "pre", "blockquote"]):
        if el.find_parent("table") is not None and el.name != "table":
            continue
        if el.name in ("p", "pre", "blockquote") and el.find_parent("li") is not None:
            continue
        if el.name == "table":
            rows = []
            for tr in el.find_all("tr"):
                cells = [_clean(c.get_text(" ")) for c in tr.find_all(["th", "td"])]
                if any(cells):
                    rows.append(cells)
            if rows:
                out.append(("table", rows))
            continue
        text = _clean(el.get_text(" "))
        if not text:
            continue
        if el.name[0] == "h":
            out.append(("heading", int(el.name[1]), text))
        elif el.name == "li":
            out.append(("item", text))
        else:
            out.append(("para", text))
    return out


# ---- DOCX -------------------------------------------------------------------------------------------------------

def parse_docx(path: Path) -> list[tuple]:
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    d = docx.Document(str(path))
    out: list[tuple] = []
    for child in d.element.body.iterchildren():
        tag = child.tag.split("}")[-1]
        if tag == "p":
            p = Paragraph(child, d)
            text = _clean(p.text)
            if not text:
                continue
            style = (p.style.name if p.style is not None else "") or ""
            m = re.match(r"heading\s*(\d)", style, re.I)
            if m:
                out.append(("heading", int(m.group(1)), text))
            elif re.match(r"title", style, re.I):
                out.append(("heading", 1, text))
            elif "list" in style.lower() or child.find(".//{*}numPr") is not None:
                out.append(("item", text))
            else:
                bold = p.runs and all(r.bold for r in p.runs if r.text.strip())
                lvl = _heading_level(text)
                if bold and len(text) < 120 and (lvl or len(text) < 70):
                    out.append(("heading", lvl or 3, text))
                else:
                    out.append(("para", text))
        elif tag == "tbl":
            t = Table(child, d)
            rows = []
            for r in t.rows:
                cells, prev = [], None
                for c in r.cells:  # merged cells repeat; keep them once
                    if c._tc is prev:
                        continue
                    prev = c._tc
                    cells.append(_clean(c.text))
                if any(cells):
                    rows.append(cells)
            if rows:
                out.append(("table", rows))
    return out


# ---- PDF --------------------------------------------------------------------------------------------------------

def parse_pdf(path: Path) -> list[tuple]:
    """PyMuPDF's table finder can crash the interpreter on some files: parse in a child process, fall back to
    text-only extraction if the child dies."""
    import subprocess

    for tables in ("1", "0"):
        r = subprocess.run([sys.executable, "-W", "ignore", "-m", "vrag.k0", "--pdf", str(path), tables],
                           capture_output=True, text=True, cwd=str(paths.ROOT), timeout=600)
        if r.returncode == 0 and r.stdout.strip():
            return [tuple(x) for x in json.loads(r.stdout.strip().splitlines()[-1])]
    raise RuntimeError(f"pdf parse failed: {path.name}")


def _parse_pdf(path: Path, use_tables: bool = True) -> list[tuple]:
    import pymupdf

    doc = pymupdf.open(str(path))
    sizes: Counter = Counter()
    pages = []
    for page in doc:
        try:
            tables = page.find_tables().tables if use_tables else []
        except Exception:
            tables = []
        tboxes = [pymupdf.Rect(t.bbox) for t in tables]
        d = page.get_text("dict")
        lines = []
        for b in d["blocks"]:
            if b.get("type") != 0:
                continue
            for ln in b["lines"]:
                spans = [s for s in ln["spans"] if s["text"].strip()]
                if not spans:
                    continue
                rect = pymupdf.Rect(ln["bbox"])
                if any(rect.intersects(tb) and (rect & tb).get_area() > 0.5 * rect.get_area() for tb in tboxes):
                    continue
                text = _clean("".join(s["text"] for s in spans))
                size = max(s["size"] for s in spans)
                bold = all((s["flags"] & 16) or "bold" in s["font"].lower() for s in spans)
                sizes[round(size)] += len(text)
                lines.append((rect.y0, rect.x0, text, size, bold, b["number"]))
        trows = []
        for t, tb in zip(tables, tboxes, strict=False):  # find_tables may skip boxes
            rows = [[_clean(c or "") for c in r] for r in t.extract()]
            rows = [r for r in rows if any(r)]
            if rows:
                trows.append((tb.y0, rows))
        pages.append((page.rect.height, lines, trows))
    body = sizes.most_common(1)[0][0] if sizes else 11
    # repeated header/footer lines
    edge = Counter()
    for h, lines, _ in pages:
        for y, _x, text, *_ in lines:
            if y < 0.07 * h or y > 0.93 * h:
                edge[re.sub(r"\d+", "#", text)] += 1
    noise = {k for k, v in edge.items() if v >= max(3, len(pages) // 3)}
    out: list[tuple] = []
    for _h, lines, trows in pages:
        items = [(y, "line", (x, text, size, bold, bno)) for y, x, text, size, bold, bno in lines] + \
                [(y, "table", rows) for y, rows in trows]
        items.sort(key=lambda it: it[0])
        buf: list[str] = []
        last_bno = None

        def flush(buf: list[str] = buf) -> None:
            if buf:
                out.append(("para", _clean(" ".join(buf))))
                buf.clear()

        for _y, kind, payload in items:
            if kind == "table":
                flush()
                out.append(("table", payload))
                continue
            x, text, size, bold, bno = payload
            if re.sub(r"\d+", "#", text) in noise or re.fullmatch(r"(page\s*)?\d+(\s*(of|/)\s*\d+)?", text, re.I):
                continue
            lvl = _heading_level(text)
            is_head = len(text) < 120 and ((size >= body + 1.5) or (bold and (lvl or len(text) < 60)))
            if is_head:
                flush()
                out.append(("heading", lvl or (1 if size >= body + 4 else 2 if size >= body + 1.5 else 3), text))
                last_bno = None
                continue
            bullet = re.match(r"^[•\-–▪●○◦■]\s*", text)
            if bullet or (bno != last_bno and buf):
                flush()
            if bullet:
                out.append(("item", text[bullet.end():].strip()))
                last_bno = None
                continue
            buf.append(text)
            last_bno = bno
        flush()
    return out


# ---- other ------------------------------------------------------------------------------------------------------

def parse_text(path: Path) -> list[tuple]:
    out = []
    for para in re.split(r"\n\s*\n", path.read_text(errors="replace")):
        para = para.strip()
        if not para:
            continue
        m = re.match(r"^(#{1,6})\s+(.*)", para)
        out.append(("heading", len(m.group(1)), m.group(2)) if m else ("para", _clean(para)))
    return out


def parse_json_doc(path: Path) -> list[tuple]:
    data = json.loads(path.read_text())
    return [("para", json.dumps(data, indent=1, ensure_ascii=False))]


def parse(path: Path) -> list[tuple]:
    ext = path.suffix.lower()
    if ext in (".html", ".htm"):
        return parse_html(path)
    if ext == ".docx":
        return parse_docx(path)
    if ext == ".pdf":
        return parse_pdf(path)
    if ext == ".json":
        return parse_json_doc(path)
    return parse_text(path)


def to_doc(path: Path, prefix: str) -> Doc:
    raw = parse(path)
    blocks: list[Block] = []
    stack: list[tuple[int, str]] = []
    n = 0

    def nid() -> str:
        nonlocal n
        n += 1
        return f"{prefix}{n:04d}"

    for item in raw:
        if item[0] == "heading":
            _, lvl, text = item
            while stack and stack[-1][0] >= lvl:
                stack.pop()
            stack.append((lvl, text))
            blocks.append(Block(nid(), "heading", text, lvl, " > ".join(t for _, t in stack[:-1])))
        elif item[0] == "table":
            rows = item[1]
            header = rows[0]
            sec = " > ".join(t for _, t in stack)
            blocks.append(Block(nid(), "row", " | ".join(header), section=sec, header=[]))
            for r in rows[1:]:
                blocks.append(Block(nid(), "row", " | ".join(r), section=sec, header=header))
        else:
            kind, text = item
            blocks.append(Block(nid(), kind, text, section=" > ".join(t for _, t in stack)))
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    return Doc(path.name, sha, path.suffix.lower().lstrip("."), blocks)


def render(doc: Doc, did: str) -> str:
    lines = [f"# [{did}] {doc.name}", ""]
    for b in doc.blocks:
        if b.kind == "heading":
            lines += ["", f"{'#' * min(b.level + 1, 6)} {b.text}  [{b.id}]"]
        elif b.kind == "item":
            lines.append(f"- [{b.id}] {b.text}")
        elif b.kind == "row":
            lines.append(f"| [{b.id}] {b.text} |")
        else:
            lines.append(f"[{b.id}] {b.text}")
    return "\n".join(lines) + "\n"


SOP_HEAD = re.compile(r"standard operating procedures?|\bSOP\b|operating procedures?|policy and procedures?|"
                      r"handbook|procedure manual", re.I)
TEMPLATE_NAME = re.compile(r"templates?\b|template_", re.I)


def classify(path: Path, doc: Doc) -> str:
    """'policy' for documents that state company rules (SOP, policy, QA review of the SOP, message templates),
    'case' for everything else (receipts, forms, letters, case files). Content-based; names are only a hint."""
    head = " ".join(b.text for b in doc.blocks[:40])[:4000]
    if TEMPLATE_NAME.search(path.stem):
        return "policy"
    if len(doc.blocks) >= 40 and (SOP_HEAD.search(head) or POLICY_NAME.search(path.stem)):
        return "policy"
    if POLICY_NAME.search(path.stem) and re.search(r"sop|handbook|procedure|qa_review", path.stem, re.I):
        return "policy"
    return "case"


def workspace_docs(task: str) -> list[Path]:
    ws = paths.workspace(task)
    return sorted(p for p in ws.rglob("*") if p.is_file() and p.suffix.lower() in DOC_EXT + (".json",)
                  and p.stat().st_size < 5_000_000)


def build(task: str) -> dict:
    out = paths.KB / task / "k0"
    out.mkdir(parents=True, exist_ok=True)
    parsed = []
    for p in workspace_docs(task):
        try:
            doc = to_doc(p, "X.")
        except Exception as e:  # unreadable case document: index the failure, never crash the build
            doc = Doc(p.name, hashlib.sha256(p.read_bytes()).hexdigest(), p.suffix.lower().lstrip("."),
                      [Block("X.0001", "para", f"[unreadable: {type(e).__name__}]")])
        parsed.append((p, doc, classify(p, doc)))
    if not any(r == "policy" for *_, r in parsed):  # fall back to the largest document
        big = max(range(len(parsed)), key=lambda i: len(parsed[i][1].blocks))
        parsed[big] = (parsed[big][0], parsed[big][1], "policy")
    parsed.sort(key=lambda x: (x[2] != "policy", -len(x[1].blocks) if x[2] == "policy" else 0, x[0].name))
    docs, md = [], {"policy": [], "case": []}
    for i, (_path, doc, role) in enumerate(parsed, 1):
        did = f"D{i}"
        for j, b in enumerate(doc.blocks, 1):
            b.id = f"{did}.{j:04d}"
        docs.append({"id": did, "role": role, **asdict(doc)})
        md[role].append(render(doc, did))
    (out / "corpus.json").write_text(json.dumps(docs, indent=1, ensure_ascii=False))
    (out / "policy.md").write_text("\n".join(md["policy"]))
    (out / "cases.md").write_text("\n".join(md["case"]))
    return {"task": task, "policy": [(d["name"], len(d["blocks"])) for d in docs if d["role"] == "policy"],
            "n_case": sum(d["role"] == "case" for d in docs), "policy_chars": sum(len(m) for m in md["policy"])}


if __name__ == "__main__":
    if sys.argv[1:2] == ["--pdf"]:
        print(json.dumps(_parse_pdf(Path(sys.argv[2]), sys.argv[3] == "1"), ensure_ascii=False))
        sys.exit(0)
    for t in sys.argv[1:] or paths.all_tasks():
        print(json.dumps(build(t)), flush=True)
