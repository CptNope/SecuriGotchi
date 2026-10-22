"""Operator-confirmed CLI missions. Never execute untrusted shell strings."""
import json
import shlex
import subprocess
from pathlib import Path
from gotchi_memory import add_memory

MISSIONS_PATH = Path(__file__).resolve().parent / "missions" / "missions.json"
ALLOWED_COMMANDS = {"nmap", "ss", "tail"}


def load_missions():
    return json.loads(MISSIONS_PATH.read_text(encoding="utf-8"))


def save_missions(missions):
    MISSIONS_PATH.write_text(json.dumps(missions, indent=2) + "\n", encoding="utf-8")


def list_missions():
    for mission in load_missions():
        status = "Done" if mission["completed"] else "Open"
        print(f"[{mission['id']}] {mission['title']} ({status})")


def run_mission(mission_id):
    missions = load_missions()
    mission = next((m for m in missions if m["id"] == mission_id), None)
    if not mission or mission.get("completed"):
        print("Mission not found or already completed")
        return False
    argv = shlex.split(mission["command"])
    if not argv or argv[0] not in ALLOWED_COMMANDS:
        raise ValueError("Command is not on the approved mission allowlist")
    print(f"Proposed command: {shlex.join(argv)}")
    print("Only run diagnostics or network scans on systems you own or may assess.")
    if input("Run this command? Type YES: ").strip() != "YES":
        print("Cancelled")
        return False
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=90, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"Mission failed: {exc}")
        return False
    print((result.stdout + result.stderr)[:4000])
    if result.returncode != 0:
        print("Command failed; XP not awarded")
        return False
    add_memory(f"Completed mission: {mission['title']}", int(mission["xp_reward"]))
    mission["completed"] = True
    save_missions(missions)
    return True


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run confirmed local missions")
    parser.add_argument("command", choices=["list", "run"])
    parser.add_argument("id", nargs="?", type=int)
    args = parser.parse_args()
    if args.command == "list":
        list_missions()
    elif args.id is not None:
        run_mission(args.id)
    else:
        parser.error("run requires a mission ID")
