"""YouTube publishing package (metadata only). Uploading is a separate, approval-gated step."""
from __future__ import annotations

import json
import re
from pathlib import Path


def build_package(out_dir: Path, meta: dict, sources_md: Path, thumbnails: list[Path], qc: dict | None = None) -> Path:
    pub = out_dir / "publish"
    pub.mkdir(parents=True, exist_ok=True)
    chapters = (pub / "chapters.txt").read_text().strip() if (pub / "chapters.txt").exists() else ""
    links = re.findall(r"https?://[^\s|)]+", sources_md.read_text())
    seen, uniq = set(), []
    for u in links:
        if u not in seen:
            seen.add(u)
            uniq.append(u)
    desc = "\n".join([
        meta["hook"], "",
        "Chapters:", chapters, "",
        "Sources (primary data used in this video):", *[f"- {u}" for u in uniq], "",
        "Maya and Dev are fictional characters; their raise, loan and card balance are illustrative examples.",
        "On-screen data is from the sources above. Charts labelled 'concept' or 'illustrative' are not real data.", "",
        "Educational content only. Not financial, investment, tax or legal advice. The creators are not licensed "
        "financial professionals.", "",
        " ".join(meta.get("hashtags", [])),
    ]).rstrip()
    pkg = {
        "title": meta["title"],
        "title_options": meta["title_options"],
        "description": desc,
        "tags": meta["tags"],
        "category": "Education",
        "language": "en-US",
        "made_for_kids": False,
        "contains_synthetic_media": True,   # AI narration + animated, altered/synthetic content disclosure
        "thumbnails": [str(p) for p in thumbnails],
        "publish_status": "AWAITING HUMAN APPROVAL",
        "qc_passed": (qc or {}).get("passed"),
    }
    (pub / "package.json").write_text(json.dumps(pkg, indent=2))
    md = [f"# Publishing package - {meta['title']}", "", "**Status: AWAITING YOUR APPROVAL. Nothing has been uploaded.**",
          "", "## Title options", *[f"{i}. {t}" for i, t in enumerate(meta["title_options"], 1)], "",
          "## Description", "```", desc, "```", "", "## Tags", ", ".join(meta["tags"]), "",
          "## Thumbnails", *[f"- {p.name}" for p in thumbnails], "",
          "## Upload settings", "- Category: Education  |  Language: English (US)  |  Not made for kids",
          "- Altered or synthetic content: YES (AI voice / animation)", "- Subtitles: attach the .srt file"]
    (pub / "youtube.md").write_text("\n".join(md) + "\n")
    return pub / "youtube.md"
