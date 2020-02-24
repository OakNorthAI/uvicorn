from .reloaderbase import ReloaderBase
import logging
import os
from pathlib import Path

import click

from uvicorn.subprocess import get_subprocess

logger = logging.getLogger("uvicorn.error")


class StatReload(ReloaderBase):
    def __init__(self, config, target, sockets):
        super().__init__(config, target, sockets)
        logger.info("Use StatReload.")

    def watch_and_reload(self):
        if self.should_restart():
            self.restart()

    def should_restart(self):
        for filename in self.iter_py_files():
            try:
                mtime = os.path.getmtime(filename)
            except OSError as exc:  # pragma: nocover
                continue

            old_time = self.mtimes.get(filename)
            if old_time is None:
                self.mtimes[filename] = mtime
                continue
            elif mtime > old_time:
                display_path = os.path.normpath(filename)
                if Path.cwd() in Path(filename).parents:
                    display_path = os.path.normpath(os.path.relpath(filename))
                message = "Detected file change in '%s'. Reloading..."
                logger.warning(message, display_path)
                return True
        return False

    def iter_py_files(self):
        for reload_dir in self.config.reload_dirs:
            for subdir, dirs, files in os.walk(reload_dir):
                for file in files:
                    if file.endswith(".py"):
                        yield subdir + os.sep + file
