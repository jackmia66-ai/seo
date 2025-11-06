import os, json, pathlib
from dotenv import load_dotenv
from modules.fetch import fetch_article
from modules.nlp import extract_keywords_entities, embed_text
from modules.serp import top_competitors, forum_questions
from modules.internal_links import build_site_index, suggest_internal_links
from modules.ai_writer import generate_draft
from modules.export import validate_pack, write_outputs

load_dotenv()
OUT = pathlib.Path("outputs"); OUT.mkdir(exist_ok=True, parents=True)

with open("data/urls.txt") as f:
    urls = [u.strip() for u in f if u.strip()]

site_index = build_site_index(os.getenv("SITE_BASE"))

for url in urls:
    art = fetch_article(url)  # {url,title,meta_title,meta_desc,headings,images,text}
    kw = extract_keywords_entities(art["text"], top_k=20)
    competitors = top_competitors(kw["primary_keyword"], exclude_domain="mentalyc.com")
    faqs = forum_questions(kw["primary_keyword"], extras=kw["secondary_keywords"][:5])

    internals = suggest_internal_links(
        source_url=url,
        source_text=art["text"],
        site_index=site_index,
        n=6
    )

    pack = {
        "source": art,
        "keywords": kw,
        "competitors": competitors,
        "faqs_seed": faqs,
        "internal_suggestions": internals
    }

    draft = generate_draft(pack)  # calls GPT with structured prompt
    pack["draft"] = draft
    pack["lint"] = validate_pack(pack)

    write_outputs(pack, OUT)
    print("✔", url)

