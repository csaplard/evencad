# Demo video

`saycad-demo.mp4` is the demo video (1920x1080).

## What is real in it

- Every text, drawing, sheet, operation and time comes from one real run of the server:
  speech to text (Whisper `base.en`, on our server), Claude (`claude-haiku-5-5`), the rules, CadQuery, the PDF sheet, Google Drive.
- The spoken commands go to the same `/session/{id}/audio` call that the glasses app uses.

## What is made for the video

- **The voices are computer voices (text to speech).** A computer voice speaks the commands, and another one the narration. No person speaks.
- The frame around the display is drawn by `tools/demo_video.py`. It uses the layout of the app (status line, drawing, info lines). It is not a recording of the glasses or of the simulator.
- The waits are cut short. The real times are on the screen.
- The app was not tested on real G2 glasses yet. The video says so.

## Make it again

```
pip install imageio-ffmpeg
python -m tools.demo_record   # runs the real server with the lines in demo/audio/, writes demo/run/
python -m tools.demo_video    # builds demo/saycad-demo.mp4 from demo/run/
```

`demo/audio/c*.mp3` are the commands, `n*.mp3` is the narration. The texts are in `tools/demo_record.py` and `tools/demo_video.py`.
