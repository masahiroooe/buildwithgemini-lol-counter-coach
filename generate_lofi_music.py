import numpy as np
from scipy.io import wavfile
import subprocess
import os
from pathlib import Path
import imageio_ffmpeg

SR = 44100  # Sample rate
BPM = 88    # Upbeat lo-fi tempo
BEAT_DUR = 60.0 / BPM
BAR_DUR = BEAT_DUR * 4
TOTAL_DURATION = 65.0  # Duration to cover the video

def note_freq(note_name):
    notes = {'C': 0, 'C#': 1, 'D': 2, 'D#': 3, 'E': 4, 'F': 5, 'F#': 6, 'G': 7, 'G#': 8, 'A': 9, 'A#': 10, 'B': 11}
    octave = int(note_name[-1])
    key = note_name[:-1]
    n = notes[key] + (octave + 1) * 12
    return 440.0 * (2.0 ** ((n - 69) / 12.0))

# Upbeat Lo-Fi Neo-Soul Chord Progression: Fmaj7 -> Em7 -> Dm7 -> Cmaj7
CHORDS = [
    [note_freq('F3'), note_freq('A3'), note_freq('C4'), note_freq('E4')], # Fmaj7
    [note_freq('E3'), note_freq('G3'), note_freq('B3'), note_freq('D4')], # Em7
    [note_freq('D3'), note_freq('F3'), note_freq('A3'), note_freq('C4')], # Dm7
    [note_freq('C3'), note_freq('E3'), note_freq('G3'), note_freq('B4')], # Cmaj7
]

BASS_NOTES = [note_freq('F2'), note_freq('E2'), note_freq('D2'), note_freq('C2')]

# Pentatonic melody notes
MELODY_NOTES = [note_freq('C4'), note_freq('D4'), note_freq('E4'), note_freq('G4'), note_freq('A4'), note_freq('C5'), note_freq('E5')]

def synthesize_epiano_note(freq, duration, sr=SR):
    t = np.linspace(0, duration, int(sr * duration), False)
    # Fundamental + harmonics for warm Rhodes/EPiano sound
    wave = 0.6 * np.sin(2 * np.pi * freq * t) + \
           0.25 * np.sin(2 * np.pi * freq * 2 * t) * np.exp(-t * 2) + \
           0.15 * np.sin(2 * np.pi * freq * 3 * t) * np.exp(-t * 4)
    
    # Smooth attack and exponential decay
    envelope = np.minimum(t / 0.01, 1.0) * np.exp(-t * 1.8)
    return wave * envelope

def synthesize_bass_note(freq, duration, sr=SR):
    t = np.linspace(0, duration, int(sr * duration), False)
    # Warm sub bass with subtle saturation
    wave = np.sin(2 * np.pi * freq * t) + 0.2 * np.sin(2 * np.pi * freq * 2 * t)
    envelope = np.minimum(t / 0.015, 1.0) * np.exp(-t * 0.8)
    return wave * envelope

def synthesize_kick(sr=SR):
    duration = 0.2
    t = np.linspace(0, duration, int(sr * duration), False)
    freq = 130 * np.exp(-t * 30) + 40
    wave = np.sin(2 * np.pi * freq * t)
    envelope = np.exp(-t * 15)
    return wave * envelope

def synthesize_snare(sr=SR):
    duration = 0.18
    t = np.linspace(0, duration, int(sr * duration), False)
    noise = np.random.uniform(-1, 1, len(t))
    tone = np.sin(2 * np.pi * 180 * t) * np.exp(-t * 20)
    envelope = np.exp(-t * 18)
    return (0.7 * noise + 0.3 * tone) * envelope

def synthesize_hihat(sr=SR):
    duration = 0.06
    t = np.linspace(0, duration, int(sr * duration), False)
    noise = np.random.uniform(-1, 1, len(t))
    envelope = np.exp(-t * 50)
    return noise * envelope

