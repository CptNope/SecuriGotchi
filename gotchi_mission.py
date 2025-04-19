import json
import subprocess

missions_path = "missions/missions.json"
brain_path = "gotchi_brain.json"

def load_missions():
    with open(missions_path) as f:
        return json.load(f)

def save_missions(missions):
    with open(missions_path, "w") as f:
        json.dump(missions, f, indent=2)

def update_brain(xp):
    with open(brain_path) as f:
        brain = json.load(f)
    brain["xp"] += xp
    brain["level"] = 1 + brain["xp"] // 100
    brain["memory_log"].append(f"Completed a mission for {xp} XP.")
    with open(brain_path, "w") as f:
        json.dump(brain, f, indent=2)

def list_missions():
    missions = load_missions()
    for m in missions:
        status = "✅" if m["completed"] else "❌"
        print(f"[{m['id']}] {m['title']} {status}")

def run_mission(mission_id):
    missions = load_missions()
    mission = next((m for m in missions if m["id"] == mission_id), None)
    if mission and not mission["completed"]:
        print(f"Running: {mission['command']}")
        result = subprocess.getoutput(mission["command"])
        print(result)
        mission["completed"] = True
        save_missions(missions)
        update_brain(mission["xp_reward"])
    else:
        print("Mission not found or already completed.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python gotchi_mission.py [list|run <id>]")
    elif sys.argv[1] == "list":
        list_missions()
    elif sys.argv[1] == "run" and len(sys.argv) == 3:
        run_mission(int(sys.argv[2]))