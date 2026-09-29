import subprocess
from pathlib import Path
import imageio_ffmpeg

FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
INPUT_VIDEO = Path("/config/Desktop/Session1/agent_demo.webm")
INPUT_AUDIO = Path("/config/Desktop/Session1/lol-counter-coach/lofi_track.wav")
OUTPUT_VIDEO = Path("/config/Desktop/Session1/agent_demo_lofi.webm")
ARTIFACT_VIDEO = Path("/config/.gemini/antigravity/brain/2d93f2be-9cfd-4095-ae35-244a90606da6/agent_demo.webm")

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
    
    print("Running ffmpeg command to mix upbeat lo-fi audio into agent_demo.webm...")
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode == 0:
        print(f"Successfully created final video with upbeat lo-fi background music: {OUTPUT_VIDEO}")
        # Copy to artifacts directory as well for easy viewing & embedding
        cmd_copy = [FFMPEG_EXE, "-y", "-i", str(OUTPUT_VIDEO), "-c", "copy", str(ARTIFACT_VIDEO)]
        subprocess.run(cmd_copy)
    else:
        print(f"Error mixing audio into video: {res.stderr}")

if __name__ == "__main__":
    mix_audio_video()
