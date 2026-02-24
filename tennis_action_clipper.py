#!/usr/bin/env python3
"""
Tennis Action Clipper
---------------------
Analyzes a static-camera tennis video, detects action segments based on
motion, and merges them into a single output video using ffmpeg.

Requirements:
    pip install opencv-python ffmpeg-python

Usage:
    python tennis_action_clipper.py input.mov
    python tennis_action_clipper.py input.mov --output highlights.mp4
    python tennis_action_clipper.py input.mov --sensitivity 0.5 --padding 2.0
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2


# ---------------------------------------------------------------------------
# Motion detection
# ---------------------------------------------------------------------------

def detect_action_segments(
    video_path: str,
    sensitivity: float = 0.3,
    min_action_duration: float = 1.5,
    padding: float = 1.5,
) -> list[tuple[float, float]]:
    """
    Scan the video frame-by-frame and return a list of (start_sec, end_sec)
    tuples for segments that contain significant motion.

    Args:
        video_path:           Path to the input video file.
        sensitivity:          Motion threshold as a fraction of total pixels
                              (0–1). Lower = more sensitive. Default 0.3.
        min_action_duration:  Discard action bursts shorter than this (seconds).
        padding:              Extra seconds added before/after each segment so
                              we don't clip the very start/end of a rally.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        sys.exit(f"[ERROR] Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps
    print(f"[INFO] Video: {total_frames} frames @ {fps:.2f} fps  ({duration:.1f}s)")

    # We analyse every Nth frame for speed (still accurate for tennis).
    sample_every = max(1, int(fps / 5))  # ~5 samples/second

    prev_gray = None
    motion_flags: list[bool] = []  # one entry per sampled frame

    frame_idx = 0
    print("[INFO] Analysing motion...", end="", flush=True)
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % sample_every == 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)
            if prev_gray is not None:
                diff = cv2.absdiff(prev_gray, gray)
                _, thresh = cv2.threshold(diff, 25, 1, cv2.THRESH_BINARY)
                motion_ratio = thresh.sum() / thresh.size
                motion_flags.append(motion_ratio > sensitivity / 100)
            prev_gray = gray
        frame_idx += 1

    cap.release()
    print(" done.")

    # Map sampled flags back to real time
    sample_duration = sample_every / fps  # seconds per sample slot

    # --- Smooth the signal: fill short gaps in motion (between-point dips) ---
    # A gap shorter than ~3 seconds inside action is probably just a brief lull.
    fill_gap = int(3.0 / sample_duration)
    flags = list(motion_flags)
    i = 0
    while i < len(flags):
        if flags[i]:
            j = i + 1
            while j < len(flags) and not flags[j]:
                j += 1
            if j - i <= fill_gap and j < len(flags):
                for k in range(i, j):
                    flags[k] = True
            i = j
        else:
            i += 1

    # --- Build raw segments from the smoothed flags ---
    raw_segments: list[tuple[float, float]] = []
    in_action = False
    seg_start = 0.0
    for idx, active in enumerate(flags):
        t = idx * sample_duration
        if active and not in_action:
            seg_start = t
            in_action = True
        elif not active and in_action:
            raw_segments.append((seg_start, t))
            in_action = False
    if in_action:
        raw_segments.append((seg_start, len(flags) * sample_duration))

    # --- Apply padding and filter short segments ---
    segments: list[tuple[float, float]] = []
    for start, end in raw_segments:
        if end - start < min_action_duration:
            continue
        padded_start = max(0.0, start - padding)
        padded_end = min(duration, end + padding)
        segments.append((padded_start, padded_end))

    # --- Merge overlapping/adjacent padded segments ---
    merged: list[tuple[float, float]] = []
    for seg in sorted(segments):
        if merged and seg[0] <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], seg[1]))
        else:
            merged.append(list(seg))

    merged = [tuple(s) for s in merged]

    total_action = sum(e - s for s, e in merged)
    print(f"[INFO] Found {len(merged)} action segment(s)  ({total_action:.1f}s of action)")
    return merged


# ---------------------------------------------------------------------------
# FFmpeg cutting & merging
# ---------------------------------------------------------------------------

def cut_and_merge(
    video_path: str,
    segments: list[tuple[float, float]],
    output_path: str,
) -> None:
    """
    Use ffmpeg to cut each segment and concatenate them into one output file.
    Cutting is done by seeking before decode (fast) then re-encoding only the
    short overlap, so quality is preserved.
    """
    if not segments:
        sys.exit("[ERROR] No action segments detected. Try lowering --sensitivity.")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        clip_paths: list[Path] = []

        print("[INFO] Cutting segments with ffmpeg...")
        for i, (start, end) in enumerate(segments):
            clip = tmp / f"clip_{i:04d}.mp4"
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(start),
                "-to", str(end),
                "-i", video_path,
                "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                "-c:a", "aac", "-b:a", "192k",
                str(clip),
            ]
            result = subprocess.run(cmd, capture_output=True)
            if result.returncode != 0:
                print(result.stderr.decode(), file=sys.stderr)
                sys.exit(f"[ERROR] ffmpeg failed on segment {i}")
            print(f"  [{i+1}/{len(segments)}] {start:.1f}s – {end:.1f}s  → {clip.name}")
            clip_paths.append(clip)

        # Write concat list file
        concat_list = tmp / "concat.txt"
        concat_list.write_text(
            "\n".join(f"file '{p}'" for p in clip_paths)
        )

        print(f"[INFO] Merging {len(clip_paths)} clips → {output_path}")
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-c", "copy",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            print(result.stderr.decode(), file=sys.stderr)
            sys.exit("[ERROR] ffmpeg concat failed")

    print(f"[DONE] Saved: {output_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cut tennis downtime and merge action clips into one video."
    )
    parser.add_argument("input", help="Path to the iPhone tennis video (MOV/MP4)")
    parser.add_argument(
        "--output", "-o", default=None,
        help="Output file path (default: <input>_highlights.mp4)",
    )
    parser.add_argument(
        "--sensitivity", "-s", type=float, default=0.3,
        help=(
            "Motion sensitivity 0.1–5.0. Lower = pick up more subtle motion. "
            "Default: 0.3  (good starting point for tennis)"
        ),
    )
    parser.add_argument(
        "--padding", "-p", type=float, default=1.5,
        help="Seconds of buffer added before/after each action burst. Default: 1.5",
    )
    parser.add_argument(
        "--min-duration", "-m", type=float, default=1.5,
        help="Minimum seconds of motion to count as action. Default: 1.5",
    )
    args = parser.parse_args()

    input_path = str(Path(args.input).resolve())
    if args.output:
        output_path = args.output
    else:
        stem = Path(args.input).stem
        output_path = str(Path(args.input).parent / f"{stem}_highlights.mp4")

    segments = detect_action_segments(
        input_path,
        sensitivity=args.sensitivity,
        min_action_duration=args.min_duration,
        padding=args.padding,
    )

    if segments:
        print("\n[INFO] Detected segments:")
        for i, (s, e) in enumerate(segments, 1):
            print(f"  {i:>3}. {s:7.2f}s  –  {e:7.2f}s  ({e-s:.1f}s)")
        print()

    cut_and_merge(input_path, segments, output_path)


if __name__ == "__main__":
    main()
