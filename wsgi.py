#!/usr/bin/env python3
"""
WSGI entry point for BilliPocket Flask application.
Use this file for production deployment with Apache mod_wsgi or Gunicorn.
"""

import os
from app import create_app

# Create application instance for production
application = create_app('production')

if __name__ == "__main__":
    application.run()