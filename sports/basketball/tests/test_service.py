import asyncio
from sports.basketball.service import BasketballDataService

def test_service_interval_is_guarded():
    service = BasketballDataService(interval_seconds=1)
    assert service.interval_seconds == 30
    asyncio.run(service.close())
