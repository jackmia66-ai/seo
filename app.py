# Streamlit SEO Optimizer (Mentaylc)
# -------------------------------------------------------------
# A single-file Streamlit app that:
# - Accepts a list of URLs (e.g., Mentalyc blog posts)
# - Extracts keywords & entities
# - Finds competitor pages and real user FAQs (Reddit/Quora via Google SERP)
# - Suggests internal & external links
# - Uses OpenAI to generate an SEO draft (meta title, meta desc, H2s, body, FAQs)
# - Lets you preview and download JSON/Markdown outputs
#
# Requirements (install in your env):
#   streamlit
#   python-dotenv
#   requests
#   readabilipy
#   beautifulsoup4
#   spacy
#   keybert
#   yake
#   sentence-transformers
#   tqdm
#   (Then: python -m spacy download en_core_web_sm)
# -------------------------------------------------------------

import os
import re
import io
import json
import textwrap
from typing import List, Dict, Any

import requests
import streamlit as st
from bs4 import BeautifulSoup
from readabilipy import simple_json_from_html_string

# NLP libs
import spacy
from keybert import KeyBERT
import yake
from sentence_transformers import SentenceTransformer, util

# ---------------------------
# App Config
# ---------------------------
st.set_page_config(page_title="SEO Optimizer (Mentaylc)", layout="wide")

# Lazy-load heavy models once
@st.cache_resource(show_spinner=False)
def load_models():
    nlp = spacy.load("en_core_web_sm")
    kw_model = KeyBERT()
    embed_model = SentenceTransformer("all-MiniLM-L6-v2")
    return nlp, kw_model, embed_model

nlp, kw_model, embed_model = load_models()

# ---------------------------
# Helpers
# ---------------------------

def fetch_article(url: str) -> Dict[str, Any]:
    """Download a page and extract readable text + basic meta."""
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123 Safari/537.36"}
    r = requests.get(url, timeout=30, headers=headers)
    r.raise_for_status()
    html = r.text

    sj = simple_json_from_html_string(html, use_readability=True)
    text = " ".join((b.get("text", "") for b in sj.get("content", []) if isinstance(b, dict))).strip()

    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.text.strip() if soup.title else ""
    md = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
    meta_desc = (md.get("content") or "").strip() if md else ""
    headings = [h.get_text(" ", strip=True) for h in soup.find_all(["h2", "h3"])]
    images = [{"src": img.get("src"), "alt": (img.get("alt") or "").strip()} for img in soup.find_all("img")]

    return dict(url=url, title=title, meta_title=title, meta_desc=meta_desc, headings=headings, images=images, text=text)


def extract_keywords_entities(text: str, top_k: int = 20) -> Dict[str, Any]:
    """Keyphrase extraction + entities."""
    try:
        kb = [k for k, _ in kw_model.extract_keywords(text, keyphrase_ngram_range=(1, 3), stop_words="english", top_n=top_k)]
    except Exception:
        kb = []
    try:
        yk = [k for k, _ in yake.KeywordExtractor(top=top_k).extract_keywords(text)]
    except Exception:
        yk = []

    merged = list(dict.fromkeys(kb + yk))
    primary = merged[0] if merged else ""

    doc = nlp(text[:200000])
    ents = sorted(set([e.text for e in doc.ents]))

    return {"primary_keyword": primary, "secondary_keywords": merged[1:12], "entities": ents}


