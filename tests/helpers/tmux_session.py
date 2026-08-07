import os
import re
import time

import pexpect


class TmuxSession:
    """Playwright-like API for tmux session testing."""

    def __init__(self, session_name="test_session", width=120, height=30):
        self.session_name = session_name
        self.width = width
        self.height = height
        self.process = None
        self.default_timeout = 10

    def launch(self):
        """Start a new tmux session."""
        # Kill existing session if it exists
        os.system(f"tmux kill-session -t {self.session_name} 2>/dev/null")

        # Start new tmux session
        cmd = f"tmux new-session -s {self.session_name} -x {self.width} -y {self.height}"
        self.process = pexpect.spawn(cmd, encoding='utf-8', timeout=self.default_timeout)

        # Wait for shell prompt
        time.sleep(0.5)
        return self

    def run_command(self, cmd):
        """Execute command in tmux session."""
        if not self.process:
            raise RuntimeError("Session not launched. Call launch() first.")

        self.process.sendline(cmd)
        time.sleep(0.2)
        return self

    def run_popup_switch(self, action="popup-switch", wait=1.5):
        """Run popup action and wait for fzf to render."""
        self.run_command(f"/app/session-zx {action}")
        time.sleep(wait)
        return self

    def press(self, key):
        """Send single keypress."""
        if not self.process:
            raise RuntimeError("Session not launched. Call launch() first.")

        self.process.send(key)
        time.sleep(0.1)
        return self

    def send_keys(self, keys):
        """Send key sequence."""
        if not self.process:
            raise RuntimeError("Session not launched. Call launch() first.")

        self.process.send(keys)
        time.sleep(0.2)
        return self

    def type_and_accept(self, query, type_wait=0.5, accept_wait=1.0):
        """Type query text and press Enter."""
        if query:
            self.send_keys(query)
            time.sleep(type_wait)
        self.press_enter()
        time.sleep(accept_wait)
        return self

    def expect(self, pattern, timeout=None):
        """Wait for output pattern."""
        if not self.process:
            raise RuntimeError("Session not launched. Call launch() first.")

        timeout = timeout or self.default_timeout
        self.process.expect(pattern, timeout=timeout)
        return self

    def wait_for_fzf(self, timeout=5):
        """Wait for fzf prompt to be ready."""
        # Look for fzf's typical prompt indicator
        try:
            self.process.expect(r'>', timeout=timeout)
            time.sleep(0.3)  # Give fzf time to render fully
        except pexpect.TIMEOUT:
            pass  # Continue anyway, fzf might be ready
        return self

    def get_output(self):
        """Get current screen content."""
        if not self.process:
            raise RuntimeError("Session not launched. Call launch() first.")

        # Capture tmux pane content
        output = os.popen(f"tmux capture-pane -t {self.session_name} -p").read()
        return output

    def screenshot(self, filepath):
        """Save output to file."""
        output = self.get_output()
        with open(filepath, 'w') as f:
            f.write(output)
        return self

    def close(self):
        """Cleanup and kill tmux session."""
        if self.process:
            self.process.close(force=True)

        # Kill tmux session
        os.system(f"tmux kill-session -t {self.session_name} 2>/dev/null")

    # fzf interaction helpers

    def press_arrow_down(self):
        """Navigate down in fzf."""
        self.send_keys('\x1b[B')  # Down arrow
        return self

    def press_arrow_up(self):
        """Navigate up in fzf."""
        self.send_keys('\x1b[A')  # Up arrow
        return self

    def press_enter(self):
        """Select item in fzf."""
        self.send_keys('\r')  # Carriage return
        return self

    def press_number(self, n):
        """Quick select with number key (1-9)."""
        if not 1 <= n <= 9:
            raise ValueError("Number must be between 1 and 9")
        self.send_keys(str(n))
        return self

    def press_del(self):
        """Send backspace (0x7f). Named 'del' for legacy reasons — this is actually backspace."""
        self.send_keys('\x7f')  # Backspace
        return self

    def press_backspace(self):
        """Send backspace (0x7f). Same as press_del(), but with a clearer name."""
        self.send_keys('\x7f')
        return self

    def press_delete(self):
        """Send real Delete key (escape sequence). Triggers fzf 'del' event."""
        self.send_keys('\x1b[3~')
        return self

    def press_tab(self):
        """Send Tab key."""
        self.send_keys('\t')
        return self

    def press_escape(self):
        """Cancel fzf selection."""
        self.send_keys('\x1b')  # Escape
        return self

    def press_ctrl_n(self):
        """Send Ctrl+N (preview down)."""
        self.send_keys('\x0e')
        return self

    def press_ctrl_p(self):
        """Send Ctrl+P (preview up)."""
        self.send_keys('\x10')
        return self

    # Utility methods

    def strip_ansi(self, text):
        """Remove ANSI escape codes from text."""
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)

    def wait_for_text(self, text, timeout=5):
        """Wait for specific text to appear in output."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            output = self.get_output()
            if text in output:
                return True
            time.sleep(0.2)
        return False

    def get_current_session(self):
        """Return the session name attached to the first tmux client."""
        result = os.popen("tmux list-clients -F '#{session_name}'").read().strip()
        # Return first line (first client)
        lines = result.split('\n')
        return lines[0] if lines else ''

    def get_all_sessions(self):
        """Return list of all tmux session names."""
        result = os.popen("tmux list-sessions -F '#S'").read().strip()
        if not result:
            return []
        return result.split('\n')

    def wait_for_session_switch(self, target, timeout=5):
        """Poll until the client is attached to target session. Returns True if switched."""
        start = time.time()
        while time.time() - start < timeout:
            current = self.get_current_session()
            if current == target:
                return True
            time.sleep(0.3)
        return False

    def wait_for_session_gone(self, name, timeout=5):
        """Poll until session no longer exists. Returns True if gone."""
        start = time.time()
        while time.time() - start < timeout:
            sessions = self.get_all_sessions()
            if name not in sessions:
                return True
            time.sleep(0.3)
        return False

    def get_pane_content(self, session_name=None):
        """Capture pane content for a session. Uses self.session_name if not given."""
        target = session_name or self.session_name
        return os.popen(f"tmux capture-pane -t '{target}' -p").read()

    def clear_query_backspaces(self, count, delay=0.08):
        """Press backspace many times to clear an fzf query."""
        for _ in range(count):
            self.press_backspace()
            time.sleep(delay)
        return self

    def assert_current_session(self, expected_name):
        """Assert current tmux client session with a clear failure message."""
        current = self.get_current_session()
        assert current == expected_name, (
            f"Expected current session '{expected_name}', got '{current}'"
        )
        return current

    def assert_session_exists(self, session_name):
        """Assert that a session exists."""
        sessions = self.get_all_sessions()
        assert session_name in sessions, (
            f"Expected session '{session_name}' to exist. Sessions: {sessions}"
        )
        return sessions

    def assert_session_missing(self, session_name):
        """Assert that a session does not exist."""
        sessions = self.get_all_sessions()
        assert session_name not in sessions, (
            f"Expected session '{session_name}' to be missing. Sessions: {sessions}"
        )
        return sessions

    def snapshot_state(self):
        """Capture current high-level tmux state for diagnostics."""
        return {
            "current_session": self.get_current_session(),
            "sessions": self.get_all_sessions(),
        }
