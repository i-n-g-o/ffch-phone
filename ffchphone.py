#!/usr/bin/python

#-------------------------------------------------------------------------------
# ffchphone.py
#
# written by Ingo Randolf 2016
#
#
# This software is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# Version 3.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#-------------------------------------------------------------------------------

import sys
import subprocess
import signal
import os
from os import listdir
import thread
import time
from time import sleep
from picamera import PiCamera
from time import gmtime, strftime
import RPi.GPIO as GPIO #for GPIO
from muxer import Muxer
from muxer import checkFolder
import ConfigParser
import logging


#sudo AUDIODEV=hw:0 rec -c 2 -r 48000 -C 320.99 --buffer 262144 noise3.mp3 gain -h bass -20 gain -l 18

##################
# variables
##################
recording_duration = 140 #seconds
rec_folder = "/home/pi/ffchdisk/rec/"
rec_folder_a = "/home/pi/ffchdisk1/rec/"
out_folder = "/home/pi/ffchdisk/out/"
backup_folder = "/home/pi/ffchdisk/backup/"
playback_file = "/home/pi/phone-audio.wav"
log_file = "/home/pi/log"
video_rec_delay = 0
audio_rec_delay = 0

# auflegen_wav = "/home/pi/auflegen.wav"

# camera
camera_width = 1920
camera_heigth = 1080
camera_fps = 25
camera_hflip = True
camera_vflip = True

# init
isRecording = False
audioProcess = None
playbackProc = None
rec_filename = None
out_filename = None
record_started = 0

rec_lock = thread.allocate_lock()

phonePinNum = 6 #BCM pin numbering
buttonPinNum = 16 #BCM pin numbering


##################
# read from config
##################
configParser = ConfigParser.RawConfigParser()
configFilePath = r"ffchphone.conf"
configParser.read(configFilePath)


try:
    recording_duration = int(configParser.get('ffch-phone', 'rec_duration'))
except ConfigParser.NoOptionError,e:
    pass

try:
    rec_folder = configParser.get('ffch-phone', 'video')
except ConfigParser.NoOptionError,e:
    pass

try:
    rec_folder_a = configParser.get('ffch-phone', 'audio')
except ConfigParser.NoOptionError,e:
    pass

try:
    out_folder = configParser.get('ffch-phone', 'out')
except ConfigParser.NoOptionError,e:
    pass

try:
    backup_folder = configParser.get('ffch-phone', 'backup')
except ConfigParser.NoOptionError,e:
    pass

try:
    playback_file = configParser.get('ffch-phone', 'playback')
except ConfigParser.NoOptionError,e:
    pass

try:
    log_file = configParser.get('ffch-phone', 'log')
except ConfigParser.NoOptionError,e:
    pass

try:
    video_rec_delay = int(configParser.get('ffch-phone', 'video_rec_delay'))
except ConfigParser.NoOptionError,e:
    pass

try:
    audio_rec_delay = int(configParser.get('ffch-phone', 'audio_rec_delay'))
except ConfigParser.NoOptionError,e:
    pass

if video_rec_delay < 0:
    video_rec_delay = 0
if audio_rec_delay < 0:
    audio_rec_delay = 0


# check folders
if not rec_folder.endswith("/"):
    rec_folder = rec_folder + "/"
if not rec_folder_a.endswith("/"):
    rec_folder_a = rec_folder_a + "/"
if not out_folder.endswith("/"):
    out_folder = out_folder + "/"
if not backup_folder.endswith("/"):
    backup_folder = backup_folder + "/"


try:
    camera_width = int(configParser.get('ffch-cam', 'width'))
    camera_height = int (configParser.get('ffch-cam', 'height'))
except Exception,e:
    camera_width = 1920
    camera_height = 1080

try:
    camera_fps = int(configParser.get('ffch-cam', 'fps'))
except Exception,e:
    pass

try:
    v = (configParser.get('ffch-cam', 'hflip'))
    camera_hflip = ((v == "True") | (v == "true") | (v == "1"))
