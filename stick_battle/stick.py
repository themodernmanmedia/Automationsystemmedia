import math, random, sys, os, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
WW,H,SS,OW,OH=1800,1920,2,1080,1920
GY=1300
FD=os.path.dirname(os.path.abspath(__file__))+"/../fonts/"
def font(sz): return ImageFont.truetype(FD+"PermanentMarker-Regular.ttf",int(sz*SS))
BLUE=(36,58,150);RED=(204,48,44);PEN=(120,118,128);INK=(40,36,48);LB=(70,120,200);STEEL=(90,96,110);BRN=(120,78,48);WHT=(250,248,240)
def cl(x): return max(0.0,min(1.0,x))
def ez(x): x=cl(x); return x*x*(3-2*x)
def lerp(a,b,u): return a+(b-a)*u
def kf(t,keys,e=ez):
    if t<=keys[0][0]: return keys[0][1]
    for (t0,v0),(t1,v1) in zip(keys,keys[1:]):
        if t<t1: return lerp(v0,v1,e((t-t0)/(t1-t0)))
    return keys[-1][1]
def pop(t,t0,d=0.25):
    x=(t-t0)/d
    if x<=0: return 0
    if x>=1: return 1
    return ez(x/0.6) if x<0.6 else 1+0.3*math.sin((x-0.6)/0.4*math.pi)
class Cv:
    def __init__(s,bg,seed): s.im=bg.copy(); s.d=ImageDraw.Draw(s.im); s.r=random.Random(seed)
    def jit(s,pts,amp,closed=False):
        if closed: pts=list(pts)+[pts[0]]
        out=[]
        for (x0,y0),(x1,y1) in zip(pts,pts[1:]):
            k=max(1,int(math.hypot(x1-x0,y1-y0)/30))
            for i in range(k): out.append((lerp(x0,x1,i/k),lerp(y0,y1,i/k)))
        out.append(pts[-1]); return [(x+s.r.gauss(0,amp),y+s.r.gauss(0,amp)) for x,y in out]
    def line(s,pts,w=6,col=INK,amp=1.5,closed=False):
        q=[(x*SS,y*SS) for x,y in s.jit(pts,amp,closed)]
        s.d.line(q,fill=col,width=max(1,int(w*SS)),joint="curve"); r=w*SS/2
        for x,y in (q[0],q[-1]): s.d.ellipse((x-r,y-r,x+r,y+r),fill=col)
    def poly(s,pts,fill,w=5,out=INK,amp=1.5):
        p=s.jit(pts,amp,True)
        if fill: s.d.polygon([(x*SS,y*SS) for x,y in p],fill=fill)
        if out and w: s.line(pts,w,out,amp,closed=True)
    def circ(s,cx,cy,r,fill=None,w=5,out=INK,amp=1.3,ry=None):
        ry=ry or r; n=max(10,int(r/4)+8)
        s.poly([(cx+r*math.cos(i/n*6.283),cy+ry*math.sin(i/n*6.283)) for i in range(n)],fill,w,out,amp)
    def text(s,x,y,t,size,col,rot=0,scale=1.0):
        if scale*size<4: return
        fo=font(size*scale); bb=s.d.textbbox((0,0),t,font=fo); pad=20
        im=Image.new("RGBA",(int(bb[2]-bb[0]+2*pad),int(bb[3]-bb[1]+2*pad)),(0,0,0,0)); ImageDraw.Draw(im).text((pad-bb[0],pad-bb[1]),t,font=fo,fill=col)
        im=im.rotate(rot+s.r.gauss(0,0.5),expand=True,resample=Image.BICUBIC)
        s.im.paste(im,(int(x*SS+s.r.gauss(0,2)-im.width/2),int(y*SS-im.height/2)),im)
