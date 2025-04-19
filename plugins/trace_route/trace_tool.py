def run():
    import subprocess
    target = input("Enter target to trace: ")
    print(f"Tracing route to {target}...")
    result = subprocess.getoutput(f"traceroute {target}")
    print(result[:2000])
    return True