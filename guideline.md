# Comprehensive Test Guidelines for hoppy.mjs

This document provides detailed requirements and examples for writing integration tests for the tmux session manager script.

## 1. Core Testing Philosophy

### Requirement: Tests MUST verify actual behavior, not just "script ran successfully"

**GOOD:**
```python
def test_session_switch_actually_works():
    os.system("tmux new-session -d -s switch_from")
    os.system("tmux new-session -d -s switch_to")

    # Run script and select target session
    os.system("tmux send-keys -t switch_from 'node /app/hoppy.mjs switch' Enter")
    time.sleep(1.0)
    os.system("tmux send-keys -t switch_from 'switch_to'")
    os.system("tmux send-keys -t switch_from Enter")
    time.sleep(0.5)

    # VERIFY WE ACTUALLY SWITCHED
    current = os.popen("tmux display-message -p '#S'").read().strip()
    assert current == "switch_to", f"Did not switch! Still in {current}"
```

**BAD:**
```python
def test_session_switch():
    os.system("tmux new-session -d -s test")

    # Run script
    result = os.system("node /app/hoppy.mjs switch")

    # Just check script didn't crash
    assert result == 0  # BULLSHIT - doesn't verify switching happened!
```

---

### Requirement: Tests MUST test the JavaScript script, not just tmux commands

**GOOD:**
```python
def test_script_lists_sessions():
    os.system("tmux new-session -d -s alpha")
    os.system("tmux new-session -d -s beta")

    # Run THE SCRIPT'S action
    output = os.popen("node /app/hoppy.mjs reload-sessions").read()

    # Verify THE SCRIPT listed them
    assert "alpha" in output
    assert "beta" in output
```

**BAD:**
```python
def test_kill_session():
    os.system("tmux new-session -d -s kill_me")

    # Just run tmux command directly
    os.system("tmux kill-session -t kill_me")  # NOT TESTING THE SCRIPT!

    sessions = os.popen("tmux list-sessions").read()
    assert "kill_me" not in sessions
```

---

### Requirement: Tests should catch real regressions

**GOOD:**
```python
def test_number_key_quick_select():
    os.system("tmux new-session -d -s num_first")
    os.system("tmux new-session -d -s num_second")

    initial = os.popen("tmux display-message -t num_first -p '#S'").read().strip()

    # Run script and press '2'
    os.system("tmux send-keys -t num_first 'node /app/hoppy.mjs switch' Enter")
    time.sleep(1.0)
    os.system("tmux send-keys -t num_first '2'")
    time.sleep(0.8)

    current = os.popen("tmux display-message -p '#S'").read().strip()

    # VERIFY we switched to DIFFERENT session
    assert current != initial, f"Number key did not switch! Still in {current}"
```

**BAD:**
```python
def test_number_key():
    os.system("tmux new-session -d -s one")
    os.system("tmux new-session -d -s two")

    # Run script
    os.system("node /app/hoppy.mjs switch")

    current = os.popen("tmux display-message -p '#S'").read().strip()

    # Just check it's one of them - doesn't prove pressing '2' did anything!
    assert current in ["one", "two"]  # BULLSHIT - could still be in 'one'!
```

## 2. Testing User Workflow with Keybindings

### **CRITICAL REQUIREMENT:** Use keybindings whenever possible - Test how users ACTUALLY work

The goal is to test the **real user workflow**, not just isolated script execution. Users interact with the tool via keybindings (Ctrl+Shift+L), not by running `node script.js` directly.

**Rule:** Ctrl+Shift+L is ALWAYS better than `node script.js`

**GOOD (testing user workflow):**
```python
def test_user_workflow_with_keybinding():
    os.system("tmux new-session -d -s test")

    # Attach to session to simulate real usage
    os.system("tmux attach -t test")

    # User presses Ctrl+Shift+L - this is what we're testing!
    # Note: In detached sessions, we simulate by running what the keybinding triggers
    os.system("tmux send-keys -t test 'node /app/hoppy.mjs popup-switch' Enter")

    # Or better yet, if we can trigger the keybinding directly:
    # os.system("tmux send-keys -t test C-S-l")  # Only works in attached sessions!
```

