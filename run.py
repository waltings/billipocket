#!/usr/bin/env python3
"""
Application entry point for BilliPocket Flask application.
"""
import os
from app import create_app

# Create application instance
app = create_app()

if __name__ == '__main__':
    # Run the application on port 5010
    app.run(debug=True, port=5010)