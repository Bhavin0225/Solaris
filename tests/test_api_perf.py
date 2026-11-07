import time

from fastapi.testclient import TestClient

from swf.api.main import create_app


def test_forecast_under_500ms(seed):
    c = TestClient(create_app(seed(), start_scheduler=False, static_dir=None))
    best = float("inf")
    for _ in range(5):
        t0 = time.perf_counter()
        assert c.get("/api/forecast").status_code == 200
        best = min(best, time.perf_counter() - t0)
    assert best < 0.5
