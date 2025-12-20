from app.main import app


def main():
    prefixes = ("/oem", "/api/oem", "/ui", "/warranty", "/predictive")
    for route in app.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", [])
        if any(path.startswith(p) for p in prefixes):
            print(f"{sorted(methods)} {path}")


if __name__ == "__main__":
    main()
