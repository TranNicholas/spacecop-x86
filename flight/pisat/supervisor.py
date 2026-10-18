"""Run the unchanged cFS executable and manage its reset lifecycle."""

import errno
import json
import os
import pty
import selectors
import signal
import subprocess
import time
from collections import deque
from pathlib import Path

from .device_host import DeviceHost
from .lifecycle import FlightConsole, launch_command


READ_SIZE = 65_536


class FlightSupervisor:
    """Coordinate devices, cFS reset re-execution, and signals."""

    def __init__(self, settings):
        self.settings = settings
        self.stopping = False
        self.child = None
        self.first_launch = True
        self.resets = deque()
        self.host = DeviceHost(settings)

    def request_stop(self, _signum, _frame):
        self.stopping = True
        if self.child and self.child.poll() is None:
            self.child.terminate()

    def run(self):
        signal.signal(signal.SIGTERM, self.request_stop)
        signal.signal(signal.SIGINT, self.request_stop)
        environment = os.environ | self.host.child_environment()

        try:
            while not self.stopping:
                command = launch_command(self.settings["command"], self.first_launch)
                returncode, reset_type = self._run_once(command, environment)
                self.first_launch = False

                if self.stopping:
                    break
                if returncode != 0 or reset_type is None:
                    return 1
                if self._reset_limit_exceeded():
                    return 1

            return 0
        finally:
            self.host.shutdown()

    def _run_once(self, command, environment):
        master, slave = pty.openpty()
        selector = selectors.DefaultSelector()
        try:
            os.set_blocking(master, False)
            self.child = subprocess.Popen(command, cwd=self.settings["working_directory"],
                                          env=environment, stdin=subprocess.DEVNULL,
                                          stdout=slave, stderr=subprocess.STDOUT)
            os.close(slave)
            slave = None

            selector.register(master, selectors.EVENT_READ)
            console = FlightConsole(lambda line: print(line, flush=True))
            self._serve_child(master, selector, console)
            returncode = self.child.wait()
            self._drain_console(master, console)
            return returncode, console.reset_type
        finally:
            selector.close()
            os.close(master)
            if slave is not None:
                os.close(slave)

    def _serve_child(self, master, selector, console):
        stop_deadline = None
        while self.child.poll() is None:
            if self.stopping and stop_deadline is None:
                stop_deadline = time.monotonic() + self.settings["stop_timeout_seconds"]
            if stop_deadline and time.monotonic() > stop_deadline:
                self.child.kill()

            self.host.feed_payload()
            if selector.select(0.1):
                data = _read_pty(master)
                if data:
                    console.feed(data)

    @staticmethod
    def _drain_console(master, console):
        # poll() can observe exit before the PTY's final bytes are readable.
        while data := _read_pty(master):
            console.feed(data)
        console.finish()

    def _reset_limit_exceeded(self):
        now = time.monotonic()
        self.resets.append(now)
        window = self.settings["reset_window_seconds"]
        while self.resets and now - self.resets[0] > window:
            self.resets.popleft()
        return len(self.resets) > self.settings["max_resets"]


def _read_pty(descriptor):
    try:
        return os.read(descriptor, READ_SIZE)
    except BlockingIOError:
        return b""
    except OSError as exc:
        if exc.errno == errno.EIO:  # Linux PTYs report EIO after the slave closes.
            return b""
        raise


def main():
    settings = json.loads(Path(os.environ["SIL_RUNTIME_PROFILE"]).read_text())
    return FlightSupervisor(settings).run()


if __name__ == "__main__":
    raise SystemExit(main())
