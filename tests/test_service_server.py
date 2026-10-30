import json
import threading
import unittest
import urllib.error
import urllib.request

import numpy as np

from coldchain_monitor import __version__
from coldchain_monitor.data import synthetic_log, write_csv
from coldchain_monitor.server import make_server
from coldchain_monitor.service import forecast_summary


class ForecastSummaryTest(unittest.TestCase):
    def test_flat_series_is_ok(self):
        r = forecast_summary(np.full(300, 2.5), hours=3)
        self.assertEqual(r.status, "ok")
        self.assertAlmostEqual(r.arima, 2.5)
        self.assertFalse(r.tier2_active)

    def test_reading_above_limit_is_excursion(self):
        series = np.r_[np.full(100, 2.5), 5.0]
        self.assertEqual(forecast_summary(series, hours=1).status, "excursion")

    def test_rising_series_gives_warning(self):
        series = 0.92 + 0.01 * np.arange(300)  # steady rise, last reading 3.91 °C
        r = forecast_summary(series, hours=3)
        self.assertEqual(r.status, "warning")
        self.assertGreater(r.arima_max, 4.0)

    def test_invalid_input(self):
        for bad in ([1.0], [1.0, float("nan")], [[1.0, 2.0]]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                forecast_summary(bad)
        for hours in (0, 25, 1.5, True):
            with self.subTest(hours=hours), self.assertRaises(ValueError):
                forecast_summary(np.full(50, 2.5), hours=hours)


class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import tempfile
        from pathlib import Path

        cls._tmp = tempfile.TemporaryDirectory()
        path = write_csv(synthetic_log(hours=24, seed=1), Path(cls._tmp.name) / "log.csv")
        cls.server = make_server("127.0.0.1", 0, example_path=path)
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls._tmp.cleanup()

    def request(self, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.base + path, data=data,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read())

    def test_health(self):
        self.assertEqual(self.request("/health"), (200, {"status": "ok", "version": __version__}))

    def test_get_forecast_on_example_log(self):
        code, body = self.request("/forecast?hours=1")
        self.assertEqual(code, 200)
        self.assertEqual(body["hours"], 1)
        self.assertIn(body["status"], {"ok", "warning", "excursion"})
        self.assertEqual(body["source"], "log")

    def test_post_forecast(self):
        code, body = self.request("/forecast", {"temperature": [2.5] * 100, "hours": 2})
        self.assertEqual(code, 200)
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["readings"], 100)

    def test_bad_requests_return_400_or_404(self):
        self.assertEqual(self.request("/forecast", {"hours": 2})[0], 400)
        self.assertEqual(self.request("/forecast", {"temperature": [1.0], "hours": 2})[0], 400)
        self.assertEqual(self.request("/forecast?hours=abc")[0], 400)
        self.assertEqual(self.request("/nothing")[0], 404)


if __name__ == "__main__":
    unittest.main()
