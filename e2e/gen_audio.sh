#!/usr/bin/env bash
# Regenerates the 12 synthetic test tracks (loud section at 40-70s) used by the local test harness.
mkdir -p "$(dirname "$0")/audio" && cd "$(dirname "$0")/audio"
for i in $(seq 1 12); do f=$((200 + i*37)); ffmpeg -v error -y -f lavfi -i "sine=frequency=$f:duration=100:sample_rate=44100" -af "volume='if(between(t,40,70),0.9,0.08)':eval=frame" -b:a 64k t$i.mp3; done
