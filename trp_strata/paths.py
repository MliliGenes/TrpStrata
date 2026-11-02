"""Choose bulk storage without importing GTK or creating directories."""
from dataclasses import dataclass
import os


@dataclass(frozen=True)
class StoragePaths:
    bulk: str | None
    install_link: str
    app: str
    cache_link: str
    cache: str
    theme_links: str
    themes: str


def paths_for(home, environment=None):
    environment = os.environ if environment is None else environment
    goinfre = os.path.join(home, "goinfre")
    bulk = os.path.join(goinfre, "trpstrata") if os.path.isdir(goinfre) else None
    install_link = os.path.join(home, ".local", "share", "trpstrata")
    cache_link = os.path.join(environment.get("XDG_CACHE_HOME", os.path.join(home, ".cache")), "trpstrata")
    theme_links = os.path.join(home, ".local", "share", "themes")
    return StoragePaths(
        bulk=bulk,
        install_link=install_link,
        app=os.path.join(bulk, "app") if bulk else install_link,
        cache_link=cache_link,
        cache=os.path.join(bulk, "cache") if bulk and not environment.get("XDG_CACHE_HOME") else cache_link,
        theme_links=theme_links,
        themes=os.path.join(bulk, "themes") if bulk else theme_links,
    )
