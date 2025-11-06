import os, requests

def _serper(q, num=5):
    r = requests.post("https://google.serper.dev/search",
        headers={"X-API-KEY": os.getenv("SERPER_API_KEY"), "Content-Type":"application/json"},
        json={"q": q, "num": num, "gl":"us", "hl":"en"})
    r.raise_for_status(); return r.json()

def top_competitors(primary_kw, exclude_domain=None, num=5):
    q = primary_kw
    data = _serper(q, num=num+3)
    items = []
    for it in data.get("organic", []):
        link = it.get("link")
        if not link: continue
        if exclude_domain and exclude_domain in link: continue
        items.append({"title": it.get("title"), "url": link})
        if len(items) == num: break
    return items

def forum_questions(primary_kw, extras=None, num=12):
    query = f'site:reddit.com OR site:quora.com "{primary_kw}" "?"'
    if extras: query += " " + " ".join(f'"{x}"' for x in extras[:3])
    data = _serper(query, num=num)
    qs = []
    for it in data.get("organic", []):
        t = (it.get("title") or "")
        if "?" in t and len(t) < 140:
            qs.append(t.strip(" »|"))
    # de-dup & top 5
    seen, out = set(), []
    for q in qs:
        if q.lower() in seen: continue
        seen.add(q.lower()); out.append(q)
        if len(out) == 5: break
    return out

