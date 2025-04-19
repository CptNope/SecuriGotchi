def run():
    import subprocess
    print("Running reverse DNS lookup on 192.168.1.0/24...")
    result = subprocess.getoutput("nmap -sL 192.168.1.0/24")
    print(result[:2000])
    return True