# ---------- background ----------
def make_bg():
    rs=np.random.RandomState(5); n=rs.normal(0,2.0,(H*SS,WW*SS))
    im=Image.fromarray(np.clip(np.stack([250+n,247+n,236+n],-1),0,255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1))
    c=Cv(im,11)
    for y in range(110,H,66): c.line([(0,y),(WW,y)],2,(168,196,226),0.4)
    c.line([(150,0),(150,H)],3,(226,150,150),0.5)
    c.circ(330,300,70,None,5,PEN)
    for i in range(10): a=i*0.628; c.line([(330+95*math.cos(a),300+95*math.sin(a)),(330+135*math.cos(a),300+135*math.sin(a))],4,PEN)
    for cx,cy in((760,420),(1280,300),(1620,520)):
        for dx,r in((-70,45),(0,62),(72,48)): c.circ(cx+dx,cy-(r-45),r,(250,247,236),4,PEN)
        c.line([(cx-120,cy+42),(cx+124,cy+44)],4,PEN)
    c.line([(0,GY-120),(260,GY-260),(520,GY-150),(840,GY-300),(1160,GY-170),(1480,GY-280),(1800,GY-140)],4,PEN,3)
    for x,col in((60,BLUE),(1700,RED)):
        c.poly([(x-55,GY),(x-55,GY-330),(x+55,GY-330),(x+55,GY)],(250,247,236),5,PEN)
        for i in range(3): c.poly([(x-55+i*40,GY-330),(x-55+i*40,GY-365),(x-25+i*40,GY-365),(x-25+i*40,GY-330)],(250,247,236),4,PEN)
        c.line([(x,GY-365),(x,GY-480)],5,PEN); c.poly([(x,GY-480),(x+(70 if x<900 else -70),GY-455),(x,GY-430)],col,4,col)
        c.poly([(x-22,GY),(x-22,GY-80),(x+22,GY-80),(x+22,GY)],PEN,0,None)
    for i in range(34):
        x=40+i*53+rs.randint(-12,12)
        for dx in(-8,0,9): c.line([(x,GY+6),(x+dx,GY-14-rs.randint(0,10))],3,(110,150,100),0.6)
    return c.im
# ---------- poses ----------
P=lambda **k:k
POSE={
"idle":P(tor=5,a1=35,a2=55,wp=60,b1=-20,b2=15,l1=14,l2=-8,m1=-14,m2=-8),
"windup":P(tor=-12,a1=150,a2=40,wp=30,b1=50,b2=30,l1=25,l2=-15,m1=-25,m2=-20),
"slash":P(tor=28,a1=45,a2=0,wp=0,b1=-50,b2=-20,l1=50,l2=-55,m1=-40,m2=-10),
"upslash":P(tor=-8,a1=150,a2=10,wp=0,b1=-30,b2=-20,l1=20,l2=-5,m1=-20,m2=-5),
"duck":P(tor=45,a1=30,a2=60,wp=60,b1=20,b2=40,l1=75,l2=-130,m1=-10,m2=-95),
"tuck":P(tor=40,a1=60,a2=80,wp=40,b1=60,b2=80,l1=100,l2=-120,m1=90,m2=-120),
"kick":P(tor=-25,a1=-30,a2=-20,wp=100,b1=-60,b2=-10,l1=95,l2=0,m1=-5,m2=-10),
"block":P(tor=-5,a1=60,a2=30,wp=80,b1=30,b2=40,l1=20,l2=-15,m1=-25,m2=-15),
"hit":P(tor=-30,a1=120,a2=20,wp=40,b1=-100,b2=-20,l1=30,l2=-10,m1=-5,m2=-40),
"rag":P(tor=-20,a1=150,a2=20,wp=0,b1=-140,b2=-30,l1=60,l2=-50,m1=-50,m2=-60),
"cheer":P(tor=0,a1=165,a2=10,wp=0,b1=-165,b2=-10,l1=14,l2=-8,m1=-14,m2=-8),
"thwind":P(tor=-22,a1=170,a2=30,wp=20,b1=60,b2=20,l1=25,l2=-10,m1=-30,m2=-25),
"thend":P(tor=32,a1=70,a2=0,wp=0,b1=-40,b2=-20,l1=45,l2=-50,m1=-40,m2=-10),
"bowdraw":P(tor=-3,a1=90,a2=0,wp=0,b1=90,b2=100,l1=18,l2=-8,m1=-18,m2=-8),
"bowrel":P(tor=0,a1=90,a2=0,wp=0,b1=55,b2=50,l1=18,l2=-8,m1=-18,m2=-8),
"clubup":P(tor=-15,a1=165,a2=15,wp=0,b1=150,b2=20,l1=20,l2=-10,m1=-25,m2=-10),
"stiff":P(tor=0,a1=150,a2=10,wp=0,b1=-150,b2=-10,l1=6,l2=-2,m1=-6,m2=-2),
"clubdown":P(tor=40,a1=55,a2=0,wp=-5,b1=50,b2=0,l1=45,l2=-50,m1=-35,m2=-5),
}
def run(ph,amp=1.0):
    s=math.sin(ph); c_=math.cos(ph)
    return P(tor=18*amp+2,a1=20-50*s*amp,a2=60,wp=60,b1=50*s*amp,b2=50,l1=45*s*amp,l2=-(20+45*max(0,c_))*amp-5,m1=-45*s*amp,m2=-(20+45*max(0,-c_))*amp-5)
