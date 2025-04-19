def run():
    import subprocess
    from gotchi_memory import load_brain
    if load_brain().get("mode", {}).get("name") != "full-control":
        print("⚠ Requires full-control mode.")
        return False
    script = '''use auxiliary/scanner/portscan/tcp
set RHOSTS 192.168.1.0/24
set PORTS 22,80,443
run
exit'''
    with open("/tmp/msf_script.rc", "w") as f:
        f.write(script)
    print("Running Metasploit scan...")
    result = subprocess.getoutput("msfconsole -r /tmp/msf_script.rc")
    print(result[:3000])
    return True