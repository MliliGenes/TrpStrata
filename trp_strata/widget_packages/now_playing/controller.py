"""Media state, artwork and playback actions."""
from trp_strata.widget_engine import handler
from trp_strata.widget_packages.base import PollingController
from trp_strata.now_playing import NowPlayingModel, PREFIX, can_control
from trp_strata.artwork import ArtworkModel


class Controller(PollingController):
    def refresh(self, ctx):
        model = ctx.model("now-playing", NowPlayingModel)
        player, error, busy = model.view()
        props = player["properties"] if player else {}
        metadata = props.get("Metadata", {})
        artwork = ctx.model("artwork", ArtworkModel).view(metadata.get("mpris:artUrl", ""))
        artists = metadata.get("xesam:artist", [])
        artist = artists if isinstance(artists, str) else ", ".join(artists)
        album = metadata.get("xesam:album", "")
        status = props.get("PlaybackStatus", "")
        source = player["name"][len(PREFIX):].split(".")[0] if player else "Open a media player to get started"
        ctx.set_state(title=metadata.get("xesam:title") or ("Unknown track" if player else "Nothing playing"),
                      artist=artist, album=album, show_artist=bool(artist), show_album=bool(album), artwork=artwork,
                      status=error or (f"{source} · {status}" if status else source),
                      controls=[{"id": method, "icon": icon, "label": label,
                                 "enabled": not busy and can_control(player, method)}
                                for method, icon, label in (("Previous", "backward-step", "Previous"),
                                    ("PlayPause", "pause" if status == "Playing" else "play",
                                     "Pause" if status == "Playing" else "Play"), ("Next", "forward-step", "Next"))])

    @handler
    def control(self, ctx, event):
        if event.get("args") not in ("Previous", "PlayPause", "Next"):
            raise ValueError("Unknown playback action")
        ctx.instance.models["now-playing"].control(event["args"])
        self.refresh(ctx)
