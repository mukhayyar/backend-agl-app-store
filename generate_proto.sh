#!/usr/bin/env bash
# Regenerate gRPC-Web TypeScript stubs for the frontend.
#
# Requirements:
#   - protoc (https://github.com/protocolbuffers/protobuf/releases)
#   - protoc-gen-grpc-web (https://github.com/grpc/grpc-web/releases)
#   - protoc-gen-js  (npm install -g protoc-gen-js)
#
# Usage:
#   ./generate_proto.sh
#   ./generate_proto.sh --protoc /path/to/protoc
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROTO_DIR="$SCRIPT_DIR/protos"
OUT_DIR="$SCRIPT_DIR/../frontend/lib/grpc/generated"

PROTOC="${PROTOC:-protoc}"
PROTOC_GEN_GRPC_WEB="${PROTOC_GEN_GRPC_WEB:-protoc-gen-grpc-web}"
PROTOC_GEN_JS="${PROTOC_GEN_JS:-protoc-gen-js}"

mkdir -p "$OUT_DIR"

echo "Generating gRPC-Web TypeScript stubs..."
"$PROTOC" \
  -I="$PROTO_DIR" \
  --js_out=import_style=commonjs:"$OUT_DIR" \
  --grpc-web_out=import_style=typescript,mode=grpcwebtext:"$OUT_DIR" \
  --plugin=protoc-gen-grpc-web="$PROTOC_GEN_GRPC_WEB" \
  --plugin=protoc-gen-js="$PROTOC_GEN_JS" \
  "$PROTO_DIR/pens-agl-store.proto"

# Rename generated client file to remove the hyphen
if [ -f "$OUT_DIR/Pens-agl-storeServiceClientPb.ts" ]; then
  mv "$OUT_DIR/Pens-agl-storeServiceClientPb.ts" "$OUT_DIR/FlathubServiceClientPb.ts"
fi

echo "Done. Files written to: $OUT_DIR"
ls "$OUT_DIR"
