"""Render saved source-pixel predictions without running the model again."""
import argparse
import json
from pathlib import Path
import subprocess

import cv2
import imageio_ffmpeg

from ml.above.cow_segment import draw


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('predictions',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--masks',action='store_true')
    args=parser.parse_args()
    if args.output.resolve() in {args.source.resolve(),args.predictions.resolve()}:
        parser.error('Output must not overwrite inputs')
    cap=cv2.VideoCapture(str(args.source))
    fps=cap.get(cv2.CAP_PROP_FPS)
    width,height=int(cap.get(3)),int(cap.get(4))
    if fps<=0 or width<=0:
        raise ValueError('Could not open source')
    scale=min(1,1920/width)
    ow,oh=round(width*scale)//2*2,round(height*scale)//2*2
    args.output.parent.mkdir(parents=True,exist_ok=True)
    log=args.output.with_suffix('.ffmpeg.log').open('w')
    command=[imageio_ffmpeg.get_ffmpeg_exe(),'-y','-f','rawvideo','-pix_fmt','bgr24',
             '-s',f'{ow}x{oh}','-r',str(fps),'-i','pipe:0','-an','-c:v','libx264',
             '-preset','fast','-crf','19','-pix_fmt','yuv420p','-movflags','+faststart',str(args.output)]
    process=subprocess.Popen(command,stdin=subprocess.PIPE,stderr=log)
    count=0
    try:
        with args.predictions.open() as records:
            for line in records:
                row=json.loads(line)
                if count==0:
                    cap.set(cv2.CAP_PROP_POS_FRAMES,row['frame'])
                    first=row['frame']
                if row['frame']!=first+count:
                    raise ValueError('Prediction frame sequence has a gap')
                ok,frame=cap.read()
                if not ok:
                    raise ValueError('Source ended before predictions')
                result=draw(frame,row['detections'],args.masks,scale)
                if result.shape[:2]!=(oh,ow):
                    result=cv2.resize(result,(ow,oh))
                process.stdin.write(result.tobytes())
                if row['frame'] in {0,409,817}:
                    cv2.imwrite(str(args.output.with_name(f'{args.output.stem}-frame-{row["frame"]:04d}.jpg')),result)
                count+=1
                if count%100==0:
                    print(f'Rendered {count} frames',flush=True)
    finally:
        cap.release()
        process.stdin.close()
        code=process.wait()
        log.close()
    if code:
        raise RuntimeError(f'FFmpeg failed: {args.output}')
    print(f'Saved {count} frames to {args.output}',flush=True)


if __name__=='__main__':
    main()
