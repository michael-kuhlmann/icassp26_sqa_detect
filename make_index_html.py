#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generated with ChatGPT

Usage
-----

Basic (each folder becomes its own section titled by the folder name):
python3 generate_audio_sections.py ./podcasts ./music ./lectures -o ./public/index.html -t "My Audio Library"

Custom section titles:
python3 generate_audio_sections.py \
  --section "Podcasts=./audio/podcasts" \
  --section "Music=./audio/music" \
  --section "Lectures=./audio/lectures" \
  -o ./docs/index.html -t "My Audio Library"

Sample 10 per section, deterministic:
python3 generate_audio_sections.py ./podcasts ./music \
  -o ./docs/index.html -t "My Audio Library" --sample 10 --seed 42

"""
import html
import mimetypes
import os
import random
from pathlib import Path
from datetime import datetime
from typing import Iterable, List, Dict, Optional, Tuple

import click

try:
    import markdown as _md  # pip install markdown
except Exception:
    _md = None

AUDIO_EXTS = {".mp3", ".m4a", ".wav", ".ogg", ".opus", ".flac", ".aac", ".webm"}

PAGE_HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{page_title}</title>
<style>
  :root {{
    --bg:#0b0f14; --card:#121821; --text:#e8eef6; --muted:#9fb3c8; --border:#1e2a38; --accent:#4fa3ff;
    --cols:{columns};
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; padding:24px; font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;
         background:var(--bg); color:var(--text); }}
  header, main, footer {{ max-width:1100px; margin:0 auto; }}
  h1 {{ margin:0 0 6px; font-size:1.6rem; letter-spacing:.2px; }}
  .meta {{ color:var(--muted); font-size:.9rem; margin-bottom:14px; }}

  .intro {{ margin:12px 0 22px; padding:16px; background:var(--card); border:1px solid var(--border); border-radius:12px; }}
  .intro :where(p, ul, ol) {{ margin: 0.5em 0; }}
  .intro pre {{ overflow:auto; background:#0e141c; padding:12px; border-radius:10px; }}

  nav.toc {{ margin:16px 0 22px; padding:12px; background:var(--card); border:1px solid var(--border); border-radius:12px; }}
  nav.toc a {{ color:var(--accent); text-decoration:none; margin-right:14px; }}
  nav.toc a:hover {{ text-decoration:underline; }}

  section.section {{ margin:28px 0; }}
  section.section > details {{ border:1px solid var(--border); border-radius:12px; background:var(--card); }}
  section.section > details > summary {{
    cursor:pointer; list-style:none; padding:12px 14px; user-select:none;
    font-weight:600; display:flex; align-items:center; gap:10px;
  }}
  section.section > details > summary::-webkit-details-marker {{ display:none; }}
  .summary-meta {{ color:var(--muted); font-weight:400; }}
  .grid-wrapper {{ padding: 0 14px 14px; }}
  .grid {{ display:grid; gap:14px; grid-template-columns: repeat(var(--cols), minmax(0, 1fr)); }}
  @media (max-width: 640px) {{
    .grid {{ grid-template-columns: 1fr; }}
  }}

  .item {{ background:#0e141c; border:1px solid var(--border); border-radius:14px; padding:14px; }}
  .row {{ display:grid; grid-template-columns:1fr auto; gap:10px; align-items:start; }}
  .name {{ font-weight:600; word-break:break-word; }}
  .name {{ overflow: hidden; }}
  .name a {{
    display: block;
    max-width: 100%;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis; /* ensures visual cut */
  }}
  .sub {{ color:var(--muted); font-size:.9rem; margin-top:2px; }}
  .right {{ text-align:right; white-space:nowrap; color:var(--muted); }}
  audio {{ width:100%; margin-top:10px; }}
  a {{ color:var(--accent); text-decoration:none; }}
  a:hover {{ text-decoration:underline; }}
  .transcript {{ margin-top:10px; font-size:.95rem; color:#d5e2f0; white-space:pre-wrap; }}
  hr.sep {{ border:0; border-top:1px solid var(--border); margin:28px 0; }}
  footer {{ color:var(--muted); font-size:.85rem; margin-top:24px; }}
</style>
</head>
<body>
<header>
  <h1>{page_title}</h1>
  <div class="meta">Total: {total_count} audio file{plural_total}. Generated {generated_at}.</div>
</header>

<main>
{intro_html}
{maybe_toc}
"""

