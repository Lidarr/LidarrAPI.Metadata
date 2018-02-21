import cherrypy

from api import app
<<<<<<< HEAD
from config import CONFIG
=======
>>>>>>> 864ffcad010b0a118eb3b676051c00507a1ea3dc


def main():
    """
    Entry point for script
    """
    cherrypy.tree.graft(app, '/')
    cherrypy.config.update({
        'log.screen': True,
        'server.socket_port': CONFIG.HTTP_PORT,
        'server.socket_host': '0.0.0.0'})
    cherrypy.engine.start()
    cherrypy.engine.block()


if __name__ == '__main__':
    main()
