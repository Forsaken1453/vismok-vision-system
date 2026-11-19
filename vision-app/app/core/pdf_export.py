"""Ekspor kwitansi rekomendasi pakan & perawatan ke PDF (v4).

Desain kwitansi A5: header brand, info deteksi + snapshot, tabel
keranjang belanja (jumlah x harga = subtotal), tips perawatan, footer.

JAMINAN ANTI-BERANTAKAN (v4):
- SEMUA teks digambar dengan setPen warna eksplisit (tidak ada lagi
  pen "bocor" bikin tulisan gelap/timbul).
- Semua kotak teks diukur dari QFontMetricsF font yang sama; teks
  satu-baris di-AUTOFIT (dikecilkan) bila tidak muat -> tidak pernah
  terpotong; teks panjang di-WRAP (multi-baris) dengan tinggi baris
  dihitung dinamis -> tidak pernah tumpang tindih.
- Kolom harga/subtotal lebih lebar (Rp xxx.xxx Orbitron muat).
"""
import datetime
import os

from PySide6.QtCore import Qt, QMarginsF, QRectF
from PySide6.QtGui import (QPdfWriter, QPainter, QColor, QFont, QPageSize,
                           QImage, QFontMetricsF, QPageLayout)

from app.config import EXPORT_DIR
from app.ui.fonts import FAMILY

ACCENT = QColor("#22D3EE")
ACCENT_DARK = QColor("#0E7490")
INK = QColor("#0F172A")
SUB_INK = QColor("#334E63")     # sub-teks: cukup gelap agar terbaca
MUTED_INK = QColor("#5A6B7E")
LINE_INK = QColor("#CBD5E1")
NAVY = QColor("#0B1B2B")
HEADER_SUB = QColor("#BFE9F5")  # teks kecil di band navy (terang!)

MARGIN = 44.0


def _fmt_rp(v):
    return "Rp {:,.0f}".format(float(v)).replace(",", ".")


def _font(display=True, size=9, bold=False):
    fam = FAMILY.get("display", "Segoe UI") if display else \
        FAMILY.get("body", "Segoe UI")
    f = QFont(fam, size)
    f.setBold(bold)
    return f


