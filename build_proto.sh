#!/bin/bash

# Create generated directory if it doesn't exist
mkdir -p generated

# Generate gRPC Python code from proto file
python -m grpc_tools.protoc \
    --proto_path=protos \
    --python_out=generated \
    --grpc_python_out=generated \
    protos/pens-agl-store.proto

# Fix the bare import in the generated gRPC file to use package-relative import
# (protoc generates `import pens_agl_store_pb2` but we need `from generated import ...`)
sed -i 's/^import pens_agl_store_pb2/from generated import pens_agl_store_pb2/' generated/pens_agl_store_pb2_grpc.py

echo "Proto files generated successfully"
