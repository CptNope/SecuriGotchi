def run():
    import subprocess
    print("Running Nikto on http://localhost...")
    result = subprocess.getoutput("nikto -h http://localhost")
    print(result[:2000])
    return True