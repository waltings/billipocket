#!/usr/bin/env python3
"""
Application entry point for BilliPocket Flask application.
"""
import os
import sys
from app import create_app

# Create application instance
app = create_app()

if __name__ == '__main__':
    # Get port from command line argument or use default
    port = 5010
    if len(sys.argv) > 2 and sys.argv[1] == '--port':
        try:
            port = int(sys.argv[2])
        except ValueError:
            print(f"Invalid port number: {sys.argv[2]}")
            sys.exit(1)
    
    # Run the application
    app.run(debug=True, port=port)