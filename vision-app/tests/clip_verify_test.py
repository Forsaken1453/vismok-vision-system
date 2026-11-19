# -*- coding: utf-8 -*-
"""Uji verifikasi jenis pakai CLIP zero-shot (whole-image)."""
import glob
import sys

import torch
import clip

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
model, preprocess = clip.load("ViT-B/32", device=DEVICE)

SPECIES = {
    "guppy": "a photo of a guppy, a small colorful tropical aquarium fish",
    "koi": "a photo of a koi carp, an ornamental carp with white red orange patches",
    "cupang": "a photo of a betta fish (siamese fighting fish) with large flowing fins",
    "molly": "a photo of a molly fish, a plain tropical livebearer fish",
    "komet": "a photo of a goldfish, orange comet goldfish",
    "chana": "a photo of a snakehead fish, an elongated predatory fish with a long dorsal fin",
    "arwana": "a photo of an arowana, a large long bony-tongue fish with big scales",
    "ikan_mas": "a photo of a common carp, a dull grey bronze carp fish",
}
names = list(SPECIES.keys())
prompts = [SPECIES[c] for c in names]
text = clip.tokenize(prompts).to(DEVICE)
with torch.no_grad():
    tfeat = model.encode_text(text)
    tfeat = tfeat / tfeat.norm(dim=-1, keepdim=True)

total = 0
match = 0
for ci, cls in enumerate(names):
    imgs = sorted(glob.glob(rf"D:\Leviathan\datasets\{cls}\*.jpg"))
    sample = imgs[::max(1, len(imgs) // 8)][:8]
    hits = 0
    from PIL import Image
    for p in sample:
        img = preprocess(Image.open(p).convert("RGB")).unsqueeze(0).to(DEVICE)
        with torch.no_grad():
            feat = model.encode_image(img)
            feat = feat / feat.norm(dim=-1, keepdim=True)
            sim = (feat @ tfeat.T).softmax(dim=-1)[0]
        pred = names[int(sim.argmax().item())]
        top3 = [(names[i], round(float(sim[i]), 2))
                for i in sim.argsort(descending=True)[:3]]
        total += 1
        ok = pred == cls
        match += ok
        hits += ok
        print(f"  {cls:9s} -> {pred:9s} {'OK' if ok else 'X'}  top3={top3}")
    print(f"[{cls}] {hits}/{len(sample)}")
print(f"\nMATCH TOTAL: {match}/{total}")
