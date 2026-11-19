# -*- coding: utf-8 -*-
"""Tulis CARA_PAKAI.txt ke dist\VISMOK\ setelah setiap build
(dist selalu di-wipe oleh PyInstaller).

Jalankan dari folder project:  python tools\write_cara_pakai.py
"""
import os

VERSION = "v2.4.7"

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(BASE, "dist", "VISMOK")

TEXT = f"""================================================================
 VISMOK ASELI NGAWI — Asisten Vision Pakan Ikan ({VERSION})
 Cara Pakai (untuk toko & pameran)
================================================================

APA INI?
Aplikasi desktop yang mendeteksi JENIS IKAN lewat kamera
(YOLOv11 + ONNX, jalan 100% offline di laptop ini), lalu
menampilkan rekomendasi pakan yang cocok + tips perawatan,
dan bisa mencetak kwitansi PDF.

Ikan yang dikenali (8 jenis):
  guppy, koi, cupang, molly, komet, chana, arwana, ikan mas

----------------------------------------------------------------
1. MENJALANKAN APLIKASI
----------------------------------------------------------------
- Buka 2x klik:  VISMOK.exe   (di folder ini)
- Tidak perlu install Python / apapun.
- Aplikasi tampil layar penuh (mode kiosk). Tekan ESC untuk
  keluar dari layar penuh, atau tombol X di pojok.

ISI FOLDER (jangan diubah/dipindah):
  VISMOK.exe           -> program utama
  models\\model.onnx   -> model deteksi ikan (WAJIB ada)
  models\\classes.json -> daftar kelas ikan (WAJIB ada)
  assets\\fonts, assets\\img -> font & gambar (WAJIB ada)
  data\\               -> database, riwayat, snapshot ikan
                          (dibuat otomatis saat pertama jalan)

----------------------------------------------------------------
2. KAMERA (PENTING UNTUK PAMERAN)
----------------------------------------------------------------
WEBCAM LAPTOP:
  - Webcam bawaan laptop ini RUSAK (hardware) — jangan dipakai.

KAMERA HP (DroidCam) — INI YANG DIPAKAI:
  a. Install "DroidCam" di HP (Play Store / App Store).
  b. Sambungkan HP & laptop ke WiFi yang SAMA
     (atau pakai hotspot HP).
  c. Buka DroidCam di HP — catat angka WiFi IP-nya,
     contoh: 192.168.43.1
  d. Di aplikasi VISMOK: klik tombol [ IP HP... ]
     lalu ketik IP-nya, contoh: 192.168.43.1
     (aplikasi otomatis menambah port/video — kalau diminta
     manual, alamatnya: http://IP:4747/video )
  e. Gambar kamera HP muncul di layar.

TIPS:
  - Jaga HP tetap terisi baterai / colok powerbank.
  - Kamera HP menghadap akuarium/tempat ikan, jarak 20-40 cm.
  - Cahaya cukup = deteksi jauh lebih akurat.

----------------------------------------------------------------
3. ALUR PEMAKAIAN (KASIR/TOKO)
----------------------------------------------------------------
1. Arahkan kamera ke ikan -> kotak + nama ikan muncul
   (deteksi dikonfirmasi 2x berturut-turut supaya stabil).
2. Aplikasi menampilkan REKOMENDASI PAKAN (jenis, takaran,
   frekuensi) + tips perawatan sesuai jenis ikan.
3. Beli? -> tombol beli/tambah -> keranjang ->
   [CETAK KWITANSI] -> PDF tersimpan & bisa dibuka.
4. Semua deteksi masuk menu RIWAYAT (bisa dibuka lagi).

MODE:
  - AUTO  : deteksi jalan terus selama kamera hidup (demo live).
  - MANUAL: ambil foto sekali (tombol snapshot) lalu deteksi
            -> paling akurat, cocok saat pameran ramai.

----------------------------------------------------------------
4. MENU ADMIN
----------------------------------------------------------------
PIN default: 2026  (bisa diganti di menu Admin)
Di Admin ada: sumber kamera, ganti PIN, nama toko,
kelola produk/pakan, export data, dsb.

----------------------------------------------------------------
5. KALAU ADA MASALAH
----------------------------------------------------------------
- Kamera HP tidak konek:
    * cek HP & laptop satu WiFi
    * buka DroidCam di HP dulu (layar kamera harus aktif)
    * IP harus persis seperti tampil di HP
    * coba isi lengkap: http://192.168.43.1:4747/video
- Ikan salah kenal:
    * dekatkan kamera (ikan memenuhi 1/3 layar)
    * gunakan MODE MANUAL (foto sekali)
    * koi vs ikan mas memang paling mirip; coba sudut lain
      supaya warna/polen terlihat jelas
- Aplikasi lambat saat baru dibuka: normal (memuat model),
  tunggu 5-10 detik.
- Log error: data\\leviathan.log

----------------------------------------------------------------
Versi {VERSION} • Dibuat untuk Pameran 2026
Model: YOLOv11s (ONNX) • Validasi: mAP50 0.977 / 8 kelas
"""


def main():
    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, "CARA_PAKAI.txt")
    with open(out, "w", encoding="utf-8-sig") as f:
        f.write(TEXT)
    print("ditulis:", out)


if __name__ == "__main__":
    main()