PAGE_TAIL = """
</main>

<footer>
  Static page; audio links are relative to this HTML file.
</footer>
<script>
(function() {{
  const ACCORDION = {accordion_js};
  const detailsList = Array.from(document.querySelectorAll('section.section details'));
  if (ACCORDION) {{
    detailsList.forEach(d => {{
      d.addEventListener('toggle', () => {{
        if (d.open) {{
          detailsList.forEach(o => {{ if (o !== d) o.open = false; }});
        }}
      }});
    }});
  }}
  document.querySelectorAll('nav.toc a').forEach(a => {{
    a.addEventListener('click', () => {{
      const id = a.getAttribute('href').slice(1);
      const sec = document.getElementById(id);
      const det = sec && sec.querySelector('details');
      if (det) det.open = true;
    }});
  }});
}})();
</script>
</body>
</html>
"""

SECTION_HEAD = """<section class="section" id="{anchor}">
  <details {open_attr}>
    <summary>{title} <span class="summary-meta">({count} file{plural})</span></summary>
    <div class="grid-wrapper">
      <div class="grid">
"""

SECTION_TAIL = """      </div>
    </div>
  </details>
</section>
"""

ITEM_TEMPLATE = """<article class="item" data-size="{size_bytes}">
  <div class="row">
    <div>
      <div class="name"><a href="{href}" title="{name}" download>{display_name}</a></div>
      <div class="sub">{size_human}{maybe_sep}{relpath}</div>
    </div>
    <div class="right">{ext_upper}</div>
  </div>
  <audio controls preload="none" src="{href}" {type_attr}></audio>
  {maybe_transcript}
</article>
"""

def human_size(num_bytes: int) -> str:
    units = ["B","KB","MB","GB","TB"]
    s = float(num_bytes)
    for u in units:
        if s < 1024 or u == units[-1]:
            return f"{s:.1f} {u}" if u != "B" else f"{int(s)} {u}"
        s /= 1024.0

def is_audio(path: Path) -> bool:
    return path.suffix.lower() in AUDIO_EXTS

def guess_mime(path: Path) -> Optional[str]:
    m, _ = mimetypes.guess_type(str(path))
    return m

def scan_dir_for_audio(root: Path, followlinks: bool) -> List[Dict]:
    results: List[Dict] = []
    for r, _, files in os.walk(root, followlinks=followlinks):
        for fn in files:
            p = Path(r) / fn
            if not is_audio(p):
                continue
            try:
                size = p.stat().st_size
            except OSError:
                continue
            results.append({
                "path": p.resolve(),
                "name": p.name,
                "ext": p.suffix,
                "size": size,
            })
    results.sort(key=lambda x: x["name"].lower())
    return results

def load_transcripts(section_dir: Path, tsv_name: Optional[str]) -> Dict[str, str]:
    """
    Returns a mapping from normalized relative path (posix-style) -> transcript text.
    """
    if not tsv_name:
        return {}
    tsv_path = (section_dir / tsv_name).resolve()
    if not tsv_path.exists():
        return {}
    mapping: Dict[str, str] = {}
    try:
        for raw in tsv_path.read_text(encoding="utf-8").splitlines():
            if not raw.strip() or raw.lstrip().startswith("#"):
                continue
            # split on first tab only
            if "\t" not in raw:
                continue
            audio_rel, text = raw.split("\t", 1)
            key = normalize_rel(audio_rel)
            mapping[key] = text.rstrip("\n\r")
    except Exception:
        # if anything odd happens, just return what we parsed so far
        pass
    return mapping

def normalize_rel(rel: str) -> str:
    rel = rel.strip().replace("\\", "/")
    while rel.startswith("./"):
        rel = rel[2:]
    return rel

def build_item_html(info: Dict, output_dir: Path, section_dir: Path,
                    transcripts: Dict[str, str], name_max_chars: int) -> str:
    full_name = info["name"]
    display_name = elide_filename_for_display(full_name, name_max_chars)

    name_html = html.escape(full_name)
    display_name_html = html.escape(display_name)

    path = info["path"]
    display_path = path.parent / display_name  # use elided name
    rel_from_output = os.path.relpath(path, output_dir)
    rel_html = html.escape(rel_from_output)
    href = rel_html.replace("\\", "/")
    size_h = human_size(info["size"])
    ext_upper = html.escape(info["ext"].upper().lstrip("."))
    mime = guess_mime(Path(info["path"]))
    type_attr = f'type="{mime}"' if mime else ""

    rel_from_section = os.path.relpath(info["path"], section_dir)
    key = normalize_rel(rel_from_section)
    txt = transcripts.get(key)
    maybe_transcript = f'<div class="transcript">{html.escape(txt)}</div>' if txt else ""

    return ITEM_TEMPLATE.format(
        size_bytes=str(info["size"]),
        href=href,
        name=display_name_html,
        display_name=display_name_html,
        size_human=size_h,
        maybe_sep=" • " if rel_from_output else "",
        relpath=html.escape(os.path.relpath(display_path, output_dir)),
        ext_upper=ext_upper,
        type_attr=type_attr,
        maybe_transcript=maybe_transcript
    )

