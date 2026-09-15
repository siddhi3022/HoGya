import requests, sys, time, os

def test_root(url):
    try:
        r = requests.get(url, timeout=3)
        print(f"{url} -> {r.status_code}")
        return r.status_code == 200
    except Exception as e:
        print(f"{url} ERROR: {e}")
        return False

if __name__ == "__main__":
    for url in ["http://localhost:8001/", "http://localhost:8002/"]:
        ok = test_root(url)
        sys.exit(0 if ok else 1)

