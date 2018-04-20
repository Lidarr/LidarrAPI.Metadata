import cherrypy

from api import app
from config import get_config


def main():
    """
    Entry point for script
    """
    config = get_config()

    mount_point = config.APPLICATION_ROOT or '/'
    if not mount_point.startswith('/'):
        mount_point = '/' + mount_point

    cherrypy.tree.graft(app, mount_point)
    cherrypy.config.update({
        'log.screen': True,
        'server.socket_port': config.HTTP_PORT,
        'server.socket_host': '0.0.0.0'})
    cherrypy.engine.start()
    cherrypy.engine.block()


if __name__ == '__main__':
    main()
