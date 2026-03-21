#!/bin/bash
# original-movies/ の MP4 を 1.5倍速・無音に変換して source-movies/ に保存

set -e

for f in original-movies/*.mp4; do
  name=$(basename "$f")
  echo "Converting: $name"
  ffmpeg -i "$f" \
    -vf "setpts=PTS/1.5" \
    -an \
    -c:v libx264 -crf 18 -preset fast \
    "source-movies/$name" -y
  echo "Done: source-movies/$name"
done
