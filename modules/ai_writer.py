import os, requests, textwrap, json

def _openai_chat(messages, model="gpt-4.1-mini"):
    r = requests.post("https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}", "Content-Type":"application/json"},
        json={"model": model, "messages": messages, "temperature": 0.2})
    r.raise_for_status(); return r.json()["choices"][0]["message"]["content"]

def generate_draft(pack):
    src = pack["source"]; kw = pack["keywords"]
    comps = pack["competitors"]; faqs = pack["faqs_seed"]; internals = pack["internal_suggestions"]

    sys = "You are an SEO editor for a mental health SaaS blog. Write clear, factual, non-clinical-advice content."
    user = f"""
Topic URL: {src['url']}
Current H2s: {src['headings'][:10]}
Primary keyword: {kw['primary_keyword']}
Secondary keywords: {kw['secondary_keywords']}
Entities: {kw['entities'][:20]}
Competitors (topical reference): {[c['url'] for c in comps]}
User questions (forums): {faqs}
Internal link candidates: {internals}

Write an optimized draft:
- Meta Title (<=60 chars) and Meta Description (<=155 chars)
- H2 outline covering: definitions, symptoms/signs (if relevant), coding/scale details (if ICD/scale page), treatment/therapy context, documentation tips, FAQs.
- 700–900 words body, neutral tone, plain language, no promises or medical advice.
- Insert [INTERNAL: anchor -> URL] suggestions where natural (2–4).
- Suggest 3–5 external citations (NIH/NIMH/WHO/APA/Wikipedia topic pages) in a list as [EXTERNAL: Title -> URL].
- Provide 5 FAQs with short answers (2–4 sentences).
Return as strict JSON with keys:
meta_title, meta_description, h2s, body, faqs (list of objects q,a),
internal_links (list anchor,url), external_links (list title,url).
"""
    content = _openai_chat([{"role":"system","content":sys},{"role":"user","content":textwrap.dedent(user)}])
    # If model returns markdown, attempt to parse JSON block:
    try:
        start = content.index("{"); end = content.rindex("}")+1
        return json.loads(content[start:end])
    except Exception:
        return {"raw": content}

