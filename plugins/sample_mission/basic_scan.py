def run():
    import subprocess
    result = subprocess.getoutput("nmap -T4 -A 192.168.1.0/24")
    print(result)
    return True