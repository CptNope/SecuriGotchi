def run():
    import subprocess
    print("Checking for usernames and recent logins...")
    passwd = subprocess.getoutput("cut -d: -f1 /etc/passwd | grep -v nologin | head -n 10")
    logins = subprocess.getoutput("last -n 5")
    print("--- Users ---")
    print(passwd)
    print("--- Recent Logins ---")
    print(logins)
    return True