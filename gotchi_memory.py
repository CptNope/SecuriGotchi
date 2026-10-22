"""SecuriGotchi's persistent XP/memory API."""
import json
from pathlib import Path
from gotchi_chain import append_to_chain

BASE_DIR = Path(__file__).resolve().parent
brain_path = BASE_DIR / "gotchi_brain.json"
changelog_path = BASE_DIR / "gotchi_memory_changelog.txt"


def load_brain():
    with Path(brain_path).open(encoding="utf-8") as handle:
        return json.load(handle)


def save_brain(data):
    with Path(brain_path).open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")


def log_change(entry):
    with Path(changelog_path).open("a", encoding="utf-8") as handle:
        handle.write(entry + "\n")


def add_memory(action, xp=0):
    if not isinstance(action, str) or not action.strip():
        raise ValueError("Memory action must be a nonempty string")
    if isinstance(xp, bool) or not isinstance(xp, int) or xp < 0:
        raise ValueError("XP must be a nonnegative integer")
    action = action.strip()
    # Append first so invalid/tampered chains do not earn XP.
    append_to_chain(action, xp)
    brain = load_brain()
    brain.setdefault("memory_log", []).append(action)
    brain["xp"] = brain.get("xp", 0) + xp
    brain["level"] = 1 + brain["xp"] // 100
    save_brain(brain)
    log_change(f"{action} (+{xp} XP)")
    try:
        from gotchi_vector import add_memory_to_vector
        add_memory_to_vector(action)
    except (ImportError, RuntimeError, OSError) as exc:
        print(f"[Info] Vector memory unavailable: {exc}")
    return brain


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Record a SecuriGotchi memory")
    parser.add_argument("action")
    parser.add_argument("xp", nargs="?", type=int, default=0)
    args = parser.parse_args()
    add_memory(args.action, args.xp)
    print(f"Memory added: {args.action} (+{args.xp} XP)")
