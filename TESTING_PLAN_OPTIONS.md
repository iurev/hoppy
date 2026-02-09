# Integration Testing Options for Tmux Session Manager

## Context
The tool will be rewritten in Python. We need integration tests that run in Docker with keyboard interactions, similar to Playwright tests.

---

## Option 1: Python + pexpect + pytest (Recommended)

**Approach:** Use Python's `pexpect` library to automate terminal interactions.

### Pros:
- **Same ecosystem** - Tool will be in Python
- Mature library for terminal automation
- Built specifically for this use case
- Good documentation and examples
- Easy pattern matching
- Rich assertion capabilities with pytest
- Excellent Docker support
- Can build Playwright-like abstractions

### Cons:
- Need to handle timing issues (wait for renders)
- ANSI escape codes need cleanup

### Example Test Structure:
```python
import pexpect
import pytest
from pathlib import Path

class TmuxSession:
    """Playwright-like API for tmux testing"""

    def __init__(self, width=80, height=30):
        self.width = width
        self.height = height
        self.tmux = None

    def launch(self):
        """Launch tmux session"""
        self.tmux = pexpect.spawn(
            'tmux',
            ['new-session', '-s', 'test'],
            dimensions=(self.height, self.width),
            encoding='utf-8'
        )
        self.tmux.expect('\$')
        return self

    def run_command(self, cmd):
        """Run a command in tmux"""
        self.tmux.sendline(cmd)

    def press(self, key):
        """Press a key"""
        self.tmux.send(key)

    def expect(self, pattern, timeout=5):
        """Wait for pattern to appear"""
        self.tmux.expect(pattern, timeout=timeout)

    def screenshot(self, filepath):
        """Capture screen to file"""
        output = self.tmux.before + self.tmux.after
        Path(filepath).write_text(output)

    def close(self):
        """Close tmux session"""
        if self.tmux:
            self.tmux.close()


# Test example
@pytest.fixture
def tmux():
    """Create tmux session for testing"""
    session = TmuxSession().launch()
    yield session
    session.close()


def test_switch_with_number_key(tmux):
    """Test switching sessions with number key"""
    # Arrange: Create test sessions
    tmux.run_command('tmux new-session -d -s session1')
    tmux.run_command('tmux new-session -d -s session2')

    # Act: Run script and press '1'
    tmux.run_command('./session-manager.py switch')
    tmux.expect('Select target session')
    tmux.press('1')

    # Assert: Should switch to session1
    tmux.expect('session1')

    # Screenshot for debugging
    tmux.screenshot('test_output/switch_test.txt')


def test_kill_session_with_del_key(tmux):
    """Test killing session with DEL key"""
    # Arrange
    tmux.run_command('tmux new-session -d -s temp-session')

    # Act
    tmux.run_command('./session-manager.py switch')
    tmux.expect('Select target session')
    tmux.press('\x7f')  # DEL key

    # Assert
    tmux.expect('Kill session')
    tmux.press('y')
    tmux.expect('killed')


def test_worktree_switch(tmux):
    """Test filtering sessions by git worktree"""
    # Arrange: Create sessions in different directories
    tmux.run_command('cd /workspace/project1')
    tmux.run_command('tmux new-session -d -s project1-main')

    # Act
    tmux.run_command('./session-manager.py worktree-switch')
    tmux.expect('Worktree sessions')

    # Assert: Should only show project1 sessions
    tmux.expect('project1-main')

    # Should NOT show other sessions
    assert 'other-project' not in tmux.tmux.before
```

### Required Packages:
```txt
pexpect>=4.8.0
pytest>=7.0.0
pytest-timeout>=2.1.0
```

### Additional Test Utilities:
```python
# helpers/tmux_utils.py
def clean_ansi(text):
    """Remove ANSI escape codes"""
    import re
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

def wait_for_fzf(tmux, timeout=2):
    """Wait for fzf to be ready"""
    tmux.expect('>', timeout=timeout)
```

---

## Option 3: Tmux Script Testing Framework (Custom)

**Approach:** Build a custom test framework using tmux's built-in commands and shell scripts.

### Pros:
- No external dependencies
- Direct tmux control
- Fast execution
- Easy to understand

### Cons:
- Need to build the framework yourself
- Less sophisticated assertions
- Harder to debug

### Example Test Structure:
```bash
#!/bin/bash

test_switch_with_number_key() {
  # Setup
  tmux new-session -d -s test1
  tmux new-session -d -s test2
  tmux new-session -d -s test3

  # Start script in a tmux pane
  tmux split-window -h "./session-zx.mjs switch"
  sleep 0.5

  # Send key '1'
  tmux send-keys -t test '1' Enter
  sleep 0.2

  # Capture output
  output=$(tmux capture-pane -p -t test)

  # Assert
  echo "$output" | grep -q "test1" && echo "PASS" || echo "FAIL"

  # Cleanup
  tmux kill-session -t test1
  tmux kill-session -t test2
  tmux kill-session -t test3
}
```

