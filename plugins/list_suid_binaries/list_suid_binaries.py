def run():
    import subprocess
    print("Searching for SUID binaries...")
    result = subprocess.getoutput("find / -perm -4000 -type f 2>/dev/null")
    print(result[:2000])
    return True