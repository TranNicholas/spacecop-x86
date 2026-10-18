"""Console framing and restart policy, independent of Linux device adapters."""


RESET_MARKERS = {
    "Exiting cFE with PROCESSOR Reset status": "PR",
    "Exiting cFE with POWERON Reset status": "PO",
}


class FlightConsole:
    """Convert PTY bytes to lines and recognize cFE's reset exit markers."""

    def __init__(self, emit):
        self.emit = emit
        self.pending = b""
        self.reset_type = None

    def _emit_line(self, raw):
        line = raw.decode(errors="replace").rstrip("\r")
        self.emit(line)
        for marker, reset_type in RESET_MARKERS.items():
            if marker in line:
                self.reset_type = reset_type

    def feed(self, data):
        self.pending += data
        while b"\n" in self.pending:
            raw, self.pending = self.pending.split(b"\n", 1)
            self._emit_line(raw)

    def finish(self):
        if self.pending:
            self._emit_line(self.pending)
            self.pending = b""


def launch_command(command, first_launch):
    """Request a power-on reset only for a newly created supervisor."""
    return [*command, "-R", "PO"] if first_launch else list(command)
