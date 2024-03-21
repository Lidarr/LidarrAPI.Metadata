import asyncio

import pytest


# With package upgrades, this seems to be necessary to avoid errors of the loop
# being closed before tests are done
@pytest.fixture(scope="session")
def event_loop():
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    yield loop
    loop.close()
