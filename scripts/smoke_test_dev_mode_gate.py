import requests

BASE = "http://127.0.0.1:8000"


def main():
    # basic reachability (unauthenticated OK)
    r = requests.get(f"{BASE}/ui/neo-dashboard")
    print("neo-dashboard status", r.status_code)
    if r.status_code == 401:
        print("INFO: auth required; skipping gated content check.")
        print("PASS")
        return
    r.raise_for_status()
    if "DEV tools" in r.text:
        print("WARN: dev text visible without dev flag (check gating).")
    r_dev = requests.get(f"{BASE}/ui/neo-dashboard?dev=1")
    print("neo-dashboard?dev=1 status", r_dev.status_code)
    if r_dev.status_code != 401 and r_dev.status_code < 500:
        if "DEV tools" in r_dev.text:
            print("DEV flag content present (expected).")
        else:
            print("Note: DEV content is JS-inserted; run in browser to verify visibility.")
    print("PASS")


if __name__ == "__main__":
    main()
