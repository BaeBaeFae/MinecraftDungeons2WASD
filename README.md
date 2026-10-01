# Minecraft Dungeons II WASD Companion

## What's new in 0.1.2 beta

- Supports the October 1 Steam game update while retaining the previous verified build.
- Optional GitHub update checks on launch, including beta releases, with verified downloads and a restore-before-restart workflow.
- Updated game controls were confirmed working by the user.

## Application updates

The app checks this repository for newer published Windows releases on launch. Disable **Check GitHub for updates on launch** in Setup to stay offline, or use **Check updates** manually. Checking does not upload game information, diagnostics, or settings. GitHub receives normal network request metadata, including your IP address.

When an update is available, click **Download update**. The current app keeps running while the ZIP is downloaded and checked against the release asset's SHA-256 and size. Click **Restart & update** when convenient: original controls are restored first, and a restoration warning stops the handoff. Reapply companion settings in the new version when ready.

Updates install alongside the original copy under `%LOCALAPPDATA%\DungeonsInputStudio\updates`. Settings and backups remain in their existing locations. Existing shortcuts to this updater-enabled version hand off to the verified newer copy on later launches. The old files remain available; `--no-update-handoff` runs an older copy directly. Launch checks can be disabled independently of this local handoff.

Versions before 0.1.2 need one manual download to gain the updater. Source runs cannot install packaged updates. Failed checks or downloads leave the current app usable. Download verification detects damaged or mismatched files; releases are still unsigned.

## What's new in 0.1.1 beta

- Automatic recovery after temporary loading and object-state interruptions, preserving applied settings and undo records.
- Automatic interaction priority: eligible interactions take precedence over stationary melee, with mouse-directed aiming preserved. No combat-time mode switch is needed.
- Manual process selection, clearer screen detection, and local redacted diagnostics.

**Dungeons Input Studio · 0.1.2 beta** is a portable Windows companion for native keyboard movement, attack-in-place, configurable turning, and an optional Jump Slam assist.

