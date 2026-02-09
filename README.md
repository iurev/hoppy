# session-zx.mjs - Tmux Session Manager

## What It Does

This script manages tmux sessions using fzf (a fuzzy finder).

## Core Actions

### 1. Switch Sessions
Change to a different tmux session.

- Shows all sessions in a list
- Sorts by frecency (frequency + recency of use)
- Press 1-9 for quick switch to top 9 sessions
- Press DEL to kill a session
- Press Ctrl+N/Ctrl+P to preview sessions (actually switches to them temporarily)

### 2. New Session
Create a new tmux session.

- Asks for a session name
- Creates and switches to it

### 3. Rename Session
Change a session's name.

### 4. Kill Sessions
Delete one or more sessions.

- Can select multiple sessions with TAB

### 5. Detach Sessions
Disconnect from sessions.

## Special Features

### Worktree Switch
Shows only sessions in git worktrees of current project.

### Capital Switch
Shows only sessions with UPPERCASE names.

### Popup Mode
Opens switcher in a tmux popup window.

## Preview Feature

When you press **Ctrl+N** or **Ctrl+P**:
- The script actually switches to that session temporarily
- You see the real tmux session content
- Keep pressing Ctrl+N/Ctrl+P to preview other sessions
- Press Enter to stay, or Esc to cancel

The script uses a debounce system (300ms delay) to prevent too many rapid switches.

## Technical Details

- Uses frecency scoring (recent usage gets higher priority)
- Validates session names (no special chars, max 100 chars)
- Logs all events to a file
- Adds number prefixes [1]-[9] for quick access

## Usage

Run the script with different actions:

```bash
./session-zx.mjs switch          # Switch sessions
./session-zx.mjs new             # Create new session
./session-zx.mjs rename          # Rename a session
./session-zx.mjs kill            # Kill sessions
./session-zx.mjs detach          # Detach sessions
./session-zx.mjs worktree-switch # Switch within git worktrees
./session-zx.mjs capital-switch  # Switch to CAPITAL sessions
./session-zx.mjs popup-switch    # Open in popup window
```
