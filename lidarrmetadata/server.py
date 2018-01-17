import cherrypy

from api import app


def main():
    """
    Entry point for script
    """

    cherrypy.tree.graft(app, '/')
    cherrypy.config.update({
        'log.screen': True,
        'server.socket_host': '0.0.0.0',
        'server.socket_port': 5000
    })

    cherrypy.engine.start()
    cherrypy.engine.block()


if __name__ == '__main__':
    main()
