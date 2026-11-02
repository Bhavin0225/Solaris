import httpx
import pytest

from swf.core.geometry import to_openmeteo_azimuth
from swf.core.settings import Settings


@pytest.mark.parametrize("pv,om", [(180, 0), (90, -90), (270, 90), (0, -180)])
def test_azimuth(pv, om):
    assert to_openmeteo_azimuth(pv) == om


def test_fixtures(settings, no_sleep, mock_client, fixtures_dir):
    assert isinstance(settings, Settings)
    no_sleep(2.0)
    assert no_sleep.calls == [2.0]
    seen = []

    def handler(req):
        seen.append(str(req.url))
        return httpx.Response(200)

    assert mock_client(handler).get("https://x.test/").status_code == 200
    assert seen == ["https://x.test/"]
    assert fixtures_dir.name == "fixtures"
