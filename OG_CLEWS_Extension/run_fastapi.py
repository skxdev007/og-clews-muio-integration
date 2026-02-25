"""
Startup script for OG-CLEWS FastAPI service

Run this to start the FastAPI server for OG-Core integration.
The service will run on http://127.0.0.1:8000
"""

import uvicorn
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    print("=" * 70)
    print("Starting OG-CLEWS FastAPI Service")
    print("=" * 70)
    print()
    print("Service will be available at: http://127.0.0.1:8000")
    print("API documentation: http://127.0.0.1:8000/docs")
    print("Alternative docs: http://127.0.0.1:8000/redoc")
    print()
    print("Key endpoints:")
    print("  - GET  /og/status          - Check OG-Core status")
    print("  - GET  /og/real_data       - Get real OG-Core data")
    print("  - POST /og/run             - Execute OG-Core")
    print("  - POST /og/transform       - Transform data (bidirectional)")
    print("  - POST /og/clews_feedback  - Apply CLEWS → OG-Core feedback")
    print("  - POST /og/coupled_run     - Run coupled execution")
    print()
    print("Press Ctrl+C to stop the server")
    print("=" * 70)
    print()
    
    uvicorn.run(
        "backend.og_fastapi:app",
        host="127.0.0.1",
        port=8000,
        reload=True,  # Auto-reload on code changes
        log_level="info"
    )
