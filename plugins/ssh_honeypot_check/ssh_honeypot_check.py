def run():
    import subprocess
    result = subprocess.getoutput("grep 'Failed password' /var/log/auth.log | tail -n 10")
    if result:
        print(result)
        return True
    print("No recent SSH brute-force attempts found.")
    return False