import functools
import logging

from uvicorn.supervisors.basereload import BaseReload

logger = logging.getLogger("uvicorn.warning")


class watchman:
    __client = None
    __pywatchman = None

    def __new__(cls, *args, **kwargs):
        if not cls.__client:
            import pywatchman

            cls.__client = pywatchman.client(timeout=20.0)
            cls.__pywatchman = pywatchman
        return cls.__client

    def __init__(self):
        pass

    @staticmethod
    def file_changed():
        try:
            watchman().receive()
            logger.info("Watchman detected file change, about to restart")
            return True
        except watchman.__pywatchman.SocketTimeout:
            return False
        except watchman.__pywatchman.WatchmanError as ex:
            logger.error("Watchman error: %s, checking server status.", ex)
            raise ex


class WatchmanReload(BaseReload):
    def __init__(self, config, target, sockets):
        super().__init__(config, target, sockets)
        logger.info("Use Watchman.")
        self.reloader_name = "watchman"

    def should_restart(self):
        """Note: Blocking method return True when file changed."""
        return watchman.file_changed()

    @classmethod
    def available(cls) -> bool:
        try:
            watchman().capabilityCheck()
            logger.info("Watchman is available")
            return True
        except Exception:
            return False

    def startup(self):
        self.update_watch()
        super().startup()

    def shutdown(self):
        watchman().close()
        super().shutdown()

    def update_watch(self):
        for path in self.config.reload_dirs:
            self._watch(path)
            logger.info("Watchman watching %s", path)

    def _watch(self, root):
        name = "uvicorn-watch-{}-[{}]".format(self.config.app or "", str(root))
        result = watchman().query("watch", root)

        if "warning" in result:
            logger.warning("Watchman warning: %s", result["warning"])
        logger.info("Watchman watch result: %s", result)

        query = {
            "expression": ["allof", ["type", "f"], ["not", "empty"], ["suffix", "py"]],
            "fields": ["name"],
            "since": self._get_clock(root),
            "dedup_results": True,
        }

        watchman().query("subscribe", root, name, query)

    @functools.lru_cache()
    def _get_clock(self, root):
        return watchman().query("clock", root)["clock"]
