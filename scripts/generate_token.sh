#!/bin/bash
#
# flat-manager Token Generator Script
# Generates JWT tokens compatible with flat-manager API
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Load environment variables
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Default values
if [ -z "$FLAT_MANAGER_SECRET" ]; then
    echo -e "${RED}Error: FLAT_MANAGER_SECRET is not set. Set it in .env or pass --secret${NC}"
    exit 1
fi
SECRET="$FLAT_MANAGER_SECRET"
REPO="${FLAT_MANAGER_REPO:-stable}"
BRANCH="${FLAT_MANAGER_BRANCH:-stable}"
GENTOKEN_PATH="${FLAT_MANAGER_GENTOKEN_PATH:-gentoken}"
DURATION_DAYS=${DURATION_DAYS:-365}
TOKEN_NAME=""
SCOPES=""

# Usage information
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -n, --name NAME         Token name (required)"
    echo "  -s, --scope SCOPE       Token scope (can be repeated)"
    echo "                          Available: build, upload, publish, download,"
    echo "                                     jobs, generate, republish, reviewcheck,"
    echo "                                     tokenmanagement"
    echo "  -r, --repo REPO         Repository name (default: stable)"
    echo "  -b, --branch BRANCH     Branch name (default: stable)"
    echo "  -d, --duration DAYS     Token validity in days (default: 365)"
    echo "  --secret SECRET         Base64-encoded secret (default: from .env)"
    echo "  --use-binary            Use gentoken binary instead of Python"
    echo "  -h, --help              Show this help message"
    echo ""
    echo "Role Shortcuts:"
    echo "  --admin                 Admin scopes (all permissions)"
    echo "  --reviewer              Reviewer scopes (reviewcheck, download, build)"
    echo "  --publisher             Publisher scopes (build, upload, publish, download)"
    echo "  --user                  User scopes (download only)"
    echo ""
    echo "Examples:"
    echo "  $0 --name mytoken --publisher"
    echo "  $0 --name admin-token --admin"
    echo "  $0 --name uploader --scope upload --scope build"
    exit 1
}

# Parse arguments
USE_BINARY=false
while [[ $# -gt 0 ]]; do
    case $1 in
        -n|--name)
            TOKEN_NAME="$2"
            shift 2
            ;;
        -s|--scope)
            SCOPES="$SCOPES $2"
            shift 2
            ;;
        -r|--repo)
            REPO="$2"
            shift 2
            ;;
        -b|--branch)
            BRANCH="$2"
            shift 2
            ;;
        -d|--duration)
            DURATION_DAYS="$2"
            shift 2
            ;;
        --secret)
            SECRET="$2"
            shift 2
            ;;
        --use-binary)
            USE_BINARY=true
            shift
            ;;
        --admin)
            SCOPES="jobs build upload publish generate download republish reviewcheck tokenmanagement"
            shift
            ;;
        --reviewer)
            SCOPES="reviewcheck download build"
            shift
            ;;
        --publisher)
            SCOPES="build upload publish download"
            shift
            ;;
        --user)
            SCOPES="download"
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            usage
            ;;
    esac
done

# Validate required arguments
if [ -z "$TOKEN_NAME" ]; then
    echo -e "${RED}Error: Token name is required${NC}"
    usage
fi

if [ -z "$SCOPES" ]; then
    echo -e "${YELLOW}Warning: No scopes specified, using 'download' as default${NC}"
    SCOPES="download"
fi

# Generate token using Python
generate_with_python() {
    python3 << EOF
import json
import base64
from datetime import datetime, timedelta
import jwt

secret = base64.b64decode("${SECRET}")
scopes = "${SCOPES}".strip().split()
exp = datetime.utcnow() + timedelta(days=${DURATION_DAYS})

claims = {
    "sub": "build",
    "scope": scopes,
    "name": "${TOKEN_NAME}",
    "prefixes": [""],
    "repos": ["${REPO}"],
    "branches": ["${BRANCH}"],
    "exp": int(exp.timestamp()),
    "token_type": "app"
}

token = jwt.encode(claims, secret, algorithm="HS256")
print(token)
EOF
}

# Generate token using gentoken binary
generate_with_binary() {
    CMD="$GENTOKEN_PATH --base64 --secret $SECRET --name $TOKEN_NAME"
    
    for scope in $SCOPES; do
        CMD="$CMD --scope $scope"
    done
    
    CMD="$CMD --repo $REPO --branch $BRANCH --duration $((DURATION_DAYS * 86400))"
    
    eval $CMD
}

# Generate the token
echo -e "${GREEN}Generating token...${NC}"
echo "  Name: $TOKEN_NAME"
echo "  Scopes: $SCOPES"
echo "  Repo: $REPO"
echo "  Branch: $BRANCH"
echo "  Duration: $DURATION_DAYS days"
echo ""

if [ "$USE_BINARY" = true ]; then
    if command -v "$GENTOKEN_PATH" &> /dev/null; then
        TOKEN=$(generate_with_binary)
    else
        echo -e "${YELLOW}gentoken binary not found, falling back to Python${NC}"
        TOKEN=$(generate_with_python)
    fi
else
    TOKEN=$(generate_with_python)
fi

echo -e "${GREEN}Generated Token:${NC}"
echo ""
echo "$TOKEN"
echo ""
echo -e "${GREEN}Use this token in Authorization header:${NC}"
echo "  Authorization: Bearer $TOKEN"
