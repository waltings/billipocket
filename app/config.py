import os


class Config:
    """Base configuration class."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///billipocket.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True
    

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    DEVELOPMENT = True


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    DEVELOPMENT = False


# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}