"""Shared device-controller behavior used by volume and brightness packages."""
from trp_strata.widget_engine import handler
from trp_strata.widget_packages.base import PollingController
from trp_strata.device_controls import DeviceModel, VolumeBackend, BrightnessBackend


class DeviceController(PollingController):
    volume = False

    def refresh(self, ctx):
        key = "volume" if self.volume else "brightness"
        value, muted, available, error = ctx.model(key, lambda: DeviceModel(VolumeBackend if self.volume else BrightnessBackend)).view()
        title = ctx.props.get("title", "Volume" if self.volume else "Brightness")
        ctx.set_state(title=title.upper(), label=title, value=value, available=available,
                      level="Muted" if self.volume and muted else f"{value}%" if available else "—",
                      mute_label="Unmute" if muted else "Mute", show_mute=self.volume, error=error, show_error=bool(error))

    @handler
    def change(self, ctx, event):
        ctx.instance.models["volume" if self.volume else "brightness"].set_value(event["value"])
        self.refresh(ctx)

    @handler
    def mute(self, ctx, event):
        if self.volume:
            ctx.instance.models["volume"].toggle_mute()
            self.refresh(ctx)
