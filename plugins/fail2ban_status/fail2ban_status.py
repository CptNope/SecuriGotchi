def run():
    import subprocess
    result = subprocess.getoutput("fail2ban-client status")
    print(result)
    return True