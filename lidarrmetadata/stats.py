"""
Utilities for sending stats
"""

from telegraf.client import TelegrafClient


class TelegrafStatsClient(object):
    def __init__(self, host='localhost', port=8092):
        self._client = TelegrafClient(host=host, port=port)

    def metric(self, key, value):
        self._client.metric(key, value)
