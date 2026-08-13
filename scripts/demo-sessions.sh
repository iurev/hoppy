#!/usr/bin/env bash
# Build a tmux playground for recording a hoppy demo by hand.
#
#   scripts/demo-sessions.sh
#
# Every session gets a different ASCII critter saying its own name, so a video
# shows at a glance that the switch really happened. Then it attaches you to a
# session called "myhoppy". Press Ctrl+Shift+L to open the switcher.
#
# Everything lives on its own tmux socket ("hoppydemo"), so your real sessions
# are never touched, never listed and never killed.
#
#   SOCKET=default         use your normal tmux server instead
#   HOPPY=/path/to/hoppy   use a different binary
#   NO_ATTACH=1            just build the sessions and exit
#
# If `cowsay` is installed it is used instead of the built-in critters.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOPPY="${HOPPY:-$REPO/hoppy}"
SOCKET="${SOCKET:-hoppydemo}"
HOME_SESSION="myhoppy"
BANNER_DIR="/tmp/hoppy-demo-banners"

if [ ! -x "$HOPPY" ]; then
  echo "no binary at $HOPPY" >&2
  echo "build it first:  docker compose run --rm build" >&2
  exit 1
fi

if [ "$SOCKET" = "default" ]; then
  TM=(tmux)
else
  TM=(tmux -L "$SOCKET")
fi

SESSIONS=(
  "Destruction of the Universe"
  "Sudo Make Me A Sandwich"
  "Schrodingers Session"
  "Improbability Drive"
  "Blue Screen of Joy"
  "Turtles All The Way Down"
  "Cosmic Rays Flipped My Bit"
  "Stack Overflow Copypasta"
  "Gopher Rodeo"
  "Tabs vs Spaces"
  "ALL YOUR BASE"
  "THE_CAKE_IS_A_LIE"
  "vim_or_death"
  "KDE_FreeBsd"
  "sixty-seven"
)

# --------------------------------------------------------------------------
# banners
# --------------------------------------------------------------------------

# A speech balloon the width of the text, cowsay style.
bubble() {
  local text="$1" bar
  bar="$(printf '%*s' $(( ${#text} + 2 )) '' | tr ' ' '_')"
  printf ' %s\n' "$bar"
  printf '< %s >\n' "$text"
  bar="$(printf '%*s' $(( ${#text} + 2 )) '' | tr ' ' '-')"
  printf ' %s\n' "$bar"
}

# One critter per index, so two sessions in a row never look the same.
critter() {
  case $(( $1 % 6 )) in
    0) cat <<'ART'
        \   ^__^
         \  (oo)\_______
            (__)\       )\/\
                ||----w |
                ||     ||
ART
    ;;
    1) cat <<'ART'
        \      .--.
         \    |o_o |
              |:_/ |
             //   \ \
            (|     | )
           /'\_   _/`\
           \___)=(___/
ART
    ;;
    2) cat <<'ART'
        \     (\(\
         \    ( -.-)
              o_(")(")
ART
    ;;
    3) cat <<'ART'
        \     .-"""-.
         \   / .   . \
             |  \_/  |
             \  ___  /
              '-...-'
              /|   |\
ART
    ;;
    4) cat <<'ART'
        \     [ - - ]
         \    |=====|
             /|     |\
              |_____|
               |] [|
ART
    ;;
    *) cat <<'ART'
        \      _____
         \    /     \
             | () () |
              \  ^  /
               |||||
               |||||
ART
    ;;
  esac
}

# Pre-render each banner to a file. send-keys then only has to `cat` it, which
# keeps every quote and backslash out of the shell round trip.
mkdir -p "$BANNER_DIR"
rm -f "$BANNER_DIR"/*.txt 2>/dev/null || true

render() {
  local name="$1" idx="$2" out="$3"
  if command -v cowsay >/dev/null 2>&1; then
    cowsay "$name" > "$out"
  else
    { printf '\n'; bubble "$name"; critter "$idx"; printf '\n'; } > "$out"
  fi
}

# --------------------------------------------------------------------------
# build
# --------------------------------------------------------------------------

if [ "$SOCKET" = "default" ]; then
  echo "SOCKET=default: leaving your existing sessions alone."
else
  "${TM[@]}" kill-server 2>/dev/null || true
fi

ALL=("${SESSIONS[@]}" "$HOME_SESSION")

i=0
for name in "${ALL[@]}"; do
  # No shell-command here on purpose: tmux then starts your default shell,
  # which is the one case that always survives. A `; exec $SHELL` command
  # dies immediately under some shells and takes the whole server with it.
  "${TM[@]}" new-session -d -s "$name" -n "$name" -x 200 -y 50
  render "$name" "$i" "$BANNER_DIR/$i.txt"
  i=$(( i + 1 ))
done

# Options need a live server, so they come after the first session exists.
"${TM[@]}" set-option -g automatic-rename off
"${TM[@]}" set-option -g allow-rename off

# Give every shell a moment to draw its prompt before typing at it.
sleep 1

i=0
for name in "${ALL[@]}"; do
  "${TM[@]}" rename-window -t "$name" "$name"
  "${TM[@]}" send-keys -t "$name" "clear; cat $BANNER_DIR/$i.txt" Enter
  i=$(( i + 1 ))
done

# Same bindings the test image uses, so the demo matches the docs.
"${TM[@]}" bind-key -n C-S-l run-shell "$HOPPY popup-switch"
"${TM[@]}" bind-key -n C-S-o run-shell "$HOPPY popup-capital-switch"
"${TM[@]}" bind-key -n C-S-p run-shell "$HOPPY popup-worktree-switch"

# A loud status bar makes the switch obvious on video.
"${TM[@]}" set-option -g status-left "#[bg=colour33,fg=colour231,bold]  #S  #[default] "
"${TM[@]}" set-option -g status-left-length 60
"${TM[@]}" set-option -g status-right ""

echo "${#SESSIONS[@]} demo sessions + $HOME_SESSION ready on socket '$SOCKET'."
echo
echo "  Ctrl+Shift+L   switch sessions"
echo "  Ctrl+Shift+O   CAPITAL sessions only"
echo "  Ctrl+Shift+P   git worktree sessions only"
echo
if [ "$SOCKET" = "default" ]; then
  echo "  tear down:   tmux kill-session -t <name>   (one by one)"
else
  echo "  tear down:   tmux -L $SOCKET kill-server"
fi

if [ -n "${NO_ATTACH:-}" ]; then
  echo
  echo "attach with:   ${TM[*]} attach -t $HOME_SESSION"
  exit 0
fi

# A private socket makes nesting safe, so drop TMUX to let attach through.
exec env -u TMUX "${TM[@]}" attach -t "$HOME_SESSION"
