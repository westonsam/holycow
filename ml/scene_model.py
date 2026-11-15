"""Train and run a color-based cattle segmentation model for this demo scene.

Training uses reviewed cow rectangles on frame zero and GrabCut weak masks.
The model is a random forest of pixel colors, accelerated by a color LUT.
It does not recognize species or generalize to arbitrary drone footage.
"""
from pathlib import Path
import argparse
import json

import cv2
import numpy as np
from scipy import ndimage

ROOT = Path(__file__).resolve().parent
ANNOTATIONS = [
    [87,350,157,402],[415,350,473,416],[587,211,639,266],
    [631,213,669,269],[755,188,804,254],[769,315,808,381],
    [761,415,804,490],[959,478,1008,538],[378,515,461,575],
    [285,555,353,619],[176,617,267,683],[751,632,810,701],
    [858,662,901,753],[950,786,1017,869],[2750,970,2818,1061],
    [2073,1161,2180,1229],[1057,1322,1161,1422],[341,1361,420,1483],
    [1203,1471,1315,1555],[1284,1515,1391,1614],[3256,1420,3351,1494],
    [995,1607,1107,1705],[9,1605,107,1708],
]


def color_features(bgr):
    """Color features independent of location; annotations are never used at inference."""
    bgr = np.asarray(bgr,dtype=np.uint8).reshape(-1,1,3)
    lab = cv2.cvtColor(bgr,cv2.COLOR_BGR2LAB).reshape(-1,3)
    hsv = cv2.cvtColor(bgr,cv2.COLOR_BGR2HSV).reshape(-1,3)
    rgb = bgr.reshape(-1,3)
    return np.concatenate([rgb,lab,hsv],axis=1).astype(np.float32)/255


def train(source, destination):
    capture=cv2.VideoCapture(str(source))
    ok, frame=capture.read()
    capture.release()
    if not ok or frame.shape[:2] != (2160,3840):
        raise ValueError('Bundled annotations require the original 3840x2160 demo clip')
    foreground=np.zeros(frame.shape[:2],np.uint8)
    excluded=np.zeros_like(foreground)
    for x1,y1,x2,y2 in ANNOTATIONS:
        padding=20
        left,top=max(0,x1-padding),max(0,y1-padding)
        right,bottom=min(frame.shape[1],x2+padding),min(frame.shape[0],y2+padding)
        crop=frame[top:bottom,left:right].copy()
        rect=(x1-left,y1-top,x2-x1,y2-y1)
        mask=np.zeros(crop.shape[:2],np.uint8)
        cv2.grabCut(crop,mask,rect,np.zeros((1,65)),np.zeros((1,65)),5,cv2.GC_INIT_WITH_RECT)
        local=((mask==cv2.GC_FGD)|(mask==cv2.GC_PR_FGD)).astype(np.uint8)
        foreground[top:bottom,left:right] |= local
        excluded[y1:y2,x1:x2]=1
    rng=np.random.default_rng(42)
    fg=frame[foreground!=0]
    bg=frame[excluded==0]
    fg=fg[rng.choice(len(fg),min(20000,len(fg)),replace=False)]
    bg=bg[rng.choice(len(bg),min(140000,len(bg)),replace=False)]
    features=color_features(np.vstack([fg,bg]))
    labels=np.concatenate([np.ones(len(fg)),np.zeros(len(bg))]).astype(np.int32)
    forest=cv2.ml.RTrees_create()
    forest.setMaxDepth(14)
    forest.setMinSampleCount(10)
    forest.setActiveVarCount(5)
    forest.setTermCriteria((cv2.TERM_CRITERIA_MAX_ITER,32,0))
    cv2.setRNGSeed(42)
    forest.train(features,cv2.ml.ROW_SAMPLE,labels)
    destination.mkdir(parents=True,exist_ok=True)
    forest.save(str(destination/'cattle-pixels.xml'))
    # Quantize each channel to 6 bits, then classify every possible color once.
    values=np.indices((64,64,64)).reshape(3,-1).T.astype(np.uint8)*4+2
    votes=forest.getVotes(color_features(values),0)
    positive=int(np.flatnonzero(votes[0]==1)[0])
    scores=votes[1:,positive]/votes[1:].sum(axis=1)
    np.save(destination/'cattle-color-lut.npy',scores.astype(np.float32).reshape(64,64,64))
    metadata={'model':'OpenCV random forest pixel segmentation','trees':32,'seed':42,
              'features':'BGR, Lab, HSV','training_frame':0,'source':str(Path(source).resolve()),
              'foreground_pixels':len(fg),'background_pixels':len(bg),
              'supervision':'Reviewed rectangles, GrabCut-generated weak masks',
              'limitations':'Scene-specific color model; no species recognition; not a general cattle detector',
              'training_boxes':ANNOTATIONS,'probabilities':'Random-forest vote fractions, not calibrated confidence'}
    (destination/'model.json').write_text(json.dumps(metadata,indent=2))
    out=ROOT/'outputs'
    out.mkdir(exist_ok=True)
    overlay=frame.copy()
    overlay[foreground!=0]=(overlay[foreground!=0]*.5+np.array([60,240,100])*.5).astype(np.uint8)
    cv2.imwrite(str(out/'training-masks.jpg'),cv2.resize(overlay,(1920,1080)))
    cv2.imwrite(str(out/'training-mask.png'),foreground*255)
    print(json.dumps(metadata),flush=True)


