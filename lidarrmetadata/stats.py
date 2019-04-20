"""
Utilities for sending stats
"""

import telegraf.client


from lidarrmetadata.config import get_config

CONFIG = get_config()

class TelegrafStatsClient(object):
    def __init__(self, host='localhost', port=8092):
        self._client = telegraf.client.TelegrafClient(host=host, port=port)

    def metric(self, key, value, tags=None):
        tags = tags or {}
        tags['application_path'] = CONFIG.APPLICATION_ROOT
        self._client.metric(key, value, tags=tags)
