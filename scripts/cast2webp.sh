#!/usr/bin/env bash
# .cast -> .gif (agg) -> animated .webp (Pillow).
#
# Runs ONLY inside the `media` compose service:
#   docker compose run --rm media scripts/cast2webp.sh <cast-name> [<cast-name>...]
#
# Each <cast-name> is a file in test_output/casts/, with or without the .cast
# suffix. For every cast you get test_output/webp/<name>.gif and .webp. Give
# two or more and you ALSO get one combined animation that plays them in the
# order listed, with a beat between clips:
#   test_output/webp/$COMBINED.webp   (default name: demo-combined)
#
# Pacing. These casts come from tests full of time.sleep(1.5), so most of the
# running time is a frozen screen. IDLE caps every pause, which is the only
# trim that matters; SPEED is left at 1.0 because the interesting screens
# (the fzf list, the filtered list) need to be readable, not fast.
#   IDLE=0.8 SPEED=1.3 scripts/cast2webp.sh <cast-name>
set -euo pipefail

if [ $# -lt 1 ]; then
    echo "usage: scripts/cast2webp.sh <cast-name> [<cast-name>...]" >&2
    echo "casts live in test_output/casts/" >&2
    exit 2
fi

CASTS_DIR="${CASTS_DIR:-test_output/casts}"
OUT_DIR="${OUT_DIR:-test_output/webp}"
COMBINED="${COMBINED:-demo-combined}"

# pacing / look knobs
IDLE="${IDLE:-1.2}"           # squash any pause longer than this
SPEED="${SPEED:-1.0}"         # then play the whole thing this much faster
THEME="${THEME:-monokai}"
FONT_SIZE="${FONT_SIZE:-14}"
FPS_CAP="${FPS_CAP:-15}"      # 15 is plenty for a terminal; halves the frames
LAST_FRAME="${LAST_FRAME:-1}" # hold the closing screen of each clip
export QUALITY="${QUALITY:-82}"
export GAP_MS="${GAP_MS:-1000}"   # extra hold between clips in the combined file

mkdir -p "$OUT_DIR"

gifs=()
for arg in "$@"; do
    name="${arg%.cast}"
    cast="$CASTS_DIR/$name.cast"
    if [ ! -f "$cast" ]; then
        echo "no such cast: $cast" >&2
        exit 1
    fi
    gif="$OUT_DIR/$name.gif"

    echo "--- agg $name"
    agg --quiet \
        --idle-time-limit "$IDLE" \
        --speed "$SPEED" \
        --theme "$THEME" \
        --font-size "$FONT_SIZE" \
        --fps-cap "$FPS_CAP" \
        --last-frame-duration "$LAST_FRAME" \
        "$cast" "$gif"

    # the per-clip WebP, useful on its own
    python3 scripts/gif2webp.py "$OUT_DIR/$name.webp" "$gif"
    gifs+=("$gif")
done

if [ "${#gifs[@]}" -gt 1 ]; then
    echo "--- combining ${#gifs[@]} clips"
    python3 scripts/gif2webp.py "$OUT_DIR/$COMBINED.webp" "${gifs[@]}"
fi
