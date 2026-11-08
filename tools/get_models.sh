#!/bin/bash
# Kokoro-82M (Apache-2.0) in ONNX form, published by kokoro-onnx (MIT) on GitHub.
set -e; mkdir -p models; B=https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0
[ -s models/kokoro-v1.0.onnx ] || curl -fsSL -o models/kokoro-v1.0.onnx $B/kokoro-v1.0.onnx
[ -s models/voices-v1.0.bin ] || curl -fsSL -o models/voices-v1.0.bin $B/voices-v1.0.bin
ls -la models
