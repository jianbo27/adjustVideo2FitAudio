import contextlib
import wave
from pydub import AudioSegment
from moviepy.editor import VideoFileClip


class tools():
    def __init__(self):
        pass

    def calcWavTime(self,wavFile):
        wav_length = 0
        with contextlib.closing(wave.open(wavFile, 'r')) as f:
            frames = f.getnframes()
            rate = f.getframerate()
            wav_length = frames / float(rate)
        return wav_length * 1000 ##to milliseconds

    def calcVideoTime(self,videoFile):
        clip = VideoFileClip(videoFile)
        return clip.duration*1000 ##to milliseconds

    def calSlientVideoPartTime(self,videoFile):
        # videoclip = VideoFileClip(videoFile)
        # audio = videoclip.audio
        # audio.write_audiofile('tmp.mp3')
        return self.detect_leading_silence(AudioSegment.from_file(r'tmp.wav',format='wav'))

    def detect_leading_silence(self,sound, silence_threshold=-50.0, chunk_size=10):
        '''
        sound is a pydub.AudioSegment
        silence_threshold in dB
        chunk_size in ms

        iterate over chunks until you find the first one with sound
        '''
        trim_ms = 0 # ms
        timing = 0
        assert chunk_size > 0 # to avoid infinite loop
        while timing < len(sound):
            if sound[timing:timing+chunk_size].dBFS < silence_threshold:
                trim_ms += chunk_size
            timing += chunk_size    
        return trim_ms
        