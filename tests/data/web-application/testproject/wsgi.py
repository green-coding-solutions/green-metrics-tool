import os

from django.core.wsgi import get_wsgi_application  # pylint: disable=import-error

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "testproject.settings")

application = get_wsgi_application()