**BAD (testing script in isolation):**
```python
def test_script_directly():
    # Just run the script - this is NOT how users work with it!
    os.system("node /app/hoppy.mjs switch")  # WRONG - users use Ctrl+Shift+L!

    # This tests the script works, but NOT the user workflow
```

### Why Keybindings Matter

Users don't type commands - they press keys:
- Real workflow: User is in tmux → presses Ctrl+Shift+L → popup appears
- Test workflow should match: Test session → trigger keybinding → verify result

**What we're testing:**
1. ✅ Keybinding is configured correctly in tmux
2. ✅ Keybinding triggers the correct script action
3. ✅ Script runs with correct environment from tmux
4. ✅ Full integration: tmux → keybinding → script → fzf → result

**What we're NOT testing when running script directly:**
1. ❌ Keybinding configuration
2. ❌ Tmux environment setup
3. ❌ Integration between tmux and script
4. ❌ Real user experience

### Workaround for Detached Sessions

**Problem:** `send-keys C-S-l` doesn't work in detached tmux sessions (test limitation)

**Solution:** Run the action that the keybinding would trigger:

```python
# Instead of triggering Ctrl+Shift+L directly (doesn't work in detached)
# os.system("tmux send-keys -t test C-S-l")  # Doesn't work!

# Run what Ctrl+Shift+L would execute
os.system("tmux send-keys -t test 'node /app/hoppy.mjs popup-switch' Enter")

# This simulates the keybinding behavior while testing in detached mode
```

### Keybinding Priority

**Priority order for testing:**
1. **BEST:** Trigger actual keybinding (Ctrl+Shift+L) if possible
2. **GOOD:** Run the script action the keybinding triggers (`popup-switch`)
3. **ACCEPTABLE:** Run script with basic action (`switch`) for non-popup tests
4. **BAD:** Run script without action (just shows menu)
5. **WORST:** Don't run script at all (just test tmux)

### Example: Complete User Workflow Test

**GOOD:**
```python
def test_complete_user_workflow():
    """Test the ENTIRE user workflow from keybinding to result."""
    # Setup: User has sessions
    os.system("tmux new-session -d -s work")
    os.system("tmux new-session -d -s personal")

    # User is in 'work' session
    before = os.popen("tmux display-message -t work -p '#S'").read().strip()
    assert before == "work"

    # User presses Ctrl+Shift+L (we simulate by running what it triggers)
    os.system("tmux send-keys -t work 'node /app/hoppy.mjs popup-switch' Enter")
    time.sleep(1.0)  # Popup appears with fzf

    # User types to filter
    os.system("tmux send-keys -t work 'personal'")
    time.sleep(0.3)

    # User presses Enter to select
    os.system("tmux send-keys -t work Enter")
    time.sleep(0.5)

    # VERIFY: User is now in 'personal' session
    after = os.popen("tmux display-message -p '#S'").read().strip()
    assert after == "personal", f"Workflow failed! Still in {after}"

    # This tests the COMPLETE user experience!
```

**BAD:**
```python
def test_just_script():
    """This doesn't test user workflow at all."""
    os.system("tmux new-session -d -s work")
    os.system("tmux new-session -d -s personal")

    # Just run script - user never does this!
    os.system("node /app/hoppy.mjs switch")

    # Missing: keybinding, tmux integration, real workflow
```

### Available Keybindings to Test

Test these user workflows:
- **Ctrl+Shift+L** → General session switching (`popup-switch`)
- **Ctrl+Shift+O** → Capital sessions only (`popup-capital-switch`)
- **Ctrl+Shift+P** → Worktree sessions only (`popup-worktree-switch`)

Each keybinding represents a different user workflow that MUST be tested.

---

## 3. Script Execution Requirements

### Requirement: Must run the script with specific actions

**GOOD:**
```python
# Test reload-sessions action
output = os.popen("node /app/hoppy.mjs reload-sessions").read()
assert "alpha" in output

# Test switch action with interaction
os.system("tmux send-keys -t test 'node /app/hoppy.mjs switch' Enter")
```

