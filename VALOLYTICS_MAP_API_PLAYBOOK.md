# VALOLYTICS Map API Playbook (Future Use)

## Goal
Reliable, repeatable conversion from in-game world coordinates to pixel positions on a map image.

## Source Endpoint
- `https://valorant-api.com/v1/maps`

This payload provides the per-map transform constants we need:
- `xMultiplier`
- `yMultiplier`
- `xScalarToAdd`
- `yScalarToAdd`
- plus useful map metadata (`displayName`, `uuid`, `displayIcon`, `mapUrl`, `callouts`).

## Canonical Transform
Use this exact mapping logic:

```python
def transform_game_coords(x: float, y: float) -> tuple[int, int]:
    x, y = y * x_multiplier + x_scalar, x * y_multiplier + y_scalar
    return int(x * width), int(y * height)
```

Notes:
- Input `x, y` are world coordinates from match data.
- `width, height` are from the chosen map image (usually `displayIcon` dimensions).
- Axis swap is intentional (`worldY -> screenX`, `worldX -> screenY`).
- `yMultiplier` is usually negative, so vertical direction is flipped.

## Standard Workflow
1. Fetch maps JSON once and cache it locally.
2. Resolve map entry by `displayName` (or stable alias map if needed).
3. Read transform constants from that map entry.
4. Load map image and read `width`, `height`.
5. Transform each world point with the formula above.
6. Plot points.
7. Validate with known `callouts` and/or VOD spot checks before publishing.

## Validation Rules (Important)
- Never "jitter" points for overlap. If two positions are identical, keep them identical.
- Do not silently rotate/translate maps globally unless explicitly confirmed.
- If a map looks off, verify in this order:
  1. Correct map asset
  2. Correct transform constants for that map
  3. Correct world coordinate field from data source
  4. Correct image width/height used in transform
- Treat custom offsets/rotations as temporary debug overrides only.

## Practical Data Fields to Keep Together
For each plotted event, persist:
- `matchId`
- `mapName`
- `roundIndex` (zero-based and human-readable round number)
- `eventTimeSec`
- `worldX`, `worldY`
- `pixelX`, `pixelY`
- player labels (`killer`, `victim`, team/side context)

This makes later audits possible when a dot looks suspicious.

## Caveats
- Practice/Range entries may have zeroed transform fields (`0,0,0,0`) and are not usable for normal match plotting.
- Callouts are helpful for sanity checks but are not a strict collision/valid-area mask.
- Keep map asset choice consistent across all maps in one view (same style family).

## Minimal Fetch Command
```powershell
curl.exe -L --max-time 30 "https://valorant-api.com/v1/maps" > .\data\maps_api.json
```

## Future Default
When asked to build/verify map plots:
1. Start from this playbook.
2. Re-fetch map metadata if there is any chance of map pool/update drift.
3. Log transform constants used in output metadata for traceability.
