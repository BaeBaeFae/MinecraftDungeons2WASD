# Recovery regression — 0.1.3 beta

All 62 automated tests pass. The Windows executable builds successfully and its packaged GUI smoke check passes without attaching to the game.

The real Engine.sync and Jump Slam synchronization were exercised after Worker.recover clears the movement reference while the same character and its identity guard remain valid. Before the fix, Jump Slam enabled reproduced a read error on every retry; disabled left the movement reference empty. Both cases now reacquire the component across repeated interruptions without Apply, retaining settings and the restoration journal. Diagnostics now include bounded filename/function/line context without source text, local variables, or full paths. This reproduces a defect consistent with the submitted report; the original in-game interruption itself has not been reproduced.

# Application updater validation

60 automated tests pass across the complete suite. Updater coverage includes beta ordering, downgrade prevention, incomplete/draft release exclusion, trusted HTTPS redirects, checksum rejection, archive path traversal/link/duplicate rejection, side-by-side extraction, runtime-file integrity checks, saved opt-out, repeated stop acknowledgments, and restoration-warning propagation.

A real GitHub integration check found the published 0.1.1 beta when simulating an older installed version, downloaded its Windows ZIP, verified its published SHA-256 and size, and staged all 993 files. It was not activated and no game controls were changed. The current 0.1.2 check correctly reported no newer release. Source and packaged GUI smoke checks pass without contacting the network.

# October 1 update — 0.1.2 beta

51 tests pass, including independent old/new build selection, per-build runtime signature verification, input-gate target checks, and unknown-build rejection. New globals were located by comparing references in the old and updated running executable, then verified against read-only runtime data. Twenty-seven relevant reflected type layouts match the previous build. Read-only title setup and camp configuration planning pass, including the native interaction condition/binding guards and movement/rotation layout validation. The user subsequently confirmed the controls working after normal title setup.

The Microsoft Store build remains unverified; selecting a process does not bypass the fingerprint gate. No new features are introduced by this compatibility update.

# Validation — 0.1.1 beta

47 automated tests pass on Windows with Python 3.12. Coverage includes movement settings, turning dynamics, input cleanup, guarded restoration, profile persistence, process selection, diagnostics redaction, and automatic interaction priority.

The production connection worker was driven through 100 simulated travel interruptions, loading periods, and replacement character generations. Every cycle resumed without another Apply or title-screen step, preserved settings and undo ownership, and avoided simulated stale-character updates during retry delays. Persistent failures back off from 0.25 to 2 seconds; Stop remains available. A simulated game restart discards the old engine and manual PID selection and requires Apply for the new session.

Interaction tests check exact apply/reapply/restore, rejection of incorrect target bindings and extra condition consumers, and stale binding guards. Read-only planning passed against the live camp input tree. The user confirmed the resulting automatic interaction behavior. Mouse-directed aiming remains unchanged.

Packaged GUI smoke checks cover readable controls and setup/recovery states. Earlier native movement, click handling, turning, and restoration were tested interactively; another PC was reported working.

Fault injection uses fake game objects. It does not reproduce the specific boss rematch or matchmaking guest report. Co-op revival and all multiplayer combinations remain unverified. Unsupported builds are rejected; fatal writes stop rather than being treated as ordinary loading. No claim of universal compatibility is made.
