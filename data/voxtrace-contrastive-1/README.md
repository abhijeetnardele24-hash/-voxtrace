# VoxTrace-Contrastive-1 preview

This checked-in preview contains **18 WAV recordings**: three licensed reference clips from three speakers and five deterministic delivery variants per reference. Each group preserves one exact transcript across reference, near-perfect, rushed, excessive-pause, low-energy, and mixed-flaw conditions.

## Source and licence

The three reference clips originate from the LibriSpeech ASR corpus, OpenSLR resource 12, licensed under **Creative Commons Attribution 4.0**:

- Source: https://www.openslr.org/12
- Dataset mirror used for the compact selected clips: https://huggingface.co/datasets/sanchit-gandhi/librispeech_asr_dummy
- Upstream authors: Vassil Panayotov, Guoguo Chen, Daniel Povey, and Sanjeev Khudanpur
- Selected utterances: `6930-75918-0003`, `374-180298-0001`, and `2277-149896-0001`

Attribution: Panayotov et al., “LibriSpeech: an ASR corpus based on public domain audio books,” ICASSP 2015. The derivative recordings in this directory retain the upstream CC BY 4.0 obligations. Project source code remains MIT-licensed; that does not replace the audio licence.

## Deterministic transformations

- `reference`: unchanged selected clip
- `near_perfect`: amplitude multiplied by 0.90; intentionally has no flaw label
- `rushed`: duration compressed by a 1.28 speed factor
- `excessive_pause`: 1.8 seconds of digital silence inserted at 55% of the reference
- `low_energy`: amplitude multiplied by 0.32
- `mixed_flaws`: 1.20 speed factor, 1.6-second inserted pause, and amplitude multiplied by 0.42

The manifest contains exact transformation intervals. Labels are marked `pending` because they are generated stress-test annotations, not human-reviewed ground truth. They must not be presented as a final human-labelled benchmark.

## Reproduction

Each variant was created by `backend/contrastive_cli.py` from a 16 kHz, mono, 16-bit PCM reference WAV. The combined manifest is at `labels/manifests.jsonl`.

## Privacy and limitations

Do not attempt to identify speakers. The preview is small, read-speech-only, English-only, and contains synthetic acoustic transformations rather than naturally produced delivery mistakes. It is useful for deterministic pipeline stress testing, not for population-level accuracy claims.