def export_receipt(species, conf, items, tips, store_name,
                   snapshot_path=None, out_path=None, device=None):
    """Buat PDF kwitansi. Return path file PDF.

    items: list dict rekomendasi + "qty" (int). qty 0 tidak dicetak.
    device: opsional QImage/QPaintDevice utk preview/test (tanpa file).
    """
    ts = datetime.datetime.now()
    items = [it for it in (items or []) if int(it.get("qty") or 0) > 0]
    if device is not None:
        dev = device
    else:
        if not out_path:
            safe = (species.get("class_name") or "ikan").replace("/", "-")
            out_path = os.path.join(
                EXPORT_DIR, f"kwitansi_{safe}_{ts.strftime('%Y%m%d_%H%M%S')}.pdf")
        dev = QPdfWriter(out_path)
        dev.setResolution(150)         # 150 dpi
        dev.setPageSize(QPageSize(QPageSize.A5))
        dev.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Millimeter)

    pw = dev.width()                   # px @150dpi (A5 ≈ 874 x 1240)
    page_h = dev.height()
    p = QPainter(dev)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    x = MARGIN
    w = pw - 2 * MARGIN

    # ---------- helper teks: warna selalu eksplisit + anti-terpotong ----------
    def draw(rect, f, s, color, align=Qt.AlignLeft | Qt.AlignVCenter,
             autofit=True):
        """drawText dgn pen eksplisit. Bila teks lebih lebar dari kotak,
        ukuran font dikecilkan bertahap sampai muat (tidak pernah terpotong).
        Return tinggi baris font yang terpakai."""
        size = f.pointSizeF()
        fm = QFontMetricsF(f)
        box_w = rect.width() - 4
        if autofit and fm.horizontalAdvance(s) > box_w and size > 4:
            while size > 4:
                size -= 0.5
                f2 = QFont(f)
                f2.setPointSizeF(size)
                if QFontMetricsF(f2).horizontalAdvance(s) <= box_w:
                    fm = QFontMetricsF(f2)
                    break
            else:
                f2 = f
        else:
            f2 = f
        p.setPen(color)
        p.setFont(f2)
        p.drawText(rect, align, s)
        return fm.height()

    def _wrap(text, width, fm):
        words = text.split(" ")
        lines, cur = [], ""
        for wd in words:
            trial = (cur + " " + wd).strip()
            if fm.horizontalAdvance(trial) <= width:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = wd
        if cur:
            lines.append(cur)
        return lines

    # ================= HEADER =================
    bh = 150.0
    p.fillRect(QRectF(0, 0, pw, bh), NAVY)
    p.fillRect(QRectF(0, bh, pw, 5), ACCENT)

    f_brand = _font(True, 22, True)
    h_brand = QFontMetricsF(f_brand).height()
    p.fillRect(QRectF(MARGIN, 32, 5, h_brand + 6), ACCENT)
    draw(QRectF(MARGIN + 16, 28, w - 200, h_brand + 8),
         f_brand, "VISMOK", QColor("#FFFFFF"))
    f_hsub = _font(False, 8.5)
    h_hsub = QFontMetricsF(f_hsub).height()
    draw(QRectF(MARGIN + 16, 28 + h_brand + 10, w - 200, h_hsub + 2),
         f_hsub, "ASELI  NGAWI  •  TOKO  IKAN", HEADER_SUB,
         Qt.AlignLeft | Qt.AlignTop)
    f_hk = _font(True, 10.5, True)
    draw(QRectF(MARGIN, bh - 36, w - 200,
                QFontMetricsF(f_hk).height() + 4),
         f_hk, "KWITANSI  &  REKOMENDASI  PAKAN", QColor("#FFFFFF"))

    # kanan atas: no dokumen + tanggal (TERANG agar terbaca di band navy)
    f_small = _font(False, 7.5)
    h_small = QFontMetricsF(f_small).height()
    draw(QRectF(pw - MARGIN - 250, 34, 250, h_small + 2),
         f_small, f"No.  {ts.strftime('VS/%Y%m%d/%H%M%S')}",
         HEADER_SUB, Qt.AlignRight)
    draw(QRectF(pw - MARGIN - 250, 36 + h_small, 250, h_small + 2),
         f_small, ts.strftime("%d %B %Y  •  %H:%M"),
         HEADER_SUB, Qt.AlignRight)

    # ================= INFO DETEKSI =================
    y = bh + 28
    if snapshot_path and os.path.isfile(snapshot_path):
        img = QImage(snapshot_path)
        if not img.isNull():
            isz = 118.0
            scaled = img.scaled(int(isz), int(isz), Qt.KeepAspectRatio,
                                Qt.SmoothTransformation)
            ix, iy = pw - MARGIN - isz, bh + 18
            p.drawImage(QRectF(ix, iy, isz, isz), scaled)
            p.setPen(QColor(ACCENT_DARK))
            p.drawRect(QRectF(ix, iy, isz, isz))

    info_w = w - 132
    f_lab = _font(False, 8)
    h_lab = QFontMetricsF(f_lab).height()
    draw(QRectF(x, y, info_w, h_lab + 2), f_lab, "JENIS IKAN", MUTED_INK)
    f_name = _font(True, 13, True)
    draw(QRectF(x, y + h_lab + 4, info_w, QFontMetricsF(f_name).height() + 8),
         f_name, (species.get("display_name") or "-").upper(), INK)
    ny = y + h_lab + 4 + QFontMetricsF(f_name).height() + 8

    # chip kecocokan (lebar otomatis dari isi teks)
    conf_pct = int(conf * 100) if conf else 0
    f_chip = _font(True, 9, True)
    chip_txt = f"{conf_pct}%  COCOK"
    fm_chip = QFontMetricsF(f_chip)
    chip_w = max(120.0, fm_chip.horizontalAdvance(chip_txt) + 40)
    chip_h = fm_chip.height() + 14
    chip_y = ny + 8
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#E0F7FA"))
    p.drawRoundedRect(QRectF(x, chip_y, chip_w, chip_h), 13, 13)
    draw(QRectF(x, chip_y, chip_w, chip_h), f_chip, chip_txt, ACCENT_DARK,
         Qt.AlignCenter)
    draw(QRectF(x, chip_y + chip_h + 6, info_w, h_lab + 2), f_lab,
         f"Kasir : {store_name or '-'}", SUB_INK)
    y = chip_y + chip_h + 6 + h_lab + 12

    # ================= TABEL KERANJANG =================
    f_sec = _font(True, 11, True)
    h_sec = QFontMetricsF(f_sec).height()
    draw(QRectF(x, y, w, h_sec + 2), f_sec, "KERANJANG  PAKAN", ACCENT_DARK)
    p.fillRect(QRectF(x, y + h_sec + 6, w, 1.4), ACCENT)
    y += h_sec + 18

    cols = [26, 276, 46, 128, w - 26 - 276 - 46 - 128]   # terakhir SUBTOTAL
    heads = ["#", "PRODUK", "JML", "HARGA", "SUBTOTAL"]
    f_head = _font(True, 8.5, True)
    h_head = QFontMetricsF(f_head).height()
    rh = h_head + 14
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#E0F2FE"))
    p.drawRect(QRectF(x, y, w, rh))
    cx = x
    for cwid, htxt, align in zip(
            cols, heads,
            [Qt.AlignCenter, Qt.AlignLeft, Qt.AlignCenter,
             Qt.AlignRight, Qt.AlignRight]):
        draw(QRectF(cx + 4, y, cwid - 8, rh), f_head, htxt, ACCENT_DARK,
             align | Qt.AlignVCenter, autofit=False)
        cx += cwid
    y += rh

    f_item = _font(True, 9.5, True)
    h_item = QFontMetricsF(f_item).height()
    f_sub = _font(False, 7.5)
    h_sub = QFontMetricsF(f_sub).height()
    fm_item = QFontMetricsF(f_item)
    fm_sub = QFontMetricsF(f_sub)

    total = 0.0
    for i, r in enumerate(items, 1):
        qty = int(r.get("qty") or 0)
        harga = float(r.get("harga") or 0)
        sub = harga * qty
        total += sub

        # --- teks baris, di-wrap agar tidak pernah tumpang tindih ---
        nm_lines = _wrap(str(r.get("nama", "")), cols[1] - 12, fm_item)
        s1 = f"{r.get('bentuk') or ''} {r.get('ukuran') or ''}  •  " \
             f"{r.get('protein') or 0:.0f}% protein"
        s2 = f"{r.get('frekuensi') or ''}  •  {r.get('dosis') or ''}"
        s1_lines = _wrap(s1.strip(), cols[1] - 12, fm_sub)
        s2_lines = _wrap(s2.strip(), cols[1] - 12, fm_sub)

        text_h = len(nm_lines) * h_item + \
            (len(s1_lines) + len(s2_lines)) * h_sub
        row_h = text_h + 14

        if i % 2 == 0:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#F5FBFF"))
            p.drawRect(QRectF(x, y, w, row_h))
        cx = x
        ty = y + 7
        draw(QRectF(cx, ty, cols[0], h_item), f_item, str(i), INK,
             Qt.AlignCenter, autofit=False)
        cx += cols[0]
        for ln in nm_lines:
            draw(QRectF(cx + 4, ty, cols[1] - 8, h_item + 2), f_item, ln,
                 INK, Qt.AlignLeft, autofit=False)
            ty += h_item
        for ln in s1_lines:
            draw(QRectF(cx + 4, ty, cols[1] - 8, h_sub + 2), f_sub, ln,
                 SUB_INK, Qt.AlignLeft, autofit=False)
            ty += h_sub
        for ln in s2_lines:
            draw(QRectF(cx + 4, ty, cols[1] - 8, h_sub + 2), f_sub, ln,
                 SUB_INK, Qt.AlignLeft, autofit=False)
            ty += h_sub
        # nilai tengah/kanan rata vertikal di tengah baris
        cy = y + (row_h - h_item) / 2
        cx += cols[1]
        draw(QRectF(cx, cy, cols[2], h_item), f_item, str(qty), INK,
             Qt.AlignCenter, autofit=False)
        cx += cols[2]
        draw(QRectF(cx + 2, cy, cols[3] - 10, h_item), _font(False, 9),
             _fmt_rp(harga), INK, Qt.AlignRight | Qt.AlignVCenter)
        cx += cols[3]
        draw(QRectF(cx + 2, cy, cols[4] - 8, h_item), f_item,
             _fmt_rp(sub), ACCENT_DARK, Qt.AlignRight | Qt.AlignVCenter)
        y += row_h
        p.setPen(LINE_INK)
        p.setBrush(Qt.NoBrush)
        p.drawLine(QRectF(x, y, w, 1).toRect().topLeft(),
                   QRectF(x + w, y, 1, 1).toRect().topLeft())

    if not items:
        draw(QRectF(x + 4, y + 12, w - 8, h_sub + 2), f_sub,
             "(tidak ada item dipilih)", MUTED_INK,
             Qt.AlignLeft, autofit=False)
        y += h_sub + 24

    # catatan rekomendasi (bullet)
    f_note = _font(False, 7.5)
    fm_note = QFontMetricsF(f_note)
    p.setFont(f_note)
    y += 10
    for r in items:
        note = (r.get("catatan") or r.get("p_catatan") or "").strip()
        if not note:
            continue
        for line in _wrap("•  " + r.get("nama", "") + ": " + note,
                          w - 12, fm_note):
            draw(QRectF(x + 4, y, w - 12, fm_note.height() + 2), f_note,
                 line, SUB_INK, Qt.AlignLeft, autofit=False)
            y += fm_note.height()
        y += 3
    y += 6

    # ====== TOTAL ======
    tb = 48.0
    p.setPen(Qt.NoPen)
    p.setBrush(NAVY)
    p.drawRoundedRect(QRectF(x, y, w, tb), 6, 6)
    draw(QRectF(x + 16, y, w - 280, tb), _font(False, 8.5),
         "TOTAL  ESTIMASI  BELANJA", HEADER_SUB,
         Qt.AlignLeft | Qt.AlignVCenter)
    f_tot = _font(True, 12.5, True)
    h_tot = QFontMetricsF(f_tot).height()
    draw(QRectF(x + w - 250, y, 236, tb), f_tot, _fmt_rp(total),
         QColor(ACCENT), Qt.AlignRight | Qt.AlignVCenter)
    y += tb + 18

    # ================= TIPS PERAWATAN =================
    draw(QRectF(x, y, w, h_sec + 2), f_sec, "TIPS  PERAWATAN", ACCENT_DARK)
    p.fillRect(QRectF(x, y + h_sec + 6, w, 1.4), ACCENT)
    y += h_sec + 18
    f_tip = _font(False, 8.5)
    fm_tip = QFontMetricsF(f_tip)
    p.setFont(f_tip)
    for k, t in enumerate((tips or [])[:6], 1):
        for line in _wrap(f"{k}.  {t}", w - 12, fm_tip):
            if y + fm_tip.height() > page_h - 100:
                break
            draw(QRectF(x + 4, y, w - 12, fm_tip.height() + 2), f_tip,
                 line, INK, Qt.AlignLeft, autofit=False)
            y += fm_tip.height()
        y += 3
        if y > page_h - 100:
            break
    y += 6

    # ================= FOOTER =================
    fh = 62.0
    fy = max(page_h - fh - 8, y)
    p.fillRect(QRectF(0, fy, pw, fh), QColor("#F1F5F9"))
    p.fillRect(QRectF(0, fy, pw, 3), ACCENT)
    f_foot = _font(False, 9, True)
    draw(QRectF(MARGIN, fy + 12, w, QFontMetricsF(f_foot).height() + 2),
         f_foot, "Terima kasih telah berbelanja di " +
         (store_name or "toko kami"), INK)
    draw(QRectF(MARGIN, fy + 14 + QFontMetricsF(f_foot).height(), w,
                h_small + 2), f_small,
         "Dibuat otomatis oleh VISMOK • harga dapat berubah • "
         "tunjukkan kwitansi ini di kasir", SUB_INK)

    p.end()
    return out_path
