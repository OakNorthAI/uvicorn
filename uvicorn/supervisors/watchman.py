import logging
import functools

from .reloaderbase import ReloaderBase
from uvicorn.config import Config

logger = logging.getLogger("uvicorn.warning")

try:
    import pywatchman
except ImportError:
    pywatchman = None


def client():
    # lazy load the pywatchman client, use it as singleton
    client.holder
    if client.holder is None:
        if pywatchman is None:
            return None
        client.holder = pywatchman.client(timeout=5.0)
    return client.holder


client.holder = None


class Watchman(ReloaderBase):
    def __init__(self, config, target, sockets):
        super().__init__(config, target, sockets)
        logger.info("Use Watchman.")

    def watch_and_reload(self):
        try:
            client().receive()
            logger.warning("Watchman detected file change, about to restart")
            self.restart()
        except pywatchman.SocketTimeout:
            pass
        except pywatchman.WatchmanError as ex:
            logger.error("Watchman error: %s, checking server status.", ex)
            # when watchman is failed, retart server fallback to statreload
            self.restart()

    @classmethod
    def available(cls) -> bool:
        try:
            if pywatchman is None:
                return False
            client().capabilityCheck()
            logger.warning("Watchman is available")
            return True
        except Exception:
            return False

    def startup(self):
        self.update_watch()
        super().startup()

    def shutdown(self):
        client().close()
        super().shutdown()

    def update_watch(self):
        for path in self.config.reload_dirs:
            self._watch(path)
            logger.info("Watchman watching %s", path)

    def _watch(self, root):
        name = "uvicorn-watch-{}-[{}]".format(self.config.app or "", str(root))
        result = client().query("watch-project", root)

        if "warning" in result:
            logger.warning("Watchman warning: %s", result["warning"])
        logger.warning("Watchman watch-project result: %s", result)

        query = {
            "expression": ["allof", ["type", "f"], ["not", "empty"], ["suffix", "py"]],
            "fields": ["name"],
            "since": self._get_clock(root),
            "dedup_results": True,
        }

        client().query("subscribe", root, name, query)

    @functools.lru_cache()
    def _get_clock(self, root):
        return client().query("clock", root)["clock"]