@st.cache_data(show_spinner=False, ttl=3600)
def serper_search(query: str, api_key: str, num: int = 10, gl: str = "us", hl: str = "en") -> Dict[str, Any]:
    r = requests.post(
        "https://google.serper.dev/search",
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        json={"q": query, "num": num, "gl": gl, "hl": hl},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def top_competitors(primary_kw: str, api_key: str, exclude_domain: str = None, num: int = 5, gl: str = "us", hl: str = "en") -> List[Dict[str, Any]]:
    data = serper_search(primary_kw, api_key, num=num + 5, gl=gl, hl=hl)
    out = []
    for it in data.get("organic", []):
        link = it.get("link")
        if not link:
            continue
        if exclude_domain and exclude_domain in link:
            continue
        out.append({"title": it.get("title"), "url": link})
        if len(out) == num:
            break
    return out


def forum_questions(primary_kw: str, api_key: str, extras: List[str] = None, num: int = 12, gl: str = "us", hl: str = "en") -> List[str]:
    q = f'site:reddit.com OR site:quora.com "{primary_kw}" "?"'
    if extras:
        q += " " + " ".join(f'"{x}"' for x in extras[:3])
    data = serper_search(q, api_key, num=num, gl=gl, hl=hl)
    qs = []
    for it in data.get("organic", []):
        t = (it.get("title") or "").strip()
        if "?" in t and 10 < len(t) < 140:
            qs.append(t.strip(" »|"))
    # dedupe & take 5
    seen, out = set(), []
    for x in qs:
        xl = x.lower()
        if xl in seen:
            continue
        seen.add(xl)
        out.append(x)
        if len(out) == 5:
            break
    return out


@st.cache_data(show_spinner=False, ttl=3600)
def fetch_sitemap_blog_urls(site_base: str) -> List[str]:
    try:
        sm = requests.get(site_base.rstrip("/") + "/sitemap.xml", timeout=20).text
        urls = re.findall(r"<loc>(.*?)</loc>", sm)
        return [u for u in urls if "/blog/" in u]
    except Exception:
        return []


def suggest_internal_links(source_url: str, source_text: str, candidates: List[str], n: int = 6) -> List[Dict[str, Any]]:
    if not candidates:
        return []
    src_vec = embed_model.encode(source_text[:5000], normalize_embeddings=True)
    cand_labels = [c.split("/")[-1].replace("-", " ") for c in candidates]
    cand_vecs = embed_model.encode(cand_labels, normalize_embeddings=True)
    sims = util.cos_sim(src_vec, cand_vecs).tolist()[0]
    paired = [(u, s) for u, s in zip(candidates, sims) if u != source_url]
    ranked = sorted(paired, key=lambda x: x[1], reverse=True)[:n]
    return [{"target_url": u, "score": float(s)} for u, s in ranked]


def openai_chat(messages: List[Dict[str, str]], api_key: str, model: str = "gpt-4.1-mini", temperature: float = 0.2) -> str:
    r = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model, "messages": messages, "temperature": temperature},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def generate_draft(pack: Dict[str, Any], openai_key: str, model: str = "gpt-4.1-mini") -> Dict[str, Any]:
    src, kw = pack["source"], pack["keywords"]
    sys = "You are an SEO editor for a mental health SaaS blog. Use clear, neutral, factual language. Do not give medical advice."
    user = f"""
    Topic URL: {src['url']}
    Current H2s: {src['headings'][:10]}
    Primary keyword: {kw['primary_keyword']}
    Secondary keywords: {kw['secondary_keywords']}
    Entities: {kw['entities'][:20]}
    Competitors: {[c['url'] for c in pack['competitors']]}
    Forum questions: {pack['faqs_seed']}
    Internal link candidates: {pack['internal_suggestions']}

    Write an optimized draft:
    - Meta Title (<=60 chars), Meta Description (<=155 chars)
    - H2 outline covering definitions, signs/symptoms or components (if relevant), ICD/scale specifics (if relevant), documentation/treatment context, best practices.
    - 700–900 words body.
    - Inline suggestions for internal links as: [INTERNAL: anchor -> URL] (2–4)
    - 3–5 reputable external citations list as: [EXTERNAL: Title -> URL]
    - 5 FAQs with 2–4 sentence answers.

    Return strict JSON with keys:
    meta_title, meta_description, h2s (array), body, faqs (list of { '{' }q,a{ '}' }),
    internal_links (list of { '{' }anchor,url{ '}' }), external_links (list of { '{' }title,url{ '}' }).
    """

    content = openai_chat([
        {"role": "system", "content": sys},
        {"role": "user", "content": textwrap.dedent(user)}
    ], api_key=openai_key, model=model)

    # try parsing JSON within the response
    try:
        start = content.index("{")
        end = content.rindex("}") + 1
        return json.loads(content[start:end])
    except Exception:
        return {"raw": content}


def to_markdown(draft: Dict[str, Any]) -> str:
    if not isinstance(draft, dict):
        return f"# Draft (raw)\n\n{draft}"
    md = []
    if draft.get("meta_title"): md += [f"# {draft['meta_title']}", ""]
    if draft.get("meta_description"): md += [f"> {draft['meta_description']}", ""]
    for h in draft.get("h2s", []): md += [f"## {h}", ""]
    md += [draft.get("body", ""), ""]
    if draft.get("faqs"):
        md += ["## FAQs"]
        for qa in draft["faqs"]:
            md += [f"**Q:** {qa.get('q','')}", f"**A:** {qa.get('a','')}", ""]
    if draft.get("internal_links"):
        md += ["## Suggested Internal Links"]
        for ln in draft["internal_links"]:
            md += [f"- **{ln.get('anchor','')}** → {ln.get('url','')}"]
    if draft.get("external_links"):
        md += ["## Suggested External Links"]
        for ln in draft["external_links"]:
            md += [f"- {ln.get('title','')} → {ln.get('url','')}"]
    return "\n".join(md)


