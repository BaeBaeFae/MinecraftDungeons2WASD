# Minecraft Dungeons II WASD Companion

## 0.1.1 beta test candidate

This branch adds recovery and diagnostics for the first field reports. The published 0.1 beta remains available below; this candidate is not a claim of validated multiplayer support.

- Transient game-memory reads and stale objects now retry without terminating the worker. Cleanup/refresh failures are handled inside recovery. Already applied settings resume automatically when the current objects become valid; title is requested only for missing native movement mappings.
- Setup includes **Game process → Refresh**, a process selector, and **Show all processes**. Select the actual game executable, not its launcher. Manual selection still checks the executable hash and runtime signature. It cannot make an unsupported storefront/build compatible. Selections are session-only and cleared when an attached game exits.
- Title/gameplay detection checks known controller class ancestry, including subclasses. An unknown controller is reported explicitly instead of being treated indefinitely as ordinary loading. We still need the affected user's exact notice, storefront, and diagnostics to confirm that report's cause.
- **Controls → Native interaction mode (revive workaround)** restores original Root/primary-click and click-approach behavior while leaving WASD and turning enabled. Enable it and Apply settings before attempting a revive. Click-to-move returns, and Jump Slam assist is suspended in this mode. Disable it and Apply to return to your saved click preferences. This workaround has not been verified in co-op; dodge behavior is unchanged.
- Recoverable and fatal failures save `%LOCALAPPDATA%\DungeonsInputStudio\diagnostics\last-session.json` automatically. **Save diagnostics** includes recent errors/transitions, retry counts, build information, controller class, input tree, relevant binding names, and the last attached snapshot even after a fatal failure. Reports are bounded and redact paths, email addresses, and raw addresses; no process list or memory dump is exported. Nothing is uploaded automatically. Review reports before sharing.

For the current reports, include whether the player was host or guest, matchmaking or invited, the map/boss transition, whether native interaction mode was enabled, and whether Apply/retry worked without returning to title. Multiplayer remains outside the validated compatibility scope.

**Dungeons Input Studio · 0.1 beta** is a portable Windows companion for native keyboard movement, attack-in-place, configurable turning, and an optional Jump Slam assist.

[Download 0.1 beta](https://github.com/BaeBaeFae/MinecraftDungeons2WASD/releases/tag/v0.1.0-beta) · [All releases](https://github.com/BaeBaeFae/MinecraftDungeons2WASD/releases) · [Report a problem](https://github.com/BaeBaeFae/MinecraftDungeons2WASD/issues)

An unofficial, experimental companion for **one verified Windows x64 Steam game build**. Not affiliated with Mojang, Microsoft, or the game's developers. No game code or assets are distributed here.

## Download and install

1. Open the [0.1 beta release](https://github.com/BaeBaeFae/MinecraftDungeons2WASD/releases/tag/v0.1.0-beta).
2. Download **MinecraftDungeons2WASD-0.1.0-beta-Windows-x64.zip**. The Source ZIP is for development.
3. Extract the entire ZIP. Keep `DungeonsInputStudio.exe` and `_internal` together.
4. Run `DungeonsInputStudio.exe`. No Python installation or installer is required.

The download is unsigned. Download only from this repository and optionally compare its SHA-256 with the release's `SHA256SUMS.txt`:

```powershell
Get-FileHash .\MinecraftDungeons2WASD-0.1.0-beta-Windows-x64.zip -Algorithm SHA256
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
| Attack in place | Pairs Root / Stand Still with the primary action. Shift can be assigned elsewhere. |
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
- Steam executable analyzed as build **1.1.1.0**.
- **One local player, single-player scope.** Restore originals before joining/hosting multiplayer.
- Accepted executable SHA-256:

```text
7c83afbf0ad34a40b853cdb25a22fffb605d08e2a1e2d431974d7c7c1ee0ba54
```

Unknown builds are rejected before writes. Updates need adapter revalidation; changing the hash alone is not a fix. Other storefronts, operating systems, multiplayer, and split-screen are unsupported.

Native WASD, clicks/interactions, Shift remapping, and smoothing were tested interactively. Second-PC success was user-reported. New Jump Slam timing and reconnect/restoration still need interactive confirmation. [VALIDATION.md](VALIDATION.md) distinguishes automated, read-only, and gameplay checks.

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

No telemetry, updater, or runtime network connection. Diagnostics remain local unless shared.

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
python -m unittest -v test_app test_slam test_backup test_recovery
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

**0.1 beta** is the first public release. It includes the latest development features (previously numbered locally through 0.4.0) and the repeated-notice fix. Public numbering starts here; this is not the older internal 0.1 development build.

Code is [MIT licensed](LICENSE.txt). Bundled Python, Tcl/Tk, and PyInstaller retain their licenses; see [THIRD-PARTY-NOTICES.txt](THIRD-PARTY-NOTICES.txt).
