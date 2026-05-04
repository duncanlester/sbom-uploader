#!/bin/sh
# Encrypt or decrypt secrets using OpenSSL
# Usage:
#   ./secret_encryptor.sh encrypt file1 [file2 ...]
#   ./secret_encryptor.sh decrypt file1.enc [file2.enc ...]

set -e

if [ $# -lt 2 ]; then
  echo "Usage: $0 <encrypt|decrypt> <file1> [file2 ...]"
  exit 1
fi

MODE="$1"
shift

case "$MODE" in
  encrypt)
    for file in "$@"; do
      if [ ! -f "$file" ]; then
        echo "File not found: $file"
        continue
      fi
      openssl enc -aes-256-cbc -salt -in "$file" -out "$file.enc"
      echo "Encrypted $file -> $file.enc"
    done
    echo "\nTo decrypt, use: $0 decrypt <file>.enc"
    ;;
  decrypt)
    for file in "$@"; do
      if [ ! -f "$file" ]; then
        echo "File not found: $file"
        continue
      fi
      out_file="${file%.enc}"
      openssl enc -d -aes-256-cbc -in "$file" -out "$out_file"
      echo "Decrypted $file -> $out_file"
    done
    ;;
  *)
    echo "Unknown mode: $MODE (use encrypt or decrypt)"
    exit 1
    ;;
esac
