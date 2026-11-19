"""Mesin deteksi Leviathan.

- Jika models/model.onnx tersedia → inferensi YOLO (v8/v11 detect) via ONNX Runtime.
- Jika belum ada → DummyDetector (mode demo/pameran): memilih random species.

Hasil: list deteksi [ {box:[x1,y1,x2,y2], cls, class_name, conf} ]
"""
import ast
import json
import os
import random
import time

import numpy as np

from app.config import CLASSES_PATH, MODEL_PATH, DEFAULTS


class BaseDetector:
    name = "?"

    def detect(self, frame_bgr):
        """Return (list_detections, fps_inf) atau (None, 0) jika gagal."""
        raise NotImplementedError


# ------------------------------------------------------------------
# Dummy mode (tanpa model)
# ------------------------------------------------------------------
class DummyDetector(BaseDetector):
    name = "DEMO"

    def __init__(self, class_names):
        self.class_names = class_names
        self._cd = time.time()
        self._held = []                # hasil "held" selama 2 dtk agar konfirmasi lolos
        self._hold_until = 0.0

    def _mk(self, cls, conf, fw, fh):
        return {
            "box": [int(fw*0.30), int(fh*0.28), int(fw*0.70), int(fh*0.72)],
            "cls": self.class_names.index(cls),
            "class_name": cls,
            "conf": round(conf, 2),
        }

    def detect(self, frame):
        h, w = frame.shape[:2]
        now = time.time()
        if now < self._hold_until:
            # regenerasi box agar pas dengan resolusi frame aktif
            return [self._mk(d["class_name"], d["conf"], w, h) for d in self._held], 0.0
        detections = []
        if now - self._cd > 4.0:            # tiap ~4 dtk muncul hasil
            self._cd = now
            cls = random.choice(self.class_names)
            detections.append(self._mk(cls, random.uniform(0.78, 0.96), w, h))
            for _ in range(random.randint(0, 2)):   # kadang deteksi ikan kedua
                cls2 = random.choice(self.class_names)
                d2 = self._mk(cls2, random.uniform(0.62, 0.88), w, h)
                d2["box"] = [int(w*0.08 + random.random()*w*0.2),
                             int(h*0.1 + random.random()*h*0.5),
                             int(w*0.4 + random.random()*w*0.2),
                             int(h*0.5 + random.random()*h*0.35)]
                detections.append(d2)
            self._held = list(detections)
            self._hold_until = now + 2.0
        return detections, 0.0


