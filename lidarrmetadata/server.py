import multiprocessing
import os

import gunicorn.app.base

from gunicorn.six import iteritems

from api import app
from config import get_config


class StandaloneApplication(gunicorn.app.base.BaseApplication):

    def __init__(self, app, options=None):
        self.options = options or {}
        self.application = app
        super(StandaloneApplication, self).__init__()

    def load_config(self):
        config = dict([(key, value) for key, value in iteritems(self.options)
                       if key in self.cfg.settings and value is not None])
        for key, value in iteritems(config):
            self.cfg.set(key.lower(), value)

    def load(self):
        return self.application


def main():
    """
    Entry point for script
    """
    config = get_config()

    mount_point = config.APPLICATION_ROOT or '/'
    if not mount_point.startswith('/'):
        mount_point = '/' + mount_point

    os.environ['SCRIPT_NAME'] = mount_point

    options = {
        'bind': '0.0.0.0:{port}'.format(port=config.HTTP_PORT),
        'workers': (multiprocessing.cpu_count() * 2) + 1
    }

    StandaloneApplication(app, options).run()


if __name__ == '__main__':
    main()
