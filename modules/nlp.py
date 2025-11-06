import spacy
import yake
from keybert import KeyBERT

# ---- Safe spaCy loader ----
def load_spacy_model():
    try:
        return spacy.load("en_core_web_sm")
    except OSError:
        # Try auto-download (works locally, sometimes cloud)
        try:
            import spacy.cli
            spacy.cli.download("en_core_web_sm")
            return spacy.load("en_core_web_sm")
        except Exception:
            # Last fallback: blank English (still works for keyword extraction)
            return spacy.blank("en")

_nlp = load_spacy_model()
_kw = KeyBERT()

def extract_keywords_entities(text, top_k=20):
    # KeyBERT + YAKE combo for main + secondary keywords
    keybert = [k for k,_ in _kw.extract_keywords(text, keyphrase_ngram_range=(1,3), stop_words="english", top_n=top_k)]
    kw_yake = [k for k,_ in yake.KeywordExtractor(top=top_k).extract_keywords(text)]

    merged = list(dict.fromkeys(keybert + kw_yake))
    primary = merged[0] if merged else ""

    doc = _nlp(text[:200000])
    ents = sorted(set([e.text for e in doc.ents]))

    return {
        "primary_keyword": primary,
        "secondary_keywords": merged[1:12],
        "entities": ents
    }
