import requests, re
from sentence_transformers import SentenceTransformer, util
_model = SentenceTransformer("all-MiniLM-L6-v2")

def build_site_index(site_base):
    # best: load sitemap.xml of /blog; fallback: crawl /blog
    # here we assume /sitemap.xml exists; if not, accept a CSV
    urls = []
    try:
        sm = requests.get(site_base + "/sitemap.xml", timeout=20).text
        urls = re.findall(r"<loc>(.*?)</loc>", sm)
        urls = [u for u in urls if "/blog/" in u]
    except: pass
    return [{"url":u} for u in urls]

def suggest_internal_links(source_url, source_text, site_index, n=6):
    if not site_index: return []
    src = _model.encode(source_text[:5000], normalize_embeddings=True)
    candidates = []
    for p in site_index:
        if p["url"] == source_url: continue
        candidates.append(p["url"])
    # Encode candidates roughly by slug (cheap); for real use fetch titles/content once & cache
    embs = _model.encode([c.split("/")[-1].replace("-", " ") for c in candidates], normalize_embeddings=True)
    sims = util.cos_sim(src, embs).tolist()[0]
    ranked = sorted(zip(candidates, sims), key=lambda x: x[1], reverse=True)[:n]
    return [{"target_url":u, "score":float(s)} for u,s in ranked]

