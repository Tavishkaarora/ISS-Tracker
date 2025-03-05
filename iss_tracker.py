from flask import Flask, request, jsonify
import logging
import requests
import redis
import xml.etree.ElementTree as ET
import math
import datetime
import json
from typing import List, Dict
from geopy.geocoders import Nominatim

app = Flask(__name__)
redis_client = redis.Redis(host="redis", port=6379, decode_responses=True)

logging.basicConfig(level=logging.DEBUG)

URL = "https://nasa-public-data.s3.amazonaws.com/iss-coords/current/ISS_OEM/ISS.OEM_J2K_EPH.xml"

def fetch_and_store_data():
    """Fetch ISS data from NASA and store it in Redis."""
    response = requests.get(URL)
    response.raise_for_status()
    state_vectors = parse_data(response.text)
    
    #Store parsed data into Redis
    redis_client.set("iss_data", json.dumps(state_vectors))

def parse_data(xml_data: str) -> List[Dict[str, float]]:
    """Data Formatting; Parse ISS XML data into a list of state vectors."""
    root = ET.fromstring(xml_data)
    state_vectors = []
    for state_vector in root.findall(".//stateVector"):
        epoch = state_vector.find("EPOCH").text
        x = float(state_vector.find("X").text)
        y = float(state_vector.find("Y").text)
        z = float(state_vector.find("Z").text)
        x_dot = float(state_vector.find("X_DOT").text)
        y_dot = float(state_vector.find("Y_DOT").text)
        z_dot = float(state_vector.find("Z_DOT").text)
        state_vectors.append({
            "epoch": epoch, "x": x, "y": y, "z": z,
            "x_dot": x_dot, "y_dot": y_dot, "z_dot": z_dot
        })
    return state_vectors

def get_iss_data():
    """Retrieve ISS data from Redis or fetch from NASA if empty."""
    if not redis_client.exists("iss_data"):
        fetch_and_store_data()
    return json.loads(redis_client.get("iss_data"))

def calculate_speed(x_dot: float, y_dot: float, z_dot: float) -> float:
    """Compute speed from velocity components sqrt(x'^2 + y'^2 + z'^2 """
    return math.sqrt(x_dot**2 + y_dot**2 + z_dot**2)

def doy_to_isoformat(epoch: str) -> str:
    """Convert day-of-year (DOY) formatted date to ISO format."""
    year, doy_time = epoch.split('-')
    doy, time = doy_time.split('T')
    date = datetime.datetime.strptime(f"{year}-{doy}", "%Y-%j").date()
    return f"{date}T{time}"

def find_closest_epoch() -> Dict:
    """Find the closest epoch to the current UTC time."""
    now = datetime.datetime.now(datetime.UTC)
    data = get_iss_data()
    return min(
        data,
        key=lambda d: abs(
            datetime.datetime.fromisoformat(doy_to_isoformat(d["epoch"])).replace(tzinfo=datetime.UTC) - now
        ),
    )

def get_geoposition(lat: float, lon: float) -> str:
    """Retrieve human-understandable location from latitude and longitude."""
    geolocator = Nominatim(user_agent="iss_tracker")
    location = geolocator.reverse((lat, lon), exactly_one=True)
    return location.address if location else "Unknown location"

#Flask Routes
@app.route("/epochs", methods=["GET"])
def get_epochs():
    """Return all epochs or a subset based on limit & offset."""
    data = get_iss_data()
    limit = request.args.get("limit", type=int)
    offset = request.args.get("offset", type=int, default=0)
    subset = data[offset:offset+limit] if limit else data[offset:]
    return jsonify(subset)

@app.route("/epochs/<epoch>", methods=["GET"])
def get_epoch(epoch):
    """Return state vectors for a specific epoch."""
    data = get_iss_data()
    result = next((d for d in data if d["epoch"] == epoch), None)
    return jsonify(result) if result else ("Epoch not found", 404)

@app.route("/epochs/<epoch>/speed", methods=["GET"])
def get_epoch_speed(epoch):
    """Return instantaneous speed for a given epoch."""
    data = get_iss_data()
    result = next((d for d in data if d["epoch"] == epoch), None)
    if result:
        speed = calculate_speed(result["x_dot"], result["y_dot"], result["z_dot"])
        return jsonify({"epoch": epoch, "speed": speed})
    return ("Epoch not found", 404)

@app.route("/epochs/<epoch>/location", methods=["GET"])
def get_epoch_location(epoch):
    """Return latitude, longitude, altitude, and geoposition for an epoch."""
    data = get_iss_data()
    result = next((d for d in data if d["epoch"] == epoch), None)
    if result:
        geoposition = get_geoposition(result["y"], result["x"])  # Swap x/y for lat/lon
        return jsonify({
            "epoch": epoch,
            "latitude": result["y"],
            "longitude": result["x"],
            "altitude": result["z"],
            "geoposition": geoposition
        })
    return ("Epoch not found", 404)

@app.route("/now", methods=["GET"])
def get_now():
    """Return instantaneous speed, latitude, longitude, altitude, and geoposition for the closest epoch."""
    closest = find_closest_epoch()
    speed = calculate_speed(closest["x_dot"], closest["y_dot"], closest["z_dot"])
    
    # Log latitude and longitude before passing to geopy
    logging.debug(f"Latitude (y): {closest['y']}, Longitude (x): {closest['x']}")

    try:
        geoposition = get_geoposition(closest["y"], closest["x"])  # Swap x/y for lat/lon
    except Exception as e:
        logging.error(f"Error in get_geoposition: {e}")
        geoposition = "Unknown location"

    return jsonify({
        **closest,
        "speed": speed,
        "geoposition": geoposition
    })

if __name__ == "__main__":
    fetch_and_store_data()
    app.run(host="0.0.0.0", port=5000, debug=True)

