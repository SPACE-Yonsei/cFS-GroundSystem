#!/usr/bin/bash

for i in {0..9}; do
  export DISPLAY=":$(expr $UID % 10 + $i)"
  PORT=$(expr 5900 + $UID % 10 + $i)

  if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null ; then
    continue
  fi

  echo "Starting VNC server, listening on 0.0.0.0:$PORT"

  Xvfb $DISPLAY -screen 0 1024x768x16 &

  # Wait for Xvfb to start
  sleep 1

  # Start fluxbox if not running
  fluxbox 2>/dev/null &

  x11vnc -display $DISPLAY -bg -forever -nopw -quiet -listen 0.0.0.0 -xkb 

  export QT_QPA_PLATFORM=xcb
  python3 GroundSystem.py

  break
done

