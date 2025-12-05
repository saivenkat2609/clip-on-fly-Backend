#!/bin/bash

  echo "============================================"
  echo "  Building AWS Lambda Layer with EJS"
  echo "============================================"

  # Clean old build
  rm -rf opt lambda_layer.zip

  # Create structure
  mkdir -p opt/bin
  mkdir -p opt/nodejs/node_modules

  # Download yt-dlp
  echo "Downloading yt-dlp..."
  curl -L -o opt/bin/yt-dlp https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp
  chmod +x opt/bin/yt-dlp

  # Download Node.js
  echo "Downloading Node.js..."
  NODE_VERSION=v20.18.0
  curl -L -o node.tar.xz https://nodejs.org/dist/$NODE_VERSION/node-$NODE_VERSION-linux-x64.tar.xz
  tar -xf node.tar.xz
  cp node-$NODE_VERSION-linux-x64/bin/node opt/bin/
  chmod +x opt/bin/node

  # Install yt-dlp-ejs
  echo "Installing yt-dlp-ejs..."
  cd opt/nodejs
  npm install yt-dlp-ejs
  cd ../..

  # Cleanup
  rm -rf node-$NODE_VERSION-linux-x64 node.tar.xz

  # Create zip
  echo "Creating lambda_layer.zip..."
  zip -r lambda_layer.zip opt

  echo "============================================"
  echo "  DONE! Upload lambda_layer.zip to AWS"
  echo "============================================"