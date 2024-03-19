import multiprocessing
import os

import gunicorn.app.base

import lidarrmetadata
from lidarrmetadata.app import app
from lidarrmetadata.config import get_config

import logging
logging.basicConfig(level=logging.DEBUG)

class StandaloneApplication(gunicorn.app.base.BaseApplication):

    def __init__(self, app, options=None):
        self.options = options or {}
        self.application = app
        super(StandaloneApplication, self).__init__()

    def load_config(self):
        config = {key: value for key, value in self.options.items()
                  if key in self.cfg.settings and value is not None}
        for key, value in config.items():
            self.cfg.set(key.lower(), value)

    def load(self):
        return self.application


def main():
    """
    Entry point for script
    """
    config = get_config()

    options = {
        'bind': '0.0.0.0:{port}'.format(port=config.HTTP_PORT),
        'log_level': 'debug',
        'workers': 1,
        'worker_class': 'uvicorn.workers.UvicornWorker'
    }

    StandaloneApplication(app, options).run()


if __name__ == '__main__':
    main()
