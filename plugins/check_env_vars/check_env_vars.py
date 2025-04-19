def run():
    import os
    print("Important Environment Variables:")
    keys = ["PATH", "HOME", "USER", "SHELL", "LANG"]
    for k in keys:
        print(f"{k}: {os.getenv(k)}")
    return True