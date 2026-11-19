"""Database SQLite Leviathan + data awal (seed).

Semua data ini bisa diubah dari Panel Admin tanpa menyentuh kode.
"""
import json
import sqlite3

from app.config import DEFAULTS, DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS species (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_name TEXT UNIQUE NOT NULL,        -- nama kelas di model YOLO (lowercase, tanpa spasi)
    display_name TEXT NOT NULL,
    emoji TEXT DEFAULT '🐟',
    habitat TEXT,
    sifat TEXT,
    suhu TEXT,
    ph TEXT,
    ukuran TEXT,
    deskripsi TEXT,
    tips TEXT DEFAULT '[]'                  -- daftar tips, format JSON
);
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nama TEXT NOT NULL,
    merek TEXT DEFAULT '',
    bentuk TEXT DEFAULT 'pelet',
    ukuran TEXT DEFAULT '',
    protein REAL DEFAULT 0,
    harga REAL DEFAULT 0,
    stok INTEGER DEFAULT 1,
    catatan TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS rekomendasi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    species_id INTEGER NOT NULL REFERENCES species(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    priority INTEGER NOT NULL DEFAULT 1,    -- 1 = paling direkomendasikan
    frekuensi TEXT DEFAULT '',
    dosis TEXT DEFAULT '',
    catatan TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS detections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    class_name TEXT NOT NULL,
    conf REAL DEFAULT 0,
    snapshot TEXT DEFAULT ''
);
"""

SPECIES_SEED = [
    # (class_name, display_name, emoji, habitat, sifat, suhu, ph, ukuran, deskripsi, tips)
    ("guppy", "Guppy", "🐠", "Akuarium / kolam kecil, air tawar tenang",
     "Ramah, rakus, cocok untuk pemula, memuntahkan (ovovivipar)",
     "22-28 °C", "6.8-7.5", "4-6 cm",
     "Ikan hias kecil paling populer di Indonesia. Warna sangat variatif dan "
     "perkembangbiakannya cepat, sehingga banyak dibudidayakan oleh pemula.",
     [
         "Jangan dicampur dengan ikan agresif (cupang) - sirip panjang guppy mudah dikejar.",
         "Air jernih & suhu hangat mempercepat warna berkembang penuh.",
         "Jangan padati terlalu banyak di satu kolam - jaga kualitas air.",
     ]),
    ("koi", "Koi", "🎏", "Kolam terbuka, air tawar",
     "Ramah, pintar, suka di permukaan kalau sudah terbiasa diberi makan",
     "18-26 °C", "6.5-7.5", "40-90 cm",
     "Ikan hias premium (kerabat ikan mas). Umurnya panjang, bisa lebih dari 20 "
     "tahun. Warna dan pola tubuh menentukan harganya.",
     [
         "Kolam minimal kedalaman 60 cm, ada aerator.",
         "Pakai pakan pelet khusus koi agar warna & tubuh optimal.",
         "Filter kolam wajib - koi mengotori air dengan cepat.",
     ]),
    ("cupang", "Cupang / Betta", "🥊", "Akuarium kecil, air tenang",
     "Agresif ke sesamanya (terutama jantan), suka tempat tenang",
     "25-28 °C", "6.5-7.0", "6-7 cm",
     "Ikan hias eksotik yang populer. Pemeliharaan mudah, cocok di akuarium "
     "minimalis; sirip panjang dan warnanya sangat menarik.",
     [
         "Cupang jantan TIDAK boleh dicampur cupang jantan lain.",
         "Air tenang + suhu hangat mencegah stres.",
         "Pakan 2x/hari secukupnya - jangan berlebihan.",
     ]),
    ("molly", "Molly", "🐠", "Akuarium / kolam kecil, air tawar",
     "Ramah, mudah dipelihara, memuntahkan",
     "24-28 °C", "7.0-8.0", "6-10 cm",
     "Ikan hias kecil yang mudah dipelihara & cepat berkembang biak. Jangan "
     "dicampur dengan ikan besar yang agresif.",
     [
         "Suka air yang sedikit beralun, pH cenderung netral-basa.",
         "Beri pakan pelet kecil / serbuk untuk ikan kecil.",
         "Suhu terlalu dingin mempermudah penyakit jamur - jaga 24-28 °C.",
     ]),
    ("komet", "Komet / Goldfish", "🪙", "Akuarium / kolam, air tawar",
     "Ramah, rakus, aktif, mudah dipelihara",
     "18-24 °C", "7.0-8.0", "12-25 cm",
     "Ikan hias klasik (goldfish komet), sangat populer di toko. Pertumbuhannya "
     "cepat tetapi juga cepat mengotori air - perlu filter.",
     [
         "Suhu terlalu tinggi mempermudah penyakit parasit - jaga 18-24 °C.",
         "Ikan ini rakus: biarkan pakan habis dalam 3-5 menit saja.",
         "Ganti 20% air setiap minggu untuk menjaga kejernihan.",
     ]),
    ("chana", "Chana (Giant / Tomang)", "🐍", "Akuarium / kolam, air tawar",
     "Predator agresif, nafsu makan tinggi, pemakan ikan kecil",
     "24-30 °C", "6.5-7.5", "40-90 cm",
     "Ikan hias predator yang kuat dan gagah, populer di kalangan hobiis. "
     "Pakannya agresif - cocok pelet protein tinggi atau pakan hidup.",
     [
         "Jangan dicampur ikan yang lebih kecil - berisiko dimakan.",
         "Tutup akuarium dengan rapat: chana pandai melompat!",
         "Selingkan pakan hidup untuk merangsang nafsu makan.",
     ]),
    ("arwana", "Arwana", "🐲", "Akuarium besar / kolam, air tawar",
     "Predator bergengsi, suka tempat tenang, pandai melompat",
     "24-30 °C", "6.5-7.5", "60-90 cm",
     "Ikan hias premium yang populer sebagai ikan hobi mahal. Butuh akuarium "
     "besar dan kualitas air yang stabil.",
     [
         "Akuarium minimal 1.2 x 0.6 m - arwana kecil cepat stres di ruang sempit.",
         "Tutup rapat: arwana sering melompat keluar.",
         "Pakai pelet khusus arwana untuk menjaga warna tetap cerah.",
     ]),
    ("ikan_mas", "Ikan Mas", "🐟", "Kolam / karamba, air tawar",
     "Kuat, rakus, multiguna (ikan hias maupun konsumsi)",
     "20-28 °C", "6.5-8.0", "25-40 cm",
     "Ikan hias sekaligus konsumsi terpopular di Indonesia, terutama Jawa "
     "Tengah. Mudah dibudidayakan dan tahan berbagai kondisi.",
     [
         "Budidaya komersial: kepadatan 20-30 ekor/m2 untuk pertumbuhan optimal.",
         "Pelet mas 2-3 mm, beri 3x/hari sesuai biomassa ikan.",
         "Air keruh kotor bekas pakan berlebih - kontrol dosis agar air bersih.",
     ]),
]

PRODUCTS_SEED = [
    # (nama, merek, bentuk, ukuran, protein, harga, stok, catatan)
    ("Pakan Serbuk Bayi", "HIAS-PRO", "serbuk", "kemasan 25 g", 48.0, 12000, 30,
     "Benih ikan kecil usia 0-1 bulan: guppy, molly, cupang muda"),
    ("Pelet Fine 0.5 mm", "HIAS-PRO", "pelet", "0.5 mm / 100 g", 45.0, 15000, 24,
     "Ikan hias kecil & benih usia 1-2 bulan"),
    ("Pelet 1.0 mm", "HIAS-PRO", "pelet", "1.0 mm / 100 g", 40.0, 18000, 20,
     "Ikan hias kecil dewasa - produk utama toko"),
    ("Pelet 2.0 mm", "HIAS-PRO", "pelet", "2.0 mm / 250 g", 32.0, 20000, 15,
     "Komet, ikan mas, dan koi muda"),
    ("Pelet Kol 3.0 mm", "HIAS-PRO", "pelet", "3.0 mm / 500 g", 30.0, 30000, 10,
     "Koi & arwana dewasa di kolam"),
    ("Pelet Warna (Color Enhancer)", "HIAS-PRO+", "pelet", "2.0 mm / 250 g", 42.0, 35000, 8,
     "Khusus arwana / koi agar warna lebih cerah"),
    ("Pelet Guppy & Molly Warna", "HIAS-PRO+", "pelet", "1.0 mm / 100 g", 45.0, 22000, 14,
     "Memaksimalkan warna guppy & molly dewasa"),
    ("Pelet Cupang (Betta Pellet)", "HIAS-PRO+", "pelet", "0.5 mm / 60 g", 43.0, 18000, 16,
     "Khusus cupang: sirip & warna lebih bagus, larut lambat"),
]

REC_SEED = {
    # class_name: [(nama_produk, priority, frekuensi, dosis, catatan), ...]
    "guppy": [
        ("Pelet Fine 0.5 mm", 1, "2x/hari",
         "Sejumput kecil per ekor, habis dalam 3-4 menit",
         "Pakan utama guppy dewasa & muda. Jangan berlebihan agar air tetap jernih."),
        ("Pakan Serbuk Bayi", 2, "3x/hari",
         "Sejumput tipis merata di permukaan air",
         "Khusus benih/anan guppy usia 0-1 bulan; beri sering dengan porsi kecil."),
        ("Pelet Guppy & Molly Warna", 3, "1x/hari",
         "5-8 pellet per ekor",
         "Selingan untuk memaksimalkan warna; gunakan rutin minimal 3x/minggu."),
    ],
    "molly": [
        ("Pelet 1.0 mm", 1, "2x/hari",
         "Sejumput per 5-6 ekor, habis dalam 3 menit",
         "Pakan utama molly dewasa. Sisa pakan segera dibersihkan agar pH stabil."),
        ("Pelet Fine 0.5 mm", 2, "2x/hari",
         "Sejumput kecil, habis dalam 3 menit",
         "Untuk molly muda / benih 1-2 bulan."),
        ("Pakan Serbuk Bayi", 3, "2-3x/hari",
         "Sejumput tipis di permukaan air",
         "Untuk anan molly yang belum bisa makan pelet."),
    ],
    "cupang": [
        ("Pelet Cupang (Betta Pellet)", 1, "2x/hari",
         "4-6 pellet per ekor per makan",
         "Pakan khusus cupang - sirip tumbuh bagus & warna pekat. Jangan overfeed."),
        ("Pelet Fine 0.5 mm", 2, "1x/hari",
         "3-4 pellet per ekor",
         "Selingan sehari sekali untuk variasi gizi."),
        ("Pakan Serbuk Bayi", 3, "2x/hari",
         "Sejumput tipis",
         "Untuk cupang muda / benih yang mulai berenang bebas."),
    ],
    "komet": [
        ("Pelet 1.0 mm", 1, "2x/hari",
         "Sejumput per 5 ekor, habis dalam 3 menit",
         "Pakan utama komet di akuarium. Komet rakus: jangan sampai kembung."),
        ("Pelet 2.0 mm", 2, "2x/hari",
         "Sejumput besar, habis dalam 5 menit",
         "Untuk komet dewasa di kolam/karamba."),
        ("Pelet Fine 0.5 mm", 3, "1x/hari",
         "Sejumput kecil",
         "Untuk komet muda / benih."),
    ],
    "koi": [
        ("Pelet Kol 3.0 mm", 1, "2-3x/hari",
         "Sekitar 3% dari berat ikan per hari, habis dalam 5 menit",
         "Pakan utama koi kolam. Beri merata di permukaan agar semua koi kebagian."),
        ("Pelet 2.0 mm", 2, "2x/hari",
         "Sejumput besar, habis dalam 5 menit",
         "Untuk koi muda (15-25 cm) di kolam."),
        ("Pelet Warna (Color Enhancer)", 3, "1x/hari",
         "Sejumput per ekor",
         "Pengganti pakan utama 3x/minggu agar pola warna makin tajam."),
    ],
    "chana": [
        ("Pelet Kol 3.0 mm", 1, "1-2x/hari",
         "2-3 pellet besar per ekor",
         "Pelet protein tinggi sebagai pakan utama chana - habis dalam 5 menit."),
        ("Pelet Warna (Color Enhancer)", 2, "1x/hari",
         "1-2 pellet per ekor",
         "Selingan untuk menjaga warna tetap gelap mengkilap."),
        ("Pelet 2.0 mm", 3, "1x/hari",
         "3-4 pellet per ekor",
         "Untuk chana muda / ukuran di bawah 30 cm."),
    ],
    "arwana": [
        ("Pelet Warna (Color Enhancer)", 1, "2x/hari",
         "2-3 pellet per ekor, habis dalam 5-10 menit",
         "Pakan utama arwana untuk warna merah/emas maksimal. Simpan di tempat kering."),
        ("Pelet Kol 3.0 mm", 2, "1x/hari",
         "2-3 pellet per ekor",
         "Pengganti untuk arwana muda / hari biasa; selingkan udang kecil 2x/minggu."),
        ("Pelet 2.0 mm", 3, "1x/hari",
         "3-4 pellet per ekor",
         "Selingan untuk arwana kecil (jarum - 25 cm)."),
    ],
    "ikan_mas": [
        ("Pelet 2.0 mm", 1, "2-3x/hari",
         "Sekitar 3% dari berat ikan per hari",
         "Pakan utama ikan mas pembesaran; sesuaikan porsi dengan biomassa kolam."),
        ("Pelet Kol 3.0 mm", 2, "2x/hari",
         "Sejumput besar per 10 ekor, habis dalam 5 menit",
         "Untuk ikan mas dewasa di kolam besar / karamba."),
        ("Pelet Fine 0.5 mm", 3, "3x/hari",
         "Sejumput kecil merata",
         "Untuk benih ikan mas usia 1-2 bulan."),
    ],
}

SEED_V = "3"     # naikkan bila data awal diubah → DB lama otomatis di-upgrade


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def seed_if_empty(conn):
    # migrasi kolom catatan utk DB lama
    try:
        conn.execute("ALTER TABLE rekomendasi ADD COLUMN catatan TEXT DEFAULT ''")
    except Exception:
        pass

    # upgrade data bila versi seed berubah (riwayat deteksi tidak disentuh)
    cur_v = {r["key"]: r["value"]
             for r in conn.execute("SELECT key, value FROM config")}.get("seed_v", "1")
    if cur_v != SEED_V:
        conn.execute("DELETE FROM rekomendasi")
        conn.execute("DELETE FROM products")

    if conn.execute("SELECT COUNT(*) FROM species").fetchone()[0] == 0:
        for s in SPECIES_SEED:
            conn.execute(
                "INSERT INTO species (class_name, display_name, emoji, habitat, sifat,"
                " suhu, ph, ukuran, deskripsi, tips) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (*s[:9], json.dumps(s[9], ensure_ascii=False)),
            )
    product_ids = {}
    if conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
        for p in PRODUCTS_SEED:
            cur = conn.execute(
                "INSERT INTO products (nama, merek, bentuk, ukuran, protein, harga,"
                " stok, catatan) VALUES (?,?,?,?,?,?,?,?)", p)
            product_ids[p[0]] = cur.lastrowid
    if conn.execute("SELECT COUNT(*) FROM rekomendasi").fetchone()[0] == 0:
        for sp in conn.execute("SELECT id, class_name FROM species").fetchall():
            for (prod_name, prio, freq, dose, note) in REC_SEED.get(sp["class_name"], []):
                pid = product_ids.get(prod_name)
                if pid:
                    conn.execute(
                        "INSERT INTO rekomendasi (species_id, product_id, priority,"
                        " frekuensi, dosis, catatan) VALUES (?,?,?,?,?,?)",
                        (sp["id"], pid, prio, freq, dose, note))
    # config default
    for k, v in DEFAULTS.items():
        conn.execute("INSERT OR IGNORE INTO config (key, value) VALUES (?,?)", (k, v))
    if cur_v != SEED_V:
        conn.execute("INSERT INTO config (key, value) VALUES ('seed_v',?)"
                     " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                     (SEED_V,))
    conn.commit()


def get_config(conn=None):
    own = conn is None
    if own:
        conn = get_conn()
    rows = {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM config")}
    if own:
        conn.close()
    return rows


def set_config(conn, key, value):
    conn.execute("INSERT INTO config (key, value) VALUES (?,?)"
                 " ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, str(value)))
    conn.commit()


def init_db():
    conn = get_conn()
    conn.executescript(SCHEMA)
    seed_if_empty(conn)
    conn.close()


def species_all(conn=None):
    own = conn is None
    if own:
        conn = get_conn()
    rows = [dict(r) for r in conn.execute("SELECT * FROM species ORDER BY display_name")]
    for r in rows:
        try:
            r["tips"] = json.loads(r.get("tips") or "[]")
        except Exception:
            r["tips"] = []
    if own:
        conn.close()
    return rows


def recs_for_species(species_id, conn=None):
    """Daftar rekomendasi (gabung produk) urut prioritas."""
    own = conn is None
    if own:
        conn = get_conn()
    rows = [dict(r) for r in conn.execute(
        """SELECT r.priority, r.frekuensi, r.dosis, r.catatan,
                  p.id AS product_id, p.nama, p.merek, p.bentuk, p.ukuran,
                  p.protein, p.harga, p.stok, p.catatan AS p_catatan
           FROM rekomendasi r JOIN products p ON p.id = r.product_id
           WHERE r.species_id = ? ORDER BY r.priority""", (species_id,))]
    if own:
        conn.close()
    return rows


def species_by_class(conn, class_name):
    row = conn.execute("SELECT * FROM species WHERE class_name = ?", (class_name,)).fetchone()
    if row is None:
        return None
    sp = dict(row)
    try:
        sp["tips"] = json.loads(sp.get("tips") or "[]")
    except Exception:
        sp["tips"] = []
    return sp


# --------------------------------------------------------------------
# riwayat deteksi
# --------------------------------------------------------------------
def add_detection(class_name, conf, snapshot_fn="", ts=None):
    import datetime
    conn = get_conn()
    conn.execute("INSERT INTO detections (ts, class_name, conf, snapshot) "
                 "VALUES (?,?,?,?)",
                 (ts or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                  class_name, float(conf), snapshot_fn))
    conn.commit()
    conn.close()


def detections_list(limit=300):
    """Riwayat hasil (JOIN species untuk display_name)."""
    conn = get_conn()
    rows = [dict(r) for r in conn.execute(
        """SELECT d.id, d.ts, d.class_name, d.conf, d.snapshot,
                  s.display_name, s.emoji
           FROM detections d
           LEFT JOIN species s ON s.class_name = d.class_name
           ORDER BY d.id DESC LIMIT ?""", (limit,))]
    conn.close()
    return rows


def detections_count():
    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) FROM detections").fetchone()[0]
    conn.close()
    return n


def detections_clear():
    """Hapus SEMUA riwayat deteksi + file snapshot-nya. Return jumlah baris."""
    import os
    from app.config import SNAP_DIR
    conn = get_conn()
    snaps = [r[0] for r in conn.execute(
        "SELECT snapshot FROM detections WHERE snapshot != ''")]
    n = conn.execute("DELETE FROM detections").rowcount
    conn.commit()
    conn.close()
    for s in snaps:                      # hapus file snapshot juga
        try:
            p = os.path.join(SNAP_DIR, s)
            if os.path.isfile(p):
                os.remove(p)
        except Exception:
            pass
    return n


def products_all():
    conn = get_conn()
    rows = [dict(r) for r in conn.execute("SELECT * FROM products ORDER BY nama")]
    conn.close()
    return rows
