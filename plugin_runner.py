from plugin_manager import load_plugins
from gotchi_memory import load_brain, save_brain
import os

def list_plugins(plugins):
    for idx, p in enumerate(plugins, 1):
        desc = p.metadata.get("description", "")
        print(f"[{idx}] {p.name} ({p.type}) - {desc}")

def run_plugin(idx):
    plugins = load_plugins()
    if idx < 1 or idx > len(plugins):
        print("Invalid plugin number.")
        return
    plugin = plugins[idx - 1]
    success = plugin.run()
    if plugin.type == "mission" and success:
        brain = load_brain()
        xp = plugin.metadata.get("xp_reward", 0)
        brain["xp"] += xp
        brain["level"] = 1 + brain["xp"] // 100
        brain["memory_log"].append(f"Plugin mission '{plugin.name}' completed for {xp} XP.")
        save_brain(brain)
        print(f"Gained {xp} XP!")
    return

if __name__ == "__main__":
    plugins = load_plugins()
    if not plugins:
        print("No plugins found.")
        exit()
    print("Available Plugins:")
    list_plugins(plugins)
    choice = input("Select plugin to run by number: ")
    try:
        run_plugin(int(choice))
    except ValueError:
        print("Please enter a valid number.")