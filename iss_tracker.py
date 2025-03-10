from flask import Flask, request, jsonify
import requests
import xml.etree.ElementTree as ET
import math
import datetime
import redis
import json
from geopy.geocoders import Nominatim
from typing import List, Dict

app = Flask(__name__)

# Connect to Redis
redis_client = redis.Redis(host="redis", port=6379, decode_responses=True)

# NASA ISS Data URL
URL = "https://nasa-public-data.s3.amazonaws.com/iss-coords/current/ISS_OEM/ISS.OEM_J2K_EPH.xml"

# Initialize Geolocator
geolocator = Nominatim(user_agent="iss_tracker")


def fetch_data():
    """Fetch and store ISS trajectory data in Redis if not already there"""
    if redis_client.exists("iss_data"):
        print("Data loaded from Redis")
    else:
        print("Fetching data from NASA...")
        response = requests.get(URL)
        response.raise_for_status()
        data = parse_data(response.text)
        redis_client.set("iss_data", json.dumps(data))


def parse_data(xml_data: str) -> List[Dict[str, float]]:
    """Convert ISS XML data into a list of state vectors"""
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


def calculate_speed(x_dot: float, y_dot: float, z_dot: float) -> float:
    """Compute speed from velocity components"""
    return math.sqrt(x_dot**2 + y_dot**2 + z_dot**2)


def doy_to_isoformat(epoch: str) -> str:
    """Convert day-of-year (DOY) formatted date to ISO format, adjusting for potential error where the date is off by one"""
    year, doy_time = epoch.split('-')
    doy, time = doy_time.split('T')
    date = datetime.datetime.strptime(f"{year}-{int(doy):03d}", "%Y-%j").date()
    
    # Fix off-by-one issue
    corrected_date = date - datetime.timedelta(days=1)

    return f"{corrected_date}T{time}"



def find_closest_epoch(data) -> Dict:
    """Find the closest epoch to the current UTC time"""
    now = datetime.datetime.now(datetime.UTC)
    return min(
        data,
        key=lambda d: abs(
            datetime.datetime.fromisoformat(doy_to_isoformat(d["epoch"])).replace(tzinfo=datetime.UTC) - now
        ),
    )


def calculate_location(x, y, z):
    """Convert Cartesian coordinates to latitude, longitude, altitude"""
    R_EARTH = 6371  # Earth's radius in km
    altitude = math.sqrt(x**2 + y**2 + z**2) - R_EARTH
    lat = math.degrees(math.atan2(z, math.sqrt(x**2 + y**2)))
    lon = math.degrees(math.atan2(y, x))

    location = geolocator.reverse((lat, lon), language="en")
    return lat, lon, altitude, location.address if location else "Geolocation Unknown"


# ------------------------- Flask Routes -------------------------

@app.route("/epochs", methods=["GET"])
def get_epochs():
    """Return all epochs or a subset based on limit/offset"""
    data = json.loads(redis_client.get("iss_data"))
    limit = request.args.get("limit", type=int)
    offset = request.args.get("offset", type=int, default=0)
    subset = data[offset:offset+limit] if limit else data[offset:]
    return jsonify(subset)


@app.route("/epochs/<epoch>", methods=["GET"])
def get_epoch(epoch):
    """Return state vectors for a specific epoch"""
    data = json.loads(redis_client.get("iss_data"))
    result = next((d for d in data if d["epoch"] == epoch), None)
    return jsonify(result) if result else ("Epoch not found", 404)


@app.route("/epochs/<epoch>/speed", methods=["GET"])
def get_epoch_speed(epoch):
    """Return instantaneous speed for a given epoch"""
    data = json.loads(redis_client.get("iss_data"))
    result = next((d for d in data if d["epoch"] == epoch), None)
    if result:
        speed = calculate_speed(result["x_dot"], result["y_dot"], result["z_dot"])
        return jsonify({"epoch": epoch, "speed": speed})
    return ("Epoch not found", 404)


@app.route("/epochs/<epoch>/location", methods=["GET"])
def get_epoch_location(epoch):
    """Return latitude, longitude, altitude, and geoposition for a given epoch"""
    data = json.loads(redis_client.get("iss_data"))
    result = next((d for d in data if d["epoch"] == epoch), None)
    if result:
        lat, lon, alt, address = calculate_location(result["x"], result["y"], result["z"])
        return jsonify({"latitude": lat, "longitude": lon, "altitude": alt, "geoposition": address})
    return ("Epoch not found", 404)


@app.route("/now", methods=["GET"])
def get_now():
    """Return location and speed for the closest epoch to the current time"""
    data = json.loads(redis_client.get("iss_data"))
    closest = find_closest_epoch(data)
    lat, lon, alt, address = calculate_location(closest["x"], closest["y"], closest["z"])
    speed = calculate_speed(closest["x_dot"], closest["y_dot"], closest["z_dot"])
    return jsonify({
        "latitude": lat, "longitude": lon, "altitude": alt,
        "geoposition": address, "speed": speed
    })


# ------------------------- Run Flask App -------------------------
if __name__ == "__main__":
    fetch_data()
    app.run(host="0.0.0.0", port=5000, debug=True)

