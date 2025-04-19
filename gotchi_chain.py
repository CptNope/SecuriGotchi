import hashlib
import json
import time
import os
import subprocess

CHAIN_FILE = "gotchi_chain.json"

def hash_block(block):
    block_string = json.dumps(block, sort_keys=True).encode()
    return hashlib.sha256(block_string).hexdigest()

def create_block(index, action, xp, prev_hash):
    timestamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    block = {
        "index": index,
        "timestamp": timestamp,
        "action": action,
        "xp": xp,
        "prev_hash": prev_hash
    }
    block["hash"] = hash_block(block)
    return block

def save_chain(chain):
    with open(CHAIN_FILE, "w") as f:
        json.dump(chain, f, indent=2)
    sign_file(CHAIN_FILE)

def load_chain():
    if not os.path.exists(CHAIN_FILE):
        genesis = create_block(0, "Genesis Block", 0, "0")
        save_chain([genesis])
    with open(CHAIN_FILE, "r") as f:
        return json.load(f)

def append_to_chain(action, xp):
    chain = load_chain()
    last_block = chain[-1]
    new_block = create_block(len(chain), action, xp, last_block["hash"])
    chain.append(new_block)
    save_chain(chain)

def validate_chain():
    chain = load_chain()
    for i in range(1, len(chain)):
        if chain[i]["prev_hash"] != chain[i - 1]["hash"]:
            return False
        if chain[i]["hash"] != hash_block(chain[i]):
            return False
    return verify_signature(CHAIN_FILE)

def sign_file(filepath):
    subprocess.run([
        "gpg", "--yes", "--armor", "--detach-sign",
        "--output", f"{filepath}.sig", filepath
    ])

def verify_signature(filepath):
    result = subprocess.run(
        ["gpg", "--verify", f"{filepath}.sig", filepath],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    return result.returncode == 0