import os, sys
from pathlib import Path
from unittest.mock import patch

root = Path(__file__).resolve().parent.parent / 'backend'
os.chdir(root)
sys.path.insert(0, str(root))
os.environ.update(DJANGO_SETTINGS_MODULE='config.settings', DATABASE_URL='', DEBUG='True',
                  DESKTOP_MODE='False', TAVILY_API_KEY='', DISCOVERY_ENABLED='False')
import django
django.setup()
from django.conf import settings
settings.DATABASES['default']['NAME'] = ':memory:'
settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
settings.BREVO_API_KEY = ''
from django.core.management import call_command
with patch('requests.sessions.Session.request', side_effect=AssertionError('HTTP réel interdit pendant C1')):
    call_command('test', *(sys.argv[1:] or ['prospection']), verbosity=1, interactive=False)
