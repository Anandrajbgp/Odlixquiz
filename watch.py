"""Auto-reload wrapper for OdlixQuiz bot.
Code mein koi bhi .py file change hote hi bot automatically restart ho jayega.
Istemaal: python watch.py
"""
import os
import sys
import time
import subprocess
import logging

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("watch")

BOT_ENTRY = "bot.py"   # ya main.py, dono same hain
WATCH_EXTENSIONS = (".py", ".env")


class BotReloader(FileSystemEventHandler):
    def __init__(self):
        self.process = None
        self.start_bot()

    def start_bot(self):
        """Bot subprocess start karega."""
        if self.process:
            self.stop_bot()
        logger.info("🚀 Bot start ho raha hai: %s", BOT_ENTRY)
        self.process = subprocess.Popen([sys.executable, BOT_ENTRY])

    def stop_bot(self):
        """Chalte hue bot process ko band karega (Windows compatible)."""
        if self.process and self.process.poll() is None:
            logger.info("🔄 Auto restart ke liye purana bot band kar raha hai...")
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
        self.process = None

    def restart_bot(self):
        """Bot ko restart karega."""
        logger.info("🔄 Code change detected! Bot restart ho raha hai...")
        self.start_bot()

    def on_any_event(self, event):
        if event.is_directory:
            return
        if not event.src_path.endswith(WATCH_EXTENSIONS):
            return
        # Thoda wait taaki file likhna puri tarah complete ho
        time.sleep(0.5)
        self.restart_bot()


def main():
    if not os.path.exists(BOT_ENTRY):
        logger.error(f"{BOT_ENTRY} nahi mila! Is folder se chalaiye.")
        return

    event_handler = BotReloader()
    observer = Observer()
    observer.schedule(event_handler, path=".", recursive=True)
    observer.start()

    logger.info("👀 Auto-reload active. Code change hote hi bot update ho jayega.")
    logger.info("🛑 Rokne ke liye Ctrl+C dabaiye.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("🛑 Watcher band ho raha hai...")
        observer.stop()
        event_handler.stop_bot()
    observer.join()


if __name__ == "__main__":
    main()