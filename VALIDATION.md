# Validation — public 0.1 beta

## 0.1.1 beta candidate

36 tests pass. New regressions cover interrupted gameplay reads with cleanup and object-refresh failures, recovery without a title transition or lost journal, worker survival and export after fatal failure, retained failure snapshots, manual selection and ambiguity, selection while waiting, controller subclasses, native-interaction overrides preserving stored preferences, bounded redaction, nonfatal diagnostic disk errors, rejected unsupported manual selections, native-click mode without tree patching, and restoration ownership after interrupted verification reads. Source and packaged GUI structural checks exercise manual-selection and unknown-screen states. No live game was running for this candidate; boss rematches, guest matchmaking, revives, and the reported title-screen variant have not been reproduced. Native interaction mode is an unverified workaround, not a confirmed automatic revive fix. Existing single-player validation does not establish co-op support.

Public 0.1 beta consolidates the development builds below. Twenty-seven tests pass, including a regression that changes live verification counters six times while logging Working only once; recovery transitions and changed errors still produce notices. The public packaged UI check passed. The final public-build game probe could not run because the game was closed; earlier read-only adapter evidence below is retained.

0.4.0: Twenty-six automated tests pass. Expanded worker coverage checks in-game reconnect, incomplete restore keeping the app open, and close-without-revert avoiding the restore path. New backup tests check write-ahead originals, reopening and restoring, rejected session mismatches, stale identities, preserved external remaps, backup-write failure, retry after a failed restore, and named binding recovery. Read-only live inspection captured 32 keyboard-profile bindings and verified the process creation-time identity. The game was at title during this check; the new no-title reconnect/restore flow still needs interactive gameplay confirmation. Packaged UI structural checks cover the resume state; no native screenshot claim is made.

0.3.0: Added opt-in Jump Slam input assist. Twenty automated tests cover the existing features plus one press per airborne movement, click-before/after-jump, focus/pause/stop/landing cleanup, manual button preservation when already held, binding conflicts and remaps, read-only suppression, failed-send release, profile validation, and Windows x64 INPUT encoding using a mocked sender. No automated test sends real input to the game. Read-only inspection confirmed HeavyJumpAttack bindings Q and ThumbMouseButton, reflected MovementMode (ground value 1), and the current world pause-state chain. Packaged UI smoke checks cover the assist warning and retained numeric contrast. New assist gameplay behavior is still pending user validation; successful synthetic sends do not prove successful attacks.

0.2.0: Guided setup uses explicit states for connection, detected title screen, waiting for Apply settings, loading, verified active controls, conflicts, missing mappings, recovery, and fatal errors. Automated worker-flow tests exercise wrong-screen startup, Apply gating, activation, stopping, and reconnect setup without touching the game. Packaged GUI smoke checks exercise the visible states and button gating. The user reported the earlier release working on a second PC with the title → Start → Apply sequence; this is user-reported evidence, not an independently observed test.

0.1.1: Turning numeric fields now set their foreground and field background explicitly. Tk runtime style checks verify at least 4.5:1 text contrast in normal, focused, active, read-only, and disabled states. Native screenshot verification was unavailable because the computer-use runtime could not initialize. The gameplay adapter is unchanged from 0.1.0.

Date: 2026-09-30. Host: Windows 11 x64, Python 3.12.4.

## Passed

- Eleven automated tests, including guided setup state transitions, Apply gating, reconnect behavior, and the existing coverage: profile round-trip and schema rejection, invalid/duplicate settings, shortest-angle wrapping, smoothing convergence and speed bounds at 30/60/120/144 Hz, acceleration after long scheduling gaps, rollback after repeated edits, refusal to restore stale or externally changed values, and FKey cache clearing.
- Read-only discovery and configuration planning against the verified running game: one local player, twelve input mapping contexts, the keyboard profile, native WASD modifiers, and the correct input state tree. No saved session heap address or fixed PID was used by the adapter.
- Source and packaged GUI startup: four tabs, thirteen guided status states, button gating, saved profile loading, layout sizing, and numeric field contrast. The GUI test did not attach to the game.
- Packaged read-only process probe, including runtime signature and executable SHA-256 checks.
- Live supported-build integration: prior experimental settings were temporarily restored to their original values, the new adapter applied nine owned data changes, ran smoothing, then restored all nine with zero skipped entries. Each restored value was compared to the captured baseline.
- Earlier interactive tests in the same gameplay session: WASD, Shift remapping, attack/interact without ground click movement, out-of-range interaction approach blocking, and 900-degree-per-second smoothed turning were confirmed by the user before packaging.

## Still needs independent validation

- Another PC and a fresh game launch using only the packaged companion.
- All custom key combinations and all input/interaction edge cases.
- Title-to-gameplay transition timing under heavy load.
- Multiplayer and split-screen. The release is scoped to one local player in single-player; stop before joining/hosting multiplayer.
- Other storefronts, operating systems, and future game builds. The current adapter rejects unknown executable hashes.

This evidence supports a shareable beta for the exact supported build. It does not establish universal compatibility.
