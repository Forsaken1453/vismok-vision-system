"""
Tools: ekstrak frame dari video (YouTube download / mp4 / mov) jadi dataset foto.

Pemakaian:
  python tools/frames_from_video.py <file_video> <folder_output> [--every 1.5] [--max 300]

Contoh:
  python tools/frames_from_video.py "D:/Downloads/guppy%20-4k.mp4" datasets/guppy/video1 --every 1.5
"""
import argparse
import os
import sys

import cv2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video", help="file video (mp4/mov/avi/mkv)")
    ap.add_argument("out", help="folder output untuk frame")
    ap.add_argument("--every", type=float, default=1.5,
                    help="ambil 1 frame tiap N detik (default 1.5)")
    ap.add_argument("--max", type=int, default=400, help="batas maksimal frame")
    ap.add_argument("--blur-threshold", type=float, default=55.0,
                    help="skip frame yang terlalu blur (variance Laplacian < threshold)")
    args = ap.parse_args()

    if not os.path.exists(args.video):
        print(f"[X] Video tidak ada: {args.video}")
        sys.exit(1)

    os.makedirs(args.out, exist_ok=True)
    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        print("[X] Gagal membuka video.")
        sys.exit(1)

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, int(round(fps * args.every)))

    total, idx, saved, skipped = 0, 0, 0, 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % step == 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
            if blur_score < args.blur_threshold:
                skipped += 1
            else:
                name = f"fr_{saved:04d}.jpg"
                cv2.imwrite(os.path.join(args.out, name), frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
                saved += 1
                if saved % 25 == 0:
                    print(f"  ... {saved} frame tersimpan")
                if saved >= args.max:
                    break
        idx += 1

    cap.release()
    dur = idx / fps if fps else 0
    print(f"[OK] {saved} frame di '{args.out}'  |  video {dur:.0f}s, step {step} frame, "
          f"skip blur(skor<{args.blur_threshold}): {skipped}")


if __name__ == "__main__":
    main()
