import os, os.path, cherrypy
from api import app
from models import *

if __name__ == '__main__':
	cherrypy.tree.graft(app, '/')
	cherrypy.config.update({
		'log.screen': True,
		'server.socket_port': 8888
	})

	database.connect()
	database.create_tables([Artist, Album, Track, Image], safe=True)
	database.close()

	cherrypy.engine.start()
	cherrypy.engine.block()