def run():
    import subprocess
    print("Scanning top 1000 ports on 192.168.1.0/24...")
    result = subprocess.getoutput("nmap -T4 192.168.1.0/24")
    print(result[:2000])
    return True