def blend(a,b,u): return {k:lerp(a[k],b[k],u) for k in a}
def pk(t,keys,runf=11,ramp=1.0):
    def g(n): return run(t*runf,ramp) if n=="run" else POSE[n]
    if t<=keys[0][0]: return g(keys[0][1])
    for (t0,n0),(t1,n1) in zip(keys,keys[1:]):
        if t<t1: return blend(g(n0),g(n1),ez((t-t0)/(t1-t0)))
    return g(keys[-1][1])
L_T,L_A,L_L,HR=62,31,37,19
def stick(c,st,col,t):
    s=st.get("s",1.6); f=st["face"]; p=st["pose"]; w=5.6*s
    V=lambda a,l:(f*math.sin(math.radians(a))*l*s,math.cos(math.radians(a))*l*s)
    def add(a,b): return (a[0]+b[0],a[1]+b[1])
    hip=(0,0); knL=add(hip,V(p["l1"],L_L)); ftL=add(knL,V(p["l1"]+p["l2"],L_L)); knM=add(hip,V(p["m1"],L_L)); ftM=add(knM,V(p["m1"]+p["m2"],L_L))
    tv=V(180-p["tor"],L_T); neck=add(hip,tv); n=math.hypot(*tv); head=add(neck,(tv[0]/n*HR*s,tv[1]/n*HR*s))
    elA=add(neck,V(p["a1"],L_A)); hdA=add(elA,V(p["a1"]+p["a2"],L_A)); elB=add(neck,V(p["b1"],L_A)); hdB=add(elB,V(p["b1"]+p["b2"],L_A))
    pts=dict(hip=hip,knL=knL,ftL=ftL,knM=knM,ftM=ftM,neck=neck,head=head,elA=elA,hdA=hdA,elB=elB,hdB=hdB)
    wa=p["a1"]+p["a2"]+p["wp"]; wl={"sword":74,"club":105}.get(st.get("weapon"),0)
    if wl: pts["tip"]=add(hdA,V(wa,wl)); pts["grd"]=add(hdA,V(wa,10))
    rot=math.radians(st.get("rot",0))
    if rot:
        cr,sr=math.cos(rot),math.sin(rot); ctr=((neck[0])/2,(neck[1])/2)
        pts={k:(ctr[0]+(x-ctr[0])*cr-(y-ctr[1])*sr,ctr[1]+(x-ctr[0])*sr+(y-ctr[1])*cr) for k,(x,y) in pts.items()}
    low=max(pts["ftL"][1],pts["ftM"][1]) if not st.get("free") else L_L*2*s*0.9
    ox,oy=st["x"],GY-low-st.get("air",0)
    pts={k:(x+ox,y+oy) for k,(x,y) in pts.items()}
    rf=math.radians(st.get("rotfeet",0))
    if rf:
        cr,sr=math.cos(rf),math.sin(rf); px,py=st["x"],GY
        pts={k:(px+(x-px)*cr-(y-py)*sr,py+(x-px)*sr+(y-py)*cr) for k,(x,y) in pts.items()}
    g=pts
    c.line([g["hip"],g["knM"],g["ftM"]],w,col,1.2); c.line([g["neck"],g["elB"],g["hdB"]],w,col,1.2)
    c.line([g["hip"],g["neck"]],w*1.1,col,1.2); c.line([g["hip"],g["knL"],g["ftL"]],w,col,1.2)
    wpn=st.get("weapon")
    if wpn=="sword":
        c.line([g["hdA"],g["tip"]],w*0.8,STEEL,0.8); dx,dy=g["tip"][0]-g["hdA"][0],g["tip"][1]-g["hdA"][1]; q=math.hypot(dx,dy) or 1
        c.line([(g["grd"][0]-dy/q*11*s,g["grd"][1]+dx/q*11*s),(g["grd"][0]+dy/q*11*s,g["grd"][1]-dx/q*11*s)],w*0.8,INK,0.6)
    elif wpn=="club":
        c.line([g["hdA"],g["tip"]],w*2.6,BRN,1.5); c.circ(g["tip"][0],g["tip"][1],w*2.0,BRN,3,INK)
    elif wpn=="bow":
        hx,hy=g["hdA"]; r=42*s; pull=st.get("pull",0)
        arc=[(hx+f*(r*0.45*math.cos(a)-r*0.2),hy+r*math.sin(a)) for a in [(-1.25+i*0.25) for i in range(11)]]
        c.line(arc,w*0.7,BRN,0.8); c.line([arc[0],(hx-f*(r*0.2+pull*40*s),hy),arc[-1]],2.5,INK,0.5)
        if pull>0.2: c.line([(hx-f*(r*0.2+pull*40*s),hy),(hx+f*50*s,hy)],3,INK,0.5)
    c.line([g["neck"],g["elA"],g["hdA"]],w,col,1.2)
    hx,hy=g["head"]; c.circ(hx,hy,HR*s,col,3,col,1.0)
    c.line([(hx+f*5*s,hy-4*s),(hx+f*14*s,hy-1*s)],3.2*s,WHT,0.4)
    if st.get("band"):
        c.line([(hx-f*HR*s*0.95,hy-7*s),(hx+f*HR*s*0.95,hy-9*s)],4*s,WHT,0.5)
        for k in(0,1): c.line([(hx-f*HR*s,hy-8*s),(hx-f*(HR+16)*s,hy-(4-k*14)*s+4*s*math.sin(t*14+k)),(hx-f*(HR+34)*s,hy-(8-k*16)*s+7*s*math.sin(t*14+k+1))],3*s,WHT,0.6)
    if st.get("spikes"):
        for a in(-0.6,0,0.6): c.line([(hx+HR*s*math.sin(a),hy-HR*s*math.cos(a)),(hx+(HR+13)*s*math.sin(a),hy-(HR+13)*s*math.cos(a))],3.4*s,col,0.5)
    return g
