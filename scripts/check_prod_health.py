import sys
import requests
import json
import time

def check_endpoint(base_url, path):
    url = f"{base_url.rstrip('/')}{path}"
    print(f"\n--- Checking {url} ---")
    try:
        resp = requests.get(url, timeout=10)
        print(f"Status Code: {resp.status_code}")
        try:
            data = resp.json()
            print("Response JSON:")
            print(json.dumps(data, indent=2))
            return True, data
        except:
            print(f"Raw Response: {resp.text}")
            return False, None
    except Exception as e:
        print(f"Request failed: {e}")
        return False, None

def main():
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    else:
        print("\n⚠️  I need the Railway URL to check the health.")
        print("   (Go to Railway -> Networking -> Click 'Generate Domain' if needed)")
        try:
            base_url = input("👉 Paste your Railway URL here: ").strip()
        except EOFError:
            base_url = ""
    
    if not base_url:
        print("Error: No URL provided.")
        return

    if not base_url.startswith("http"):
        base_url = "https://" + base_url

    print(f"\nTarget URL: {base_url}")
    
    # 1. Check General Health (DB, OCR, LLM)
    ok, health = check_endpoint(base_url, "/health/full")
    if ok and health.get("status") == "ok":
        print("✅ Health Check Passed!")
    else:
        print("❌ Health Check Failed or Degraded.")

    # 2. Check OCR specific
    check_endpoint(base_url, "/health/ocr")

    # 3. Check Reviews Stats (New Endpoint)
    ok, stats = check_endpoint(base_url, "/reviews/stats")
    if ok and "reviews" in stats:
        print(f"✅ Review Stats Valid. Reviews: {stats['reviews']}")
    else:
        print("❌ Review Stats Endpoint Failed (Status 404 means build didn't update yet?)")

if __name__ == "__main__":
    main()
