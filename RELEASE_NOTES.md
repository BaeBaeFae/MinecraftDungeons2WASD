# 0.1.1 beta

- Give native interactions priority over stationary melee automatically. Mouse-directed attacks and aiming remain intact; Root / Stand Still bindings are no longer paired with the primary button.
- Retry temporary game-state failures without discarding applied settings or restoration records. Resume after loading when the required input objects are ready.
- Add manual process selection with the same supported-build checks as automatic detection.
- Improve title/gameplay controller detection and show an explicit status for unrecognized screens.
- Save bounded, redacted diagnostics locally after failures; retain error history for manual export.
- Clarify control overrides and add a reset to companion control defaults.

## Updating

Close the previous companion and choose to restore original controls. Extract the entire new ZIP and run DungeonsInputStudio.exe. Complete the normal title-screen setup once. Keep Attack in place enabled and Original click behavior disabled for automatic interaction priority.

Temporary travel interruptions recover automatically. A restarted game requires applying settings for the new session. Return to title only when the app reports missing movement mappings.

## Validation and compatibility

47 automated tests pass, including 100 simulated travel-recovery cycles, bounded retry delays, new-process handling, and exact interaction-patch restoration. Automatic interaction behavior was confirmed by the user. The reported matchmaking disconnect and a co-op revive have not been independently reproduced; this remains a beta for the previously supported Windows x64 Steam build.

No telemetry or runtime network connection. Diagnostics stay on the player's PC unless manually shared. The release includes the application, curated source, licenses, and SHA-256 checksums.
