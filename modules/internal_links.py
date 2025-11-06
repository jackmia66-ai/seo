# modules/internal_links.py
import re
import requests

_embed = None
_has_st = None  # cache whether sentence-transformers is available

def _maybe_get_embed_model():
    """Lazy optional import of sentence-transformers.
    Returns a model or None if the package isn't installed.
    """
    global _embed, _has_st
    if _has_st is False:
        return None
    if _embed is not None:
        return _embed
    try:
        from sentence_transformers import SentenceTransformer
        try:
            _embed = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception:
            _embed = SentenceTransformer("paraphrase-MiniLM-L6-v2")
        _has_st = True
        return _embed
    except Exception:
        _has_st = False
        return None

def build_site_index(site_base: str):
    """Return list of blog URLs from sitemap.xml (best-effort)."""
    try:
        sm = requests.get(site_base.rstrip("/") + "/sitemap.xml", timeout=20).text
        urls = re.findall(r"<loc>(.*?)</loc>", sm)
        return [u for u in urls if "/blog/" in u]
    except Exception:
        return []

def suggest_internal_links(source_url: str, source_text: str, candidates: list[str], n: int = 6):
    """Suggest internal links.
    If embeddings available → semantic ranking.
    Else → cheap slug-similarity fallback.
    """
    if not candidates:
        return []

    model = _maybe_get_embed_model()
    if model is None:
        # Fallback: rank by simple slug similarity
        import difflib
        src_slug = source_url.rstrip("/").split("/")[-1].replace("-", " ")
        scored = []
        for u in candidates:
            if u == source_url:
                continue
            slug = u.rstrip("/").split("/")[-1].replace("-", " ")
            score = difflib.SequenceMatcher(None, src_slug, slug).ratio()
            scored.append((u, score))
        ranked = sorted(scored, key=lambda x: x[1], reverse=True)[:n]
        return [{"target_url": u, "score": float(s)} for u, s in ranked]

    # Semantic ranking with embeddings (only if package present)
    from sentence_transformers import util
    src_vec = model.encode(source_text[:5000] if source_text else "", normalize_embeddings=True)
    cand_labels = [c.split("/")[-1].replace("-", " ") for c in candidates]
    cand_vecs = model.encode(cand_labels, normalize_embeddings=True)
    sims = util.cos_sim(src_vec, cand_vecs).tolist()[0]
    pairs = [(u, s) for u, s in zip(candidates, sims) if u != source_url]
    ranked = sorted(pairs, key=lambda x: x[1], reverse=True)[:n]
    return [{"target_url": u, "score": float(s)} for u, s in ranked]
