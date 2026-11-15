import os, tempfile, time
from pathlib import Path
import cv2
import numpy as np
import streamlit as st
from ultralytics import YOLO
from rtmlib import ViTPose

st.set_page_config(page_title='HERD / motion intelligence', layout='wide')
st.markdown('''<style>.stApp{background:#09110f;color:#e8f2e9} h1,h2,h3{letter-spacing:-.04em} [data-testid="stSidebar"]{background:#101b17} div.stButton>button{background:#c3f572;color:#14210a;border:0;font-weight:700} .tag{color:#c3f572;letter-spacing:.18em;font-size:12px;font-weight:700}</style>''', unsafe_allow_html=True)
st.markdown('<div class="tag">HERD / MOTION INTELLIGENCE &nbsp; ● &nbsp; PROTOTYPE</div>', unsafe_allow_html=True)
st.title('See the herd in motion.')
st.caption('Cow segmentation + animal pose estimation · Visual concept for a future lameness workflow')
st.warning('Prototype only: scores are simulated for presentation and do not measure lameness. Do not use for animal health decisions.')
with st.sidebar:
    st.header('Analysis settings')
    confidence=st.slider('Cow detection confidence',.1,.8,.25,.05)
    pose_conf=st.slider('Keypoint confidence',.05,.9,.3,.05)
    start_seconds=st.number_input('Video start (seconds)',min_value=0.0,value=7.0,step=1.0)
    end_seconds=st.number_input('Video end (seconds)',min_value=0.0,value=20.0,step=1.0)
    st.caption('First run downloads model weights. Video processing runs locally and may take several minutes on CPU.')

@st.cache_resource
def models():
    return YOLO('yolo11n-seg.pt'), ViTPose('https://huggingface.co/JunkyByte/easy_ViTPose/resolve/main/onnx/apt36k/vitpose-s-apt36k.onnx', model_input_size=(192,256), backend='onnxruntime', device='cpu', to_openpose=False)

SKELETON=[(0,2),(1,2),(2,3),(3,5),(5,6),(6,7),(3,8),(8,9),(9,10),(3,4),(4,11),(11,12),(12,13),(4,14),(14,15),(15,16)]
COLOR=(68,212,19)  # #13D444 in BGR

class Tracker:
    """Short-term spatial association for stable illustrative labels."""
    def __init__(self):
        self.tracks={}; self.next_id=1; self.frame=0
    def update(self, boxes):
        self.frame+=1
        candidates=[]
        for i,b in enumerate(boxes):
            for ident,(old,last) in self.tracks.items():
                if self.frame-last>15: continue
                x1=max(b[0],old[0]); y1=max(b[1],old[1]); x2=min(b[2],old[2]); y2=min(b[3],old[3])
                inter=max(0,x2-x1)*max(0,y2-y1)
                area=lambda x:max(1,(x[2]-x[0])*(x[3]-x[1]))
                iou=inter/(area(b)+area(old)-inter)
                if iou>.15: candidates.append((iou,i,ident))
        assigned={}; used=set()
        for _,i,ident in sorted(candidates,reverse=True):
            if i not in assigned and ident not in used:
                assigned[i]=ident; used.add(ident)
        for i,b in enumerate(boxes):
            if i not in assigned:
                assigned[i]=self.next_id; self.next_id+=1
            self.tracks[assigned[i]]=(b.copy(),self.frame)
        self.tracks={k:v for k,v in self.tracks.items() if self.frame-v[1]<=15}
        return [assigned[i] for i in range(len(boxes))]

