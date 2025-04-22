from flask import Flask, render_template, request, jsonify
import json
import os
import subprocess
from datetime import datetime
import gotchi_query
import gotchi_memory
import gotchi_chain

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/brain')
def get_brain():
    with open('gotchi_brain.json', 'r') as f:
        brain = json.load(f)
    return jsonify(brain)

@app.route('/api/memory')
def get_memory():
    with open('gotchi_memory_changelog.txt', 'r') as f:
        memory = f.readlines()
    return jsonify(memory)

@app.route('/api/query', methods=['POST'])
def query_memory():
    query = request.json.get('query', '')
    results = gotchi_query.search_memory(query, top_k=5)
    return jsonify(results)

@app.route('/api/run_plugin', methods=['POST'])
def run_plugin():
    plugin_name = request.json.get('plugin', '')
    target = request.json.get('target', '')
    
    # Security check - validate plugin name against allowed list
    allowed_plugins = [
        'Metasploit Basic Scan', 'Nikto Web Scan', 'Nmap Top Ports', 
        'Reverse DNS Scan', 'Netstat Summary', 'Fail2Ban Status',
        'UID Check', 'Environment Vars', 'List SUID Binaries',
        'SSH Honeypot Check', 'User Enumeration', 'WHOIS Lookup',
        'Traceroute Tool', 'GeoIP Lookup', 'TCPDump Sniffer'
    ]
    
    if plugin_name not in allowed_plugins:
        return jsonify({"error": "Invalid plugin"}), 400
    
    # Run the plugin and add to memory
    result = f"Ran {plugin_name} on {target} at {datetime.now().isoformat()}"
    gotchi_memory.add_memory_entry(f"Plugin: {plugin_name}", f"Target: {target}", result)
    
    # Update and sign the chain
    gotchi_chain.update_chain()
    
    return jsonify({"success": True, "result": result})

@app.route('/api/chain_verify')
def verify_chain():
    result = subprocess.run(['python', 'gotchi_chain.py', '--verify'], 
                           capture_output=True, text=True)
    return jsonify({"valid": "Signature verified successfully" in result.stdout})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