class SceneSegmenter:
    def __init__(self, model_dir=None, threshold=.55, min_area=300):
        self.model_dir=Path(model_dir or ROOT/'weights'/'scene-cattle')
        self.lut=np.load(self.model_dir/'cattle-color-lut.npy')
        self.threshold=threshold
        self.min_area=min_area
        self.device='cpu'
        self.previous_centers=[]

    def predict(self, frame):
        b,g,r=cv2.split(frame)
        probabilities=self.lut[b//4,g//4,r//4]
        binary=(probabilities>=self.threshold).astype(np.uint8)
        binary=cv2.morphologyEx(binary,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
        n, labels, stats, _=cv2.connectedComponentsWithStats(binary,8)
        detections=[]
        for label in range(1,n):
            x,y,w,h,area=map(int,stats[label])
            if area < self.min_area or area > 10000 or min(w,h)<4 or max(w,h)>220:
                continue
            if max(w,h)/min(w,h)>6 or area/(w*h)<.12:
                continue
            region=(labels[y:y+h,x:x+w]==label).astype(np.uint8)
            contours,_=cv2.findContours(region,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
            contour=max(contours,key=cv2.contourArea)
            polygon=cv2.approxPolyDP(contour,1,True).reshape(-1,2)+np.array([x,y])
            if len(polygon)<3:
                continue
            score=float(np.mean(probabilities[y:y+h,x:x+w][region!=0]))
            if score < .80:
                continue
            # Separate touching animals using substantial interior cores, then
            # assign the original mask pixels to their nearest core.
            distance=cv2.distanceTransform(region,cv2.DIST_L2,5)
            kernel=max(3,round(float(distance.max())*.9)//2*2+1)
            eroded=cv2.erode(region,np.ones((kernel,kernel),np.uint8))
            seed_n,seeds,seed_stats,_=cv2.connectedComponentsWithStats(eroded,8)
            valid=[i for i in range(1,seed_n) if seed_stats[i,4]>=max(25,area*.05)]
            parts=[region]
            priors=[]
            for cx,cy in self.previous_centers:
                px,py=round(cx)-x,round(cy)-y
                if 0<=px<w and 0<=py<h and region[py,px]:
                    priors.append((px,py))
            if 1 < len(priors) <= 3:
                cores=np.zeros_like(seeds)
                for instance,(px,py) in enumerate(priors,1):
                    cores[py,px]=instance
                nearest=ndimage.distance_transform_edt(cores==0,return_distances=False,return_indices=True)
                assigned=cores[tuple(nearest)]
                parts=[((assigned==instance)&(region!=0)).astype(np.uint8) for instance in range(1,len(priors)+1)]
            elif not priors and 1 < len(valid) <= 3:
                cores=np.zeros_like(seeds)
                for instance,seed in enumerate(valid,1):
                    cores[seeds==seed]=instance
                nearest=ndimage.distance_transform_edt(cores==0,return_distances=False,return_indices=True)
                assigned=cores[tuple(nearest)]
                parts=[((assigned==instance)&(region!=0)).astype(np.uint8) for instance in range(1,len(valid)+1)]
            for part in parts:
                contours,_=cv2.findContours(part,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
                contour=max(contours,key=cv2.contourArea)
                px,py,pw,ph=cv2.boundingRect(contour)
                if pw*ph<self.min_area:
                    continue
                polygon=cv2.approxPolyDP(contour,1,True).reshape(-1,2)+np.array([x,y])
                if len(polygon)<3:
                    continue
                pad=4
                interior=cv2.distanceTransform(part,cv2.DIST_L2,5)
                _,_,_,center=cv2.minMaxLoc(interior)
                detections.append({'box':[max(0,x+px-pad),max(0,y+py-pad),min(frame.shape[1],x+px+pw+pad),min(frame.shape[0],y+py+ph+pad)],
                                   'score':score,'polygon':polygon.tolist(),'mask_area':int(part.sum()),
                                   'mask_center':[x+center[0],y+center[1]]})
        # Join small detached head/leg fragments to the nearby torso.
        # Comparable-sized bodies remain separate, including touching cows.
        merged=[]
        for detection in sorted(detections,key=lambda d:d['mask_area'],reverse=True):
            target=None
            for torso in merged:
                if detection['mask_area'] > torso['mask_area']*.45:
                    continue
                a,b=detection['box'],torso['box']
                dx=max(a[0]-b[2],b[0]-a[2],0)
                dy=max(a[1]-b[3],b[1]-a[3],0)
                distance=np.linalg.norm(np.array(detection['mask_center'])-torso['mask_center'])
                if np.hypot(dx,dy)<=8 and distance < max(b[2]-b[0],b[3]-b[1])*.95:
                    target=torso
                    break
            if target is None:
                merged.append(detection)
            else:
                a,b=target['box'],detection['box']
                target['box']=[min(a[0],b[0]),min(a[1],b[1]),max(a[2],b[2]),max(a[3],b[3])]
                target['polygon']=cv2.convexHull(np.array(target['polygon']+detection['polygon'],np.int32)).reshape(-1,2).tolist()
                target['mask_area']+=detection['mask_area']
        detections=merged
        self.previous_centers=[d['mask_center'] for d in detections]
        return detections


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path)
    p.add_argument('--model-dir',type=Path,default=ROOT/'weights'/'scene-cattle')
    a=p.parse_args()
    train(a.source,a.model_dir)
