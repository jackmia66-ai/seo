# modules/nlp.py
import spacy
import yake
from keybert import KeyBERT

_nlp_model = None
_kw_model = None

def _get_nlp():
    """Lazy-load spaCy model with safe fallbacks."""
    global _nlp_model
    if _nlp_model is not None:
        return _nlp_model
    try:
        _nlp_model = spacy.load("en_core_web_sm")
    except OSError:
        try:
            import spacy.cli
            spacy.cli.download("en_core_web_sm")
            _nlp_model = spacy.load("en_core_web_sm")
        except Exception:
            _nlp_model = spacy.blank("en")  # last resort
    return _nlp_model

def _get_kw():
    """Lazy-load KeyBERT (fast)."""
    global _kw_model
    if _kw_model is None:
        _kw_model = KeyBERT()
    return _kw_model

def extract_keywords_entities(text: str, top_k: int = 20):
    """Return primary + secondary keywords and entities from text."""
    nlp = _get_nlp()
    kw_model = _get_kw()

    try:
        kb = [k for k, _ in kw_model.extract_keywords(
            text,
            keyphrase_ngram_range=(1, 3),
            stop_words="english",
            top_n=top_k
        )]
    except Exception:
        kb = []

    try:
        yk = [k for k, _ in yake.KeywordExtractor(top=top_k).extract_keywords(text)]
    except Exception:
        yk = []

    merged = list(dict.fromkeys(kb + yk))
    primary = merged[0] if merged else ""

    try:
        doc = nlp(text[:200000])
        ents = sorted(set([e.text for e in doc.ents]))
    except Exception:
        ents = []

    return {
        "primary_keyword": primary,
        "secondary_keywords": merged[1:12],
        "entities": ents
    }