**BAD:**
```python
# Just run script with no action
os.system("node /app/hoppy.mjs")  # Shows menu but doesn't test anything

# Or don't run script at all
os.system("tmux switch-client -t target")  # Testing tmux, not the script!
```

### Available Script Actions:
- `switch` - Interactive session switching with fzf
- `reload-sessions` - List all sessions (bypasses fzf)
- `new` - Create new session (with tmux input prompt)
- `popup-switch` - What Ctrl+Shift+L triggers
- `popup-capital-switch` - What Ctrl+Shift+O triggers
- `popup-worktree-switch` - What Ctrl+Shift+P triggers

## 4. Keybinding & Configuration

### Requirement: Use SAME config as production, no test-specific configs

**GOOD:**
```python
# Dockerfile has production keybindings
RUN cat > /root/.tmux.conf << 'EOF'
bind-key -n C-S-l run-shell "/app/hoppy.mjs popup-switch"
bind-key -n C-S-o run-shell "/app/hoppy.mjs popup-capital-switch"
EOF

# Test simulates what keybinding does
os.system("node /app/hoppy.mjs popup-switch")
```

**BAD:**
```python
# Add test-specific keybinding
RUN cat >> /root/.tmux.conf << 'EOF'
bind-key -n C-t run-shell "test-mode"  # WRONG - not production config!
EOF

# Or try to trigger keybinding in detached session
os.system("tmux send-keys -t test C-S-l")  # Doesn't work in detached!
```

### Required Keybindings in Docker tmux:
- `Ctrl+Shift+L` → `/app/hoppy.mjs popup-switch`
- `Ctrl+Shift+O` → `/app/hoppy.mjs popup-capital-switch`
- `Ctrl+Shift+P` → `/app/hoppy.mjs popup-worktree-switch`

## 5. fzf Interaction Testing

### Requirement: Must verify keyboard interactions work

**GOOD:**
```python
def test_escape_returns_to_shell():
    os.system("tmux new-session -d -s escape_test")

    # Run script - fzf should appear
    os.system("tmux send-keys -t escape_test 'node /app/hoppy.mjs switch' Enter")
    time.sleep(1.0)

    during = os.popen("tmux capture-pane -t escape_test -p").read()
    assert ">" in during, "fzf not showing"

    # Press ESC
    os.system("tmux send-keys -t escape_test Escape")
    time.sleep(0.5)

    # VERIFY we're back at shell
    after = os.popen("tmux capture-pane -t escape_test -p").read()
    assert ">" not in after or "$" in after, "Did not return to shell"
```

**BAD:**
```python
def test_navigation():
    # Run script
    os.system("node /app/hoppy.mjs switch")

    # Just check sessions are shown - doesn't test Ctrl+N does anything!
    output = os.popen("node /app/hoppy.mjs reload-sessions").read()
    assert "session" in output  # NONSENSE - doesn't test navigation!
```

### Keyboard Interactions to Test:

**Navigation:**
- Arrow keys (Up/Down) change selection
- Ctrl+N / Ctrl+P change selection
- Typing filters the list

**Selection:**
- Number keys (1-9) for quick selection
- Enter to select highlighted item
- ESC to cancel and return to shell

**Actions:**
- DEL key to kill session (with Y/N confirmation)

## 6. Behavior Verification Requirements

### Session Switching

**GOOD:**
```python
def test_switch():
    os.system("tmux new-session -d -s A")
    os.system("tmux new-session -d -s B")

    # Start in A
    before = os.popen("tmux display-message -t A -p '#S'").read().strip()
    assert before == "A"

    # Switch to B
    os.system("tmux send-keys -t A 'node /app/hoppy.mjs switch' Enter")
    time.sleep(1.0)
    os.system("tmux send-keys -t A 'B'")
    os.system("tmux send-keys -t A Enter")
    time.sleep(0.5)

    # VERIFY we're now in B
    after = os.popen("tmux display-message -p '#S'").read().strip()
    assert after == "B", f"Did not switch! Still in {after}"
```

