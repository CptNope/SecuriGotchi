# Phase 6 — native event-source adapters

This is an **initial read-only implementation**, not full endpoint detection and response.

- Windows: uses the OS `wevtutil` Security log to read events 4624 (success) and 4625 (failure). Requires OS permission to read the Security log; no elevation attempts. Reads at most 250 recent records per poll.
- Linux/Raspberry Pi: uses `journalctl` with `_COMM=sshd` and cursor checkpoints, or defaults to an accessible SSH text file when present. The journal adapter cannot compensate for missing journald permissions.
- macOS: uses `/usr/bin/log show` with a five-minute SSH predicate and deduplication. macOS may redact messages, and this adapter requires device testing.

Run `python gotchi_monitor.py once --source auto` to sample or `python gotchi_monitor.py watch --interval 60 --source auto` for a continuous local collector. Override `--source` with `file`, `journal`, `windows` or `macos`.

All adapters avoid executing security responses. The **first successful poll establishes a baseline without turning old events into fresh alerts**. Subsequent events feed the existing alerts and character mood. OS queries are capped, so high-volume events can be missed. If you see `partial` or `unavailable`, do not interpret missing alerts as evidence of safety. No permissions are changed and no administrator/sudo access is requested.

Native adapters have fixture-based parser tests and must be verified on actual Windows/macOS/Raspberry Pi systems before production deployment.
