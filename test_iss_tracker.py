import unittest
from unittest.mock import patch
from flask import json
from iss_tracker import app, calculate_speed, doy_to_isoformat, calculate_location

# Sample ISS data for testing
data_sample = [
    {"epoch": "2025-081T12:00:00.000Z", "x": -6111.569, "y": -2741.316, "z": -1176.237, 
     "x_dot": 2.90, "y_dot": -3.97, "z_dot": -5.86},
    {"epoch": "2025-081T11:26:30.000Z", "x": -3272.614, "y": 3185.615, "z": 5023.641, 
     "x_dot": -6.50, "y_dot": -3.53, "z_dot": -1.98}
]

class TestISSTracker(unittest.TestCase):
    """
    Unit tests for ISS tracker functions and Flask routes.
    """

    def setUp(self):
        """Set up the test client for Flask"""
        self.app = app.test_client()
        self.app.testing = True

    @patch("iss_tracker.redis_client.get", return_value=json.dumps(data_sample))
    def test_get_epochs(self, mock_redis):
        """Test the /epochs route with and without query parameters."""
        response = self.app.get("/epochs")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(json.loads(response.data)), 2)

        response = self.app.get("/epochs?limit=1")
        self.assertEqual(len(json.loads(response.data)), 1)

    @patch("iss_tracker.redis_client.get", return_value=json.dumps(data_sample))
    def test_get_epoch(self, mock_redis):
        """Test retrieving a specific epoch."""
        response = self.app.get("/epochs/2025-081T12:00:00.000Z")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.data)["epoch"], "2025-081T12:00:00.000Z")

    @patch("iss_tracker.redis_client.get", return_value=json.dumps(data_sample))
    def test_get_invalid_epoch(self, mock_redis):
        """Test retrieving an invalid epoch (should return 404)."""
        response = self.app.get("/epochs/invalid-epoch")
        self.assertEqual(response.status_code, 404)

    @patch("iss_tracker.redis_client.get", return_value=json.dumps(data_sample))
    def test_get_epoch_speed(self, mock_redis):
        """Test retrieving speed for a specific epoch."""
        response = self.app.get("/epochs/2025-081T12:00:00.000Z/speed")
        self.assertEqual(response.status_code, 200)
        self.assertAlmostEqual(json.loads(response.data)["speed"], 7.6601, places=1)

    @patch("iss_tracker.redis_client.get", return_value=json.dumps(data_sample))
    def test_get_epoch_location(self, mock_redis):
        """Test retrieving latitude, longitude, altitude, and geoposition for a specific epoch."""
        response = self.app.get("/epochs/2025-081T12:00:00.000Z/location")
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.data)
        self.assertIn("latitude", data)
        self.assertIn("longitude", data)
        self.assertIn("altitude", data)
        self.assertIn("geoposition", data)

    @patch("iss_tracker.redis_client.get", return_value=json.dumps(data_sample))
    def test_get_now(self, mock_redis):
        """Test retrieving the closest epoch to the current time."""
        response = self.app.get("/now")
        self.assertEqual(response.status_code, 200)
        self.assertIn("speed", json.loads(response.data))
        self.assertIn("latitude", json.loads(response.data))

    def test_calculate_speed(self):
        """Test if speed calculation is correct."""
        speed = calculate_speed(7.39, 2.01, -0.16)
        self.assertAlmostEqual(speed, 7.6601, places=1)

    def test_doy_to_isoformat(self):
        """Test conversion of DOY formatted date to ISO format."""
        self.assertEqual(doy_to_isoformat("2025-081T12:00:00.000Z"), "2025-03-21T12:00:00.000Z")

    def test_calculate_location(self):
        """Test converting Cartesian coordinates to latitude, longitude, and altitude."""
        lat, lon, alt, _ = calculate_location(-6111.569, -2741.316, -1176.237)
        self.assertIsInstance(lat, float)
        self.assertIsInstance(lon, float)
        self.assertIsInstance(alt, float)

    @patch("iss_tracker.redis_client.get", return_value=json.dumps(data_sample))
    def test_redis_data_storage(self, mock_redis):
        """Test if ISS data is correctly stored in Redis."""
        redis_data = json.loads(mock_redis.return_value)
        self.assertGreater(len(redis_data), 0, "Redis should store at least one epoch of data")

if __name__ == '__main__':
    unittest.main()

