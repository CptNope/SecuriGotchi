def run():
    import subprocess
    ip = input("Enter IP address: ")
    print(f"Looking up location for {ip}...")
    result = subprocess.getoutput(f"geoiplookup {ip}")
    print(result)
    return True