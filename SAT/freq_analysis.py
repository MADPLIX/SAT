import librosa
import numpy as np
import json
import os

def analyze_frequency_bands(filepath, sr=22050, hop_length=512):
    y, sr = librosa.load(filepath, sr=sr)
    S = np.abs(librosa.stft(y, hop_length=hop_length))
    freqs = librosa.fft_frequencies(sr=sr)

    bands = {
        'NONE': (0, 0),
        'Sub-Bass': (20, 60),
        'Bass': (60, 250),
        'Low Midrange': (250, 500),
        'Midrange': (500, 2000),
        'High Midrange': (2000, 4000),
        'Presence': (4000, 6000),
        'Brilliance': (6000, 20000)
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
