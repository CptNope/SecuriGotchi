def run():
    with open("/etc/passwd") as f:
        lines = f.readlines()
    print("UID < 1000 accounts:")
    for line in lines:
        parts = line.strip().split(":")
        if len(parts) > 2 and parts[2].isdigit() and int(parts[2]) < 1000:
            print(f"{parts[0]} (UID: {parts[2]})")
    return True