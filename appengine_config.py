"""
`appengine_config.py` is automatically loaded when Google App Engine
starts a new instance of your application. This runs before any
WSGI applications specified in app.yaml are loaded.
"""

# linkenv script to work with py27 virtualenv on dev appserver
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'gaenv')) 

from google.appengine.ext import vendor
from google.appengine.ext.appstats import recording

# add `lib` subdirectory to `sys.path`, so our `main` module can load
# third-party libraries.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))

# Third-party libraries are stored in "lib", vendoring will make
# sure that they are importable by the application.
vendor.add('lib')

# Workaround the dev-environment SSL
#   http://stackoverflow.com/q/16192916/893652
if os.environ.get('SERVER_SOFTWARE', '').startswith('Development'):
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'stdlib'))

    from google.appengine.tools.devappserver2.python import sandbox
    sandbox._WHITE_LIST_C_MODULES += ['_ssl', '_socket']

    import patched_socket
    sys.modules['socket'] = patched_socket
    socket = patched_socket
