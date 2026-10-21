#!/bin/bash
set -euo pipefail

if [ "$#" -ne 3 ]; then
    echo "Usage: $0 BOOK_URL BUCKET EXPIRES_SECONDS" >&2
    echo "Example: $0 https://www.gutenberg.org/cache/epub/41537/pg41537.txt secret-pfm8rn 604800" >&2
    exit 1
fi

URL="$1"
BUCKET="$2"
EXPIRES="$3"
FILE="$(basename "$URL")" 


mkdir -p books
echo "Downloading $URL ..."
curl -fsSL -o "books/$FILE" "$URL"

if aws s3 ls "s3://$BUCKET" > /dev/null 2>&1; then
    echo "Bucket $BUCKET already exists"
else
    echo "Creating bucket $BUCKET"
    aws s3 mb "s3://$BUCKET"
fi


aws s3 cp "books/$FILE" "s3://$BUCKET/$FILE" \
    --content-type "text/plain; charset=utf-8"
echo "Presigned URL (expires in $EXPIRES seconds):"
aws s3 presign "s3://$BUCKET/$FILE" --expires-in "$EXPIRES"

