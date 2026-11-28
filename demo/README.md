# Demo video

`saycad-demo.mp4` is the demo video (1920x1080).

## What is real in it

- Every text, drawing, sheet, operation and time comes from one real run of the server:
  speech to text (Whisper `base.en`, on our server), Claude (`claude-haiku-5-5`), the rules, CadQuery, the PDF sheet, Google Drive.
- The spoken commands go to the same `/session/{id}/audio` call that the glasses app uses.

## What is made for the video

- **The voice is an AI voice (text to speech), made from the voice of the author.** It speaks the commands and the narration. Nobody spoke them live.
- The frame around the display is drawn by `tools/demo_video.py`. It uses the layout of the app (status line, drawing, info lines). It is not a recording of the glasses or of the simulator.
- The waits are cut short. The real times are on the screen.
- The turning 3D model is drawn by `tools/demo_model3d.py` from the STEP file of the run (`revA.step`). It is not a screen recording of a CAD program.
- The Autodesk Fusion picture is a screenshot (`fusion/fusion-view.png`): the same STEP file (`fusion/saycad-shaft-revA.step`), opened by hand in Fusion. Nothing was changed in the model.
- The app was not tested on real G2 glasses yet. The video does not show glasses, and it does not say this on screen; the README does.

## Make it again

```
pip install imageio-ffmpeg
python -m tools.demo_record   # runs the real server with the lines in demo/audio/, writes demo/run/
python -m tools.demo_model3d  # draws the STEP file of the run as a turning 3D model
python -m tools.demo_video    # builds demo/saycad-demo.mp4 from demo/run/
```

The sound files are not in the repository, because they hold the voice of a person. Put your own files into `demo/audio/`:
`c01.mp3` ... `c15.mp3` are the commands, `n01.mp3` ... `n13.mp3` is the narration. The texts are in `tools/demo_record.py` and `tools/demo_video.py`.
