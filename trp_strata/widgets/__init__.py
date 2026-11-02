"""Built-in components. layout.json composes these and user-defined widgets."""
from .clock import Clock
from .calendar import Calendar
from .notes import Notes
from .system import System
from .logtime import Logtime
from .cleaner import Cleaner
from .now_playing import NowPlaying
from .launcher import Launcher
from .file_search import FileSearch
from .quick_links import QuickLinks
from .device_controls import Volume, Brightness

WIDGETS = (Clock, Calendar, System, Notes, Logtime, Cleaner, NowPlaying, Launcher, FileSearch, QuickLinks, Volume, Brightness)


__all__ = ["Clock", "Calendar", "System", "Notes", "Logtime", "Cleaner", "NowPlaying", "Launcher", "FileSearch", "QuickLinks", "Volume", "Brightness", "WIDGETS"]
