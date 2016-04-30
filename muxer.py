#!/usr/bin/python

#-------------------------------------------------------------------------------
# muxer.py
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
import os
from os import listdir
from os.path import isfile, join
import subprocess
import signal
import shutil
from time import sleep

def checkForLock(folder):
    if len([x for x in listdir(folder) if ("lock" in x)]) > 0:
        return True
    return False

def checkFolder(path):
    if not os.path.isdir(path):
        # create directory
        try:
            os.mkdir(path)
        except IOError,e:
            print e
            return False
        else:
            print "Successful created ", path
    return True

class Muxer(object):

    def doExec(self, cmd):
        while checkForLock(self.video_folder):
            # wait until lock is removed
            sleep(1)
        p = subprocess.Popen(cmd, shell=False)
        self.muxPid = p.pid
        return p

    def executeCmd(self, cmd):
        # check
        p = None
        if self.rec_lock is not None:
            with self.rec_lock:
                p = self.doExec(cmd)
        else:
            p = self.doExec(cmd)

        if p is not None:
            p.wait()
        else:
            print "error: process is None"

    def getPid(self):
        return self.muxPid

    def setLock(self, lock):
        self.rec_lock = lock

    def isMuxing(self):
        return self.isMuxing

    def setFPS(self, fps):
        self.fps = fps

    def doMux(self, vfn, afn):

        v_file = vfn+".h264"
        a_file = afn+".wav"
        # check files
        if not os.path.isfile(v_file):
            print "file does not exist: ", v_file
            return False
        if not os.path.isfile(a_file):
            # check in same folder as video...
            a_file = vfn+".wav"
            if not os.path.isfile(a_file):
                print "file does not exist: ", a_file
                return False

        #
        audio_format = ".m4a"
        # "-loglevel", "0",
        audio_convert_cmd = ["ffmpeg", "-y", "-i", a_file, "-strict", "experimental", "-acodec", "aac", "-b:a", "128k", vfn+audio_format]
        #"-quiet",
        mux_cmd = ["MP4Box", "-fps", str(self.fps), "-add", v_file, "-add", vfn+audio_format, vfn+".mp4"]
        #
        self.isMuxing = True
        self.executeCmd(audio_convert_cmd)
        self.muxPid = 0
        self.executeCmd(mux_cmd)
        self.muxPid = 0

        # move files around
        if os.path.isfile(vfn+".mp4"):
            print "Muxer: moving file", vfn+".mp4 to:", self.out_folder
            shutil.move(vfn+".mp4", self.out_folder)
        else:
            print "error: file does not exist"

        try:
            os.remove(v_file)
        except IOError,e:
            print "error removing:", v_file, ":", e
        # shutil.move(v_file, self.backup_folder)
        shutil.move(a_file, self.backup_folder)
        if os.path.isfile(vfn+audio_format):
            shutil.move(vfn+audio_format, self.backup_folder)

        print "done muxing:", vfn+".mp4"
        self.isMuxing = False
        return True

    def start(self):

        if self.isMuxing:
            print "already muxing return"
            return

        if not os.path.isdir(self.video_folder):
            return

        files = listdir(self.video_folder)
        files.sort()

        ############################
        # check if we are recording
        ############################
        if len([f for f in files if ("lock" in f)]) > 0:
            return

        ############################
        # fill hash
        ############################
        myhash = {}
        for f in [os.path.splitext(x)[0] for x in files]:
            if ".DS_Store" in f:
                continue
            if "._" in f:
                continue
            if f is None:
                continue
            if not f:
                continue
            myhash[f] = True

        ############################
        # iterate thorugh hash keys
        ############################
        filenames = myhash.keys()
        for f in filenames:
            if (f+".lock" in files):
                pass
            if (f+".lock" in files):
                pass
            else:
                print "processing: ", f
                if not self.doMux(self.video_folder + f, self.audio_folder + f):
                    print "failed muxing: " + f

    def setFolders(self, v_folder, a_folder, o_folder, b_folder):
        self.video_folder = v_folder
        self.audio_folder = a_folder
        self.out_folder = o_folder
        self.backup_folder = b_folder
        ############################
        # check for folder
        ############################
        checkFolder(self.video_folder)
        checkFolder(self.audio_folder)
        checkFolder(self.out_folder)
        checkFolder(self.backup_folder)

    def __init__(self, v_folder, a_folder, o_folder, b_folder):
        print "init muxer"

        self.muxPid = 0
        self.rec_lock = None
        self.isMuxing = False
        self.fps = 25

        self.setFolders(v_folder, a_folder, o_folder, b_folder)
