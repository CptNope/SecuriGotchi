# Plugin Architecture

Drop plugins into the `plugins/` directory. Each plugin must have:
- `manifest.json` with:
  - name: string
  - type: "mission" or "tool"
  - module: name of the .py file (without .py)
  - description: string
  - xp_reward (for missions): integer
- `<module>.py` implementing a `run()` function.

Use `plugin_manager.load_plugins()` to discover plugins.