**BAD:**
```python
def test_switch():
    os.system("tmux new-session -d -s A")
    os.system("tmux new-session -d -s B")

    # Run script
    os.system("node /app/hoppy.mjs switch")

    # Just check B exists - doesn't verify we switched TO it!
    sessions = os.popen("tmux list-sessions").read()
    assert "B" in sessions  # BULLSHIT - doesn't prove switching worked!
```

### Frecency Sorting

**GOOD:**
```python
def test_frecency_sorting():
    os.system("tmux new-session -d -s rarely")
    os.system("tmux new-session -d -s often")

    # Access 'often' multiple times to boost frecency
    for _ in range(3):
        os.system("tmux switch-client -t often")
        time.sleep(0.2)

    # Get session list
    output = os.popen("node /app/hoppy.mjs reload-sessions").read()
    lines = output.split('\n')

    # Find indices
    often_index = next(i for i, l in enumerate(lines) if "often" in l)
    rarely_index = next(i for i, l in enumerate(lines) if "rarely" in l)

    # VERIFY 'often' appears BEFORE 'rarely'
    assert often_index < rarely_index, \
        f"Frecency not working: often at {often_index}, rarely at {rarely_index}"
```

**BAD:**
```python
def test_frecency():
    os.system("tmux new-session -d -s test")

    # Just check session is listed
    output = os.popen("node /app/hoppy.mjs reload-sessions").read()
    assert "test" in output  # Doesn't test sorting at all!
```

### Kill Session

**GOOD:**
```python
def test_kill():
    os.system("tmux new-session -d -s kill_me")
    os.system("tmux new-session -d -s keep_me")

    # Verify both exist
    before = os.popen("tmux list-sessions").read()
    assert "kill_me" in before
    assert "keep_me" in before

    # Run script and kill kill_me
    os.system("tmux send-keys -t keep_me 'node /app/hoppy.mjs switch' Enter")
    time.sleep(1.0)
    os.system("tmux send-keys -t keep_me 'kill_me'")
    os.system("tmux send-keys -t keep_me DEL")
    time.sleep(0.5)
    os.system("tmux send-keys -t keep_me 'y'")
    time.sleep(0.5)

    # VERIFY kill_me is GONE and keep_me still EXISTS
    after = os.popen("tmux list-sessions").read()
    assert "kill_me" not in after, "Session was not killed!"
    assert "keep_me" in after, "Wrong session was killed!"
```

**BAD:**
```python
def test_kill():
    os.system("tmux new-session -d -s test")

    # Just run tmux kill directly
    os.system("tmux kill-session -t test")  # NOT TESTING THE SCRIPT!

    assert "test" not in os.popen("tmux list-sessions").read()
```

**NOTE:** DEL key doesn't work reliably in detached tmux sessions - this test should be skipped.

### Session Listing

**GOOD:**
```python
def test_listing():
    sessions = ["alpha", "beta", "gamma"]
    for s in sessions:
        os.system(f"tmux new-session -d -s {s}")

    # Get SCRIPT output
    output = os.popen("node /app/hoppy.mjs reload-sessions").read()

    # Verify ALL sessions in output
    for s in sessions:
        assert s in output, f"Session {s} not listed"

    # Verify formatting
    assert "[" in output and "]" in output, "No number prefixes"
    assert "@" in output, "No delimiter"
    assert "windows" in output, "No window count"
```

**BAD:**
```python
def test_listing():
    os.system("tmux new-session -d -s test")

    # Use tmux command instead of script
    output = os.popen("tmux list-sessions").read()  # NOT TESTING THE SCRIPT!
    assert "test" in output
```

### Expected Output Format:
```
[1] session_name @ 3 windows
[2] another_session @ 1 windows
```

## 7. Docker Environment Setup

