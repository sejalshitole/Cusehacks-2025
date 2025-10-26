"""
Utility functions for the feedback agent
Handles audio analysis and image compression for Gemini API
"""

import os
import numpy as np
from PIL import Image
from typing import List
import io


def compress_images_for_gemini(
    images: List[Image.Image], 
    max_images: int = 6, 
    target_size: tuple = (640, 480)
) -> List[Image.Image]:
    """
    Compress and resize images for Gemini API to reduce token usage
    
    Args:
        images: List of PIL Images
        max_images: Maximum number of images to return
        target_size: Target size for resizing (width, height)
    
    Returns:
        List of compressed PIL Images
    """
    # Sample images if we have too many
    if len(images) > max_images:
        step = len(images) // max_images
        images = [images[i] for i in range(0, len(images), step)][:max_images]
    
    compressed = []
    for img in images:
        # Resize to target size while maintaining aspect ratio
        img.thumbnail(target_size, Image.Resampling.LANCZOS)
        
        # Convert to RGB if needed
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        compressed.append(img)
    
    return compressed


def analyze_audio_tone_fast(audio_path: str) -> str:
    """
    Fast audio analysis using librosa for tone, energy, and pace
    
    Args:
        audio_path: Path to audio file (WAV format)
    
    Returns:
        String description of audio characteristics
    """
    try:
        import librosa
        
        # Load audio file
        y, sr = librosa.load(audio_path, sr=16000, duration=5.0)  # Only analyze up to 5 seconds
        
        if len(y) == 0:
            return "No audio detected"
        
        # Calculate energy/volume
        rms = librosa.feature.rms(y=y)[0]
        avg_energy = np.mean(rms)
        energy_variance = np.std(rms)
        
        # Calculate pitch
        pitches, magnitudes = librosa.piptrack(y=y, sr=sr)
        pitch_values = []
        for t in range(pitches.shape[1]):
            index = magnitudes[:, t].argmax()
            pitch = pitches[index, t]
            if pitch > 0:
                pitch_values.append(pitch)
        
        avg_pitch = np.mean(pitch_values) if pitch_values else 0
        
        # Calculate speaking rate (zero-crossing rate as proxy)
        zcr = librosa.feature.zero_crossing_rate(y)[0]
        avg_zcr = np.mean(zcr)
        
        # Interpret results
        volume_desc = "loud" if avg_energy > 0.05 else "moderate" if avg_energy > 0.02 else "quiet"
        energy_desc = "varied" if energy_variance > 0.02 else "consistent"
        pitch_desc = f"{avg_pitch:.0f}Hz" if avg_pitch > 0 else "unclear"
        pace_desc = "fast" if avg_zcr > 0.08 else "moderate" if avg_zcr > 0.04 else "slow"
        
        return f"Volume: {volume_desc} ({energy_desc}), Pitch: {pitch_desc}, Pace: {pace_desc}"
        
    except ImportError:
        # Fallback if librosa is not available
        return "Audio analysis unavailable (librosa not installed)"
    except Exception as e:
        return f"Audio analysis error: {str(e)[:50]}"


def analyze_audio_segment(audio_bytes: bytes, sample_rate: int = 48000) -> str:
    """
    Analyze a raw audio segment (for real-time analysis)
    
    Args:
        audio_bytes: Raw audio data
        sample_rate: Sample rate of audio
    
    Returns:
        String description of audio characteristics
    """
    try:
        import librosa
        
        # Convert bytes to numpy array
        audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
        
        # Convert to float and normalize
        y = audio_array.astype(np.float32) / 32768.0
        
        if len(y) == 0:
            return "No audio detected"
        
        # Calculate basic metrics
        rms = np.sqrt(np.mean(y**2))
        volume_desc = "loud" if rms > 0.05 else "moderate" if rms > 0.02 else "quiet"
        
        # Calculate zero-crossing rate for pace
        zero_crossings = np.sum(np.abs(np.diff(np.sign(y)))) / 2
        zcr = zero_crossings / len(y)
        pace_desc = "fast" if zcr > 0.08 else "moderate" if zcr > 0.04 else "slow"
        
        return f"Volume: {volume_desc}, Pace: {pace_desc}"
        
    except ImportError:
        return "Audio analysis unavailable"
    except Exception as e:
        return f"Audio analysis error: {str(e)[:50]}"