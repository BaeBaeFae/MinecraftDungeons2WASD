# Validation — 0.1.1 beta

47 automated tests pass on Windows with Python 3.12. Coverage includes movement settings, turning dynamics, input cleanup, guarded restoration, profile persistence, process selection, diagnostics redaction, and automatic interaction priority.

The production connection worker was driven through 100 simulated travel interruptions, loading periods, and replacement character generations. Every cycle resumed without another Apply or title-screen step, preserved settings and undo ownership, and avoided simulated stale-character updates during retry delays. Persistent failures back off from 0.25 to 2 seconds; Stop remains available. A simulated game restart discards the old engine and manual PID selection and requires Apply for the new session.

Interaction tests check exact apply/reapply/restore, rejection of incorrect target bindings and extra condition consumers, and stale binding guards. Read-only planning passed against the live camp input tree. The user confirmed the resulting automatic interaction behavior. Mouse-directed aiming remains unchanged.

Packaged GUI smoke checks cover readable controls and setup/recovery states. Earlier native movement, click handling, turning, and restoration were tested interactively; another PC was reported working.

Fault injection uses fake game objects. It does not reproduce the specific boss rematch or matchmaking guest report. Co-op revival and all multiplayer combinations remain unverified. Unsupported builds are rejected; fatal writes stop rather than being treated as ordinary loading. No claim of universal compatibility is made.
