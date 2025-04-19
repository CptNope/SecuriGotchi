def run():
    import subprocess
    domain = input("Enter domain to lookup: ")
    print(f"Running whois on {domain}...")
    result = subprocess.getoutput(f"whois {domain}")
    print(result[:2000])
    return True