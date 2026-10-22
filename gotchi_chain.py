"""Locally verifiable hash-chained activity log (not a blockchain)."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone

CHAIN_FILE = Path(__file__).resolve().parent / "gotchi_chain.json"


def hash_block(block):
    """Hash canonical block data excluding the stored hash itself."""
    content = {key: value for key, value in block.items() if key != "hash"}
    payload = json.dumps(content, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def create_block(index, action, xp, prev_hash):
    block = {
        "index": index,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "action": action,
        "xp": xp,
        "prev_hash": prev_hash,
    }
    block["hash"] = hash_block(block)
    return block


def sign_file(filepath):
    """Best-effort local signature; never ask for a key interactively."""
    filepath = Path(filepath)
    signature = Path(str(filepath) + ".sig")
    if signature.exists():
        signature.unlink()  # Never leave a signature of an old version.
    if not shutil.which("gpg"):
        return False
    try:
        result = subprocess.run(
            ["gpg", "--batch", "--yes", "--detach-sign", "--armor",
             "--output", str(signature), str(filepath)],
            capture_output=True, timeout=15, check=False,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def verify_signature(filepath):
    filepath = Path(filepath)
    signature = Path(str(filepath) + ".sig")
    if not signature.is_file() or not shutil.which("gpg"):
        return False
    try:
        result = subprocess.run(
            ["gpg", "--batch", "--verify", str(signature), str(filepath)],
            capture_output=True, timeout=15, check=False,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def save_chain(chain):
    path = Path(CHAIN_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        temporary_path = Path(handle.name)
        json.dump(chain, handle, indent=2)
        handle.write("\n")
    os.replace(temporary_path, path)
    return sign_file(path)


def load_chain():
    path = Path(CHAIN_FILE)
    if not path.exists():
        save_chain([create_block(0, "Genesis Block", 0, "0")])
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def append_to_chain(action, xp):
    chain = load_chain()
    if not validate_blocks(chain):
        raise ValueError("Refusing to append: the chain is corrupted")
    chain.append(create_block(len(chain), action, xp, chain[-1]["hash"]))
    save_chain(chain)


def validate_blocks(chain):
    if not isinstance(chain, list) or not chain:
        return False
    for index, block in enumerate(chain):
        if not isinstance(block, dict) or block.get("index") != index:
            return False
        if block.get("hash") != hash_block(block):
            return False
        if block.get("prev_hash") != (chain[index - 1]["hash"] if index else "0"):
            return False
    return True


def validate_chain(require_signature=True):
    try:
        chain = load_chain()
        return validate_blocks(chain) and (
            not require_signature or verify_signature(CHAIN_FILE)
        )
    except (OSError, ValueError, TypeError, KeyError):
        return False


if __name__ == "__main__":
    import sys
    is_valid = validate_chain()
    print("Chain and GPG signature valid" if is_valid else "Invalid/unsigned chain")
    sys.exit(0 if is_valid else 1)