def generate_lofi_track(total_dur=TOTAL_DURATION):
    total_samples = int(SR * total_dur)
    audio = np.zeros(total_samples, dtype=np.float32)
    
    num_bars = int(total_dur / BAR_DUR) + 1
    
    # Generate Vinyl Crackle / Ambient Texture
    crackle = np.random.normal(0, 0.012, total_samples)
    audio += crackle
    
    kick = synthesize_kick()
    snare = synthesize_snare()
    hihat = synthesize_hihat()
    
    np.random.seed(42)  # For consistent musical melody
    
    for bar in range(num_bars):
        bar_start_sample = int(bar * BAR_DUR * SR)
        chord = CHORDS[bar % len(CHORDS)]
        bass = BASS_NOTES[bar % len(BASS_NOTES)]
        
        # 1. Add Chords (Plucked / Strummed Rhode EPiano)
        for i, freq in enumerate(chord):
            strum_delay = int(i * 0.025 * SR)
            note_wav = synthesize_epiano_note(freq, BAR_DUR)
            start = bar_start_sample + strum_delay
            end = min(start + len(note_wav), total_samples)
            if start < total_samples:
                audio[start:end] += note_wav[:end - start] * 0.22

        # 2. Add Sub Bass
        bass_wav = synthesize_bass_note(bass, BAR_DUR)
        end = min(bar_start_sample + len(bass_wav), total_samples)
        if bar_start_sample < total_samples:
            audio[bar_start_sample:end] += bass_wav[:end - bar_start_sample] * 0.35

        # 3. Add Upbeat Drum Beat (4 Beats per Bar)
        for beat in range(4):
            beat_sample = bar_start_sample + int(beat * BEAT_DUR * SR)
            
            # Kick on Beat 0, and 2.5 (syncopated upbeat)
            if beat == 0 and beat_sample < total_samples:
                end = min(beat_sample + len(kick), total_samples)
                audio[beat_sample:end] += kick[:end - beat_sample] * 0.5
            elif beat == 2:
                # Syncopated kick on the "and" of beat 2
                upbeat_sample = beat_sample + int(0.5 * BEAT_DUR * SR)
                if upbeat_sample < total_samples:
                    end = min(upbeat_sample + len(kick), total_samples)
                    audio[upbeat_sample:end] += kick[:end - upbeat_sample] * 0.45

            # Snare on Beat 1 and 3
            if beat in [1, 3] and beat_sample < total_samples:
                end = min(beat_sample + len(snare), total_samples)
                audio[beat_sample:end] += snare[:end - beat_sample] * 0.32

            # Hi-hats every 8th note
            for sub in [0, 0.5]:
                hat_sample = beat_sample + int(sub * BEAT_DUR * SR)
                if hat_sample < total_samples:
                    vol = 0.18 if sub == 0 else 0.12  # Swung velocity
                    end = min(hat_sample + len(hihat), total_samples)
                    audio[hat_sample:end] += hihat[:end - hat_sample] * vol

        # 4. Add Upbeat Lo-Fi Lead Melody
        for beat in range(4):
            if np.random.rand() > 0.3:
                m_freq = np.random.choice(MELODY_NOTES)
                m_dur = BEAT_DUR * np.random.choice([0.5, 1.0])
                m_sample = bar_start_sample + int(beat * BEAT_DUR * SR)
                m_wav = synthesize_epiano_note(m_freq, m_dur)
                end = min(m_sample + len(m_wav), total_samples)
                if m_sample < total_samples:
                    audio[m_sample:end] += m_wav[:end - m_sample] * 0.28

    # Normalize audio & apply smooth fade out
    max_val = np.max(np.abs(audio))
    if max_val > 0:
        audio = audio / max_val * 0.85
        
    # Fade out last 3 seconds
    fade_samples = int(3.0 * SR)
    audio[-fade_samples:] *= np.linspace(1.0, 0.0, fade_samples)

    # Convert float32 to int16 PCM WAV
    audio_int16 = (audio * 32767).astype(np.int16)
    
    wav_path = "/config/Desktop/Session1/lol-counter-coach/lofi_track.wav"
    wavfile.write(wav_path, SR, audio_int16)
    print(f"Generated upbeat lo-fi track: {wav_path}")
    return wav_path

if __name__ == "__main__":
    generate_lofi_track()