# ---------------------------
# UI
# ---------------------------
with st.sidebar:
    st.header("Settings")
    openai_key = st.text_input("OpenAI API Key", type="password")
    serper_key = st.text_input("Serper API Key", type="password")
    site_base = st.text_input("Site Base (for internal links)", value="https://www.mentalyc.com")
    model = st.selectbox("OpenAI Model", ["gpt-4.1", "gpt-4.1-mini"], index=1)
    gl = st.selectbox("Search Country (gl)", ["us", "in", "au", "gb", "ca"], index=0)
    hl = st.selectbox("Search Lang (hl)", ["en"], index=0)

st.title("SEO Optimizer — Mentalyc Blog")
st.write("Paste one URL per line. Click **Run** to get a full optimization pack.")

urls_text = st.text_area("Target URLs", height=160, value="\n".join([
    "https://www.mentalyc.com/blog/psychological-assessment-report",
    "https://www.mentalyc.com/blog/icd-10-code-for-depression",
    "https://www.mentalyc.com/blog/therapeutic-relationships-in-cognitive-behavioral-therapy",
]))

col_run, col_clear = st.columns([1,1])
run = col_run.button("Run")
if col_clear.button("Clear"):
    urls_text = ""

if run:
    urls = [u.strip() for u in urls_text.splitlines() if u.strip()]

    if not urls:
        st.warning("Please provide at least one URL.")
        st.stop()
    if not openai_key:
        st.warning("Please provide your OpenAI API key in the sidebar.")
        st.stop()
    if not serper_key:
        st.warning("Please provide your Serper API key in the sidebar.")
        st.stop()

    blog_index = fetch_sitemap_blog_urls(site_base)

    results = []
    progress = st.progress(0.0, text="Processing...")

    for i, url in enumerate(urls, start=1):
        st.markdown(f"### Processing: {url}")
        try:
            src = fetch_article(url)
            kw = extract_keywords_entities(src["text"]) if src.get("text") else {"primary_keyword": "", "secondary_keywords": [], "entities": []}
            comps = top_competitors(kw.get("primary_keyword", "") or src.get("title", ""), serper_key, exclude_domain="mentalyc.com", gl=gl, hl=hl)
            faqs = forum_questions(kw.get("primary_keyword", "") or src.get("title", ""), serper_key, extras=kw.get("secondary_keywords", []), gl=gl, hl=hl)
            internals = suggest_internal_links(url, src.get("text", ""), blog_index, n=6)

            pack = {
                "source": src,
                "keywords": kw,
                "competitors": comps,
                "faqs_seed": faqs,
                "internal_suggestions": internals,
            }

            draft = generate_draft(pack, openai_key, model=model)
            pack["draft"] = draft

            # quick lint
            d = draft if isinstance(draft, dict) else {}
            pack["lint"] = {
                "title_len": len(d.get("meta_title", "")),
                "desc_len": len(d.get("meta_description", "")),
                "missing_image_alts": sum(1 for img in src.get("images", []) if not (img.get("alt")))
            }

            results.append(pack)

            # Show UI blocks per URL
            with st.expander(f"Result: {url}", expanded=True):
                c1, c2, c3 = st.columns([2, 2, 1])
                c1.json({"keywords": kw, "faqs_seed": faqs})
                c2.json({"competitors": comps, "internal": internals, "lint": pack["lint"]})

                # Preview draft
                if isinstance(draft, dict):
                    st.subheader("Draft Preview")
                    st.markdown(to_markdown(draft))
                else:
                    st.subheader("Draft (raw)")
                    st.code(draft)

                # Downloads
                slug = url.rstrip("/").split("/")[-1]
                json_bytes = io.BytesIO(json.dumps(pack, ensure_ascii=False, indent=2).encode("utf-8"))
                st.download_button(
                    label="Download JSON",
                    data=json_bytes,
                    file_name=f"{slug}.json",
                    mime="application/json",
                )

                md_bytes = io.BytesIO(to_markdown(draft).encode("utf-8"))
                st.download_button(
                    label="Download Markdown",
                    data=md_bytes,
                    file_name=f"{slug}.md",
                    mime="text/markdown",
                )

        except Exception as e:
            st.error(f"Error on {url}: {e}")
        finally:
            progress.progress(i / max(1, len(urls)), text=f"Processed {i}/{len(urls)}")

    st.success("Done!")

# End of app.py
