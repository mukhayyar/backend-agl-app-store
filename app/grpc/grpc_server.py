"""
gRPC Server for App Store.
Wraps the existing gRPC service implementation.
"""
import logging
import signal
import sys
from concurrent import futures
from typing import Optional

import grpc

from app.core.config import get_settings

# Import existing gRPC service
sys.path.insert(0, str(__file__).replace('app/grpc/grpc_server.py', ''))
from service import PENSAGLStoreService
from generated import pens_agl_store_pb2_grpc

logger = logging.getLogger(__name__)
settings = get_settings()


class GRPCServer:
    """gRPC server wrapper with graceful shutdown."""
    
    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        max_workers: Optional[int] = None
    ):
        self.host = host or settings.grpc_host
        self.port = port or settings.grpc_port
        self.max_workers = max_workers or settings.max_workers
        self.server: Optional[grpc.Server] = None
        self._shutdown_event = None
    
    def create_server(self) -> grpc.Server:
        """Create and configure the gRPC server."""
        self.server = grpc.server(
            futures.ThreadPoolExecutor(max_workers=self.max_workers),
            options=[
                ('grpc.max_send_message_length', 50 * 1024 * 1024),
                ('grpc.max_receive_message_length', 50 * 1024 * 1024),
            ]
        )
        
        # Add the existing service
        pens_agl_store_pb2_grpc.add_FlathubServiceServicer_to_server(
            PENSAGLStoreService(),
            self.server
        )
        
        server_address = f'{self.host}:{self.port}'
        self.server.add_insecure_port(server_address)
        
        return self.server
    
    def start(self):
        """Start the gRPC server."""
        if self.server is None:
            self.create_server()
        
        self.server.start()
        server_address = f'{self.host}:{self.port}'
        logger.info(f"gRPC server started at {server_address}")
    
    def stop(self, grace: int = 5):
        """Stop the gRPC server gracefully."""
        if self.server:
            logger.info("Stopping gRPC server...")
            self.server.stop(grace)
    
    def wait_for_termination(self, timeout: Optional[float] = None):
        """Wait for server termination."""
        if self.server:
            self.server.wait_for_termination(timeout)
    
    def serve(self):
        """Start server and block until termination."""
        self.start()
        
        # Setup signal handlers
        def signal_handler(sig, frame):
            logger.info(f"Received signal {sig}, shutting down...")
            self.stop()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        self.wait_for_termination()


def create_grpc_server(
    host: Optional[str] = None,
    port: Optional[int] = None,
    max_workers: Optional[int] = None
) -> GRPCServer:
    """Factory function to create gRPC server."""
    return GRPCServer(host=host, port=port, max_workers=max_workers)


# Singleton instance
_grpc_server: Optional[GRPCServer] = None


def get_grpc_server() -> GRPCServer:
    """Get singleton gRPC server instance."""
    global _grpc_server
    if _grpc_server is None:
        _grpc_server = create_grpc_server()
    return _grpc_server


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    server = get_grpc_server()
    server.serve()
