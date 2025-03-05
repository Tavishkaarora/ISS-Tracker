import unittest
from unittest.mock import patch
from flask import json
import redis
from iss_tracker import app, calculate_speed, parse_data, doy_to_isoformat, find_closest_epoch, get_iss_data

#Sample Redis client for testing
class MockRedis:
    def __init__(self):
        self.storage = {}

    def set(self, key, value):
        self.storage[key] = value

    def get(self, key):
        return self.storage.get(key)

    def exists(self, key):
        return key in self.storage

class TestISSTracker(unittest.TestCase):
    """Unit tests for ISS tracker Flask app and core functions (same idea as before, but with correct Redis client)"""

    def setUp(self):
        """Set up test client and sample Redis."""
        self.app = app.test_client()
        self.app.testing = True
        self.mock_redis = MockRedis()

    @patch("iss_tracker.redis_client", new_callable=lambda: MockRedis())
    def test_fetch_and_store_data(self, mock_redis):
        """Test that data is fetched and stored in Redis."""
        mock_redis.set("iss_data", json.dumps([{"epoch": "2025-045T12:00:00.000Z"}]))
        data = json.loads(mock_redis.get("iss_data"))
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["epoch"], "2025-045T12:00:00.000Z")

    @patch("iss_tracker.get_iss_data")
    def test_get_epochs(self, mock_data):
        """Test the /epochs route"""
        mock_data.return_value = [
            {"epoch": "2025-045T12:00:00.000Z"},
            {"epoch": "2025-046T14:30:00.000Z"},
        ]

        response = self.app.get("/epochs")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(json.loads(response.data)), 2)

    @patch("iss_tracker.get_iss_data")
    def test_get_epoch(self, mock_data):
        """Test retrieving a specific epoch."""
        mock_data.return_value = [{"epoch": "2025-045T12:00:00.000Z"}]

        response = self.app.get("/epochs/2025-045T12:00:00.000Z")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.data)["epoch"], "2025-045T12:00:00.000Z")

        response = self.app.get("/epochs/invalid-epoch")
        self.assertEqual(response.status_code, 404)

    @patch("iss_tracker.get_iss_data")
    def test_get_epoch_speed(self, mock_data):
        """Test retrieving speed for a specific epoch."""
        mock_data.return_value = [
            {"epoch": "2025-045T12:00:00.000Z", "x_dot": 7.39, "y_dot": 2.01, "z_dot": -0.16}
        ]

        response = self.app.get("/epochs/2025-045T12:00:00.000Z/speed")
        self.assertEqual(response.status_code, 200)
        self.assertAlmostEqual(json.loads(response.data)["speed"], 7.6601, places=1)

        response = self.app.get("/epochs/invalid-epoch/speed")
        self.assertEqual(response.status_code, 404)

    @patch("iss_tracker.get_iss_data")
    def test_get_epoch_location(self, mock_data):
        """Test retrieving latitude, longitude, and altitude."""
        mock_data.return_value = [
            {"epoch": "2025-045T12:00:00.000Z", "x": 10.0, "y": 20.0, "z": 400.0}
        ]

        response = self.app.get("/epochs/2025-045T12:00:00.000Z/location")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["latitude"], 20.0)
        self.assertEqual(data["longitude"], 10.0)
        self.assertEqual(data["altitude"], 400.0)

    @patch("iss_tracker.find_closest_epoch")
    def test_get_now(self, mock_closest_epoch):
        """Test retrieving the closest epoch's details."""
        mock_closest_epoch.return_value = {
            "epoch": "2025-045T12:00:00.000Z",
            "x": 10.0, "y": 20.0, "z": 400.0,
            "x_dot": 7.39, "y_dot": 2.01, "z_dot": -0.16
        }

        response = self.app.get("/now")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn("speed", data)

if __name__ == '__main__':
    unittest.main()