**GOOD:**
```dockerfile
# Dockerfile - Complete setup
FROM python:3.11-slim

# Install all dependencies
RUN apt-get update && apt-get install -y \
    tmux \
    fzf \
    git \
    curl

# Install Node.js 20
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs

# Create production tmux config
RUN mkdir -p /root && cat > /root/.tmux.conf << 'EOF'
set -g status off
bind-key -n C-S-l run-shell "/app/hoppy.mjs popup-switch"
EOF
```

**BAD:**
```dockerfile
# Incomplete setup
FROM python:3.11-slim

# Missing tmux, fzf, node!
RUN apt-get update && apt-get install -y git

# No tmux config - tests will have different environment!
```

### Required Dependencies:
- **Base:** python:3.11-slim
- **System:** tmux, fzf, git, curl
- **Node.js:** Version 20
- **Node packages:** zx, node-localstorage, @getstation/frecency
- **Python packages:** pexpect, pytest, pytest-timeout
- **Environment:** TERM=xterm-256color, NODE_ENV=test

## 8. Test Implementation Patterns

### Timing

**GOOD:**
```python
# Give operations time to complete
os.system("tmux send-keys -t test 'node /app/hoppy.mjs switch' Enter")
time.sleep(1.0)  # Wait for fzf to load

os.system("tmux send-keys -t test 'filter'")
time.sleep(0.3)  # Wait for fzf to filter

os.system("tmux send-keys -t test Enter")
time.sleep(0.5)  # Wait for switch to complete
```

**BAD:**
```python
# No timing - race conditions!
os.system("tmux send-keys -t test 'node /app/hoppy.mjs switch' Enter")
os.system("tmux send-keys -t test Enter")  # Runs before fzf loads!
current = os.popen("tmux display-message -p '#S'").read()  # Reads before switch!
```

### Cleanup

**GOOD:**
```python
def test_something():
    os.system("tmux new-session -d -s test1")
    os.system("tmux new-session -d -s test2")

    try:
        # Test logic here
        pass
    finally:
        # ALWAYS cleanup even if test fails
        os.system("tmux kill-session -t test1 2>/dev/null")
        os.system("tmux kill-session -t test2 2>/dev/null")
```

**BAD:**
```python
def test_something():
    os.system("tmux new-session -d -s test")

    # Test logic

    # No cleanup - sessions leak between tests!
```

### Verification

**GOOD:**
```python
# Verify BEFORE state
before = os.popen("tmux display-message -t A -p '#S'").read().strip()
assert before == "A", f"Initial state wrong: {before}"

# Perform action
os.system("tmux send-keys -t A 'node /app/hoppy.mjs switch' Enter")
time.sleep(1.0)
os.system("tmux send-keys -t A 'B' Enter")
time.sleep(0.5)

# Verify AFTER state
after = os.popen("tmux display-message -p '#S'").read().strip()
assert after == "B", f"Did not switch! Still in {after}"
```

**BAD:**
```python
# No before state check
os.system("node /app/hoppy.mjs switch")

# Weak after check
sessions = os.popen("tmux list-sessions").read()
assert len(sessions) > 0  # Proves nothing!
```

### Recommended Timing Values:
- **fzf load:** 1.0 seconds
- **fzf filter:** 0.3 seconds
- **Session switch:** 0.5 seconds
- **Window creation:** 0.3 seconds
- **Session creation:** 0.5 seconds
- **Key press response:** 0.2 seconds

## 9. Output Capture Requirements

**GOOD:**
```python
# Use script's direct output (bypasses fzf)
output = os.popen("node /app/hoppy.mjs reload-sessions").read()
assert "session_name" in output

# Use tmux display-message for current session
current = os.popen("tmux display-message -p '#S'").read().strip()
assert current == "expected"

# Use tmux list-sessions to check existence
sessions = os.popen("tmux list-sessions 2>&1").read()
assert "session_name" in sessions
```

**BAD:**
```python
# Try to capture popup output
output = os.popen("tmux capture-pane -t test -p").read()  # Won't capture popup!

# Or no verification at all
os.system("node /app/hoppy.mjs switch")
# How do we know it worked???
```

### Why capture-pane doesn't work:
- `popup-switch` creates a separate popup window
- `capture-pane` only captures the main pane
- Popups are separate tmux panes that aren't captured

