"""
Unified Server Entry Point.
Runs both HTTP (FastAPI) and gRPC servers concurrently.
"""
import asyncio
import json
import logging
import signal
import sys
import threading
from concurrent import futures
from typing import Optional

import uvicorn

from app.core.config import get_settings
from app.http.http_server import http_app
from app.grpc.grpc_server import get_grpc_server


class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter for production."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0] is not None:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data, default=str)


# Configure logging with structured JSON output
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JSONFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler])
logger = logging.getLogger(__name__)
settings = get_settings()


class DualProtocolServer:
    """
    Runs both HTTP and gRPC servers.
    - HTTP Server: FastAPI with uvicorn on port 8000
    - gRPC Server: grpcio on port 50051
    """

    def __init__(self):
        self.grpc_server = None
        self.grpc_thread = None
        self.uvicorn_server = None
        self._shutdown = False

    def start_grpc_server(self):
        """Start gRPC server in a separate thread."""
        try:
            self.grpc_server = get_grpc_server()
            self.grpc_server.start()
            self.grpc_server.wait_for_termination()
        except Exception as e:
            logger.error(f"gRPC server error: {e}")
            raise

    async def start_http_server(self):
        """Start HTTP server."""
        config = uvicorn.Config(
            http_app,
            host=settings.http_host,
            port=settings.http_port,
            log_level="info",
        )
        self.uvicorn_server = uvicorn.Server(config)
        await self.uvicorn_server.serve()

    def shutdown(self, sig=None, frame=None):
        """Shutdown both servers gracefully."""
        if self._shutdown:
            return

        self._shutdown = True
        logger.info("Shutting down servers...")

        # Stop gRPC server
        if self.grpc_server:
            self.grpc_server.stop(grace=5)

        # Stop uvicorn
        if self.uvicorn_server:
            self.uvicorn_server.should_exit = True

    async def run(self):
        """Run both servers."""
        settings.validate_for_production()

        # Setup signal handlers
        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)

        # Start gRPC in separate thread
        self.grpc_thread = threading.Thread(
            target=self.start_grpc_server,
            daemon=True
        )
        self.grpc_thread.start()

        logger.info("=" * 60)
        logger.info("PENS AGL App Store Server")
        logger.info("=" * 60)
        logger.info(f"HTTP Server: http://{settings.http_host}:{settings.http_port}")
        logger.info(f"  - API Docs: http://{settings.http_host}:{settings.http_port}/http/docs")
        logger.info(f"  - Health: http://{settings.http_host}:{settings.http_port}/http/health")
        logger.info(f"gRPC Server: {settings.grpc_host}:{settings.grpc_port}")
        logger.info("=" * 60)

        # Start HTTP server (blocks until shutdown)
        await self.start_http_server()

        # Wait for gRPC thread to finish
        if self.grpc_thread and self.grpc_thread.is_alive():
            self.grpc_thread.join(timeout=5)


def main():
    """Main entry point."""
    server = DualProtocolServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