def slugify(s: str) -> str:
    out = "".join(ch.lower() if ch.isalnum() else "-" for ch in s)
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-") or "section"

def render_markdown(md_text: str) -> str:
    if _md is not None:
        try:
            # extensions are optional; keep it light
            return _md.markdown(md_text, extensions=["extra", "sane_lists", "tables"])
        except Exception:
            pass
    # Fallback: safe-pre format
    return f"<pre>{html.escape(md_text)}</pre>"

def elide_filename_for_display(filename: str, max_chars: int) -> str:
    if max_chars <= 0 or len(filename) <= max_chars:
        return filename
    stem, ext = os.path.splitext(filename)
    # Ensure we don't cut away the extension; reserve room for ellipsis + ext
    reserve = len(ext) + 1  # 1 for ellipsis
    if max_chars <= reserve:
        # Not enough room; just hard cut and add ellipsis
        return filename[:max(1, max_chars - 1)] + "…"
    avail = max_chars - reserve
    # Split remaining between head and tail of the stem
    head = max(1, int(avail * 0.66))
    tail = max(0, avail - head)
    elided = stem[:head] + "…" + (stem[-tail:] if tail else "") + ext
    return elided

@click.command(context_settings=dict(help_option_names=["-h","--help"]))
@click.argument(
    "paths",
    nargs=-1,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
)
@click.option("-o","--output", type=click.Path(dir_okay=False, path_type=Path),
              default=Path("index.html"), help="Output HTML file (default: index.html)")
