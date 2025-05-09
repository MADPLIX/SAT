import librosa as _librosa
import numpy as np

def detect_bpm(filepath):
    try:
        y, sr = _librosa.load(filepath)
        tempo, _ = _librosa.beat.beat_track(y=y, sr=sr)

        if isinstance(tempo, (list, np.ndarray)):
            tempo = tempo[0]

        if tempo is None or np.isnan(tempo) or tempo <= 0:
            return None

        return round(float(tempo))
    except Exception as e:
        print(f"[BPM-Fehler] {e}")
        return None
