r"""
Create (or change) a login for the Yard Control dashboard.

Run in the yard_ai folder:
    .\.venv\Scripts\python.exe make_password_hash.py

It asks for a username and password, then adds the login to
.streamlit/secrets.toml under [auth.users] (replacing that user's old
password if they already exist). Only a hash is stored, never the password.

For Streamlit Cloud, copy the printed line into the app's Secrets too
(under [auth.users]).
"""
import getpass
import hashlib
import os
import re
import sys

ITERATIONS = 200_000
SECRETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".streamlit", "secrets.toml")


def make_line(username, password):
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS).hex()
    return f'{username} = "pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest}"'


def save_user(path, username, line):
    text = open(path, encoding="utf-8").read() if os.path.exists(path) else ""
    lines = text.splitlines()

    header = next((i for i, l in enumerate(lines) if l.strip() == "[auth.users]"), None)
    if header is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines += ["[auth.users]", line]
        action = "added"
    else:
        end = next((i for i in range(header + 1, len(lines)) if lines[i].strip().startswith("[")), len(lines))
        user_re = re.compile(rf"^\s*{re.escape(username)}\s*=")
        existing = [i for i in range(header + 1, end) if user_re.match(lines[i])]
        for i in reversed(existing):
            del lines[i]
        lines.insert(header + 1, line)
        action = "updated" if existing else "added"

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return action


if __name__ == "__main__":
    username = input("Username (letters, numbers, _ or -): ").strip().lower()
    if not re.fullmatch(r"[a-z0-9_-]+", username):
        sys.exit("Username may only contain letters, numbers, _ or -.")

    password = getpass.getpass("Password (min 8 characters, typing is hidden): ")
    if len(password) < 8:
        sys.exit("Password must be at least 8 characters.")
    if password != getpass.getpass("Repeat password: "):
        sys.exit("Passwords do not match.")

    line = make_line(username, password)
    action = save_user(SECRETS, username, line)

    print(f"\nLogin '{username}' {action} in {SECRETS}")
    print("Refresh the dashboard page and sign in.")
    print("\nFor Streamlit Cloud, put this line under [auth.users] in the app's Secrets:\n")
    print(line)
