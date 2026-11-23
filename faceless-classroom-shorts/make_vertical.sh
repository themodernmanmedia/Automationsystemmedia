#!/usr/bin/env bash
# Reframe a 16:9 clip into a 1080x1920 Short: blurred background, title caption, watermark.
# Usage: ./make_vertical.sh input.mp4 output.mp4 "PIP CHILL BRO" [crop_x]
set -euo pipefail
IN="$1"; OUT="$2"; TITLE="$3"; CROPX="${4:-200}"
FONT=$(fc-match -f '%{file}' 'DejaVu Sans:bold')
ffmpeg -loglevel error -y -i "$IN" -filter_complex \
"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=30:2,eq=brightness=-0.15[bg];\
[0:v]crop=880:720:${CROPX}:0,scale=1080:-2[fg];\
[bg][fg]overlay=(W-w)/2:(H-h)/2,\
drawtext=fontfile=${FONT}:text='${TITLE}':fontsize=96:fontcolor=white:borderw=8:bordercolor=black:x=(w-text_w)/2:y=230,\
drawtext=fontfile=${FONT}:text='@ROOM13':fontsize=44:fontcolor=white@0.85:borderw=4:bordercolor=black:x=(w-text_w)/2:y=h-330[v]" \
-map "[v]" -map 0:a? -c:v libx264 -crf 18 -preset medium -c:a aac -b:a 192k -movflags +faststart "$OUT"
echo "Wrote $OUT"
