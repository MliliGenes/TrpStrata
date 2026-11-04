"""Widget font presets and process-local registration of the bundled Doto face."""
import logging
from pathlib import Path

PRESETS = {
    "sans": ("Clean · Sans", '"Inter", "DejaVu Sans", sans-serif', '"Inter", "DejaVu Sans", sans-serif'),
    "dotted": ("Dotted · Doto", '"Inter", "DejaVu Sans", sans-serif', '"Doto", "DejaVu Sans Mono", monospace'),
    "mono": ("Technical · Mono", '"DejaVu Sans Mono", monospace', '"DejaVu Sans Mono", monospace'),
    "serif": ("Editorial · Serif", '"DejaVu Serif", serif', '"DejaVu Serif", serif'),
}
FONT_FILE = Path(__file__).with_name("assets") / "fonts" / "Doto.ttf"
_registered = False


def css(preset):
    if preset not in PRESETS:
        raise ValueError("widget_font must be one of: " + ", ".join(PRESETS))
    _label, body, display = PRESETS[preset]
    return f"""
#ws-desktop-widgets .desktop-widget,
#ws-desktop-widgets .logtime-login {{ font-family: {body}; }}
#ws-desktop-widgets .clock-time,
#ws-desktop-widgets .calendar-day,
#ws-desktop-widgets .metric-value,
#ws-desktop-widgets .logtime-percent,
#ws-desktop-widgets .logtime-hours {{ font-family: {display}; }}
"""


def register():
    """Make Doto available to this process without installing fonts into the user's home."""
    global _registered
    if _registered:
        return True
    import ctypes
    import ctypes.util
    try:
        library = ctypes.util.find_library("fontconfig")
        if library is None or not FONT_FILE.is_file():
            raise OSError("Bundled font or Fontconfig is unavailable")
        fc = ctypes.CDLL(library)
        fc.FcConfigGetCurrent.argtypes = []
        fc.FcConfigGetCurrent.restype = ctypes.c_void_p
        fc.FcConfigAppFontAddFile.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        fc.FcConfigAppFontAddFile.restype = ctypes.c_int
        fc.FcConfigBuildFonts.argtypes = [ctypes.c_void_p]
        fc.FcConfigBuildFonts.restype = ctypes.c_int
        config = fc.FcConfigGetCurrent()
        if not config or not fc.FcConfigAppFontAddFile(config, str(FONT_FILE).encode()) or not fc.FcConfigBuildFonts(config):
            raise OSError("Fontconfig could not register Doto")
        _registered = True
    except (OSError, AttributeError) as error:
        logging.getLogger(__name__).warning("Using widget font fallback: %s", error)
    return _registered