# ---------- choreography ----------
def rag(t,t0,x0,vx,vy=1250,grav=1500,face=-1,**k):
    d=t-t0; return dict(x=x0+vx*d,air=110+vy*d-grav*d*d,rot=d*900*(1 if vx>0 else -1),face=face,pose=POSE["rag"],free=True,weapon=None,**k)
def hero(t):
    x=kf(t,[(0,300),(2.2,300),(2.9,440),(4.45,440),(5.25,660),(12.2,660),(12.75,612),(13.55,560),(13.9,330),(14.1,330),(14.5,500),(15.0,753),(15.6,920),(16.05,985),(16.35,1150),(16.8,1220),(19.0,1220),(19.9,850)],lambda u:u)
    air=kf(t,[(4.45,0),(4.85,270),(5.25,0),(13.55,0),(13.72,95),(13.9,0),(14.5,0),(15.0,225),(15.6,440),(16.05,720),(16.35,260),(16.75,0)],lambda u:u)
    if 4.45<t<5.25: u=(t-4.45)/0.8; air=270*4*u*(1-u)
    if 15.6<t<16.05: u=(t-15.6)/0.45; air=440+280*(1-(1-u)**2)
    rot=kf(t,[(4.5,0),(5.2,360),(5.21,0),(14.55,0),(14.65,-28),(15.55,-28),(15.65,0),(16.05,360),(16.06,0)],lambda u:u)
    pose=pk(t,[(0,"idle"),(2.2,"idle"),(2.3,"run"),(2.88,"run"),(3.0,"idle"),(3.12,"duck"),(3.5,"duck"),(3.6,"upslash"),(3.9,"upslash"),(4.1,"idle"),(4.4,"duck"),(4.55,"tuck"),(5.12,"tuck"),(5.25,"duck"),(5.4,"kick"),(5.55,"kick"),(5.64,"windup"),(5.75,"slash"),(5.95,"slash"),(6.15,"idle"),(6.55,"idle"),(6.66,"block"),(6.86,"block"),(6.93,"windup"),(7.0,"slash"),(7.25,"slash"),(7.5,"idle"),(8.24,"idle"),(8.3,"windup"),(8.36,"slash"),(8.6,"idle"),(8.96,"duck"),(9.06,"upslash"),(9.3,"idle"),(9.5,"duck"),(9.78,"duck"),(9.92,"thwind"),(10.08,"thwind"),(10.16,"thend"),(10.5,"thend"),(10.8,"idle"),(11.25,"idle"),(11.5,"hit"),(12.15,"hit"),(12.25,"run"),(12.7,"run"),(12.82,"duck"),(13.0,"idle"),(13.5,"idle"),(13.6,"tuck"),(13.85,"tuck"),(13.95,"duck"),(14.1,"run"),(15.55,"run"),(15.66,"tuck"),(15.98,"tuck"),(16.06,"windup"),(16.22,"windup"),(16.3,"slash"),(16.65,"slash"),(16.85,"duck"),(17.3,"duck"),(17.6,"idle"),(19.0,"idle"),(19.08,"run"),(19.85,"run"),(19.95,"idle"),(20.25,"idle"),(20.4,"cheer")],runf=14)
    face=-1 if (5.58<t<6.0 or t>16.6 and t<20.0 or 12.2<t<12.9) else 1
    if t>20.4: air=abs(math.sin((t-20.4)*7))*38
    return dict(x=x,air=air,rot=rot,face=face,pose=pose,weapon=None if 10.12<t<12.8 else "sword",band=True)
