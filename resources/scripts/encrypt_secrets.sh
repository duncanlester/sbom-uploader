#!/bin/sh
# Encrypt .env and secrets files for safe git storage using OpenSSL
# Usage: ./encrypt_secrets.sh [file1] [file2] ...
# Example: ./encrypt_secrets.sh .env admin_password postgres_password

set -e

if [ $# -eq 0 ]; then
  echo "Usage: $0 [file1] [file2] ..."
  exit 1
fi

for file in "$@"; do
  if [ ! -f "$file" ]; then
    echo "File not found: $file"
    continue
  fi
  openssl enc -aes-256-cbc -salt -in "$file" -out "$file.enc"
  echo "Encrypted $file -> $file.enc"
done

echo "\nTo decrypt, use:"
echo "  openssl enc -d -aes-256-cbc -in <file>.enc -out <file>"
