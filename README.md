# transcribe-xlights

This utility will take an audio file as imput and output two files.

A JSON file containing the timing of the words in the audio file with all the details as provided from AWS Transcribe.

It will also take the resulting JSON file and output a xtiming file that can be used in xLights timing tracks.

# Usage

python transcribe-xlights.py --song filename.mp3
