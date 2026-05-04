#!/bin/sh
# Decrypt .enc files using OpenSSL
# Usage: ./decrypt_secrets.sh [file1.enc] [file2.enc] ...
# Example: ./decrypt_secrets.sh .env.enc admin_password.enc postgres_password.enc

set -e

if [ $# -eq 0 ]; then
  echo "Usage: $0 [file1.enc] [file2.enc] ..."
  exit 1
fi

for file in "$@"; do
  if [ ! -f "$file" ]; then
    echo "File not found: $file"
    continue
  fi
  out_file="${file%.enc}"
  openssl enc -d -aes-256-cbc -in "$file" -out "$out_file"
  echo "Decrypted $file -> $out_file"
done

echo "\nYou will be prompted for the password used during encryption."
