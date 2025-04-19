def run():
    import subprocess
    print("TCP Ports:")
    print(subprocess.getoutput("netstat -tuln | grep tcp"))
    print("\nUDP Ports:")
    print(subprocess.getoutput("netstat -tuln | grep udp"))
    return True