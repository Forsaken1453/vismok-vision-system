# -*- coding: utf-8 -*-
"""Render PENJELASAN_KODE_ARDUINO.md jadi PDF (A4) pakai PySide6 QPdfWriter.
Satu QPainter untuk seluruh dokumen (pola standar QPdfWriter).
Emoji dibuang (font PDF tidak punya glyph emoji)."""
import os
import re

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QColor, QFont, QGuiApplication, QPainter,
                           QPageSize, QPdfWriter, QPen)
from PySide6.QtWidgets import QApplication

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "PENJELASAN_KODE_ARDUINO.md")
OUT = os.path.join(HERE, "PENJELASAN_KODE_ARDUINO.pdf")

EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF"
    "\u2b00-\u2bff\u2190-\u21ff\ufe0f\u2705\u274c\u23f3\u23f0]")

app = QApplication([])
writer = QPdfWriter(OUT)
writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
writer.setResolution(96)

p = QPainter(writer)
PAGE_W = writer.width()
PAGE_H = writer.height()
MARGIN = int(PAGE_W / 12)
RIGHT = PAGE_W - MARGIN
TOP = MARGIN
BOTTOM = PAGE_H - MARGIN

F_BODY = QFont("Segoe UI", 10)
F_H1 = QFont("Segoe UI", 17)
F_H1.setBold(True)
F_H2 = QFont("Segoe UI", 13)
F_H2.setBold(True)
F_H3 = QFont("Segoe UI", 11)
F_H3.setBold(True)
F_CODE = QFont("Consolas", 9)
F_TINY = QFont("Segoe UI", 9)

y = TOP
pages = 1


def new_page():
    global y, pages
    writer.newPage()
    y = TOP
    pages += 1


def ensure(h):
    if y + h > BOTTOM:
        new_page()


def wrap_text(text, font, maxw):
    p.setFont(font)
    lines = []
    for para in text.split("\n"):
        if not para.strip():
            lines.append("")
            continue
        cur = ""
        for word in para.split(" "):
            trial = (cur + " " + word).strip()
            if p.fontMetrics().horizontalAdvance(trial) > maxw:
                lines.append(cur)
                cur = word
            else:
                cur = trial
        if cur:
            lines.append(cur)
    return lines


def draw(text, font=None, color=None, lead=1.25, indent=0):
    font = font or F_BODY
    color = color or QColor("#1A2430")
    p.setFont(font)
    fm = p.fontMetrics()
    lh = int(fm.height() * lead)
    x0 = MARGIN + indent
    maxw = RIGHT - x0
    for line in wrap_text(text, font, maxw):
        ensure(lh)
        if line:
            p.setPen(QPen(color, 1))
            p.drawText(QRectF(x0, y, maxw, lh),
                       Qt.AlignLeft | Qt.AlignVCenter, line)
        globals()["y"] = y + lh
    globals()["y"] = y + 4


def rule():
    global y
    ensure(14)
    p.setPen(QPen(QColor("#22D3EE"), 2))
    p.drawLine(QPointF(MARGIN, y), QPointF(RIGHT, y))
    globals()["y"] = y + 12


def heading(t, level):
    global y
    ensure(48)
    globals()["y"] = y + 10
    fonts = {1: F_H1, 2: F_H2, 3: F_H3}
    colors = {1: QColor("#0B1B2B"), 2: QColor("#0E7490"), 3: QColor("#155E75")}
    draw(t, fonts[level], colors[level], 1.2)
    if level <= 2:
        rule()
    else:
        globals()["y"] = y + 2


def table(rows):
    global y
    p.setFont(F_TINY)
    fm = p.fontMetrics()
    ncol = max(len(r) for r in rows)
    colw = int((RIGHT - MARGIN - (ncol - 1) * 8) / ncol)
    lh = int(fm.height() * 1.2)
    for ri, row in enumerate(rows):
        cells = []
        maxlines = 1
        for ci in range(ncol):
            cell = row[ci] if ci < len(row) else ""
            lines = wrap_text(cell, F_TINY, colw)
            cells.append(lines)
            maxlines = max(maxlines, len(lines))
        rh = lh * maxlines + 4
        if y + rh > BOTTOM:
            new_page()
        for ci in range(ncol):
            x = MARGIN + ci * (colw + 8)
            if ci:
                p.setPen(QPen(QColor("#CBD5E1"), 1))
                p.drawLine(QPointF(x - 4, y), QPointF(x - 4, y + rh - 2))
            p.setPen(QPen(QColor("#0B1B2B") if ri == 0
                          else QColor("#1A2430"), 1))
            for li, line in enumerate(cells[ci]):
                p.drawText(QRectF(x, y + li * lh, colw, lh),
                           Qt.AlignLeft | Qt.AlignVCenter, line)
        if ri == 0:
            p.setPen(QPen(QColor("#22D3EE"), 2))
            p.drawLine(QPointF(MARGIN, y + rh), QPointF(RIGHT, y + rh))
        globals()["y"] = y + rh
    globals()["y"] = y + 8


with open(SRC, encoding="utf-8") as f:
    md = f.read()

lines = md.split("\n")
i = 0
while i < len(lines):
    ln = EMOJI.sub("", lines[i]).rstrip()
    if ln.startswith("|"):
        rows = []
        while i < len(lines) and lines[i].startswith("|"):
            cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
            if not set("".join(cells)) <= set("-: "):
                rows.append([EMOJI.sub("", c).replace("**", "").replace("`", "")
                             for c in cells])
            i += 1
        if rows:
            table(rows)
        continue
    if ln.startswith("# "):
        heading(ln[2:], 1)
    elif ln.startswith("## "):
        heading(ln[3:], 2)
    elif ln.startswith("### "):
        heading(ln[4:], 3)
    elif ln.startswith("```"):
        i += 1
        while i < len(lines) and not lines[i].startswith("```"):
            draw(EMOJI.sub("", lines[i]).rstrip(), F_CODE,
                 QColor("#0E7490"), 1.15, 12)
            i += 1
        globals()["y"] = y + 6
    elif ln.startswith("> "):
        draw(ln[2:], F_BODY, QColor("#155E75"), 1.25, 20)
    elif ln.startswith("- "):
        draw("•  " + ln[2:], F_BODY, None, 1.25, 12)
    elif re.match(r"^\d+\. ", ln):
        draw(ln, F_BODY, None, 1.25, 12)
    elif ln.strip() == "---":
        rule()
    elif ln.strip():
        draw(ln.replace("**", ""))
    i += 1

p.end()
print("PDF selesai:", OUT, os.path.getsize(OUT), "bytes |", pages, "halaman")
