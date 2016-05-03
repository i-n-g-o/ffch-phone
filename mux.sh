#!/bin/bash

echo $1
echo $2
echo "output to: $3"
gst-launch-1.0 filesrc location=$1 ! video/x-h264,width=1920,height=1080,framerate=25/1 ! h264parse ! queue ! mux. filesrc location=$2 ! decodebin ! audioconvert ! queue ! mux. avimux name=mux ! filesink location=$3
