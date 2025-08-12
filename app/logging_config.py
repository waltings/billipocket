import logging
import logging.handlers
import os
from datetime import datetime


def setup_logging(app):
    """Configure logging for the Flask application."""
    
    # Set up logging level based on debug mode
    if app.config.get('DEBUG'):
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    
    # Create logs directory if it doesn't exist
    log_dir = os.path.join(app.instance_path, '..', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # Configure main application logger
    app_logger = logging.getLogger('billipocket')
    app_logger.setLevel(log_level)
    
    # Remove any existing handlers
    app_logger.handlers.clear()
    
    # Console handler for development
    if app.config.get('DEBUG'):
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        console_formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        app_logger.addHandler(console_handler)
    
    # File handler for all environments
    file_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, 'billipocket.log'),
        maxBytes=10485760,  # 10MB
        backupCount=10
    )
    file_handler.setLevel(log_level)
    file_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(name)s.%(module)s.%(funcName)s: %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    app_logger.addHandler(file_handler)
    
    # Error file handler for warnings and errors
    error_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, 'billipocket_errors.log'),
        maxBytes=10485760,  # 10MB
        backupCount=10
    )
    error_handler.setLevel(logging.WARNING)
    error_handler.setFormatter(file_formatter)
    app_logger.addHandler(error_handler)
    
    # Set Flask's logger to use our handlers
    app.logger.handlers = app_logger.handlers
    app.logger.setLevel(log_level)
    
    # Log startup message
    app_logger.info(f"BilliPocket application started - Debug: {app.config.get('DEBUG')}")
    
    return app_logger


def get_logger(name='billipocket'):
    """Get a logger instance."""
    return logging.getLogger(name)