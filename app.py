#!/usr/bin/env python3
"""
AGL App Store — gRPC Server Entry Point
Starts the gRPC backend on PENS_AGL_STORE_PORT (default 50051).
"""
import os
import logging
from concurrent import futures
import grpc
from generated import pens_agl_store_pb2_grpc
from service import PENSAGLStoreService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

def serve():
    host = os.getenv("PENS_AGL_STORE_HOST", "0.0.0.0")
    port = os.getenv("PENS_AGL_STORE_PORT", "50051")
    workers = int(os.getenv("MAX_WORKERS", "10"))

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=workers))
    pens_agl_store_pb2_grpc.add_FlathubServiceServicer_to_server(PENSAGLStoreService(), server)
    listen_addr = f"{host}:{port}"
    server.add_insecure_port(listen_addr)
    server.start()
    log.info(f"gRPC server listening on {listen_addr}")
    server.wait_for_termination()

if __name__ == "__main__":
    serve()