[Download 0.1.2 beta](https://github.com/BaeBaeFae/MinecraftDungeons2WASD/releases/tag/v0.1.2-beta) · [All releases](https://github.com/BaeBaeFae/MinecraftDungeons2WASD/releases) · [Report a problem](https://github.com/BaeBaeFae/MinecraftDungeons2WASD/issues)

An unofficial, experimental companion for **verified Windows x64 Steam game builds**. Not affiliated with Mojang, Microsoft, or the game's developers. No game code or assets are distributed here.

## Download and install

1. Open the [0.1.2 beta release](https://github.com/BaeBaeFae/MinecraftDungeons2WASD/releases/tag/v0.1.2-beta).
2. Download **MinecraftDungeons2WASD-0.1.2-beta-Windows-x64.zip**. The Source ZIP is for development.
3. Extract the entire ZIP. Keep `DungeonsInputStudio.exe` and `_internal` together.
4. Run `DungeonsInputStudio.exe`. No Python installation or installer is required.

The download is unsigned. Download only from this repository and optionally compare its SHA-256 with the release's `SHA256SUMS.txt`:

```powershell
Get-FileHash .\MinecraftDungeons2WASD-0.1.2-beta-Windows-x64.zip -Algorithm SHA256
```

Place the companion anywhere; it discovers the game without a fixed Steam library path. It does not need to be copied into the game folder.

## First setup

1. Launch Minecraft Dungeons II and **stay at the title screen**.
2. Click **Start companion**. Wait for **Title screen detected**.
3. Choose your options and click **Apply settings** while still at title.
4. When it says **Settings applied — load your character**, press Play in the game.
5. Wait for **Working — controls are active**. Keep the companion open while playing.

If W/A/S/D are assigned to emotes, the multiplayer wheel, or another action, move those bindings in the game's Controls menu. Detected movement conflicts are listed instead of silently changing unrelated controls.

The status panel stays visible on every tab. Its **Next** instruction explains what to do; diagnostics are not required for setup. Setup shows live verification. Editing a setting displays an unapplied-changes notice until Apply settings.

## Do I have to return to title every time?

**No.** Change options and Apply settings while connected. After restoring or reconnecting, the companion checks whether the current character still has all four native movement mappings. At **Ready to resume — stay in your game**, click Apply settings without leaving gameplay.

Title is still needed if those mappings are missing, such as first setup or after an input-context rebuild. Follow the displayed instruction.

## Features and customization

| Setting | Behavior |
| --- | --- |
| Keyboard movement | Native movement; four distinct letters or arrow keys. |
| Attack in place | Gives native interactions priority over stationary melee. Mouse aiming and Root bindings are preserved. |
| Disable ground click movement | Blocks held-click movement and movement toward the last released click. |
| Walk to interactions yourself | Stops approach to distant chests/NPCs. Move into range, then interact. |
| Smooth turning | Ramps turn speed up and eases down near the target direction. |
| Maximum turn speed | 90–1,800 degrees/second; default 900. |
| Acceleration / deceleration | 500–20,000 degrees/second²; defaults 6,000 / 7,000. |
| Near-target response | 4–40; default 18. Lower softens the finish. |
| Turning presets | Responsive, Gentle, and Fast; individual values remain editable. |
| Jump Slam assist | Optional jump + hold-left-click using a separate game binding. Off by default. |
| Profiles | Import/export companion settings as JSON; not a complete game-controls preset. |

Other actions remain configurable in the game. Release keys and mouse buttons while applying settings.

### Jump Slam assist

Attack-in-place can interfere with the original jump-and-hold-click slam gesture. The assist sends a short press of your separate Jump Slam binding when airborne and left-click is held.

1. Bind **Jump Slam** in the game to an unused letter, number, middle mouse, or side button.
2. Enable **Jump + hold left-click to slam (beta)** in Controls.
3. Leave the binding on **Auto**, or select the matching game binding, then Apply settings.

Auto prefers a supported, unshared side button. `ThumbMouseButton` is side button 1; `ThumbMouseButton2` is side button 2. Your manual binding remains available.

One press is sent per airborne movement, including falling off a ledge. Left-click can be held before jumping or pressed in the air. Minimum airborne time defaults to 80 ms, adjustable from 0–500 ms. Landing rearms it. Returning focus while airborne waits for landing before rearming.

Input requires the focused game, current character and binding, and an unpaused world. Stop, landing, focus loss, or left-click release cleans up a held button. Ctrl/Alt/Windows shortcuts suspend it. The counter reports **presses sent**, not successful attacks. Timing and unpaused-overlay behavior still need gameplay testing.

### Restore original controls

**Restore originals** stops the companion and restores its owned changes directly in the running game, without a title-screen requirement for restoration itself.

Closing offers:

- **Yes:** restore original controls and close.
- **No:** close without reverting bindings and click behavior.
- **Cancel:** stay open.

Closing without reverting still stops smoothing and Jump Slam, sets the configured constant turn speed, and clears the native feature flag to protect the next title-screen Play check. Live features cannot all remain active after exit. Restore problems keep the app open with a warning.

Before changes, readable binding snapshots and guarded undo records are saved locally. Reopening can restore recorded changes without enabling features first. Runtime addresses are reused only for the exact process creation time/build; object identity and current values are rechecked. Named backups recover managed Root bindings the game may save across restarts. Later unrelated player remaps are preserved.

This restores **companion-owned changes**, not a full controls preset. Changes made before a backup existed cannot be reconstructed. When upgrading from a development build, close it normally so it restores before this version records a baseline.

## Compatibility

- Windows x64, packaged with Python 3.12 and Tk.
- Original Steam build and the October 1 updated Steam executable.
- **One local player, single-player scope.** Restore originals before joining/hosting multiplayer.
- Accepted executable SHA-256 fingerprints:

```text
7c83afbf0ad34a40b853cdb25a22fffb605d08e2a1e2d431974d7c7c1ee0ba54
231147bd0c655a4ae73f90873675d42917f2bfb3a9ee164fc64f217d6d6bd4ef
```

Unknown builds are rejected before writes. Updates need adapter revalidation; changing the hash alone is not a fix. Other storefronts, operating systems, multiplayer, and split-screen are unsupported.

Native WASD, clicks/interactions, Shift remapping, and smoothing were tested interactively. Second-PC success was user-reported. Automatic interaction behavior was user-confirmed. Recovery passed simulated fault tests; the exact matchmaking report has not been reproduced live. [VALIDATION.md](VALIDATION.md) distinguishes automated, read-only, and gameplay checks.

## Process selection and diagnostics

If automatic detection fails, use Game process > Refresh, select the game executable, and start the companion. Show all processes can help locate it. Manual selection never bypasses build validation. Failures save a bounded, redacted report at `%LOCALAPPDATA%\DungeonsInputStudio\diagnostics\last-session.json`; use Save diagnostics to export it. Nothing uploads automatically.

## Troubleshooting

| Notice or symptom | What to do |
| --- | --- |
| Waiting for the game | Launch it; detection retries automatically. |
| Return to title | Movement mappings are missing. Go to title, Apply, then load. |
| Movement key conflict | Rebind the listed action in the game; the companion rechecks. |
| Controls are not ready | Wait during loading. If persistent, follow the title/apply/reload instruction and save diagnostics. |
| Jump Slam needs attention | Check its game binding, select Auto or the matching key, and Apply. Avoid shared bindings. |
| Input blocked / cannot open process | Run both programs at the same permission level. Administrator access is not requested by default. |
| Unsupported version | Use a release validated for your build; do not bypass the hash check. |
| Originals not fully restored | Objects expired, values changed, or writes could not be verified. Retry after loading; restart to clear runtime changes. |
| Update requested at Play | Restore originals. The WASD flag must be off at title; restart if an older experiment left it enabled. |
| Repeated Working notice | Fixed here: live counters update without duplicating the unchanged notice. Real transitions and new errors remain logged. |

Forced termination can bypass cleanup. Restarting clears runtime patches; Restore originals can recover saved managed bindings. If a synthetic button remains held after abrupt termination, tap that button to release it.

[Report problems](https://github.com/BaeBaeFae/MinecraftDungeons2WASD/issues) with companion version, game version/storefront, displayed notice, reproduction steps, and whether it happened at title, loading, or gameplay. Save diagnostics from **Setup & diagnostics**, review them, and share only what you choose.

## Local data and privacy

No telemetry. Optional update checks and requested downloads contact GitHub; diagnostics remain local unless manually shared. Disable launch checks for offline use.

| Location | Contents |
| --- | --- |
| `%LOCALAPPDATA%\DungeonsInputStudio\settings.json` | Companion options. |
| `%LOCALAPPDATA%\DungeonsInputStudio\backups` | Original bindings, named recovery data, session undo records. |
| Your chosen export path | Exported profiles and diagnostics. |

Backups may contain process IDs, runtime addresses, and controls. They are never included in public binary/source ZIPs. Keep them while you may need restoration.

## Build and test

Use Windows x64 and Python 3.12 with Tkinter. Runtime source uses the standard library. Build dependencies are pinned in `requirements-build.txt`.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-build.txt
python -m unittest -v test_app test_slam test_backup test_recovery test_input_states test_interaction test_builds test_updater
python app.py --ui-smoke ui-smoke.json
python -m PyInstaller --noconfirm --clean --onedir --windowed --noupx --name DungeonsInputStudio app.py
```

Optional, with a supported game running: `python app.py --probe probe.json`.

`--probe` reads the game and previews configuration without modifying it. `--ui-smoke` checks the interface without attaching. Normal launch waits for Start companion.

Distribute the **entire** `dist/DungeonsInputStudio` folder with README, LICENSE, VALIDATION, third-party notices, and runtime licenses. Exclude caches, user settings, diagnostics, and backups. Releases include Windows and curated source ZIPs plus SHA-256 checksums.

### Source overview

- `app.py`, `worker.py`: GUI and recoverable connection worker; live status and diagnostic notices are separate.
- `diagnostics.py`, `errors.py`: bounded redacted reports and transient error classification.
- `guidance.py`: setup/recovery states.
- `engine.py`, `ue.py`, `winmem.py`: exact-build adapter and validated process-data access.
- `journal.py`, `control_backup.py`: guarded undo and named binding recovery.
- `model.py`: settings, validation, and turning calculations.
- `slam.py`: Jump Slam state machine and Windows input adapter.
- `test_*.py`: settings, smoothing, lifecycle, logging, restoration, and assist regression tests.

The companion edits live data only. It does not patch executables/assets, inject executable code, or change page protections. New game support needs measured validation.

## Release history and license

**0.1.1 beta** adds automatic interaction priority, recovery, process selection, and local diagnostics. **0.1 beta** was the first public release.

Code is [MIT licensed](LICENSE.txt). Bundled Python, Tcl/Tk, and PyInstaller retain their licenses; see [THIRD-PARTY-NOTICES.txt](THIRD-PARTY-NOTICES.txt).
