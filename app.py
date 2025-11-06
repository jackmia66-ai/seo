import streamlit as st
import requests
from modules.fetch import fetch_article
from modules.nlp import extract_keywords_entities
from modules.serp import top_competitors
from modules.forums import forum_questions
from modules.internal_links import suggest_internal_links
from modules.ai_writer import generate_draft

st.set_page_config(page_title="Mentalyc SEO Optimizer", layout="wide")

st.title("🧠 Mentalyc SEO Optimization Assistant")
st.write("Enter blog URLs to automatically analyze & optimize content.")

openai_key = st.sidebar.text_input("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", type="password")
serper_key = st.sidebar.text_input("5cb974df5481dfb855ca9c1878a7a1f71c2bd3836f6e72761316fba01bac7c8c", type="password")
site_base = st.sidebar.text_input("Site Base URL", value="https://www.mentalyc.com")

urls_input = st.text_area("Enter URLs (one per line)")
run = st.button("Run Optimization")

if run:
    urls = [u.strip() for u in urls_input.splitlines() if u.strip()]
    for url in urls:
        st.subheader(f"🔍 Processing: {url}")
        src = fetch_article(url)
        kw = extract_keywords_entities(src["text"])
        comps = top_competitors(kw["primary_keyword"], serper_key, exclude_domain="mentalyc.com")
        faqs = forum_questions(kw["primary_keyword"], serper_key, extras=kw["secondary_keywords"])
        internals = suggest_internal_links(url, src["text"], [url])

        pack = {
            "source": src,
            "keywords": kw,
            "competitors": comps,
            "faqs_seed": faqs,
            "internal_suggestions": internals
        }

        draft = generate_draft(pack, openai_key)

        st.write("### 🗝 Keywords & Entities")
        st.json(kw)

        st.write("### ❓ Real User FAQs")
        st.json(faqs)

        st.write("### 🔗 Internal Link Suggestions")
        st.json(internals)

        st.write("### ✍️ Generated SEO Draft Preview")
        st.markdown(draft.get("body", "No body generated"))
