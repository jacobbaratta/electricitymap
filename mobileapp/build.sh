#!/bin/bash
set -eu -o pipefail

# Extract
CONTAINER_ID=$(docker create electricitymap_web)

rm -rf www/electricitymap || true
docker cp $CONTAINER_ID:/home/web/public/ www/electricitymap

rm -rf locales || true
docker cp $CONTAINER_ID:/home/web/locales/ .
docker cp $CONTAINER_ID:/home/web/app .

docker rm $CONTAINER_ID

# Run node in order to build index.html
echo 'Generating index pages..'
node generate-index.js
