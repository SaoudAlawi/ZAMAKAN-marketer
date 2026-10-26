# Describing a frame in film language (frame-match mode, and every shot note)

Look at the image (or contact sheet) and write, in this order. Only describe what you can see.

1. **Shot size**: extreme wide · wide · full · medium · medium close-up · close-up · extreme close-up/insert.
2. **Angle and framing**: eye level · low · high · top-down · over-the-shoulder · POV · two-shot · symmetry · frame-in-frame.
3. **Lens feel**: wide (space stretched, close to subject) · normal · long (space compressed, background big) · shallow
   or deep focus · anamorphic flares/oval bokeh · fisheye distortion.
4. **Light**: time of day (golden hour, blue hour, midday, night) · direction (front, side, back, top) · hard or soft ·
   practicals in frame · haze · contrast (low key / high key).
5. **Colour**: run `palette.py --image` and name the feeling (warm/cool, saturated/muted, a dominant hue).
6. **Movement** (video) or implied movement (still): static, push, track, handheld, orbit...
7. **Subject and gesture**: who, doing what; the emotional beat.

Then map each line to technique ids in `techniques.json` and search those. In the board, `run.frame` holds the
description plus `shot_size`, `lens`, `light`, `movement` and the palette.

## Matching honestly
- Judge matches from what you saw: the thumbnail, stills or a listing. Say "from the thumbnail" when that is all you saw.
- Never describe scenes inside a video you haven't watched; quote the source's description instead and add it to `watch_list`.
- Credits only from a source that states them (Eyecannndy, a case page, trade press). Don't add DOPs from memory.
