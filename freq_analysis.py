import librosa
import numpy as np
import json
import os

def analyze_frequency_bands(filepath, sr=22050, hop_length=512):
    y, sr = librosa.load(filepath, sr=sr)
    S = np.abs(librosa.stft(y, hop_length=hop_length))
    freqs = librosa.fft_frequencies(sr=sr)

    bands = {
        "kick": (40, 100),
        "bass": (100, 200),
        "snare": (400, 1000),
        "hihat": (6000, 10000)
    }

    energy = {}
    for name, (fmin, fmax) in bands.items():
        band_idx = (freqs >= fmin) & (freqs <= fmax)
        energy[name] = S[band_idx, :].mean(axis=0).tolist()

    return energy, librosa.get_duration(y=y, sr=sr), sr, hop_length


def save_energy_as_json(filepath, output_path):
    energy, duration, sr, hop = analyze_frequency_bands(filepath)
    fps = sr / hop
    data = {
        "energy": energy,
        "fps": fps,
        "duration": duration
    }
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)
