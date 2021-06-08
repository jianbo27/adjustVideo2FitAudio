import cv2
import numpy as np
from scipy.io import wavfile
import math
from audiotsm import phasevocoder
from arrayWav import ArrReader, ArrWriter
import subprocess
from tools import tools



# we assume the audio is in synchronization with video

videoFile = r'配音-原.mp4'
theotherwavFile = r'1.wav'
# here we want to use silentSpeed to help us control the length of video
# it means the speed ration is calculated by 
#    terminology:
#       slient part of video - sv
#
# Situation 1:
#  if len(audio) > len(video):
#      1/r1 = [len(audio) - len(video) + len(sv)] / len(sv)  ## use the slient part to compensate for the gap
#      r1 is the real ratio that slient part should multiple(slow down)
# Situation 2 is not considered in this version
t = tools()

len_audio = t.calcWavTime(theotherwavFile)
len_video = t.calcVideoTime(videoFile)
len_sv = t.calSlientVideoPartTime(videoFile)

silentSpeed =  round( len_sv / (len_audio - len_video + len_sv),2 )
print(silentSpeed)

cap = cv2.VideoCapture(videoFile)

width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
fps = round(cap.get(cv2.CAP_PROP_FPS))

extractAudio = "ffmpeg -i {} -ab 160k -ac 2 -ar 44100 -vn tmp.wav".format(videoFile)
subprocess.call(extractAudio, shell=True)

out = cv2.VideoWriter("spedup.mp4", fourcc, fps, (width, height))
sampleRate, audioData = wavfile.read("tmp.wav")

skipped = 0

channels = int(audioData.shape[1])

def getMaxVolume(s):
    maxv = np.max(s)
    minv = np.min(s)
    return max(maxv,-minv)

nFrames = 0

def writeFrames(frames, nAudio, speed, samplePerSecond, writer):
    numAudioChunks = round(nAudio / samplePerSecond * fps)
    global nFrames
    numWrites = numAudioChunks - nFrames
    # a = [1, 2, 3], len(a) == 3 but a[3] is error
    limit = len(frames) - 1
    for i in range(numWrites):
        frameIndex = round(i * speed)
        if frameIndex > limit:
            writer.write(frames[-1])
        else:
            writer.write(frames[frameIndex])
        nFrames += 1
normal = 0
# 0 for silent, 1 for normal
switchStart = 0
maxVolume = getMaxVolume(audioData)
fadeInSamples = 400
preMask = np.arange(fadeInSamples)/fadeInSamples
mask = np.repeat(preMask[:, np.newaxis], 2, axis = 1)
y = np.zeros_like(audioData, dtype=np.int16)
yPointer = 0
frameBuffer = []

while (cap.isOpened()):
    ret, frame = cap.read()

    # 1000 milisecond == 1 second, since samplerate is in seconds, I need to convert this to second as well
    currentTime = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
    if ret == False:
        break

    audioSampleStart = math.floor(currentTime * sampleRate)
    # import pdb; pdb.set_trace()
    # audioSampleStart + one frame worth of samples
    audioSampleEnd = audioSampleStart + (sampleRate // fps)

    switchEnd = audioSampleEnd

    audioChunk = audioData[audioSampleStart:audioSampleEnd]

    # if it's quite
    if getMaxVolume(audioChunk) < 500:
        skipped += 1
        # if the frame is 'switched'
        frameBuffer.append(frame)
        normal = 0
    else: # if it's 'loud'

        # and the last frame is 'loud'
        if normal:
            out.write(frame)
            nFrames += 1
            switchStart = switchEnd

            yPointerEnd = yPointer + audioChunk.shape[0]
            y[yPointer : yPointerEnd] = audioChunk
            yPointer = yPointerEnd
        else:
            spedChunk = audioData[switchStart:switchEnd]
            spedupAudio = np.zeros((0,2), dtype=np.int16)
            # ArrReader (array, channels, samplerate, samplewidth)
            with ArrReader(spedChunk, channels, sampleRate, 2) as reader:
                # 2 as sampleWidth for now
                with ArrWriter(spedupAudio, channels, sampleRate, 2) as writer:
                    tsm = phasevocoder(reader.channels, speed=silentSpeed)
                    tsm.run(reader, writer)
                    spedupAudio = writer.output

            yPointerEnd = yPointer + spedupAudio.shape[0]
            y[yPointer : yPointerEnd] = spedupAudio
            yPointer = yPointerEnd

            writeFrames(frameBuffer, yPointerEnd, silentSpeed, sampleRate, out)
            frameBuffer = []
            switchStart = switchEnd

        normal = 1
    if skipped % 1000 == 0:
        print("{} frames inspected".format(skipped))
        skipped += 1

y = y[:yPointer]

wavfile.write("spedupAudio.wav", sampleRate, y)

cap.release()
out.release()
# cv2.destroyAllWindows()

outFile = "{}_faster{}".format(videoFile[:videoFile.rfind('.')],videoFile[videoFile.rfind('.'):])
mergeCommand = "ffmpeg -i spedup.mp4 -i spedupAudio.wav -c:v copy -c:a aac {}".format(outFile)

error = subprocess.call(mergeCommand, shell=True)
if error == 0:
    removeCommand = "rm spedup.mp4 spedupAudio.wav"
    rmError = subprocess.call(removeCommand, shell=True)
    # rm is not available on Windows, so rm would return != 0
    if rmError != 0:
        error = subprocess.call("del output.wav spedup.mp4 spedupAudio.wav", shell=True)