except Exception,e:
    pass

try:
    v = (configParser.get('ffch-cam', 'vFlip'))
    camera_vflip = ((v == "True") | (v == "true") | (v == "1"))
except Exception,e:
    pass


video_offset = (1.0/camera_fps)*float(video_rec_delay)
audio_offset = (1.0/camera_fps)*float(audio_rec_delay)


############################
# prepare camera
############################
camera = PiCamera()
camera.framerate = camera_fps
camera.resolution = (camera_width, camera_heigth)
camera.hflip = camera_hflip
camera.vflip = camera_vflip
# camera.exposure_mode = "fixedfps"


def checkAllFolders():
    subprocess.call(["mount", "-a"], shell=False)
    checkFolder(rec_folder)
    checkFolder(rec_folder_a)
    checkFolder(out_folder)

def wipeAllLocks(folder):
    if not folder.endswith("/"):
        folder = folder + "/"
    files = listdir(folder)
    for lf in [f for f in files if (".lock" in f)]:
        try:
            os.remove(folder+lf)
        except IOError,e:
            print e

def checkForLock(folder):
    if len([x for x in listdir(folder) if ("lock" in x)]) > 0:
        return True
    return False


def doStartVideo(filename):
    if video_offset > 0:
        target_time = time.clock() + video_offset
        while time.clock() < target_time:
            pass
    camera.start_recording(filename, format='h264', quality=20)


def startRecord():
    global isRecording
    global rec_filename
    global out_filename
    global camera
    global audioProcess
    global muxer_pid
    global record_started
    global rec_lock
    global playbackProc

    if isRecording:
        stopRecord()


    # remount all and check folder
    checkAllFolders()

    # playback file
    if os.path.isfile(playback_file):
        playbackProc = subprocess.Popen(["aplay", playback_file], shell=False)

    with rec_lock:
        #--------------------
        # get muxer pid
        muxer_pid = mx.getPid()

        #--------------------
        # pause muxer process
        if muxer_pid > 0:
            try:
                os.kill(muxer_pid, signal.SIGSTOP)
            except OSError,e:
                pass

        now = strftime("%Y_%m_%d-%H_%M_%S", gmtime())
        rec_filename = rec_folder + now + "-ffch"
        rec_filename_a = rec_folder_a + now + "-ffch"
        out_filename = out_folder + now + "-ffch"
        print "start recording with file prefix: ", rec_filename

        #"-d", str(recording_duration),
        # arecord -c 1 -f dat -t wav file.wav
        #-R, --start-delay=#     delay for automatic PCM start is # microseconds
        # (relative to buffer size if <= 0)

        audiocmd = ["arecord", "-c", "1", "-f", "dat", "-t", "wav", rec_filename_a+".wav"]

        # write lock files
        open(rec_filename+".lock", 'a').close()


        # started recording
        isRecording = True
        record_started = time.time()

        ############################
        # start video recording:
        ############################
        # start video in own thread, so we can delay it if needed
        thread.start_new_thread( doStartVideo, (rec_filename + ".h264",))

        # delay audio recording if needed
        if audio_offset > 0:
            target_time = time.clock() + audio_offset
            while time.clock() < target_time:
                pass
        audioProcess = subprocess.Popen(audiocmd, shell=False)


def stopPlayback():
    global playbackProc

    if playbackProc is not None:
        try:
            playbackProc.terminate()
            # while playbackProc.poll():
            #     continue
        except OSError,e:
            print "terminate playback error"
        playbackProc = None