@click.option("-t","--title", default="Audio Library", help="Page title")
@click.option("--follow-symlinks", is_flag=True, help="Follow symlinks while walking")
@click.option(
    "--section",
    "section_specs",
    multiple=True,
    help='Define a section as "Title=PATH". Can be used multiple times. '
         "If provided, this overrides positional PATHS."
)
@click.option(
    "--no-jekyll",
    is_flag=True,
    help="Create an empty .nojekyll file next to the output (useful for GitHub Pages)."
)
@click.option(
    "--sample",
    type=click.IntRange(min=1),
    default=None,
    help="Randomly sample up to N audio files from each section (without replacement)."
)
@click.option(
    "--seed",
    type=int,
    default=None,
    help="Seed for deterministic sampling (used with --sample)."
)
@click.option(
    "--columns",
    type=click.IntRange(min=1, max=12),
    default=2,
    help="Number of columns for the audio grid (responsive)."
)
@click.option(
    "--tsv-file",
    type=str,
    default="transcripts.tsv",
    help="TSV filename to read per section, with 'audio<TAB>text'. Relative to each section directory."
)
@click.option(
    "--intro-md",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Path to a Markdown file rendered as an introduction at the top of the page."
)
@click.option(
    "--accordion/--no-accordion",
    default=True,
    help="When enabled, opening one section will close the others."
)
@click.option(
    "--start-collapsed",
    is_flag=True,
    help="Start with all sections collapsed (no section opened initially)."
)
@click.option(
    "--name-max-chars",
    type=click.IntRange(min=0, max=200),
    default=60,
    help="Max characters to show for filenames (0 = no cut). Extension is preserved; the middle is elided."
)
def cli(paths: Iterable[Path], output: Path, title: str, follow_symlinks: bool,
        section_specs: Iterable[str], no_jekyll: bool, sample: Optional[int], seed: Optional[int],
        columns: int, tsv_file: Optional[str], intro_md: Optional[Path],
        accordion: bool, start_collapsed: bool, name_max_chars: int):
    """
    Generate a static HTML page with separate sections per folder of audio files,
    with optional transcripts (TSV), intro (Markdown), columns, sampling and accordion collapse.
    """
    # Ensure common audio MIME types are known
    mimetypes.add_type("audio/mpeg", ".mp3")
    mimetypes.add_type("audio/mp4", ".m4a")
    mimetypes.add_type("audio/ogg", ".ogg")
    mimetypes.add_type("audio/opus", ".opus")
    mimetypes.add_type("audio/wav", ".wav")
    mimetypes.add_type("audio/flac", ".flac")
    mimetypes.add_type("audio/aac", ".aac")
    mimetypes.add_type("audio/webm", ".webm")

    # Build section list
    sections: List[Dict] = []
    if section_specs:
        for spec in section_specs:
            if "=" not in spec:
                raise click.UsageError(f'--section must be "Title=PATH", got: {spec}')
            sec_title, sec_path = spec.split("=", 1)
            p = Path(sec_path).expanduser().resolve()
            if not p.exists() or not p.is_dir():
                raise click.UsageError(f"Section path not a directory: {p}")
            sections.append({"title": sec_title.strip(), "path": p})
    else:
        if not paths:
            raise click.UsageError("Provide at least one PATH or use --section 'Title=PATH'.")
        for p in paths:
            sections.append({"title": p.name or str(p), "path": p.resolve()})

    # RNG for deterministic sampling
    rng = random.Random(seed) if seed is not None else random

    # Scan, load transcripts, and (optionally) sample per section
    for s in sections:
        sdir = s["path"]
        files = scan_dir_for_audio(sdir, follow_symlinks)
        transcripts = load_transcripts(sdir, tsv_file)
        if sample is not None and len(files) > sample:
            files = rng.sample(files, sample)
            files.sort(key=lambda x: x["name"].lower())
        s["files"] = files
        s["transcripts"] = transcripts

    total = sum(len(s["files"]) for s in sections)

    out_path = output.resolve()
    out_dir = out_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    # Table of contents if multiple sections
    if len(sections) > 1:
        toc_links = []
        for s in sections:
            anchor = slugify(s["title"])
            toc_links.append(f'<a href="#{html.escape(anchor)}">{html.escape(s["title"])}</a>')
        toc_html = f'<nav class="toc">{"".join(toc_links)}</nav>'
    else:
        toc_html = ""

    # Intro markdown
    if intro_md:
        try:
            md_text = intro_md.read_text(encoding="utf-8")
        except Exception as e:
            raise click.ClickException(f"Failed to read --intro-md: {e}")
        intro_html_block = f'<section class="intro">{render_markdown(md_text)}</section>'
    else:
        intro_html_block = ""

    # Build HTML
    parts: List[str] = []
    parts.append(PAGE_HEAD.format(
        page_title=html.escape(title),
        total_count=total,
        plural_total="" if total == 1 else "s",
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        intro_html=intro_html_block,
        maybe_toc=toc_html,
        columns=columns,
    ))

    for idx, s in enumerate(sections):
        anchor = slugify(s["title"])
        open_attr = "" if start_collapsed else ("open" if idx == 0 else "")
        parts.append(SECTION_HEAD.format(
            anchor=html.escape(anchor),
            title=html.escape(s["title"]),
            count=len(s["files"]),
            plural="" if len(s["files"]) == 1 else "s",
            open_attr=open_attr
        ))
        for info in s["files"]:
            parts.append(build_item_html(info, out_dir, s["path"], s["transcripts"], name_max_chars))
        parts.append(SECTION_TAIL)
        if idx < len(sections) - 1:
            parts.append('<hr class="sep">')

    parts.append(PAGE_TAIL.format(
        accordion_js="true" if accordion else "false"
    ))
    html_out = "".join(parts)

    out_path.write_text(html_out, encoding="utf-8")

    if no_jekyll:
        (out_dir / ".nojekyll").write_text("", encoding="utf-8")

    # Console summary
    click.echo(f"Wrote {out_path} ({total} audio file{'s' if total!=1 else ''} in {len(sections)} section{'s' if len(sections)!=1 else ''}).")
    if sample is not None:
        click.echo(f"Per-section sampling: up to {sample} file(s) (seed={seed}).")
    if intro_md:
        click.echo(f"Included intro from: {intro_md}")
    if tsv_file:
        found_any = sum(1 for s in sections if s['transcripts'])
        click.echo(f"Transcripts TSV: '{tsv_file}' ({found_any}/{len(sections)} sections had it).")
    rel_hints = ", ".join([os.path.relpath(s['path'], out_dir) for s in sections])
    click.echo(f"Note: keep this HTML's relative paths to these folders intact: {rel_hints}")


if __name__ == "__main__":
    cli()
