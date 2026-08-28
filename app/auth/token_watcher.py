import threading
import time
from typing import Optional

from .token_manager import TokenManager


class TokenWatcher:
    """
    Runs forever:
    - every 30 minutes checks if token exists / valid
    - refreshes if needed
    """
    def __init__(self, token_manager: TokenManager, interval_seconds: int = 1800):
        self.token_manager = token_manager
        self.interval_seconds = interval_seconds
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.token_manager.get_valid_access_token()
                # You can log a small message if you want:
                # print("✅ Access token ensured (length):", len(token))
            except Exception as e:
                print("⚠️ TokenWatcher error:", str(e))

            # sleep in small chunks so stop() is responsive
            slept = 0
            while slept < self.interval_seconds and not self._stop_event.is_set():
                time.sleep(1)
                slept += 1
