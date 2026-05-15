import json
import urllib.request
import urllib.parse
import time
import os

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

def fetch_overpass_data(query: str) -> dict:
    encoded_query = urllib.parse.urlencode({"data": query})
    url = f"{OVERPASS_URL}?{encoded_query}"
    print(f"Fetching data from Overpass API...")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'KumaVectorExporter/1.0'})
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

def osm_to_geojson(osm_data: dict) -> dict:
    if not osm_data or "elements" not in osm_data:
        return {"type": "FeatureCollection", "features": []}
    
    features = []
    for element in osm_data["elements"]:
        if element["type"] == "way" and "geometry" in element:
            coords = [[p["lon"], p["lat"]] for p in element["geometry"]]
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": coords
                },
                "properties": element.get("tags", {})
            }
            features.append(feature)
    
    return {
        "type": "FeatureCollection",
        "features": features
    }

def main():
    queries = {
        "roads": """
            [out:json];
            area["name:ja"="青森県"]->.a;
            (
              way["highway"~"motorway|trunk|primary|secondary"](area.a);
            );
            out geom;
        """,
        "railways": """
            [out:json];
            area["name:ja"="青森県"]->.a;
            (
              way["railway"="rail"](area.a);
            );
            out geom;
        """,
        "rivers": """
            [out:json];
            area["name:ja"="青森県"]->.a;
            (
              way["waterway"="river"](area.a);
            );
            out geom;
        """
    }
    
    output_dir = r"c:\Users\tked1\py\03_map_and_gis\kuma-vector-exporter"
    
    for name, query in queries.items():
        print(f"Processing {name}...")
        data = fetch_overpass_data(query)
        if data:
            geojson = osm_to_geojson(data)
            filename = os.path.join(output_dir, f"aomori_{name}.json")
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(geojson, f, ensure_ascii=False)
            print(f"Saved to {filename}")
        time.sleep(2) # Be nice to the API

if __name__ == "__main__":
    main()