def reds(t):
    out=[]
    if t<3.6: out.append(dict(x=kf(t,[(1.0,1900),(2.6,560)],lambda u:u),face=-1,pose=pk(t,[(1.0,"run"),(2.55,"run"),(2.7,"idle"),(2.95,"windup"),(3.2,"slash"),(3.5,"slash")]),weapon="sword",spikes=True))
    elif t<5.4: out.append(rag(t,3.6,560,620,spikes=True))
    if t<5.75:
        tb=abs(math.sin(t*8))*18 if 2.9<t<4.0 else 0
        out.append(dict(x=kf(t,[(1.2,2050),(2.8,820),(4.0,820),(4.6,570)],lambda u:u),air=tb,face=-1 if t<5.45 else 1,pose=pk(t,[(1.2,"run"),(2.75,"run"),(2.9,"cheer"),(3.9,"cheer"),(4.0,"run"),(4.42,"run"),(4.5,"windup"),(4.62,"slash"),(4.95,"slash"),(5.2,"idle"),(5.5,"windup")]),weapon="sword",spikes=True))
    elif t<7.6: out.append(rag(t,5.75,570,-640,spikes=True))
    if t<7.0:
        tb=abs(math.sin(t*8+1))*18 if 3.1<t<4.0 else 0
        out.append(dict(x=kf(t,[(1.4,2150),(3.0,980),(4.0,980),(4.7,790),(5.4,790),(5.75,1000),(6.1,1000),(6.5,790)],lambda u:u),air=tb,face=-1,pose=pk(t,[(1.4,"run"),(2.95,"run"),(3.1,"cheer"),(3.9,"cheer"),(4.0,"run"),(4.65,"run"),(4.8,"idle"),(5.38,"idle"),(5.44,"hit"),(5.95,"hit"),(6.1,"run"),(6.45,"run"),(6.55,"windup"),(6.7,"slash"),(6.95,"slash")]),weapon="sword",spikes=True))
    elif t<8.8: out.append(rag(t,7.0,790,640,spikes=True))
    if 6.3<t<10.4:
        pull=max(kf(t,[(7.7,0),(7.9,1),(8.0,1),(8.03,0)]),kf(t,[(8.4,0),(8.6,1),(8.7,1),(8.73,0)]),kf(t,[(9.0,0),(9.2,1),(9.3,1),(9.33,0)]))
        out.append(dict(x=kf(t,[(6.3,1950),(7.6,1100)],lambda u:u),face=-1,pose=pk(t,[(6.3,"run"),(7.55,"run"),(7.7,"bowrel"),(7.9,"bowdraw"),(8.0,"bowdraw"),(8.04,"bowrel"),(8.4,"bowrel"),(8.6,"bowdraw"),(8.7,"bowdraw"),(8.74,"bowrel"),(9.0,"bowrel"),(9.2,"bowdraw"),(9.3,"bowdraw"),(9.34,"bowrel"),(10.05,"bowrel"),(10.2,"hit")]),weapon="bow",pull=pull,spikes=True))
    elif 10.4<=t<12.2: out.append(rag(t,10.4,1100,560,spikes=True))
    if 10.9<t<18.75:
        g=dict(x=kf(t,[(10.9,2150),(13.0,1050)],lambda u:u),face=-1,s=5.4,weapon="club",spikes=True,
               pose=pk(t,[(10.9,"run"),(12.95,"run"),(13.1,"clubup"),(13.62,"clubup"),(13.8,"clubdown"),(15.7,"clubdown"),(16.1,"idle"),(16.3,"hit"),(17.1,"hit"),(17.6,"stiff")],runf=5.2,ramp=0.55),
               rotfeet=-88*cl((t-17.2)/1.0)**2.2+(4*math.sin((t-16.4)*9) if 16.4<t<17.2 else 0))
        out.append(g)
    return out