def draw(frame, detector, animal, conf, threshold, tracker=None):
    result=detector.predict(frame,classes=[19],conf=conf,verbose=False)[0]
    boxes=result.boxes.xyxy.cpu().numpy() if result.boxes is not None else np.empty((0,4))
    ids=tracker.update(boxes) if tracker is not None else list(range(1,len(boxes)+1))
    if len(boxes)==0: return frame,0
    original=frame.copy(); overlay=frame.copy()
    if result.masks is not None:
        for poly in result.masks.xy:
            pts=np.asarray(poly,dtype=np.int32)
            if len(pts)>2: cv2.fillPoly(overlay,[pts],COLOR)
        frame=cv2.addWeighted(overlay,.055,frame,.945,0)
        for poly in result.masks.xy:
            pts=np.asarray(poly,dtype=np.int32)
            if len(pts)>2: cv2.polylines(frame,[pts],True,COLOR,1,cv2.LINE_AA)
    points,scores=animal(original,bboxes=boxes.tolist())
    h,w=frame.shape[:2]
    for i,box in enumerate(boxes):
        x1,y1,x2,y2=map(int,box)
        x1=max(0,x1); y1=max(0,y1); x2=min(w-1,x2); y2=min(h-1,y2)
        # Compact corner marks keep the scene visible.
        length=max(5,min(14,(x2-x1)//4,(y2-y1)//4))
        for x,y,dx,dy in [(x1,y1,1,1),(x2,y1,-1,1),(x1,y2,1,-1),(x2,y2,-1,-1)]:
            cv2.line(frame,(x,y),(x+dx*length,y),COLOR,1,cv2.LINE_AA)
            cv2.line(frame,(x,y),(x,y+dy*length),COLOR,1,cv2.LINE_AA)
        if i < len(points):
            for a,b in SKELETON:
                if scores[i][a]>=threshold and scores[i][b]>=threshold:
                    p=tuple(np.asarray(points[i][a],dtype=int)); q=tuple(np.asarray(points[i][b],dtype=int))
                    cv2.line(frame,p,q,(245,250,250),1,cv2.LINE_AA)
            for p,score in zip(points[i],scores[i]):
                if score>=threshold:
                    p=tuple(np.asarray(p,dtype=int)); cv2.circle(frame,p,2,COLOR,-1,cv2.LINE_AA)
        # Fixed illustrative value per short-term track; not a gait measurement.
        value=[0.6,0.8,0.5,1.0,0.7,0.9][(ids[i]-1)%6]
        label=f'{ids[i]:02d}  |  {value:.1f} / 5'
        size,_=cv2.getTextSize(label,cv2.FONT_HERSHEY_SIMPLEX,.37,1)
        top=max(0,y1-20); left=min(x1,max(0,w-size[0]-12)); right=min(w,left+size[0]+12)
        patch=frame[top:min(h,top+19),left:right]
        if patch.size: frame[top:min(h,top+19),left:right]=cv2.addWeighted(patch,.3,np.full_like(patch,(8,18,18)),.7,0)
        cv2.putText(frame,label,(left+5,top+14),cv2.FONT_HERSHEY_SIMPLEX,.37,(235,255,255),1,cv2.LINE_AA)
    return frame,len(boxes)

upload=st.file_uploader('Choose a cow image or video',type=['jpg','jpeg','png','mp4','mov','avi'])
if upload:
    suffix=Path(upload.name).suffix.lower()
    is_image=suffix in ('.jpg','.jpeg','.png')
    if st.button('RUN ANALYSIS',type='primary'):
        try:
            with st.spinner('Loading models and analyzing your footage…'):
                detector,animal=models()
                with tempfile.TemporaryDirectory() as temp:
                    src=Path(temp)/('input'+suffix); src.write_bytes(upload.getvalue())
                    if is_image:
                        image=cv2.imread(str(src))
                        if image is None: raise ValueError('Could not decode image.')
                        out,count=draw(image,detector,animal,confidence,pose_conf)
                        ok,encoded=cv2.imencode('.png',out)
                        if not ok: raise ValueError('Could not encode result.')
                        st.image(cv2.cvtColor(out,cv2.COLOR_BGR2RGB),caption=f'{count} cow(s) detected · scores simulated')
                        st.download_button('Download annotated image',encoded.tobytes(),'herd-analysis.png','image/png')
                    else:
                        cap=cv2.VideoCapture(str(src))
                        if not cap.isOpened(): raise ValueError('Could not open video.')
                        if end_seconds <= start_seconds: raise ValueError('Video end must be later than video start.')
                        fps=cap.get(cv2.CAP_PROP_FPS) or 25
                        if not np.isfinite(fps) or fps<=0: fps=25
                        w=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); h=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        dest=Path(temp)/'herd-analysis.mp4'
                        writer=cv2.VideoWriter(str(dest),cv2.VideoWriter_fourcc(*'mp4v'),fps,(w,h))
                        if not writer.isOpened(): raise ValueError('Could not create video file on this machine.')
                        cap.set(cv2.CAP_PROP_POS_MSEC, start_seconds * 1000)
                        status=st.empty(); progress=st.progress(0); n=0; limit=max(1, int(fps*(end_seconds-start_seconds)))
                        tracker=Tracker()
                        try:
                            while n<limit:
                                ok,frame=cap.read()
                                if not ok: break
                                annotated,count=draw(frame,detector,animal,confidence,pose_conf,tracker)
                                writer.write(annotated); n+=1
                                if n%5==0:
                                    status.caption(f'Processed {n} frames · {count} cow(s) in latest frame')
                                    progress.progress(min(n/limit,1.0))
                        finally:
                            cap.release(); writer.release()
                        if not n: raise ValueError('The video contains no readable frames.')
                        progress.progress(1.0); status.caption(f'Finished {n} frames · scores simulated')
                        data=dest.read_bytes()
                        st.download_button('Download annotated video',data,'herd-analysis.mp4','video/mp4')
                        st.caption('The downloaded MP4 is the output. Some browsers may not preview the default MP4 codec.')
        except Exception as e:
            st.error(f'Analysis failed: {e}')
