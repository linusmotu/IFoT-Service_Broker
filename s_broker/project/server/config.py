# project/server/config.py

import os
basedir = os.path.abspath(os.path.dirname(__file__))


class BaseConfig(object):
    """Base configuration."""
    WTF_CSRF_ENABLED = True
    REDIS_URL = 'redis://163.221.68.242:6379/0' #Pi4
    #REDIS_URL = 'redis://163.221.68.206:6379/0' #NUC
    MASTER1 = 'http://163.221.68.242:5001/'
    #MASTER1 = 'http://163.221.68.206:5001/'
    QUEUES = ['default']
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = 'client/static/uploads'
    TOTAL_CHUNKS = 200
    NUMBER_OF_NODES = 3

class DevelopmentConfig(BaseConfig):
    """Development configuration."""
    WTF_CSRF_ENABLED = False
    CORS_HEADERS = 'Content-Type'


class TestingConfig(BaseConfig):
    """Testing configuration."""
    TESTING = True
    WTF_CSRF_ENABLED = False
    PRESERVE_CONTEXT_ON_EXCEPTION = False
