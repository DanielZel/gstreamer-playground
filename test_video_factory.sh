#!/bin/bash
gst-launch-1.0 -e videotestsrc num-buffers=150 ! video/x-raw,width=640,height=480,framerate=10/1 ! timeoverlay halignment=left valignment=top ! videoconvert ! x264enc ! mp4mux ! filesink location=test.mp4


