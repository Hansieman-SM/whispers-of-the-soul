#!/bin/bash
# tools/sheet.sh video.mp4 sheet.jpg  -> 10 frames evenly spread (incl. first and last), 5x2 grid (works for 9:16 and 16:9)
V=$1; O=$2; D=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$V")
WH=$(ffprobe -v error -select_streams v -show_entries stream=width,height -of csv=p=0 "$V"); W=${WH%,*}; H=${WH#*,}
if [ "$W" -gt "$H" ]; then S=480:270; else S=270:480; fi
TMP=$(mktemp -d); i=0
for f in 0.004 0.1 0.2 0.3 0.4 0.5 0.6 0.75 0.93 0.995; do
  t=$(python3 -c "print(max(0,min($D-0.05,$D*$f)))"); ffmpeg -v error -y -ss $t -i "$V" -frames:v 1 -vf scale=$S $TMP/$(printf %02d $i).png; i=$((i+1)); done
ffmpeg -v error -y -i $TMP/%02d.png -vf tile=5x2 "$O"; rm -r $TMP
