# ffch-phone
a video-phone for filming for change (http://www.filmingforchange.net) running on a raspberry-pi with a pi-camera.
video+audio recording is started when a GPIO-pin is pulled low (when the receiver is put off the phone) and stopped when this GPIO-pin is high again (phone-receiver put back on the phone)

when the raspberry-pi is idle, it converts the audio to mpeg4 audio (m4a) and muxes it with the recorded h264 video stream.

the recording folders for video and audio can be set sepearte from each other.
other parameters can be set in a config file.