def stopRecord():
    global isRecording
    global camera
    global audioProcess
    global rec_filename
    global out_filename
    global muxer_pid
    global record_started
    global rec_lock
    global playbackProc

    stopPlayback()

    with rec_lock:

        if not isRecording:
            return

        now = time.time()
        if record_started > 0 and (now - record_started) < 2:
            print "recorded too less, sleep a bit"
            sleep(2)

        # camera.wait_recording(recording_duration)
        print "stop video recording"

        if camera.recording:
            camera.stop_recording()
        else:
            print "error: camera not recording"

        if audioProcess is not None:
            try:
                audioProcess.terminate()
                # while audioProcess.poll():
                #     continue
            except OSError,e:
                print "error: no audioProcess!"
                pass
            audioProcess = None
        else:
            print "error: audio not recording"


        ############################
        # done recording remove lock file
        wipeAllLocks(rec_folder)

        #--------------------
        # get muxer pid
        muxer_pid = mx.getPid()

        #--------------------
        # continue muxer process
        if muxer_pid > 0:
            try:
                os.kill(muxer_pid, signal.SIGCONT)
            except OSError,e:
                pass

        audioProcess = None
        isRecording = False
        record_started = 0


############################
# setup GPIO
############################
GPIO.setmode(GPIO.BCM)

# setup GPIO pins
GPIO.setup(phonePinNum, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(buttonPinNum, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def phoneButtonPressed(channel):
    if (GPIO.input(phonePinNum) == 0):
        print "GPIO stop recording"
        stopRecord()
    else:
        print "GPIO start recording"
        startRecord()


def btnButtonPressed(channel):
    if (GPIO.input(buttonPinNum) == 0):
        # button down
        if (GPIO.input(phonePinNum) > 0):
            print "button: stop recording"
            stopRecord()
        pass
    else:
        # up
        if (GPIO.input(phonePinNum) > 0):
            print "button: start recording"
            startRecord()
        pass

# setup button callbacks
GPIO.add_event_detect(phonePinNum, GPIO.BOTH, callback=phoneButtonPressed, bouncetime=1000)
GPIO.add_event_detect(buttonPinNum, GPIO.BOTH, callback=btnButtonPressed, bouncetime=1000)


############################
# check for folder
############################
# function in muxer.py
checkAllFolders()

############################
# setup logging
############################
logging.basicConfig(filename=log_file,
                    filemode='a',
                    format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                    datefmt='%H:%M:%S',
                    level=logging.DEBUG)

my_logger = logging.getLogger('ffch-phone')
my_logger.info('ffch-phone starting up')

##################
# print vars
##################
my_logger.info("----- ffch phone start -----")
my_logger.info("record duration: " + str(recording_duration) + " seconds")
my_logger.info("video folder: " + rec_folder)
my_logger.info("audio folder: " + rec_folder_a)
my_logger.info("out folder: " + out_folder)
my_logger.info("backup folder: " + backup_folder)
my_logger.info("playback file: " + playback_file)
my_logger.info("video recording delay: " + str(video_rec_delay) + " frames: " + str(video_offset) + " seconds")
my_logger.info("audio recording delay: " + str(audio_rec_delay) + " frames: " + str(audio_offset) + " seconds")

my_logger.info("camera settings: " + str(camera_width)+"x"+str(camera_height) + " @ " + str(camera_fps) + "fps. [" + str(camera_hflip) + "," + str(camera_vflip) + "]")



############################
# initally wipe the locks
############################
wipeAllLocks(rec_folder)

############################
# setup muxer
############################
mx = Muxer(rec_folder, rec_folder_a, out_folder, backup_folder)
mx.setLock(rec_lock)
mx.setFPS(camera_fps)

# print "ready to record..."

############################
# main loop
############################
while True:
    try:
        sleep(0.5)

        now = time.time()
        if record_started > 0:
            if (now - record_started) > recording_duration:
                stopPlayback()
                # play auflegen_wav
                # subprocess.call(["aplay", auflegen_wav], shell=False);
                sleep(0.5)
                stopRecord()
        else:
            if not mx.isMuxing:
                # start muxing
                mx.start()


    except KeyboardInterrupt:
        break
    except Exception,e:
        # pass any other exceptions
        print "exception in main loop: ", e
        pass

# cleanup
stopRecord()

GPIO.remove_event_detect(phonePinNum)
GPIO.remove_event_detect(buttonPinNum)
GPIO.cleanup()

print "done - exit"
