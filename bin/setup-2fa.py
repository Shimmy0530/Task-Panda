#!/usr/bin/env python3
"""Generate a TOTP secret and provisioning URI for AUTH_TOTP_SECRET in .env.

Usage:
    python3 bin/setup-2fa.py
"""
import sys

try:
    import pyotp
except ImportError:
    sys.stderr.write("Missing dependency: pip install pyotp\n")
    sys.exit(1)


def main():
    secret = pyotp.random_base32()
    uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name="owner", issuer_name="Focus"
    )
    print()
    print("Add to .env:")
    print()
    print(f"AUTH_TOTP_SECRET={secret}")
    print()
    print("Provisioning URI (paste into 1Password, Bitwarden, Aegis, etc.):")
    print()
    print(uri)
    print()
    print("Or render as QR with:  qrencode -t ANSIUTF8 '<uri above>'")
    print()
    # Verify roundtrip with a generated code so the user can sanity-check.
    sample = pyotp.TOTP(secret).now()
    print(f"Current code (test it lines up with your app once added): {sample}")


if __name__ == "__main__":
    main()
