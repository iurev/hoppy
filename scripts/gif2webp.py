"""GIF(s) -> one animated WebP, keeping the per-frame delays.

Called by scripts/cast2webp.sh. Runs ONLY inside the `media` compose service.

    python3 scripts/gif2webp.py OUT.webp IN1.gif [IN2.gif ...]

With one input this is a plain format conversion. With several, the frames of
each GIF are appended in order, so the clips play one after another as a single
animation. The last frame of every clip except the last one is held for an
extra GAP_MS, which gives the viewer a beat to notice that one workflow ended
and the next began. All inputs must have the same pixel size; a mismatch is a
hard error, never a silent rescale.

Why Pillow and not ffmpeg: ffmpeg re-times an animation to a constant frame
rate. A terminal recording is the opposite of constant - a burst of frames
while text appears, then a long hold. Flattening that ruins the pacing.
Pillow copies each frame's own duration across unchanged.

Env knobs: QUALITY (default 82), GAP_MS (default 1000).
"""

import os
import sys

from PIL import Image

QUALITY = int(os.environ.get("QUALITY", "82"))
GAP_MS = int(os.environ.get("GAP_MS", "1000"))


def load(path):
    """Return (frames, durations) for one GIF."""
    im = Image.open(path)
    frames, durations = [], []
    for i in range(im.n_frames):
        im.seek(i)
        frames.append(im.convert("RGBA"))
        durations.append(im.info.get("duration", 100))
    return frames, durations


def main(argv):
    if len(argv) < 3:
        print("usage: gif2webp.py OUT.webp IN1.gif [IN2.gif ...]", file=sys.stderr)
        return 2

    dst, sources = argv[1], argv[2:]

    frames, durations, size = [], [], None
    for n, src in enumerate(sources):
        f, d = load(src)
        if size is None:
            size = f[0].size
        elif f[0].size != size:
            print(
                f"size mismatch: {src} is {f[0].size}, expected {size}. "
                "Re-record with the same terminal size or render with the same "
                "agg --font-size; this script never rescales.",
                file=sys.stderr,
            )
            return 1
        # beat between clips: hold the closing screen a little longer
        if n < len(sources) - 1:
            d[-1] += GAP_MS
        frames.extend(f)
        durations.extend(d)
        print(f"  + {os.path.basename(src)}  {len(f)} frames  {sum(d) / 1000:.1f}s")

    frames[0].save(
        dst,
        format="WEBP",
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        quality=QUALITY,
        method=6,
    )

    gif_kb = sum(os.path.getsize(s) for s in sources) / 1024
    print(
        f"{dst}\n"
        f"  clips      {len(sources)}\n"
        f"  frames     {len(frames)}\n"
        f"  size       {size[0]}x{size[1]}\n"
        f"  duration   {sum(durations) / 1000:.1f}s\n"
        f"  gif in     {gif_kb:.0f} KB\n"
        f"  webp out   {os.path.getsize(dst) / 1024:.0f} KB"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