def allies(t):
    out=[]
    for i,xf in enumerate((420,560,690)):
        if t>19.2+i*0.15:
            x=kf(t,[(19.2+i*0.15,-120-i*60),(20.3+i*0.15,xf)],lambda u:u); mv=t<20.3+i*0.15
            out.append(dict(x=x,face=1,s=1.45,air=0 if mv else abs(math.sin(t*7+i*1.3))*34,pose=run(t*14+i) if mv else POSE["cheer"],weapon="sword"))
    return out
HITS=[(3.6,.09),(5.42,.06),(5.75,.09),(6.7,.04),(7.0,.09),(8.36,.04),(9.06,.04),(10.4,.1),(13.8,.14),(16.3,.32),(18.2,.12)]
def t_anim(tv):
    for th,fz in HITS:
        if tv<th: return tv
        if tv<th+fz: return th
        tv-=fz
    return tv
def t_video(ta): return ta+sum(fz for th,fz in HITS if th<ta)
END=24.2; VLEN=END+sum(f for _,f in HITS)
SHAKES=[(3.6,10),(5.42,6),(5.75,10),(6.7,5),(7.0,10),(10.4,10),(11.3,7),(11.9,9),(12.5,11),(13.0,13),(13.8,34),(16.3,30),(18.2,40)]
STARS=[(3.6,520,GY-200,RED),(5.42,770,GY-190,RED),(5.75,590,GY-210,RED),(6.7,725,GY-250,(240,180,40)),(7.0,760,GY-200,RED),(8.36,720,GY-240,(240,180,40)),(9.06,715,GY-250,(240,180,40)),(10.4,1095,GY-200,RED),(16.3,1040,GY-470,RED)]
SLASH=[(3.6,455,GY-185,1,-1),(5.75,645,GY-195,-1,1),(7.0,675,GY-195,1,1),(8.36,675,GY-200,1,1),(9.06,675,GY-200,1,-1),(16.3,1075,GY-430,1,1)]
def fx(c,t):
    for t0,x,y,col in STARS:
        d=t-t0
        if 0<=d<0.22:
            r=40+d*520
            for i in range(10): a=i*0.628+t0; c.line([(x+r*0.45*math.cos(a),y+r*0.45*math.sin(a)),(x+r*math.cos(a),y+r*math.sin(a))],7,col,1)
            c.circ(x,y,r*0.3,WHT,5,col)
    for t0,x,y,f,dr in SLASH:
        d=t-t0
        if -0.05<=d<0.14:
            big=2.3 if t0>16 else 1.0; R=120*big
            arc=[(x+f*R*math.cos(a),y+dr*R*math.sin(a)) for a in [(-1.25+i*0.21) for i in range(13)]]
            inner=[(x+f*R*0.72*math.cos(a)+f*10,y+dr*R*0.8*math.sin(a)) for a in [(-1.25+i*0.21) for i in range(13)]]
            c.poly(arc+inner[::-1],(200,220,250),4,LB,1.2)
    for t0,x in ((13.8,500),(18.2,700),(18.2,460),(18.2,900),(5.25,660),(16.8,1220)):
        d=t-t0
        if 0<=d<0.6:
            n=7 if t0 in(13.8,18.2) else 3
            for i in range(n):
                sx=(i-(n-1)/2)*60*(1+d*2.5); r=(22+i%3*10)*(1+d*2.2)*(1.6 if n==7 else 0.8)
                if d<0.45 or i%2: c.circ(x+sx,GY-r*0.6-d*60,r,None,4,PEN)
    if 13.8<=t<19:
        for i in range(5): c.line([(500,GY+4),(500+(i-2)*45,GY+50+abs(i-2)*-10+40)],4,INK,2)
    if 18.25<t<19.0:
        d=t-18.25
        for i in range(9):
            x=420+i*75; r=(60+(i*37)%40)*(1+d*1.2)*(1-d/0.9*0.3)
            pts=[(x+r*math.cos(a*1.7)+c.r.gauss(0,8),GY-90-d*120+r*0.7*math.sin(a*2.3)) for a in range(9)]
            c.line(pts,5,RED if i%2 else PEN,3)
