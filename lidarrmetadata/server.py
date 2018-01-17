import cherrypy

from api import app
from config import CONFIG



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
