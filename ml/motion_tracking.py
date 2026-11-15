# Spatial tracker adapted from the user-supplied motion prototype.
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
