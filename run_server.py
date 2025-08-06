#!/usr/bin/env python3
"""
CoachEduAI Server Startup Script
This script provides a robust way to start the CoachEduAI web server
"""

import os
import sys
import subprocess
import time

def check_dependencies():
    """Check if required dependencies are installed"""
    required_packages = ['flask', 'flask_socketio', 'eventlet']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"Missing required packages: {', '.join(missing_packages)}")
        print("Please install them using: pip install " + " ".join(missing_packages))
        return False
    
    return True

def start_server():
    """Start the CoachEduAI server"""
    print("🚀 Starting CoachEduAI Server...")
    
    # Set environment variables
    os.environ.setdefault('PORT', '5000')
    os.environ.setdefault('HOST', '0.0.0.0')
    os.environ.setdefault('DEBUG', 'True')
    
    port = os.environ.get('PORT', '5000')
    host = os.environ.get('HOST', '0.0.0.0')
    debug = os.environ.get('DEBUG', 'True').lower() == 'true'
    
    print(f"📍 Server will run on: http://{host}:{port}")
    print(f"🔧 Debug mode: {debug}")
    print("⏳ Starting server...")
    
    try:
        # Import and run the main application
        from main import app, socketio, init_db, start_background_tasks
        
        # Initialize database
        print("🗄️  Initializing database...")
        init_db()
        
        # Start background tasks
        print("🔄 Starting background tasks...")
        start_background_tasks()
        
        # Start the server
        print("✅ Server is ready!")
        print(f"🌐 Open your browser and go to: http://localhost:{port}")
        print("⏹️  Press Ctrl+C to stop the server")
        
        socketio.run(app, host=host, port=int(port), debug=debug, allow_unsafe_werkzeug=True)
        
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        print("🔧 Trying fallback mode...")
        try:
            from main import app
            app.run(host=host, port=int(port), debug=debug)
        except Exception as e2:
            print(f"❌ Fallback also failed: {e2}")
            return False
    
    return True

if __name__ == '__main__':
    if not check_dependencies():
        sys.exit(1)
    
    success = start_server()
    if not success:
        sys.exit(1) 