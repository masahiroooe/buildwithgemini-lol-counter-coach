import subprocess
from pathlib import Path
import imageio_ffmpeg

FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
ARTIFACT_DIR = Path("/config/.gemini/antigravity/brain/2d93f2be-9cfd-4095-ae35-244a90606da6")
INPUT_VIDEO = ARTIFACT_DIR / "demo_recording.webm"
INPUT_AUDIO = Path("/config/Desktop/Session1/lol-counter-coach/lofi_track.wav")
OUTPUT_VIDEO = ARTIFACT_DIR / "demo_recording_lofi.webm"

def mix_audio_video():
    print(f"Using ffmpeg binary: {FFMPEG_EXE}")
    cmd = [
        FFMPEG_EXE,
        "-y",
        "-i", str(INPUT_VIDEO),
        "-i", str(INPUT_AUDIO),
        "-c:v", "copy",
        "-c:a", "libopus",
        "-b:a", "128k",
        "-shortest",
        str(OUTPUT_VIDEO)
    ]
    
    print("Running ffmpeg command to mix upbeat lo-fi audio...")
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode == 0:
        print(f"Successfully created video with upbeat lo-fi background music: {OUTPUT_VIDEO}")
    else:
        print(f"Error mixing audio into video: {res.stderr}")

if __name__ == "__main__":
    mix_audio_video()
