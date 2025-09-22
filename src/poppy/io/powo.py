import requests


def is_powo_plant(scientific_name: str, timeout: int = 10) -> bool:
    query = scientific_name.strip()
    url = f"https://powo.science.kew.org/api/2/search?q={query.replace(' ', '%20')}"
    try:
        r = requests.get(url, timeout=timeout)
        if r.status_code == 200:
            data = r.json()
            if data.get("results"):
                for result in data["results"]:
                    if result.get("name", "").lower() == query.lower():
                        return True
                return True  # any result → likely a plant
        return False
    except Exception:
        return False