# ------------------------------------------------------------------
# YOLO ONNX (v8/v11 detect, format output [1, 4+nc, 8400])
# ------------------------------------------------------------------
class YoloOnnxDetector(BaseDetector):
    name = "ONNX"

    def __init__(self, model_path=MODEL_PATH, imgsz=640, conf=0.45):
        import onnxruntime as ort

        self.conf = conf
        self.imgsz = int(imgsz)
        so = ort.SessionOptions()
        providers = ["CPUExecutionProvider"]
        try:
            if ort.get_device() == "GPU":
                providers.insert(0, "DmlExecutionProvider")  # DirectML (RTX 3050 tanpa CUDA wheel)
        except Exception:
            pass
        self.sess = ort.InferenceSession(model_path, so, providers=providers)
        from app.core.logs import log
        log(f"model ONNX termuat: providers={self.sess.get_providers()} "
            f"threads={so.intra_op_num_threads}")
        self.input_name = self.sess.get_inputs()[0].name
        meta_names = self._read_names_meta()
        self.class_names = meta_names if meta_names else []
        self._inf_count = 0

    def _read_names_meta(self):
        try:
            meta = self.sess.get_modelmeta()
            data = getattr(meta, "custom_metadata_maps", None)
            if data and "names" in data:
                parsed = ast.literal_eval(str(data["names"]))
                if isinstance(parsed, dict):
                    return [str(parsed[k]) for k in sorted(parsed)]
        except Exception:
            pass
        # fallback: classes.json
        if os.path.exists(CLASSES_PATH):
            try:
                with open(CLASSES_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    return data
                if isinstance(data, dict):
                    return [str(data[k]) for k in sorted(data, key=lambda x: int(x))]
            except Exception:
                pass
        return []

    # --- preprocessing ---
    def _prep(self, frame):
        import cv2
        img = cv2.resize(frame, (self.imgsz, self.imgsz))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        arr = img.astype(np.float32) / 255.0
        arr = arr.transpose(2, 0, 1)[None]         # 1,3,S,S
        return arr

    # --- decoding YOLO output ---
    def _decode(self, pred, fw, fh):
        p = pred[0]                                 # (4+nc, N) atau (N, 4+nc)
        if p.shape[0] < p.shape[1]:
            p = p.T                                 # (N, 4+nc)
        nc = p.shape[1] - 4
        if nc <= 0:
            return []
        boxes = p[:, :4]                            # cx,cy,w,h (pixel @imgsz)
        raw = p[:, 4:]
        # Export ONNX ultralytics SUDAH menerapkan sigmoid di dalam graf
        # (nilai 0..1). Sigmoid dobel membuat semua skor jadi ~0.5 ->
        # ribuan kotak sampah lolos (mis. muka manusia "terdeteksi").
        # Deteksi otomatis: ada nilai negatif = masih logits -> sigmoid.
        if raw.size and float(raw.min()) < 0.0:
            scores = 1.0 / (1.0 + np.exp(-raw))
        else:
            scores = raw
        cls_idx = np.argmax(scores, axis=1)
        cls_conf = scores[np.arange(len(scores)), cls_idx]
        m = cls_conf >= self.conf
        boxes, cls_idx, cls_conf = boxes[m], cls_idx[m], cls_conf[m]
        if len(boxes) == 0:
            return []

        sx, sy = fw / self.imgsz, fh / self.imgsz
        x1 = (boxes[:, 0] - boxes[:, 2] / 2) * sx
        y1 = (boxes[:, 1] - boxes[:, 3] / 2) * sy
        x2 = (boxes[:, 0] + boxes[:, 2] / 2) * sx
        y2 = (boxes[:, 1] + boxes[:, 3] / 2) * sy

        keep = self._nms(np.stack([x1, y1, x2, y2], 1), cls_conf)
        out = []
        for i in keep:
            name = self.class_names[cls_idx[i]] if cls_idx[i] < len(self.class_names) \
                else str(cls_idx[i])
            out.append({
                "box": [float(x1[i]), float(y1[i]), float(x2[i]), float(y2[i])],
                "cls": int(cls_idx[i]),
                "class_name": name,
                "conf": round(float(cls_conf[i]), 2),
            })
        return out

    @staticmethod
    def _nms(boxes, scores, iou_thr=0.5):
        x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
        areas = (x2 - x1) * (y2 - y1)
        order = scores.argsort()[::-1]
        keep = []
        while order.size > 0:
            i = order[0]
            keep.append(i)
            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])
            w = np.maximum(0.0, xx2 - xx1)
            h = np.maximum(0.0, yy2 - yy1)
            inter = w * h
            iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-9)
            order = order[1:][iou <= iou_thr]
        return keep

    def detect(self, frame):
        import cv2
        import time as _t
        h, w = frame.shape[:2]
        blob = self._prep(frame)
        t0 = _t.time()
        try:
            out = self.sess.run(None, {self.input_name: blob})[0]
        except Exception:
            return None, 0.0
        dt = _t.time() - t0
        self._inf_count += 1
        if self._inf_count % 50 == 0:
            from app.core.logs import log
            log(f"infer #{self._inf_count} ({dt*1000:.0f} ms)")
        dets = self._decode(out, w, h)
        return dets, (1.0 / dt if dt > 0 else 0.0)


def load_detector(class_names, imgsz=640, conf=0.45):
    """Pilih detector: ONNX jika model tersedia, else Dummy."""
    if os.path.exists(MODEL_PATH):
        try:
            det = YoloOnnxDetector(MODEL_PATH, imgsz=imgsz, conf=conf)
            if not det.class_names:
                det.class_names = class_names      # dari DB sebagai fallback
            return det
        except Exception as e:
            print("[Leviathan] Gagal load ONNX:", e)
    return DummyDetector(class_names)
