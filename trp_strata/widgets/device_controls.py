"""Independent desktop volume and brightness cards."""
from ..components import Button, Column, Row, Slider, Text, component, use_model
from ..device_controls import BrightnessBackend, DeviceModel, VolumeBackend


def control(title, model, volume=False):
    value, muted, available, error = model.view()
    return Column(
        Row(Text(title.upper(), class_name="widget-label", align="start", expand=True),
            Text("Muted" if volume and muted else f"{value}%" if available else "—"), spacing=8),
        Slider(value, label=title, on_change=model.set_value, sensitive=available, key="level"),
        Button("Unmute" if muted else "Mute", on_click=model.toggle_mute, sensitive=available) if volume else None,
        Text(error, visible=bool(error), wrap=True, max_width_chars=32, align="start"),
        spacing=10, class_name="launcher-card device-card",
    )


@component
def Volume(config, title="Volume"):
    return control(title, use_model(lambda: DeviceModel(VolumeBackend), key="volume"), volume=True)


@component
def Brightness(config, title="Brightness"):
    return control(title, use_model(lambda: DeviceModel(BrightnessBackend), key="brightness"))
