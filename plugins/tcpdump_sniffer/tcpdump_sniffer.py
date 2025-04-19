def run():
    import subprocess
    iface = input("Enter interface (e.g. eth0): ")
    filter_exp = input("Enter BPF filter (e.g. port 80): ")
    print(f"Sniffing on {iface} with filter: {filter_exp}")
    cmd = f"timeout 15 tcpdump -i {iface} '{filter_exp}' -c 100"
    result = subprocess.getoutput(cmd)
    print(result)
    return True