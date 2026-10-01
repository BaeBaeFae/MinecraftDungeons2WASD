# 0.1.2 beta

- Support the October 1 Steam executable with a separate verified address profile, retaining previous-build support.
- Resolve movement-context tags by native name rather than relocated global pointers.
- Add optional GitHub release checks on launch and a manual Check updates button, including published beta releases.
- Download and verify updates before offering Restart & update. Restore game controls before handoff; keep the original application available as a fallback.
- Preserve settings and backups. No diagnostics or game data are uploaded; update checks introduce an optional GitHub network connection.

Updated game controls were user-confirmed. Automated and packaged validation results are documented in VALIDATION.md. Microsoft Store compatibility remains unverified. Older companion versions need one manual download to acquire this updater.

60 automated tests pass. Packaged GUI checks pass. A real GitHub release download was verified and staged successfully without activation.