---

## Option 4: Playwright for Terminal (tmux-playwright - Custom Library)

**Approach:** Build a Playwright-like API specifically for tmux testing.

### Pros:
- API feels exactly like Playwright
- Great developer experience
- Reusable across projects
- Screenshot/video capabilities

### Cons:
- Significant upfront investment
- Need to build and maintain the library

### Example Test Structure:
```javascript
import { TmuxTest } from './tmux-playwright';

describe('Session Manager', () => {
  let tmux;

  beforeEach(async () => {
    tmux = await TmuxTest.launch({
      docker: true,
      width: 80,
      height: 30,
    });
  });

  test('switch with number key', async () => {
    // Navigate
    await tmux.exec('./session-zx.mjs switch');

    // Interact
    await tmux.keyboard.press('1');

    // Assert
    await tmux.expect('session-name').toBeVisible();

    // Screenshot
    await tmux.screenshot('after-switch.txt');
  });

  afterEach(async () => {
    await tmux.close();
  });
});
```

### What You'd Build:
- `TmuxTest` class with Docker support
- Keyboard simulation
- Screen capture and assertions
- Wait utilities
- Screenshot/recording

---

## Option 5: Expect + TAP (Traditional Unix Way)

**Approach:** Use TCL's `expect` with TAP output format.

### Pros:
- Battle-tested for decades
- Designed for this exact use case
- Available everywhere

### Cons:
- TCL syntax (less familiar)
- Old-school tooling
- Harder to integrate with modern CI

### Example Test Structure:
```tcl
#!/usr/bin/expect

spawn tmux new-session -s test
expect "$"

send "./session-zx.mjs switch\r"
expect "Select target session"

send "1"
expect "session-name"

puts "ok 1 - switch with number key"
exit 0
```

---

## Recommendation: Option 1 (Python + pexpect + pytest)

**Why:**
1. **Same ecosystem** - Tool will be written in Python
2. **Mature and proven** - pexpect is battle-tested for terminal automation
3. **Playwright-like feel** - Can build similar abstractions easily
4. **Excellent pytest integration** - Modern testing features (fixtures, parametrize, etc)
5. **Great Docker support** - Easy to run in containers
6. **Good debugging** - Screenshots, logs, and pytest's detailed output

**Implementation Plan:**

1. Create test helper class `TmuxSession` (Playwright-like API)
2. Wrap `pexpect` with clean, intuitive methods
3. Add utilities: `wait_for`, `press`, `expect`, `screenshot`
4. Write tests with clear arrange/act/assert pattern
5. Run in Docker with minimal tmux config
6. Add pytest fixtures for common setups

---

## Docker Setup (All Options)

**Minimal Dockerfile:**
```dockerfile
FROM python:3.11-slim

# Install tmux and fzf
RUN apt-get update && apt-get install -y \
    tmux \
    fzf \
    git \
    && rm -rf /var/lib/apt/lists/*

# Minimal tmux config (no status bar, clean output)
RUN echo "set -g status off" > /root/.tmux.conf && \
    echo "set -g default-terminal 'screen'" >> /root/.tmux.conf && \
    echo "set -g escape-time 10" >> /root/.tmux.conf

WORKDIR /app

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

CMD ["pytest", "-v", "--tb=short"]
```

**requirements.txt:**
```txt
pexpect>=4.8.0
pytest>=7.0.0
pytest-timeout>=2.1.0
```

**docker-compose.yml** (for easier testing):
```yaml
version: '3.8'

services:
  test:
    build: .
    volumes:
      - .:/app
    environment:
      - TERM=xterm-256color
    command: pytest -v
```

---

## Testing During Rewrite

**Strategy:**

1. **Write tests first** (TDD approach)
   - Define expected behavior in tests
   - Rewrite Python code to pass tests
   - Ensures feature parity

2. **Parallel testing**
   - Keep JS version running
   - Test both versions with same test cases
   - Compare outputs

3. **Incremental migration**
   - Test each action separately (switch, new, rename, etc)
   - Build confidence incrementally

**Test Structure:**
```
tests/
├── conftest.py           # Pytest fixtures
├── helpers/
│   ├── tmux_session.py   # TmuxSession class
│   └── utils.py          # Helper functions
├── test_switch.py        # Switch session tests
├── test_new.py           # New session tests
├── test_kill.py          # Kill session tests
├── test_worktree.py      # Worktree filter tests
└── test_capital.py       # Capital filter tests
```

---

## Next Steps

Choose an option and I can:
1. Create the full test framework structure
2. Write the `TmuxSession` helper class
3. Write example tests for all actions
4. Set up Docker configuration
5. Create pytest configuration
6. Set up CI/CD pipeline

**Recommended:** Start with Option 1 (Python + pexpect) since it aligns with the rewrite.

Which option do you prefer?
