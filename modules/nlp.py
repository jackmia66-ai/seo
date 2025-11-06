import spacy, yake
from keybert import KeyBERT
_nlp = spacy.load("en_core_web_sm")
_kw = KeyBERT()

def extract_keywords_entities(text, top_k=20):
    keybert = [k for k,_ in _kw.extract_keywords(text, keyphrase_ngram_range=(1,3), stop_words="english", top_n=top_k)]
    kw_yake = [k for k,_ in yake.KeywordExtractor(top=top_k).extract_keywords(text)]
    merged = list(dict.fromkeys(keybert + kw_yake))
    primary = merged[0] if merged else ""
    doc = _nlp(text[:200000])
    ents = sorted(set([e.text for e in doc.ents]))
    return {"primary_keyword": primary, "secondary_keywords": merged[1:11], "entities": ents}