def arrows(c,t):
    def arrow(x,y,ang):
        dx,dy=math.cos(ang)*46,math.sin(ang)*46
        c.line([(x-dx,y-dy),(x+dx,y+dy)],4,INK,0.5); c.line([(x-dx,y-dy),(x-dx+12*math.cos(ang+0.6),y-dy+12*math.sin(ang+0.6))],4,INK,0.4); c.line([(x-dx,y-dy),(x-dx+12*math.cos(ang-0.6),y-dy+12*math.sin(ang-0.6))],4,INK,0.4)
        c.line([(x+dx,y+dy),(x+dx+14*math.cos(ang+0.5),y+dy+14*math.sin(ang+0.5))],3,RED,0.4); c.line([(x+dx,y+dy),(x+dx+14*math.cos(ang-0.5),y+dy+14*math.sin(ang-0.5))],3,RED,0.4)
    for t0,defl in((8.02,True),(8.72,True),(9.32,False)):
        d=t-t0
        if d<0: continue
        y0=GY-215
        if d<0.34 or not defl:
            x=1040-d*1060
            if x>-100: arrow(x,y0,0)
        elif d<1.3:
            e=d-0.34; arrow(700-e*260,y0-e*900+e*e*1100,e*22)
    if 10.12<t<=10.4: u=(t-10.12)/0.28; x,y,a=lerp(720,1090,u),GY-215,u*25
    elif 10.4<t<11.2: u=(t-10.4)/0.8; x,y,a=lerp(1090,612,u),GY-215-640*4*u*(1-u)+175*u,25+u*18.85
    elif 11.2<=t<12.8: x,y,a=612,GY-40,1.5708
    else: return
    dx,dy=math.cos(a)*40,math.sin(a)*40; c.line([(x-dx,y-dy),(x+dx,y+dy)],7,STEEL,0.6)
    c.line([(x-dx*0.6-dy*0.3,y-dy*0.6+dx*0.3),(x-dx*0.6+dy*0.3,y-dy*0.6-dx*0.3)],7,INK,0.5)
BG=None
def render(tv,seed):
    global BG
    if BG is None: BG=make_bg()
    t=t_anim(tv); c=Cv(BG,seed)
    c.line([(0,GY+8),(WW,GY+10)],6,INK,2.2)
    for st in allies(t): stick(c,st,LB,t)
    for st in reds(t): stick(c,st,RED,t)
    arrows(c,t); stick(c,hero(t),BLUE,t); fx(c,t)
    if 0.3<t<2.6: c.text(620,640,"DOODLE WAR",150,INK,-4,pop(t,0.3)*(1 if t<2.3 else max(0,1-(t-2.3)/0.3)))
    if t>20.5: c.text(700,560,"VICTORY!",170,BLUE,-5,pop(t,20.5))
    if t>22.2:
        c.text(700,760,"to be continued...",70,RED,2,pop(t,22.2))
        for i in range(4): c.circ(1500+i*70,GY-130-(i%2)*50,12,RED,2,RED) if int(t*3+i)%4 else None
    z=kf(t,[(0,1.0),(1.2,1.0),(2.2,1.6),(7.4,1.6),(7.9,1.3),(10.7,1.3),(11.4,1.05),(15.5,1.05),(16.0,1.2),(16.8,1.05),(19.4,1.05),(20.6,1.25)])
    cx=kf(t,[(0,560),(2.5,480),(3.6,520),(4.6,560),(5.3,680),(6.1,720),(7.4,730),(8.0,880),(10.7,880),(11.6,860),(13.0,780),(14.0,740),(15.6,860),(16.5,1040),(18.2,800),(19.9,700),(24,690)])
    cy=kf(t,[(0,960),(2.2,GY-250),(7.4,GY-250),(8.0,GY-300),(10.7,GY-300),(11.4,GY-420),(19.4,GY-420),(20.6,GY-380)])
    sh=sum(a*math.exp(-(t-t0)*9) for t0,a in SHAKES if t>=t0 and t-t0<0.6)
    w,h=OW/z,OH/z; x=cx-w/2+random.uniform(-sh,sh); y=cy-h/2+random.uniform(-sh,sh)
    x=max(0,min(x,WW-w-0.01)); y=max(0,min(y,H-h-0.01))
    return c.im.resize((OW,OH),Image.BILINEAR,box=(x*SS,y*SS,(x+w)*SS,(y+h)*SS),reducing_gap=2.0)
