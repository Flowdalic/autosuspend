import configparser
import json
from typing import Any, Dict, Optional

from . import Activity, ConfigurationError, TemporaryCheckError
from .util import NetworkMixin


def _add_default_kodi_url(config: configparser.SectionProxy) -> None:
    if "url" not in config:
        config["url"] = "http://localhost:8080/jsonrpc"


class Kodi(NetworkMixin, Activity):
    @classmethod
    def collect_init_args(cls, config: configparser.SectionProxy) -> Dict[str, Any]:
        try:
            _add_default_kodi_url(config)
            args = NetworkMixin.collect_init_args(config)
            args["suspend_while_paused"] = config.getboolean(
                "suspend_while_paused", fallback=False
            )
            return args
        except ValueError as error:
            raise ConfigurationError("Configuration error {}".format(error)) from error

    @classmethod
    def create(cls, name: str, config: configparser.SectionProxy) -> "Kodi":
        return cls(name, **cls.collect_init_args(config))

    def __init__(
        self, name: str, url: str, suspend_while_paused: bool = False, **kwargs: Any
    ) -> None:
        self._suspend_while_paused = suspend_while_paused
        if self._suspend_while_paused:
            request = url + (
                '?request={"jsonrpc": "2.0", "id": 1, '
                '"method": "XBMC.GetInfoBooleans",'
                '"params": {"booleans": ["Player.Playing"]} }'
            )
        else:
            request = url + (
                '?request={"jsonrpc": "2.0", "id": 1, '
                '"method": "Player.GetActivePlayers"}'
            )
        NetworkMixin.__init__(self, url=request, **kwargs)
        Activity.__init__(self, name)

    def _safe_request_result(self) -> Dict:
        try:
            return self.request().json()["result"]
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise TemporaryCheckError("Unable to get or parse Kodi state") from error

    def check(self) -> Optional[str]:
        reply = self._safe_request_result()
        if self._suspend_while_paused:
            return (
                "Kodi actively playing media" if reply.get("Player.Playing") else None
            )
        else:
            return "Kodi currently playing" if reply else None


class KodiIdleTime(NetworkMixin, Activity):
    @classmethod
    def collect_init_args(cls, config: configparser.SectionProxy) -> Dict[str, Any]:
        try:
            _add_default_kodi_url(config)
            args = NetworkMixin.collect_init_args(config)
            args["idle_time"] = config.getint("idle_time", fallback=120)
            return args
        except ValueError as error:
            raise ConfigurationError("Configuration error " + str(error)) from error

    @classmethod
    def create(cls, name: str, config: configparser.SectionProxy) -> "KodiIdleTime":
        return cls(name, **cls.collect_init_args(config))

    def __init__(self, name: str, url: str, idle_time: int, **kwargs: Any) -> None:
        request = url + (
            '?request={{"jsonrpc": "2.0", "id": 1, '
            '"method": "XBMC.GetInfoBooleans",'
            '"params": {{"booleans": ["System.IdleTime({})"]}}}}'.format(idle_time)
        )
        NetworkMixin.__init__(self, url=request, **kwargs)
        Activity.__init__(self, name)
        self._idle_time = idle_time

    def check(self) -> Optional[str]:
        try:
            reply = self.request().json()
            if not reply["result"]["System.IdleTime({})".format(self._idle_time)]:
                return "Someone interacts with Kodi"
            else:
                return None
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise TemporaryCheckError("Unable to get or parse Kodi state") from error
