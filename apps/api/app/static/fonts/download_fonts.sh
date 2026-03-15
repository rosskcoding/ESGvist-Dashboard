#!/bin/bash
# Download Noto fonts for PDF print
# Run from: apps/api/app/static/fonts/

set -e

echo "Downloading Noto fonts for PDF print..."

# Base URL for Google Fonts static files
# These are the actual font files served by Google Fonts CDN
GOOGLE_FONTS_BASE="https://fonts.gstatic.com/s"

# Noto Sans - Latin + Cyrillic
curl -L -o NotoSans-Regular.woff2 \
  "https://fonts.gstatic.com/s/notosans/v36/o-0mIpQlx3QUlC5A4PNB6Ryti20_6n1iPHjcz6L1SoM-jCpoiyD9A-9a6Vc.woff2"

curl -L -o NotoSans-Bold.woff2 \
  "https://fonts.gstatic.com/s/notosans/v36/o-0mIpQlx3QUlC5A4PNB6Ryti20_6n1iPHjcz6L1SoM-jCpoiyAjBe9a6Vc.woff2"

curl -L -o NotoSans-Italic.woff2 \
  "https://fonts.gstatic.com/s/notosans/v36/o-0kIpQlx3QUlC5A4PNr4C5OaxRsfNNlKbCePevHtVtX57DGjDU1.woff2"

# Noto Serif - Latin + Cyrillic
curl -L -o NotoSerif-Regular.woff2 \
  "https://fonts.gstatic.com/s/notoserif/v23/ga6iaw1J5X9T9RW6j9bNVls-hfgvz8JcMofYTYk.woff2"

curl -L -o NotoSerif-Bold.woff2 \
  "https://fonts.gstatic.com/s/notoserif/v23/ga6law1J5X9T9RW6j9bNdOwzTRCUcM1IKoY.woff2"

# Noto Mono
curl -L -o NotoMono-Regular.woff2 \
  "https://fonts.gstatic.com/s/notosansmono/v30/BngrUXNETWXI6LwhGYvaxZikqZqK6fBq6kPvUce2oAZcdthSBUsYck4-_FNJ09vd1w.woff2"

echo ""
echo "✓ Fonts downloaded successfully!"
echo ""
echo "Files:"
ls -la *.woff2

echo ""
echo "Note: These fonts are licensed under SIL Open Font License (OFL)"


