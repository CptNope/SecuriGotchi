import json
from gotchi_chain import append_to_chain

brain_path = "gotchi_brain.json"
changelog_path = "gotchi_memory_changelog.txt"

def load_brain():
    with open(brain_path, "r") as f:
        return json.load(f)

def save_brain(data):
    with open(brain_path, "w") as f:
        json.dump(data, f, indent=2)

def log_change(entry):
    with open(changelog_path, "a") as f:
        f.write(entry + "\n")

def add_memory(action, xp=0):
    brain = load_brain()
    brain["memory_log"].append(action)
    brain["xp"] += xp
    brain["level"] = 1 + brain["xp"] // 100
    save_brain(brain)
    append_to_chain(action, xp)
    log_change(f"{action} (+{xp} XP)")
    print(f"Memory added: {action} (+{xp} XP)")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        add_memory(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 0)
    else:
        print("Usage: python gotchi_memory.py "action description" [xp]")