"""Local single-admin bootstrap and password verification; no web signup.

Credentials and signing keys are stored outside the Git checkout in a 0700
directory. This is local authentication, NOT a remote-access security boundary.
"""
import argparse
from contextlib import closing
import getpass
import hashlib
import hmac
import os
from pathlib import Path
import secrets
import sqlite3
import stat

ADMIN_USERNAME = "admin"
SCHEME = "scrypt-v1"
N, R, P = 2**14, 8, 1


def data_dir():
    configured = os.environ.get("SECURIGOTCHI_DATA_DIR")
    path = Path(configured).expanduser() if configured else Path.home() / ".local" / "share" / "securigotchi"
    path = path.absolute()
    if path.is_symlink():
        raise RuntimeError("Security data directory may not be a symlink")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not path.is_dir() or path.stat().st_uid != os.getuid():
        raise RuntimeError("Security data directory must be owned by the current user")
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise RuntimeError("Security data directory must have 0700 permissions")
    return path


def _private_file(name):
    return data_dir() / name


def _prepare_database():
    path = _private_file("auth.sqlite3")
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            raise RuntimeError("Credentials database must be a regular file owned by this user")
        if stat.S_IMODE(info.st_mode) & 0o077:
            raise RuntimeError("Credentials database must be private (0600)")
    finally:
        os.close(descriptor)
    return path


def _connect():
    conn = sqlite3.connect(_prepare_database(), timeout=10)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS admins ("
        "username TEXT PRIMARY KEY, salt BLOB NOT NULL, "
        "password_hash BLOB NOT NULL, scheme TEXT NOT NULL)"
    )
    return conn


def has_admin():
    with closing(_connect()) as conn:
        row = conn.execute("SELECT 1 FROM admins LIMIT 1").fetchone()
        return row is not None


def _hash(password, salt):
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=N, r=R, p=P, dklen=32)


def create_admin(password):
    if not isinstance(password, str) or not 14 <= len(password) <= 256:
        raise ValueError("Admin password must be 14 to 256 characters")
    if len(password.encode("utf-8")) > 1024:
        raise ValueError("Password exceeds the byte limit")
    salt = secrets.token_bytes(16)
    digest = _hash(password, salt)
    with closing(_connect()) as conn:
        try:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute("SELECT 1 FROM admins LIMIT 1").fetchone():
                raise ValueError("An administrator already exists; registration is closed")
            conn.execute(
                "INSERT INTO admins (username,salt,password_hash,scheme) VALUES (?,?,?,?)",
                (ADMIN_USERNAME, salt, digest, SCHEME),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def verify_admin(username, password):
    if not isinstance(username, str) or not isinstance(password, str):
        return False
    if len(password) > 256:
        return False
    with closing(_connect()) as conn:
        row = conn.execute(
            "SELECT salt,password_hash,scheme FROM admins WHERE username=?",
            (ADMIN_USERNAME,),
        ).fetchone()
    if row is None or username != ADMIN_USERNAME or row[2] != SCHEME:
        return False
    try:
        return hmac.compare_digest(_hash(password, row[0]), row[1])
    except (ValueError, TypeError):
        return False


def signing_key():
    path = _private_file("flask_signing_key.bin")
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError:
        pass
    else:
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(secrets.token_bytes(32))
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            path.unlink(missing_ok=True)
            raise
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise RuntimeError("Signing key must be user-owned and readable only by the owner")
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = -1
            value = handle.read(64)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if len(value) != 32:
        raise RuntimeError("Signing key file has an invalid length")
    return value


def main():
    parser = argparse.ArgumentParser(description="Manage the local SecuriGotchi admin")
    parser.add_argument("command", choices=["init-admin", "status"])
    args = parser.parse_args()
    if args.command == "status":
        print("Admin configured" if has_admin() else "Admin not configured")
        return
    if has_admin():
        parser.error("Admin already exists; bootstrap cannot overwrite credentials")
    first = getpass.getpass("Choose an administrator password (14+ characters): ")
    second = getpass.getpass("Confirm password: ")
    if not hmac.compare_digest(first, second):
        parser.error("Passwords do not match")
    try:
        create_admin(first)
    except ValueError as exc:
        parser.error(str(exc))
    print("Local administrator registered. Sign in as 'admin' at http://127.0.0.1:5000/login")


if __name__ == "__main__":
    main()
