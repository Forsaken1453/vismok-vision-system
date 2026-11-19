"""Unduh gambar referensi ikan & produk pakan dari Wikipedia (REST summary).

Output: assets/img/fish/<class_name>.jpg  &  assets/img/products/*.jpg
Aman diulang (file yang sudah ada dilewati).
"""
import json
import os
import sys
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_FISH = os.path.join(BASE, "assets", "img", "fish")
OUT_PROD = os.path.join(BASE, "assets", "img", "products")
os.makedirs(OUT_FISH, exist_ok=True)
os.makedirs(OUT_PROD, exist_ok=True)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) VismokDataset/1.0")

FISH_PAGES = {
    "guppy":    ["Guppy", "Poecilia reticulata"],
    "koi":      ["Koi", "Cyprinus rubrofuscus"],
    "cupang":   ["Siamese fighting fish", "Betta splendens"],
    "molly":    ["Poecilia sphenops", "Molly (fish)", "Poecilia latipinna"],
    "komet":    ["Comet (goldfish)", "Goldfish"],
    "chana":    ["Channa micropeltes", "Channa striata", "Snakehead (fish)"],
    "arwana":   ["Asian arowana", "Arowana", "Scleropages formosus"],
    "ikan_mas": ["Common carp", "Cyprinus carpio", "Goldfish"],
}

PRODUCT_PAGES = {
    "pellet":  ["Fish food", "Pellet food"],
    "serbuk":  ["Fish food", "Flake food"],
}


def fetch_summary(title):
    url = ("https://en.wikipedia.org/api/rest_v1/page/summary/"
           + title.replace(" ", "_"))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.load(r)
    except Exception as e:
        return {"error": str(e)}


def download(src_url, dst):
    try:
        req = urllib.request.Request(src_url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=25) as r, open(dst, "wb") as f:
            f.write(r.read())
        return True
    except Exception as e:
        print(f"    gagal unduh: {e}")
        return False


def get_image(pages, out_path):
    for page in pages:
        s = fetch_summary(page)
        if "error" in s:
            print(f"  [{page}] summary gagal: {s['error']}")
            continue
        thumb = ((s.get("originalimage") or {}).get("source")
                 or (s.get("thumbnail") or {}).get("source"))
        if not thumb:
            print(f"  [{page}] tidak punya gambar")
            continue
        print(f"  [{page}] -> {out_path}")
        if download(thumb, out_path):
            return True
    return False


def main():
    ok_fish, ok_prod = 0, 0
    print("== FISH ==")
    for cls, pages in FISH_PAGES.items():
        dst = os.path.join(OUT_FISH, cls + ".jpg")
        if os.path.exists(dst) and os.path.getsize(dst) > 10000:
            print(f"  {cls}: sudah ada, skip")
            ok_fish += 1
            continue
        if get_image(pages, dst):
            ok_fish += 1
    print("== PRODUCTS ==")
    for key, pages in PRODUCT_PAGES.items():
        dst = os.path.join(OUT_PROD, key + ".jpg")
        if os.path.exists(dst) and os.path.getsize(dst) > 10000:
            print(f"  {key}: sudah ada, skip")
            ok_prod += 1
            continue
        if get_image(pages, dst):
            ok_prod += 1
    print(f"\nSELESAI: fish {ok_fish}/8, products {ok_prod}/2")
    sys.exit(0 if ok_fish == 8 and ok_prod == 2 else 2)


if __name__ == "__main__":
    main()
