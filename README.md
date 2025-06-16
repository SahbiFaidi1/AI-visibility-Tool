# Local Mistral-7B Chat

A simple command-line interface to run Mistral-7B locally on Apple Silicon (M1/M2) Macs.

## Requirements

- macOS with Apple Silicon (M1/M2)
- Python 3.9 or higher
- At least 8GB of RAM (16GB recommended)
- At least 8GB of free disk space

## Setup

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Run the script:
```bash
python mistral_client.py
```

The first run will download the Mistral-7B model (about 4GB). This might take a while depending on your internet connection.

## Features

- Runs completely locally on your Mac
- Uses GPU acceleration for faster responses
- No internet connection required after initial download
- No API keys or costs
- Real-time response generation

## Notes

- The model is quantized to 4-bit to run efficiently on your Mac
- First response might be slower as the model warms up
- Response time depends on your prompt length and complexity 