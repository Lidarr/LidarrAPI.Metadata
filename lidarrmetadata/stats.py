"""
Utilities for sending stats
"""

from telegraf.client import TelegrafClient


from lidarrmetadata.config import get_config

CONFIG = get_config()

class TelegrafStatsClient(object):
    def __init__(self, host='localhost', port=8092):
        self._client = TelegrafClient(host=host, port=port)

    def metric(self, key, value, tags=None):
        tags = tags or {}
        tags['root'] = CONFIG.APPLICATION_ROOT
        self._client.metric(key, value, tags=tags)
