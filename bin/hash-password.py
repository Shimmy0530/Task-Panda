#!/usr/bin/env python3
"""Generate a bcrypt hash for AUTH_PASSWORD_HASH in .env.

Usage:
    python3 bin/hash-password.py

Or, with no Python on host, run inside the backend image:
    docker run --rm -it $(docker build -q ./backend) python3 -c \
        'import bcrypt, getpass; pw=getpass.getpass("password: ").encode(); \
         print(bcrypt.hashpw(pw, bcrypt.gensalt(12)).decode())'
"""
import getpass
import sys

try:
    import bcrypt
except ImportError:
    sys.stderr.write("Missing dependency: pip install bcrypt\n")
    sys.exit(1)


def main():
    pw = getpass.getpass("password: ").encode("utf-8")
    if len(pw) < 12:
        sys.stderr.write("password must be at least 12 chars\n")
        sys.exit(1)
    again = getpass.getpass("again: ").encode("utf-8")
    if pw != again:
        sys.stderr.write("mismatch\n")
        sys.exit(1)
    h = bcrypt.hashpw(pw, bcrypt.gensalt(12)).decode("utf-8")
    print()
    print("Add this line to .env (single quotes preserve $):")
    print()
    print(f"AUTH_PASSWORD_HASH='{h}'")


if __name__ == "__main__":
    main()
