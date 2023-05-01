from pathlib import Path
import os

from giverofepic.secrets import giveaway_api_key

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'wo3dcrhjjo_8z2#2)5%u64$*i=eu=p^bes4dsmmc45ljkgj6fdgdg-^*ot^(i'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "giverofepic.settings")

ALLOWED_HOSTS = ['*', 'localhost']
USED_HOST = f"{ALLOWED_HOSTS[1]}:8000"

# Application definition
INSTALLED_APPS = [
    "admin_interface",
    "colorfield",
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'ninja_apikey',
    'django_rq',
    'giveaway',
    'website',
    'wallet',
    ]

RQ_QUEUES = {
    'default': {
        'HOST': 'redis-19490.c10.us-east-1-3.ec2.cloud.redislabs.com',
        'PORT': 19490,
        'USERNAME': 'default',
        'PASSWORD': 'EXCUFGFOeyBRjEtGSx6Z5OwyK5jTMBLM',
        'DB': 0,
        'DEFAULT_TIMEOUT': 360,
        },
    }

X_FRAME_OPTIONS = "SAMEORIGIN"
SILENCED_SYSTEM_CHECKS = ["security.W019"]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    ]

ROOT_URLCONF = 'giverofepic.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                ],
            },
        },
    ]

WSGI_APPLICATION = 'giverofepic.wsgi.application'

# Database
# https://docs.djangoproject.com/en/4.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Password validation
# https://docs.djangoproject.com/en/4.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
        },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
        },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
        },
    ]

# Internationalization
# https://docs.djangoproject.com/en/4.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.1/howto/static-files/
STATIC_URL = 'static/'
STATIC_ROOT = '/dev_static/'
STATICFILES_DIRS = (os.path.join(BASE_DIR, 'static'),)

# Default primary key field type
# https://docs.djangoproject.com/en/4.1/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

SENTRY_DSN = "https://9238840ac47c4289a2035ba9d797566b@o4504589365411840.ingest.sentry.io/4504589366329344"


if os.getenv('DJANGO_DEVELOPMENT') == 'true':
    # DEBUG = False
    SENTRY_DSN = "https://6f6cefddc3d849dc99dafaa8c9c0c6be@o4504589365411840.ingest.sentry.io/4504589394706432"
    ALLOWED_HOSTS = ['localhost', 'giverofepic.com', 'www.giverofepic.com', '209.127.179.199']
    USED_HOST = f"{ALLOWED_HOSTS[1]}"
    GIVEAWAY_API_KEY = giveaway_api_key

    RQ_QUEUES = {
        'default': {
            'HOST': '127.0.0.1',
            'PORT': 6379,
            'DB': 0,
            'DEFAULT_TIMEOUT': 360,
            },
        }