def audio():
    import soundfile as sf
    sr=44100; N=int(VLEN*sr); rng=np.random.default_rng(4); out=np.zeros(N)
    def put(t0,y,g=1.0):
        s=int(t0*sr)
        if s<0 or s>=N: return
        y=np.asarray(y)[:N-s]; out[s:s+len(y)]+=y*g
    def tt(d): return np.arange(int(d*sr))/sr
    class A(np.ndarray):
        def __add__(s,o):
            if isinstance(o,np.ndarray) and len(o)!=len(s):
                n=max(len(s),len(o)); x=np.zeros(n); x[:len(s)]+=np.asarray(s); x[:len(o)]+=np.asarray(o); return x.view(A)
            return np.add(np.asarray(s),np.asarray(o)).view(A)
        __radd__=__add__
    def kick(): q=tt(0.25); return (np.sin(2*np.pi*(50*q+40*(1-np.exp(-q*30))/30*8))*np.exp(-q*14)).view(A)
    def noise(d,dec,hp=0.0):
        q=tt(d); n=rng.standard_normal(len(q))
        if hp: n=n-np.convolve(n,np.ones(int(hp))/hp,"same")
        return (n*np.exp(-q*dec)).view(A)
    def tone(f,d,dec=6,sq=False):
        q=tt(d); y=np.sin(2*np.pi*f*q); y=np.sign(y)*0.5 if sq else y; return (y*np.exp(-q*dec)).view(A)
    def whoosh(d=0.22):
        q=tt(d); n=rng.standard_normal(len(q)); k=40; n=np.convolve(n,np.ones(k)/k,"same"); return n*np.sin(np.pi*q/d)**2*3
    bpm=150; b=60/bpm; riff=[55,55,65.4,55,73.4,55,82.4,73.4]
    i=0; t0=0.0
    while t0<VLEN-0.3:
        quiet=0.45 if (t0<t_video(1.0) or t0>t_video(19.2)) else 1.0
        if i%2==0: put(t0,kick(),0.55*quiet)
        if i%4==2: put(t0,noise(0.16,26,30),0.22*quiet)
        put(t0,noise(0.04,90,6),0.07*quiet)
        put(t0,tone(riff[i%8]*2,b*0.5,7,True),0.10*quiet)
        if i%8 in(0,3,6): put(t0,tone(riff[i%8]*8,0.18,12),0.05*quiet)
        i+=1; t0+=b/2
    V=t_video
    for th in (3.2,3.55,4.6,5.7,6.68,6.95,8.32,9.02,10.12,13.72,16.2): put(V(th)-0.06,whoosh(),0.5)
    for th in (3.6,5.42,5.75,7.0,10.4): put(V(th),tone(120,0.25,16)+noise(0.12,40,20)*0.6,0.9)
    for th in (6.7,8.36,9.06): put(V(th),tone(1900,0.3,14)+tone(2630,0.3,16)+tone(3410,0.2,22),0.22)
    for th in (8.02,8.72,9.32): put(V(th),tone(240,0.18,20)+noise(0.05,60,10)*0.4,0.4)
    for th,g in ((11.3,.6),(11.9,.75),(12.5,.9),(13.0,1.0)): put(V(th),tone(45,0.5,7)+noise(0.2,25)*0.3,g*0.9)
    for th in (13.8,18.2): put(V(th),tone(38,0.9,4)*1.4+noise(0.5,9)*0.7,1.2)
    put(V(16.3),tone(90,0.6,6)+noise(0.4,10,25)+tone(1500,0.5,8)*0.3,1.3)
    put(V(11.2),tone(700,0.12,30),0.3)
    for k,f in enumerate((392,494,587,784,784)): put(V(20.5)+k*0.14,tone(f,0.5 if k<4 else 1.2,3.5,True)+tone(f*2,0.4,5)*0.3,0.28)
    out=np.tanh(out*1.3)*0.85; sf.write("mix.wav",out,sr)
if __name__=="__main__":
    if sys.argv[1]=="sheet":
        ts=[float(x) for x in sys.argv[2:]]; cols=8; rows=(len(ts)+cols-1)//cols
        sh=Image.new("RGB",(216*cols,384*rows))
        for k,t in enumerate(ts): sh.paste(render(t_video(t)+0.001,k).resize((216,384)),((k%cols)*216,(k//cols)*384))
        sh.save("sheet.jpg",quality=88)
    else:
        audio()
        p=subprocess.Popen(["ffmpeg","-y","-loglevel","error","-f","rawvideo","-pix_fmt","rgb24","-s","1080x1920","-r","24","-i","-","-c:v","libx264","-crf","19","-preset","medium","-pix_fmt","yuv420p","video.mp4"],stdin=subprocess.PIPE)
        for f in range(int(VLEN*24)): p.stdin.write(render(f/24,(f//2)*7919+1).tobytes())
        p.stdin.close(); p.wait()
