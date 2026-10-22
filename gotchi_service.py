"""Generate a conservative systemd *user* unit; never start or enable it.

A graphical user service may emit desktop notifications when notify-send is
available. To avoid accidental remote access, the unit runs only the collector.
"""
import argparse
from pathlib import Path
import os


def _checked_path(path):
    value = str(path.resolve())
    if any(char in value for char in ('"', "\\", "\n", "\r", "%")):
        raise ValueError("Unsupported characters in service path")
    return value


def render_unit(repo, interval=60, notify=False, notify_level="high"):
    if not isinstance(interval, int) or not 10 <= interval <= 3600:
        raise ValueError("Interval must be 10-3600 seconds")
    if notify_level not in ("warning", "high", "critical"):
        raise ValueError("Invalid notification severity")
    repo = Path(repo)
    interpreter = _checked_path(repo / ".venv" / "bin" / "python")
    monitor = _checked_path(repo / "gotchi_monitor.py")
    cwd = _checked_path(repo)
    # systemd interprets quoted ExecStart arguments, without invoking a shell.
    cmd = f'ExecStart="{interpreter}" "{monitor}" watch --interval {interval}'
    if notify:
        cmd += f" --notify --notify-level {notify_level}"
    return "\n".join([
        "[Unit]",
        "Description=SecuriGotchi local defensive event collector",
        "Documentation=https://github.com/CptNope/SecuriGotchi",
        "",
        "[Service]",
        "Type=simple",
        f"WorkingDirectory={cwd}",
        cmd,
        "Restart=on-failure",
        "RestartSec=5",
        "TimeoutStopSec=20",
        "NoNewPrivileges=true",
        "PrivateTmp=true",
        "ProtectSystem=strict",
        "ProtectKernelTunables=true",
        "ProtectControlGroups=true",
        "RestrictSUIDSGID=true",
        "UMask=0077",
        # The collector needs its private SQLite directory to remain writable.
        f"ReadWritePaths={_checked_path(Path.home() / '.local' / 'share' / 'securigotchi')}",
        "",
        "[Install]",
        "WantedBy=default.target",
        "",
    ])


def main():
    parser = argparse.ArgumentParser(description="Generate SecuriGotchi systemd user service")
    parser.add_argument("command", choices=["print", "install"])
    parser.add_argument("--interval", type=int, default=60)
    parser.add_argument("--notify", action="store_true", help="Opt in to local desktop notifications")
    parser.add_argument("--notify-level", choices=["warning", "high", "critical"], default="high")
    parser.add_argument("--replace", action="store_true", help="Overwrite an existing generated unit")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parent
    if not (repo / ".venv" / "bin" / "python").is_file():
        parser.error("Create .venv first with bash secgotchi_install.sh")
    if os.environ.get("SECURIGOTCHI_DATA_DIR"):
        parser.error("Custom SECURIGOTCHI_DATA_DIR is not supported by the generated systemd unit; configure manually.")
    service = render_unit(repo, args.interval, args.notify, args.notify_level)
    if args.command == "print":
        print(service)
        return
    destination = Path.home() / ".config" / "systemd" / "user" / "securigotchi-monitor.service"
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if destination.exists() and (destination.is_symlink() or not args.replace):
        parser.error("Unit exists; use --replace for a regular file you own")
    flags = os.O_WRONLY | os.O_CREAT | (os.O_TRUNC if args.replace else os.O_EXCL)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(destination, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(service)
    print("Wrote", destination)
    print("Next: systemctl --user daemon-reload")
    print("Then manually: systemctl --user enable --now securigotchi-monitor.service")
    print("The service was NOT enabled or started by this command.")


if __name__ == "__main__":
    main()