### Solutions:
1. Use `reload-sessions` action to get direct output
2. Use `tmux display-message -p '#S'` to check current session
3. Use `tmux list-sessions` to verify session existence
4. Run script directly with `switch` action (not popup)

## 10. Test Files Structure

**GOOD:**
```python
# tests/test_real_behavior.py - Tests ACTUAL behavior

def test_session_switch_actually_works():
    """Test that we can actually SWITCH from one session to another."""
    # Creates sessions, runs script, VERIFIES switch happened
    assert current == "switch_to", f"Did not switch! Still in {current}"

def test_number_key_quick_select():
    """Test that pressing number 2 actually selects a different session."""
    # VERIFIES we switched to DIFFERENT session
    assert current != initial, f"Number key did not switch!"
```

**BAD:**
```python
# tests/test_full_integration.py - "Bullshit" tests

def test_script_navigation_with_ctrl_n():
    """Test Ctrl+N navigation."""
    # Runs script, gets session list
    output = os.popen("node /app/hoppy.mjs reload-sessions").read()
    assert "session" in output  # NONSENSE - doesn't test Ctrl+N at all!

def test_kill_session_with_tmux_command():
    """Test killing session."""
    os.system("tmux kill-session -t test")  # NOT TESTING THE SCRIPT!
    assert "test" not in os.popen("tmux list-sessions").read()
```

### Recommended Test Organization:

**tests/test_script_executes.py** - Smoke tests
- Script runs without errors
- Script shows action menu
- Script exits cleanly

**tests/test_script_functionality.py** - Script logic tests
- `reload-sessions` action lists all sessions
- Session formatting is correct
- Window counts are accurate
- Special characters are handled

**tests/test_real_behavior.py** - ACTUAL behavior tests
- Session switching works (A → B)
- Number keys trigger switching
- Frecency sorting works
- ESC returns to shell
- Filtering works

## 11. What NOT to Test

**GOOD (testing script behavior):**
```python
# Test the script handles switching
os.system("tmux send-keys -t A 'node /app/hoppy.mjs switch' Enter")
current = os.popen("tmux display-message -p '#S'").read().strip()
assert current == "B"
```

**BAD (just testing tmux works):**
```python
# Just verify tmux switch-client works
os.system("tmux switch-client -t B")
current = os.popen("tmux display-message -p '#S'").read().strip()
assert current == "B"  # This tests tmux, not the script!
```

---

**GOOD (verifying state change):**
```python
# Capture before and after
before = get_current_session()
run_script_action()
after = get_current_session()
assert before != after  # Proves state changed
```

**BAD (just verifying output exists):**
```python
# Just check output contains something
output = run_script()
assert len(output) > 0  # Proves nothing!
assert "session" in output  # Proves nothing!
```

## Summary of Key Principles

1. **Test USER WORKFLOW, not isolated scripts** - ALWAYS prefer keybindings (Ctrl+Shift+L) over running `node script.js` directly
2. **Test behavior, not execution** - Verify state changes, not just "script ran"
3. **Test the script, not tmux** - Run the JavaScript script, don't just use tmux commands
4. **Verify before and after** - Check initial state, perform action, verify result
5. **Use production config** - Same tmux config as real usage
6. **Give operations time** - Use appropriate sleep() delays
7. **Always cleanup** - Use try/finally to kill test sessions
8. **Catch real regressions** - Tests should fail if features break
9. **Document with tests** - Tests serve as specification for Python rewrite

## Anti-Patterns to Avoid

- ❌ **Running `node script.js` directly instead of using keybindings** - Users don't type commands, they press keys!
- ❌ Testing tmux commands instead of the script
- ❌ Testing script in isolation without tmux integration
- ❌ No before/after state verification
- ❌ Weak assertions that prove nothing
- ❌ Test-specific configurations
- ❌ No cleanup between tests
- ❌ Race conditions from missing delays
- ❌ Tests that pass even when broken
- ❌ Testing output existence instead of correctness
