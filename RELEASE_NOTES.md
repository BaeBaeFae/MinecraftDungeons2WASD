# 0.1 beta — first public release

Download **MinecraftDungeons2WASD-0.1.0-beta-Windows-x64.zip**, extract everything, and run `DungeonsInputStudio.exe`. No Python required. The executable is unsigned. `SHA256SUMS.txt` contains checksums for both ZIPs.

This is the latest complete build, published as our first public **0.1 beta**, including all features developed through internal 0.4.0.

## Included

- Native WASD, customizable keys, and conflict notices.
- Attack-in-place, ground-click blocking, and interaction-approach options.
- Accelerated, eased turning with customization and presets.
- Optional Jump Slam assist and automatic binding detection.
- Guided setup, live verification, and in-game reconnect when ready.
- Original-control backups, restoration, and restore / keep / cancel on close.
- Portable profiles and local diagnostics.
- **Fixed repeated Working notices:** live counters still refresh; unchanged notices are logged once. New errors and genuine transitions remain visible.

## Start here

First setup: **Title screen → Start companion → Apply settings → Load character**. Reconnect in gameplay when Ready to resume appears. Close older companions normally before upgrading so they restore before this release captures originals.

## Scope and validation

Windows x64, verified Steam build 1.1.1.0 only; unknown hashes are rejected. Single-player, one local player. Restore originals before multiplayer.

27 automated tests and packaged UI checks pass. Read-only adapter checks passed during development; the game was closed during the final public-build probe, so that check could not be repeated. Earlier controls/smoothing were confirmed during gameplay; second-PC success was user-reported. New Jump Slam timing and reconnect/restoration still need interactive confirmation. Closing stops smoothing and Jump Slam even if bindings are left in place.

See the [full README](https://github.com/BaeBaeFae/MinecraftDungeons2WASD#readme) for setup, settings, troubleshooting, restoration, supported hash, and privacy. Unofficial beta; no game code/assets included.
