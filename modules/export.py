import json, re, pathlib

def validate_pack(pack):
    d = pack.get("draft", {}) or {}
    mt = len((d.get("meta_title") or "")); md = len((d.get("meta_description") or ""))
    missing_alts = sum(1 for i in pack["source"]["images"] if not i.get("alt"))
    return {"title_len": mt, "desc_len": md, "missing_image_alts": missing_alts}

def write_outputs(pack, outdir: pathlib.Path):
    slug = pack["source"]["url"].rstrip("/").split("/")[-1]
    with open(outdir/f"{slug}.json", "w", encoding="utf-8") as f:
        json.dump(pack, f, ensure_ascii=False, indent=2)
    # convenience MD
    d = pack.get("draft", {})
    md = []
    if "meta_title" in d: md += [f"# {d['meta_title']}", ""]
    if "meta_description" in d: md += [f"> {d['meta_description']}", ""]
    for h in d.get("h2s", []): md += [f"## {h}",""]
    md += [d.get("body","")]
    if d.get("faqs"):
        md += ["\n## FAQs"]
        for qa in d["faqs"]:
            md += [f"**Q:** {qa['q']}", f"**A:** {qa['a']}", ""]
    with open(outdir/f"{slug}.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md))

