# Frame Art

Watches a folder of photos and shows them on a Samsung Frame TV, each one set
in a realistic bevel-cut paper mat.

## Getting started

1. Start the add-on and click **Open Web UI** (or **Frame Art** in the sidebar).
2. **Settings → Television**: enter the TV's IP address (give it a fixed DHCP lease)
   and press **Test connection**. Accept the "Allow" prompt that appears on the TV.
3. Put photos in `/media/frame` (Media → My media, Samba, or point Immich/another
   sync tool at it). JPEG, PNG, HEIC/HEIF and WebP are supported, in any case.
4. **Frame** tab: design the mat with a live preview, then **Save & show**.

The add-on rotates on its own schedule. New files are shown as soon as they land
(toggle in Settings), and portrait photos are paired side by side.

## The frame designer

| Control | What it does |
| --- | --- |
| Style | Bevel mat, flat mat, or no mat (photo fills the screen) |
| Opening | *Fill* crops the photo to the opening; *Match* shapes the opening to the photo |
| Mat width / bottom weight | Border size; bottom weight gives a classic heavier bottom margin |
| Bevel width / shading / light from | The 45° cut edge and how the room light falls on it |
| Depth shadow | The shadow the mat's thickness casts onto the photo |
| Embossed rule | A debossed line around the opening |
| Imperfection | Master control for paper grain, mottling, colour drift, cut wobble and stray fibres |

With **Different flaws for every photo** on, each photo gets its own subtle
variation (deterministic – the same photo always renders the same way). **New
variation** rolls a new seed for all of them.

## Automations

The add-on exposes `sensor.frame_art` (current photo) and accepts commands via
`hassio.addon_stdin`:

```yaml
action: hassio.addon_stdin
data:
  addon: <your add-on slug, see the add-on page URL>
  input: next            # or: pause, resume, rescan, {"show": "holiday/IMG_0042.heic"}
```

Example – new photo when someone walks into the living room in the morning:

```yaml
triggers:
  - trigger: state
    entity_id: binary_sensor.living_room_motion
    to: "on"
conditions:
  - condition: time
    after: "06:00:00"
    before: "10:00:00"
actions:
  - action: hassio.addon_stdin
    data:
      addon: <your add-on slug>
      input: next
```

## Notes

- **TV storage**: the add-on deletes older images it uploaded, keeping the last 30
  (Settings → Keep last N uploads). Photos it has already uploaded are re-selected
  instead of re-uploaded, as long as the frame style hasn't changed.
- **TV off**: if the TV is unreachable the attempt is logged and retried at the next
  rotation.
- **Network shares**: the folder is polled, not watched with inotify, so photos
  arriving over SMB/NFS are picked up too.
