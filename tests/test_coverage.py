import json
from datetime import date

import httpx
import pytest

from swf.coverage import probe

TODAY = date(2026, 11, 1)


@pytest.fixture
def pf(fixtures_dir):
    return json.loads((fixtures_dir / "probe_summary.json").read_text())


def test_first_last_valid():
    assert probe.first_valid(["t0", "t1", "t2"], [None, 3.0, None]) == "t1"
    assert probe.last_valid(["t0", "t1", "t2"], [None, 3.0, None]) == "t1"
    assert probe.first_valid(["a"], [None]) is None and probe.last_valid(["a"], [None]) is None


def test_eligibility_on_recorded_probe(pf):
    res = {m: probe.is_eligible(m, d) for m, d in pf["models"].items()}
    assert res["gfs_seamless"] == (True, [])
    ok, why = res["ecmwf_ifs025"]
    assert not ok and any("HF shortwave_radiation first valid 2024-03-05T08:00" in w for w in why)
    ok, why = res["ecmwf_ifs"]
    assert not ok and any("PR day1" in w and "2025-10-01" in w for w in why)
    assert not res["icon_seamless"][0] and "2022-11-16" in res["icon_seamless"][1][0]
    ok, why = res["best_match"]
    assert not ok and "alias" in why[0]


def test_never_valid_pr_variable_fails(pf):
    m = json.loads(json.dumps(pf["models"]["gfs_seamless"]))
    m["pr"]["cloud_cover_previous_day1"] = None
    assert not probe.is_eligible("gfs_seamless", m)[0]


def test_upper_wind_uses_looser_bound(pf):
    m = json.loads(json.dumps(pf["models"]["gfs_seamless"]))
    m["pr"]["shortwave_radiation_previous_day1"] = "2024-03-01T00:00"  # late for rule (a)
    assert not probe.is_eligible("gfs_seamless", m)[0]
    m["pr"]["shortwave_radiation_previous_day1"] = "2024-01-19T12:00"
    m["pr"]["wind_speed_80m_previous_day1"] = "2024-03-01T00:00"  # on time for rule (b)
    assert probe.is_eligible("gfs_seamless", m)[0]


def _handler(seen, *, reject=None, smoke_status=200):
    """Canned Open-Meteo/NASA responses; `reject` = (host, status) for end==today requests."""

    def h(req):
        q = dict(req.url.params)
        seen.append(req)
        host = req.url.host
        if host == "power.larc.nasa.gov":
            if reject and reject[0] == "nasa" and q["end"] == "20261101":
                return httpx.Response(reject[1], json={"message": "end in future"})
            keys = ["2026103022", "2026103023", "2026110100"]
            vals = {p: dict(zip(keys, [1.0, 2.0, -999.0])) for p in q["parameters"].split(",")}
            return httpx.Response(200, json={"header": {"fill_value": -999.0, "time_standard": "UTC"},
                                             "geometry": {"coordinates": [75.9, 14.4, 597.0]},
                                             "properties": {"parameter": vals}})
        if reject and reject[0] == "era5" and host.startswith("archive") and q["end_date"] == "2026-11-01":
            return httpx.Response(reject[1], json={"reason": "x"})
        if host.startswith("previous-runs") and q["start_date"] == q["end_date"] and smoke_status != 200:
            return httpx.Response(smoke_status, json={"reason": "too many"})
        names = q["hourly"].split(",")
        t = ["2024-01-01T00:00", "2024-01-01T01:00", "2024-01-01T02:00"]
        body = {"latitude": 14.5, "longitude": 76.0, "elevation": 598.0,
                "hourly": {"time": t, **{n: [None, 1.0, 2.0] for n in names}}}
        return httpx.Response(200, json=body)

    return h


def test_collect_requests_and_cache(settings, mock_client, no_sleep, tmp_path):
    seen = []
    c = mock_client(_handler(seen))
    out = probe.collect(c, settings, raw_root=tmp_path, today=TODAY, sleep=no_sleep)
    n_models = len(settings.data.openmeteo.probe_models)
    assert len(seen) == 3 * n_models + 3
    root = tmp_path / "probe" / "20261101"
    assert (root / "pr_smoke_gfs_seamless.json").exists() and (root / "nasa_tail.json").exists()
    hf = [r for r in seen if r.url.host.startswith("historical")]
    assert dict(hf[0].url.params)["start_date"] == probe.HF_PROBE_START
    assert len(dict(hf[0].url.params)["hourly"].split(",")) == 14
    pr = [r for r in seen if r.url.host.startswith("previous") and dict(r.url.params)["start_date"] != dict(r.url.params)["end_date"]]
    assert len(pr) == n_models and len(dict(pr[0].url.params)["hourly"].split(",")) == 42
    assert dict(pr[0].url.params)["start_date"] == probe.PR_PROBE_START
    arch = [r for r in seen if r.url.host.startswith("archive")]
    assert dict(arch[0].url.params)["models"] == "era5" and dict(arch[0].url.params)["start_date"] == "1940-01-01"
    assert out["models"]["gfs_seamless"]["hf"]["shortwave_radiation"] == "2024-01-01T01:00"
    assert out["models"]["gfs_seamless"]["grid"]["elevation"] == 598.0
    assert out["nasa_tail"]["T2M"] == "2026103023"
    assert out["era5"]["first_valid_cached"] == {}
    n = len(seen)
    probe.collect(c, settings, raw_root=tmp_path, today=TODAY, sleep=no_sleep)
    assert len(seen) == n


def test_split_leads_when_smoke_rejected(settings, mock_client, no_sleep, tmp_path):
    seen = []
    out = probe.collect(mock_client(_handler(seen, smoke_status=400)), settings, raw_root=tmp_path,
                        today=TODAY, sleep=no_sleep)
    root = tmp_path / "probe" / "20261101"
    for n in (1, 2, 3):
        assert (root / f"pr_gfs_seamless_day{n}.json").exists()
    assert len(out["models"]["gfs_seamless"]["pr"]) == 42


@pytest.mark.parametrize("which,status", [("era5", 400), ("nasa", 422)])
def test_tail_retries_once_with_yesterday(settings, mock_client, no_sleep, tmp_path, which, status):
    seen = []
    probe.collect(mock_client(_handler(seen, reject=(which, status))), settings, raw_root=tmp_path,
                  today=TODAY, sleep=no_sleep)
    if which == "nasa":
        t = [r for r in seen if r.url.host == "power.larc.nasa.gov"]
        assert [dict(r.url.params)["end"] for r in t] == ["20261101", "20261031"]
    else:
        t = [r for r in seen if r.url.host.startswith("archive") and dict(r.url.params)["start_date"] != "1940-01-01"]
        assert [dict(r.url.params)["end_date"] for r in t] == ["2026-11-01", "2026-10-31"]


def test_cached_era5_first_valid(settings, mock_client, no_sleep, tmp_path):
    d = tmp_path / "openmeteo" / "archive" / "era5"
    d.mkdir(parents=True)
    names = list(settings.data.openmeteo.hourly)
    (d / "2001.json").write_text(json.dumps({"hourly": {"time": ["2001-01-01T00:00"], **{n: [1.0] for n in names}}}))
    out = probe.collect(mock_client(_handler([])), settings, raw_root=tmp_path, today=TODAY, sleep=no_sleep)
    assert out["era5"]["first_valid_cached"]["wind_speed_80m"] == "2001-01-01T00:00"
