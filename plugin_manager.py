import os
import importlib.util
import json

PLUGIN_FOLDER = "plugins"

class Plugin:
    def __init__(self, plugin_dir):
        manifest = json.load(open(os.path.join(plugin_dir, "manifest.json")))
        self.name = manifest["name"]
        self.type = manifest["type"]
        self.metadata = manifest
        module_name = manifest["module"]
        spec = importlib.util.spec_from_file_location(module_name, os.path.join(plugin_dir, module_name + ".py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.module = module

    def run(self):
        return self.module.run()

def load_plugins():
    plugins = []
    for entry in os.listdir(PLUGIN_FOLDER):
        pdir = os.path.join(PLUGIN_FOLDER, entry)
        if os.path.isdir(pdir) and os.path.exists(os.path.join(pdir, "manifest.json")):
            try:
                plugins.append(Plugin(pdir))
            except Exception as e:
                print(f"Error loading plugin {entry}: {e}")
    return plugins