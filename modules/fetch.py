import requests
from readabilipy import simple_json_from_html_string
from bs4 import BeautifulSoup

def fetch_article(url: str):
    r = requests.get(url, timeout=30, headers={"User-Agent":"Mozilla/5.0"})
    r.raise_for_status()
    html = r.text
    sj = simple_json_from_html_string(html, use_readability=True)
    text = " ".join((b["text"] for b in sj.get("content", []) if "text" in b)).strip()
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.text.strip() if soup.title else ""
    meta_title = title
    meta_desc = ""
    md = soup.find("meta", attrs={"name":"description"}) or soup.find("meta", attrs={"property":"og:description"})
    if md: meta_desc = (md.get("content") or "").strip()
    h2 = [h.get_text(" ", strip=True) for h in soup.find_all(["h2","h3"])]
    imgs = [{"src":i.get("src"), "alt":(i.get("alt") or "").strip()} for i in soup.find_all("img")]
    return {"url":url, "title":title, "meta_title":meta_title, "meta_desc":meta_desc, "headings":h2, "images":imgs, "text":text}

