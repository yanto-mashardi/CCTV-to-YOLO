import math

class Counter:
    """Finite line crossing with hysteresis; one inbound event per track/session."""
    def __init__(self, line, entry, margin=0.012, max_gap=2.5):
        self.a, self.b = line
        self.entry = entry
        self.margin = margin
        self.max_gap = max_gap
        self.tracks = {}
        self.counted = set()
        self.dx = self.b[0]-self.a[0]
        self.dy = self.b[1]-self.a[1]
        self.length = math.hypot(self.dx,self.dy)
        if not self.length or entry not in ("negative_to_positive","positive_to_negative"):
            raise ValueError("Invalid line or entry direction")
    def update(self, track, point, now):
        d = (self.dx*(point[1]-self.a[1])-self.dy*(point[0]-self.a[0]))/self.length
        side = 1 if d>self.margin else -1 if d < -self.margin else 0
        old = self.tracks.get(track)
        if old and now-old[3]>self.max_gap:
            old=None
            self.tracks.pop(track,None)
        if side==0:
            return False
        self.tracks[track]=(side,point,d,now)
        if not old or old[0]==side or track in self.counted:
            return False
        if (old[0],side) != ((-1,1) if self.entry=="negative_to_positive" else (1,-1)):
            return False
        t=old[2]/(old[2]-d)
        x=old[1][0]+t*(point[0]-old[1][0])
        y=old[1][1]+t*(point[1]-old[1][1])
        u=((x-self.a[0])*self.dx+(y-self.a[1])*self.dy)/(self.length**2)
        if 0<=u<=1:
            self.counted.add(track)
            return True
        return False
