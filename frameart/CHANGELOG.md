# Changelog

## 2.0.0

Complete rewrite.

- Runs as a service instead of a one-shot: watches the photo folder and rotates on a schedule.
- Web UI in the Home Assistant sidebar (ingress): now showing, frame designer with live preview, library, settings, history.
- New mat renderer: bevel cut with directional light, depth shadow, optional embossed rule, and adjustable "hand-made" imperfections (paper grain, mottling, colour drift, cut wobble, fibres).
- Portrait photos are paired side by side in a double-opening mat.
- Re-selects images already on the TV instead of re-uploading, and prunes old uploads.
- Control from automations via `hassio.addon_stdin` (`next`, `pause`, `resume`, `{"show": "path"}`); exposes `sensor.frame_art`.
- Built locally by Home Assistant – no container registry.
- Google Art and Bing sources removed; the add-on is folder-only.
- Upgrading from 1.x imports the TV address and media folder automatically. Matte options are replaced by the frame designer. The daily "start add-on" automation is no longer needed.
- Only 64-bit systems (aarch64, amd64) are supported.
