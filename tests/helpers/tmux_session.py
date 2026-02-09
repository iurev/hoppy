"""Helper class for interacting with tmux sessions in tests."""
import time
import pexpect
import re
import os


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
        """Delete key for kill action."""
        self.send_keys('\x7f')  # DEL/Backspace
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
