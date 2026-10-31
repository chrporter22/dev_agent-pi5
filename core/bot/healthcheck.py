import os
import socket
import sys
import urllib.parse as urlparse


def main():
    base = os.environ.get("AI_GATEWAY_BASE_URL", "")
    if not base:
        print("AI_GATEWAY_BASE_URL not set", file=sys.stderr)
        sys.exit(1)

    parsed = urlparse.urlparse(base)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    if not host:
        print(f"AI_GATEWAY_BASE_URL has no host: {base}", file=sys.stderr)
        sys.exit(1)

    try:
        with socket.create_connection((host, port), timeout=5):
            pass
    except Exception as e:
        print(f"Gateway unreachable at {host}:{port}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
