# -*- coding: utf-8 -*-
"""Kumpulkan dataset foto ikan dari Wikimedia Commons utk training VISMOK.

- Sumber: commons.wikimedia.org API (gambar bebas-lisensi).
- Output: datasets\\<class_name>\\*.jpg (resolusi ~1024px).
- Aman diulang: file/URL yang sudah diunduh dilewati.
- Filter: hanya JPEG/PNG, lebar >= 500px, bukan diagram/peta/logo.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "datasets")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) VismokDatasetBot/1.0"

# target jumlah foto per kelas (dengan headroom utk filter auto-label nanti)
TARGETS = {
    "guppy": 240, "koi": 420, "cupang": 360, "molly": 260,
    "komet": 360, "chana": 420, "arwana": 240, "ikan_mas": 420,
}

# query pencarian per kelas (Wikimedia Commons, bahasa Inggris paling kaya)
QUERIES = {
    "guppy": ["guppy fish", "Poecilia reticulata aquarium", "guppy male fish",
              "Poecilia reticulata", "guppy breeding aquarium",
              "guppy colorful fish", "guppy tank", "Poecilia reticulata male"],
    "koi":   ["koi carp fish", "koi fish pond", "Cyprinus rubrofuscus koi",
              "nishikigoi", "koi garden pond", "kohaku koi fish",
              "showa koi fish", "butterfly koi fish", "koi fish tank",
              "asagi koi fish", "koi carp closeup"],
    "cupang": ["Betta splendens", "siamese fighting fish betta",
               "betta fish aquarium", "halfmoon betta fish",
               "Betta splendens male", "plakat betta fish",
               "betta splendens female", "crowntail betta",
               "veiltail betta fish", "betta fish bowl",
               "betta fish red blue"],
    "molly": ["Poecilia sphenops", "Poecilia latipinna fish",
              "molly fish aquarium", "Poecilia velifera",
              "sailfin molly", "black molly fish aquarium",
              "Poecilia formosa", "shortfin molly fish",
              "Poecilia mexicana", "molly poecilia tank"],
    "komet": ["comet goldfish", "goldfish swimming", "Carassius auratus",
              "goldfish aquarium", "common goldfish fish",
              "goldfish pond", "orange goldfish fish",
              "goldfish closeup", "sarasa goldfish",
              "shubunkin goldfish"],
    "chana": ["Channa striata", "Channa micropeltes fish",
              "snakehead fish", "Channa argus", "Channa marulius",
              "giant snakehead fish", "Channa asiatica",
              "Channa punctata", "northern snakehead fish",
              "Channa gachua", "snakehead fish aquarium",
              "snakehead fish closeup", "Channa barca",
              "snakehead fish head", "Channa andreae"],
    "arwana": ["arowana fish", "Scleropages formosus", "Asian arowana fish",
               "arowana aquarium", "Scleropages jardinii",
               "silver arowana fish", "Osteoglossum bicirrhosum",
               "arowana tank", "Scleropages leichardti",
               "golden arowana fish"],
    "ikan_mas": ["common carp fish", "Cyprinus carpio", "crucian carp fish",
                 "Carassius carassius", "mirror carp fish",
                 "common carp pond", "carp fish fishing",
                 "wild common carp", "koi × goldfish hybrid",
                 "Carassius auratus gibelio", "carp fish closeup",
                 "prussian carp fish"],
}

BADWORDS = ("map", "diagram", "logo", "icon", "distribution", "skeleton",
            "skull", "drawing", "illustration", "engraving", "statue",
            "stamp", "coin", "silk", "painting", "embroidery", "artwork")

HDRS = {"User-Agent": UA}


def api_search(query, limit=50):
    """Cari file gambar di Wikimedia Commons. Return list dict
    {title, thumburl, width, height, mime}."""
    params = {
        "action": "query", "format": "json",
        "generator": "search", "gsrsearch": query,
        "gsrnamespace": 6, "gsrlimit": str(limit),
        "prop": "imageinfo", "iiprop": "url|size|mime",
        "iiurlwidth": "1024",
    }
    url = ("https://commons.wikimedia.org/w/api.php?"
           + urllib.parse.urlencode(params))
    data = None
    for attempt in range(4):          # retry dgn backoff saat 429
        req = urllib.request.Request(url, headers=HDRS)
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                data = json.load(r)
            break
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 3:
                wait = 20 * (attempt + 1)
                print(f"  429 rate-limit [{query}] → tunggu {wait}s")
                time.sleep(wait)
                continue
            print(f"  !! API gagal [{query}]: {e}")
            return []
        except Exception as e:
            print(f"  !! API gagal [{query}]: {e}")
            return []
    if data is None:
        return []
    out = []
    for page in (data.get("query", {}).get("pages") or {}).values():
        ii = (page.get("imageinfo") or [None])[0]
        if not ii:
            continue
        mime = ii.get("mime", "")
        if mime not in ("image/jpeg", "image/png"):
            continue
        wd, ht = int(ii.get("width") or 0), int(ii.get("height") or 0)
        if wd < 500 or ht < 300:
            continue
        thumb = ii.get("thumburl") or ii.get("url")
        if not thumb:
            continue
        title = page.get("title", "").lower()
        if any(b in title for b in BADWORDS):
            continue
        out.append({"title": page["title"], "url": thumb,
                    "w": wd, "h": ht})
    return out


def download(job):
    url, dst = job
    for attempt in range(3):          # retry unduhan
        try:
            req = urllib.request.Request(url, headers=HDRS)
            with urllib.request.urlopen(req, timeout=40) as r:
                data = r.read()
            if len(data) < 15000:            # < 15 KB = thumbnail rusak/toy
                return False
            with open(dst, "wb") as f:
                f.write(data)
            return True
        except Exception:
            time.sleep(1.5 * (attempt + 1))
    return False


def collect_class(cls, queries, target):
    out_dir = os.path.join(OUT, cls)
    os.makedirs(out_dir, exist_ok=True)
    # kumpulkan kandidat dari semua query (dedup by title)
    seen, cands = set(), []
    for q in queries:
        for it in api_search(q):
            if it["title"] in seen:
                continue
            seen.add(it["title"])
            cands.append(it)
        time.sleep(3.0)               # sopan ke server (hindari 429)
    # yang sudah ada di folder = skip
    have = {fn.rsplit(".", 1)[0] for fn in os.listdir(out_dir)}
    need = target - len(have)
    if need <= 0:
        print(f"[{cls}] sudah cukup: {len(have)} foto")
        return len(have)
    jobs, made = [], 0
    idx = len(have)
    for it in cands:
        if made >= need:
            break
        safe = "".join(c if c.isalnum() or c in "-_" else "_"
                       for c in it["title"].replace("File:", ""))[:80]
        if safe in have:
            continue
        fn = f"{safe}_{idx}.jpg"
        idx += 1
        jobs.append((it["url"], os.path.join(out_dir, fn)))
        made += 1
    ok = 0
    with ThreadPoolExecutor(max_workers=5) as ex:
        for success in ex.map(download, jobs):
            if success:
                ok += 1
    # buang file gagal (kosong)
    for fn in os.listdir(out_dir):
        fp = os.path.join(out_dir, fn)
        if os.path.getsize(fp) < 15000:
            os.remove(fp)
    total = len(os.listdir(out_dir))
    print(f"[{cls}] terunduh {ok}/{len(jobs)} → total {total}/{target}")
    return total


def main():
    grand = 0
    for cls, queries in QUERIES.items():
        n = collect_class(cls, queries, TARGETS[cls])
        grand += n
    print(f"\n=== TOTAL FOTO DATASET: {grand} ===")
    print("Lanjut: python tools\\autolabel_dataset.py")


if __name__ == "__main__":
    main()
