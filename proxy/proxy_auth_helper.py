#!/usr/bin/env python3
import sys

# Squid basic auth helper: accept any username/password and echo OK.
# Input lines: "user password" or "user:password" (implementation varies by client/helper).
for line in sys.stdin:
    line = line.strip()
    if not line:
        print("ERR")
        sys.stdout.flush()
        continue

    user = ""
    parts = line.split()
    if parts:
        if len(parts) == 1:
            user = parts[0].split(":", 1)[0]
        else:
            user = parts[0]

    if user:
        print("OK")
    else:
        print("ERR")
    sys.stdout.flush()
