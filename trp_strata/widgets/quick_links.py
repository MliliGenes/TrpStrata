"""Named website shortcuts, editable through the control panel."""
from ..components import Button, Column, Text, component, use_model
from ..quick_links import DEFAULT_LINKS, QuickLinksModel, normalize_links


@component
def QuickLinks(config, title="Quick links", links=DEFAULT_LINKS):
    model = use_model(QuickLinksModel, key="quick-links")
    links = normalize_links(links)
    return Column(
        Text(title.upper(), class_name="widget-label", align="start"),
        [Button(link["label"], system_icon=model.icon(link["url"]), tooltip=link["url"],
                on_click=lambda link=link: model.launch(link["label"], link["url"]), key=f"link-{index}")
         for index, link in enumerate(links)],
        Text("Add websites using Edit beside Quick links in the app.", visible=not links,
             wrap=True, max_width_chars=30, align="start"),
        Text(model.status, visible=bool(model.status), wrap=True, max_width_chars=30, align="start"),
        spacing=10, class_name="launcher-card quick-links-card",
    )
