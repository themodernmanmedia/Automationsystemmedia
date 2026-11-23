import math, random, json, sys, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
W,H,SS=1920,1080,2
FD=os.path.dirname(os.path.abspath(__file__))+"/../fonts/"
_fc={}
def font(name,size):
    k=(name,int(size*SS))
    if k not in _fc: _fc[k]=ImageFont.truetype(FD+{"m":"PermanentMarker-Regular.ttf","h":"PatrickHand-Regular.ttf","g":"GochiHand-Regular.ttf"}[name],k[1])
    return _fc[k]
INK=(38,32,44);RED=(212,66,62);GRN=(72,150,92);BLU=(72,120,188);YEL=(246,202,72);WHT=(252,250,244);GRY=(150,146,150)
TAN=(214,178,120);NAVY=(52,62,98);PUR=(120,84,150);TEAL=(60,140,140);BRN=(120,80,58);DGRN=(96,160,104)
SK=[(244,206,168),(196,140,100),(232,184,140),(150,100,72),(250,220,190)]
rs=np.random.RandomState(3)
n=rs.normal(0,1,(H*SS//4,W*SS//4)); n=np.kron(n,np.ones((4,4)))*3+rs.normal(0,2.2,(H*SS,W*SS))
PAPER=Image.fromarray(np.clip(np.stack([246+n,240+n,224+n],-1),0,255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1))
def cl(x): return max(0.0,min(1.0,x))
def ez(x): x=cl(x); return x*x*(3-2*x)
def pop(tl,t0,d=0.28):
    x=(tl-t0)/d
    if x<=0: return 0
    if x>=1: return 1
    return 1+0.25*math.sin(x*math.pi)*(1-x)*2 if x>0.6 else ez(x/0.6)
def lerp(a,b,u): return a+(b-a)*u
class Cv:
    def __init__(s,seed):
        s.im=PAPER.copy(); s.d=ImageDraw.Draw(s.im); s.r=random.Random(seed)
    def jit(s,pts,amp,closed=False):
        if closed: pts=list(pts)+[pts[0]]
        out=[]
        for (x0,y0),(x1,y1) in zip(pts,pts[1:]):
            L=math.hypot(x1-x0,y1-y0); k=max(1,int(L/26))
            for i in range(k): u=i/k; out.append((lerp(x0,x1,u),lerp(y0,y1,u)))
        out.append(pts[-1])
        return [(x+s.r.gauss(0,amp),y+s.r.gauss(0,amp)) for x,y in out]
    def line(s,pts,w=5,col=INK,amp=1.6,prog=1.0,closed=False):
        if prog<=0: return
        p=s.jit(pts,amp,closed)
        if prog<1: p=p[:max(2,int(len(p)*prog))]
        q=[(x*SS,y*SS) for x,y in p]
        s.d.line(q,fill=col,width=int(w*SS),joint="curve")
        r=w*SS/2
        for x,y in (q[0],q[-1]): s.d.ellipse((x-r,y-r,x+r,y+r),fill=col)
    def poly(s,pts,fill,w=5,out=INK,amp=1.6,off=(5,4)):
        p=s.jit(pts,amp,True)
        if fill: s.d.polygon([((x+off[0])*SS,(y+off[1])*SS) for x,y in p],fill=fill)
        if out and w: s.line(pts,w,out,amp,closed=True)
    def ell(s,cx,cy,rx,ry,fill=None,w=5,out=INK,amp=1.4,a0=0,a1=360,n=28):
        pts=[(cx+rx*math.cos(math.radians(lerp(a0,a1,i/n))),cy+ry*math.sin(math.radians(lerp(a0,a1,i/n)))) for i in range(n+(0 if a1-a0>=360 else 1))]
        if a1-a0>=360: s.poly(pts,fill,w,out,amp)
        else: s.line(pts,w,out,amp)
    def rect(s,x,y,w_,h_,fill=None,w=5,out=INK,amp=1.6): s.poly([(x,y),(x+w_,y),(x+w_,y+h_),(x,y+h_)],fill,w,out,amp)
    def text(s,x,y,t,size=60,col=INK,f="h",anchor="mm",rot=0,box=None,scale=1.0):
        if scale<=0.15 or size*scale<3: return
        fo=font(f,size*scale); x+=s.r.gauss(0,1.0); y+=s.r.gauss(0,1.0)
        if not rot and not box:
            s.d.multiline_text((x*SS,y*SS),t,font=fo,fill=col,anchor=anchor,align="center",spacing=size*0.1*SS); return
        bb=s.d.multiline_textbbox((0,0),t,font=fo,align="center"); pad=int(26*SS*scale)
        tw,th=int(bb[2]-bb[0]+2*pad),int(bb[3]-bb[1]+2*pad)
        im=Image.new("RGBA",(tw,th),(0,0,0,0)); d=ImageDraw.Draw(im)
        if box: d.rounded_rectangle((6,6,tw-6,th-6),radius=int(14*SS),outline=col,width=int(7*SS*scale),fill=box if box!=1 else None)
        d.multiline_text((pad-bb[0],pad-bb[1]),t,font=fo,fill=col,align="center")
        im=im.rotate(rot+s.r.gauss(0,0.4),expand=True,resample=Image.BICUBIC)
        s.im.paste(im,(int(x*SS-im.width/2),int(y*SS-im.height/2)),im)
    def arrow(s,a,b,prog=1,w=6,col=INK,bend=0):
        if prog<=0: return
        mx,my=(a[0]+b[0])/2,(a[1]+b[1])/2-bend
        pts=[((1-u)**2*a[0]+2*u*(1-u)*mx+u*u*b[0],(1-u)**2*a[1]+2*u*(1-u)*my+u*u*b[1]) for u in [i/14 for i in range(15)]]
        k=max(2,int(len(pts)*cl(prog))); pts=pts[:k]; s.line(pts,w,col,1.0)
        if prog>=0.95:
            (x0,y0),(x1,y1)=pts[-3],pts[-1]; an=math.atan2(y1-y0,x1-x0)
            for da in(2.6,-2.6): s.line([(x1,y1),(x1+30*math.cos(an+da),y1+30*math.sin(an+da))],w,col,0.8)
def bez(a,b,bend,u):
    mx,my=(a[0]+b[0])/2,(a[1]+b[1])/2-bend
    return ((1-u)**2*a[0]+2*u*(1-u)*mx+u*u*b[0],(1-u)**2*a[1]+2*u*(1-u)*my+u*u*b[1])
# ---------- props ----------
def guy(c,x,y,s=1.0,suit=NAVY,skin=0,mood="n",hair=0,arms=None,tie=RED,glasses=False,robe=False):
    sk=SK[skin]; hy=y-178*s
    for sx in(-1,1):
        c.line([(x+sx*16*s,y-4),(x+sx*18*s,y+52*s)],6); c.ell(x+sx*24*s,y+56*s,17*s,8*s,INK,3)
    arms=arms or [(-62,-10),(62,-10)]
    for i,sx in enumerate((-1,1)):
        ax,ay=arms[i]; sh=(x+sx*40*s,y-98*s); hd=(x+ax*s,y+ay*s)
        el=((sh[0]+hd[0])/2+sx*8*s,(sh[1]+hd[1])/2+10*s)
        c.line([sh,el,hd],13*s,suit,1.2); c.line([sh,el,hd],3,INK,1.6); c.ell(hd[0],hd[1],12*s,12*s,sk,3)
    if robe: c.poly([(x-52*s,y-112*s),(x+52*s,y-112*s),(x+62*s,y+10*s),(x-62*s,y+10*s)],suit)
    else:
        c.poly([(x-46*s,y-112*s),(x+46*s,y-112*s),(x+38*s,y),(x-38*s,y)],suit)
        c.poly([(x-16*s,y-112*s),(x+16*s,y-112*s),(x,y-70*s)],WHT,3)
        if tie: c.poly([(x-7*s,y-108*s),(x+7*s,y-108*s),(x+9*s,y-58*s),(x,y-46*s),(x-9*s,y-58*s)],tie,3)
    c.ell(x,hy,62*s,58*s,sk)
    hc=[(60,42,34),(30,26,30),(170,110,50),(200,200,205),(110,60,40)][hair%5]
    if hair==0: c.poly([(x-60*s,hy-14*s),(x-40*s,hy-56*s),(x+10*s,hy-66*s),(x+56*s,hy-40*s),(x+60*s,hy-10*s),(x+20*s,hy-34*s),(x-30*s,hy-30*s)],hc,3)
    elif hair==1: c.poly([(x-62*s,hy+10*s),(x-58*s,hy-44*s),(x,hy-70*s),(x+58*s,hy-44*s),(x+62*s,hy+10*s),(x+46*s,hy-26*s),(x-46*s,hy-26*s)],hc,3)
    elif hair==2: c.ell(x,hy-64*s,26*s,22*s,hc,3); c.poly([(x-58*s,hy-18*s),(x-30*s,hy-58*s),(x+30*s,hy-58*s),(x+58*s,hy-18*s),(x,hy-36*s)],hc,3)
    elif hair==3:
        for sx in(-1,1): c.poly([(x+sx*62*s,hy+6*s),(x+sx*66*s,hy-30*s),(x+sx*40*s,hy-50*s),(x+sx*46*s,hy-10*s)],hc,3)
    elif hair==4: c.poly([(x-60*s,hy-10*s),(x-50*s,hy-60*s),(x-20*s,hy-50*s),(x,hy-74*s),(x+22*s,hy-50*s),(x+52*s,hy-60*s),(x+60*s,hy-10*s),(x,hy-30*s)],hc,3)
    ex=22*s; ey=hy-4*s
    if mood=="panic":
        for sx in(-1,1): c.ell(x+sx*ex,ey,17*s,19*s,WHT,3); c.ell(x+sx*ex,ey+2,4*s,4*s,INK,2)
        c.ell(x,hy+32*s,13*s,15*s,(90,30,30),3)
        for sx,dy in((-1,-30),(1,-10)): c.poly([(x+sx*76*s,hy+dy*s),(x+sx*84*s,hy+(dy+18)*s),(x+sx*68*s,hy+(dy+18)*s)],(140,200,240),2)
    elif mood=="happy":
        for sx in(-1,1): c.ell(x+sx*ex,ey+6*s,11*s,11*s,None,4,a0=200,a1=340,n=8)
        c.ell(x,hy+18*s,24*s,20*s,None,4,a0=20,a1=160,n=10)
    elif mood=="smug":
        c.poly([(x-44*s,ey-12*s),(x+44*s,ey-12*s),(x+38*s,ey+12*s),(x+6*s,ey+10*s),(x,ey-2*s),(x-6*s,ey+10*s),(x-38*s,ey+12*s)],INK,2)
        c.line([(x-10*s,hy+30*s),(x+8*s,hy+33*s),(x+24*s,hy+24*s)],4)
    else:
        for sx in(-1,1): c.ell(x+sx*ex,ey,5*s,6*s,INK,2)
        if mood=="sad": c.ell(x,hy+40*s,16*s,12*s,None,4,a0=200,a1=340,n=8)
        else: c.line([(x-12*s,hy+30*s),(x+12*s,hy+30*s)],4)
    if glasses and mood!="smug":
        for sx in(-1,1): c.ell(x+sx*ex,ey,19*s,17*s,None,3)
        c.line([(x-4*s,ey),(x+4*s,ey)],3)
def bank(c,x,y,s=1.0,label="BANK"):
    c.rect(x-170*s,y-40*s,340*s,40*s,(206,200,190))
    c.rect(x-150*s,y-250*s,300*s,210*s,(232,226,214))
    for i in range(4): c.rect(x-128*s+i*76*s,y-240*s,30*s,200*s,WHT,4)
    c.poly([(x-180*s,y-250*s),(x,y-360*s),(x+180*s,y-250*s)],(206,200,190))
    c.text(x,y-292*s,label,34*s,INK,"m")
def bag(c,x,y,s=1.0,col=TAN,label="$"):
    c.poly([(x-18*s,y-70*s),(x+18*s,y-70*s),(x+10*s,y-52*s),(x-10*s,y-52*s)],col,3)
    c.ell(x,y-22*s,44*s,36*s,col); c.text(x,y-22*s,label,44*s,(60,110,60),"m")
def bill(c,x,y,s=1.0,rot=0):
    ca,sa=math.cos(rot),math.sin(rot); P=lambda px,py:(x+(px*ca-py*sa)*s,y+(px*sa+py*ca)*s)
    c.poly([P(-36,-18),P(36,-18),P(36,18),P(-36,18)],DGRN,3,amp=1); c.ell(x,y,9*s,9*s,(200,230,200),2)
def monitor(c,x,y,w,h,col=(226,236,244)):
    c.rect(x-w/2-16,y-h/2-16,w+32,h+32,(70,70,82)); c.rect(x-w/2,y-h/2,w,h,col,3)
    c.poly([(x-40,y+h/2+16),(x+40,y+h/2+16),(x+60,y+h/2+70),(x-60,y+h/2+70)],(70,70,82))
def bubble(c,x,y,t,size=54,tail=(0,0),sc=1.0,f="h",col=INK):
    if sc<=0.05: return
    bb=c.d.multiline_textbbox((0,0),t,font=font(f,size)); rx=((bb[2]-bb[0])/SS/2+50)*sc; ry=((bb[3]-bb[1])/SS/2+38)*sc
    c.poly([(x-20*sc,y+ry*0.8),(x+tail[0],y+tail[1]),(x+25*sc,y+ry*0.8)],WHT,4)
    c.ell(x,y,rx,ry,WHT,5); c.text(x,y-4,t,size,col,f,scale=sc)
def tag(c,t,col=RED): c.text(250,95,t,58,WHT,"m",rot=-4,box=col)
def desk(c,x,y,w=520): c.rect(x-w/2,y,w,26,BRN); c.line([(x-w/2+30,y+26),(x-w/2+30,y+150)],8,BRN); c.line([(x+w/2-30,y+26),(x+w/2-30,y+150)],8,BRN)
def money(v):
    return "$"+f"{int(v):,}"
# ---------- scenes ----------
def s1(c,tl,cu):
    bank(c,360,930,1.5,"BIG BANK")
    L=[(1240,930,PUR,1,2),(1490,950,TEAL,3,0),(1740,930,BRN,2,4)]
    no=tl>cu[2]+2.6
    for i,(x,y,su,sk,ha) in enumerate(L):
        m="n" if tl<4.5 else ("smug" if no else "happy")
        arms=[(-30,-150),(30,-150)] if (tl>4.5 and not no) else ([(-20,-50),(20,-50)] if no else None)
        guy(c,x,y,1.4,su,sk,m,ha,arms)
        if no: bag(c,x,y-40,1.1)
    if 3.0<tl<cu[1]+1.5:
        for i in range(14):
            u=((tl-3.0)*0.45+i*0.09)%1.0
            if (tl-3.0)*0.45+i*0.09<0.3: continue
            px,py=bez((420,500),(1490,560),300+40*math.sin(i),u); bill(c,px,py,1.5,u*6+i)
    if tl>2.6:
        v=900e6*ez((tl-3.4)/3.2); c.text(960,120,money(v),140,RED if v>8.9e8 else INK,"m",scale=pop(tl,2.6))
    if cu[1]<tl<cu[2]: c.text(960,620,"BY ACCIDENT.",120,RED,"m",rot=-7,box=WHT,scale=pop(tl,cu[1]))
    if tl>cu[2]:
        k=ez((tl-cu[2])/0.8); guy(c,lerp(360,800,k),960,1.4,NAVY,0,"panic" if no else "sad",0,[(70,-90),(90,-60)])
        if tl<cu[2]+2.6: bubble(c,820,360,"can we have\nthat back?",56,(-10,170),pop(tl,cu[2]+0.5))
    if no: bubble(c,1490,400,"NO.",150,(0,190),pop(tl,cu[2]+2.6),"m",RED)
def s2(c,tl,cu):
    if tl<cu[1]:
        c.text(960,480,"Here's how it happened",120,INK,"m",scale=pop(tl,0.1)); c.line([(430,580),(1490,590)],9,RED,2,prog=cl((tl-0.5)/0.8)); return
    t=tl-cu[1]
    a=pop(t,0.3)
    if a:
        c.rect(180,560,240,250,(240,170,180)); c.poly([(160,560),(300,470),(440,560)],(214,120,140))
        c.rect(270,660,30,80,YEL,3); c.poly([(270,660),(300,660),(300,630),(275,615)],RED,3)
        c.text(300,870,"REVLON",56,INK,"m"); c.text(300,925,"(cosmetics company)",34,GRY)
    if t>2.6:
        for i,(x,su,sk,ha) in enumerate([(1470,PUR,1,2),(1640,TEAL,3,0),(1810,BRN,2,4)]): guy(c,x,820,0.95,su,sk,"n",ha)
        c.text(1640,925,"LENDERS",56,INK,"m",scale=pop(t,2.6))
        c.arrow((330,430),(1600,560),cl((t-3.2)/0.9),6,RED,330); c.text(960,235,"owes them $$$",60,RED,"h",scale=pop(t,3.6))
    if t>5.8:
        k=pop(t,5.8); bank(c,960,830,1.0*k,"CITIBANK")
        if t>7.2: c.text(960,930,"the middleman",64,BLU,"m",rot=-3,scale=pop(t,7.2))
        if t>8.0:
            u=((t-8.0)*0.5)%1
            if u<0.5: px,py=bez((440,640),(770,640),60,u*2)
            else: px,py=bez((1150,640),(1420,640),60,(u-0.5)*2)
            bill(c,px,py,1.3,0.2); c.arrow((450,720),(760,720),1,6,GRN); c.arrow((1160,720),(1400,720),1,6,GRN)
def s3(c,tl,cu):
    tag(c,"AUG 11, 2020",BLU)
    desk(c,620,800,560); ok=tl>cu[1]
    guy(c,620,800,1.25,NAVY,0,"happy" if ok else "n",0,[(-70,-20),(130,-170)] if ok else [(-70,-20),(110,-60)])
    k=pop(tl,1.4)
    if k:
        x,y=1320,470; s=k
        c.poly([(x-330*s,y-170*s),(x+330*s,y-170*s),(x+330*s,y+170*s),(x-330*s,y+170*s)],WHT); c.line([(x-330*s,y-170*s),(x,y+10*s),(x+330*s,y-170*s)],5)
        c.text(x,y+85*s,"$8 MILLION",84,GRN,"m",scale=s); c.text(x,y+250,"interest payment",72,INK,"h",scale=pop(tl,2.6))
    if ok:
        c.text(1320,860,"Simple.",110,INK,"m",rot=-4,scale=pop(tl,cu[1])); c.line([(1560,850),(1600,900),(1690,790)],12,GRN,1.5,prog=cl((tl-cu[1]-0.3)/0.4))
def s4(c,tl,cu):
    monitor(c,1060,470,1180,640,(216,224,214))
    c.rect(470,150,1180,56,(90,110,150),3); c.text(1060,177,"LOAN SYSTEM  v1.0   (c) 1990-something",36,WHT)
    for i in range(5): c.line([(520,250+i*22),(900+((i*97)%300),250+i*22)],3,GRY,1)
    c.rect(1380,240,220,90,(200,200,200),3); c.text(1490,285,"HELP ???",34,INK)
    labs=["FRONT","FUND","PRINCIPAL"]; t=tl-cu[1]
    for i,l in enumerate(labs):
        k=pop(t,1.6+i*0.75)
        if not k: continue
        y=430+i*120; c.rect(560,y-34,68,68,WHT,6); c.text(670,y,l,70,INK,"m","lm",scale=k)
        if tl>cu[2]+0.9:
            if i==2: c.line([(568,y),(590,y+26),(640,y-40)],12,GRN,1.2,prog=cl((tl-cu[2]-0.9)/0.25))
            elif tl>cu[2]+1.6: c.text(594,y,"?",70,RED,"m",scale=pop(tl,cu[2]+1.6+i*0.2)); 
    if t>4.0: c.text(1330,520,"tick ALL\nTHREE!",72,RED,"m",rot=6,scale=pop(t,4.0)); c.arrow((1180,470),(1010,440),cl((t-4.3)/0.4),6,RED,-40)
    if tl>cu[2]:
        u=ez((tl-cu[2])/0.8); x,y=lerp(1400,605,u),lerp(820,690,u)
        c.poly([(x,y),(x,y+62),(x+16,y+46),(x+30,y+76),(x+42,y+70),(x+28,y+42),(x+48,y+40)],WHT,4)
    if tl>cu[2]+1.9: c.text(1250,720,"he ticked ONE.",84,RED,"m",rot=-5,box=WHT,scale=pop(tl,cu[2]+1.9))
    guy(c,230,940,1.1,NAVY,0,"n",0,[(-60,-20),(110,-90)])
def s5(c,tl,cu):
    P=[(430,NAVY,0,0,False),(960,(110,90,70),3,1,True),(1490,(90,60,90),2,2,False)]
    for i,(x,su,sk,ha,gl) in enumerate(P):
        if i>0 and tl<0.3+i*0.5: continue
        guy(c,x,760,1.55,su,sk,"panic" if False else "n",ha,None,glasses=gl)
        hy=760-178*1.55
        for j,sx in enumerate((-1,1)):
            ex=x+sx*34; c.ell(ex,hy-6,26,28,WHT,4); c.ell(ex+6*math.sin(tl*2+i),hy-4,8,9,INK,2)
            if tl>cu[1]+0.3+(i*2+j)*0.22: c.text(ex,hy-150,str(i*2+j+1),70,BLU,"m",scale=pop(tl,cu[1]+0.3+(i*2+j)*0.22))
        if tl>cu[2]+0.5+i*0.5: c.text(x,700,"APPROVED",76,GRN,"m",rot=-12+i*9,box=1,scale=pop(tl,cu[2]+0.5+i*0.5,0.18))
    if tl>cu[1]: c.text(960,960,'the "six eyes" review',84,INK,"m",scale=pop(tl,cu[1]))
def s6(c,tl,cu):
    t=tl-cu[1]; pan=t>3.2
    c.rect(70,150,260,280,(190,222,244)); c.line([(200,150),(200,430)],5); c.line([(70,290),(330,290)],5)
    sy=lerp(400,230,ez(tl/3)); c.ell(200,sy,46,46,YEL,4)
    tag(c,"NEXT MORNING",BLU) if tl<3 else None
    desk(c,560,820,560); guy(c,520,820,1.25,NAVY,0,"panic" if pan else "n",0,[(-90,-150),(100,-150)] if pan else [(-70,-20),(110,-70)])
    if not pan: c.rect(640,740,50,60,WHT,4); c.ell(700,770,14,18,None,4,a0=-90,a1=90,n=6)
    else: c.rect(700,790,60,40,WHT,4); c.poly([(690,822),(640,826),(600,818),(650,812)],(120,80,50),2)
    monitor(c,1320,440,900,520)
    c.text(1320,250,"TOTAL SENT:",60,INK,"m")
    if t<1.2: c.text(1320,440,"$8,000,000 ?",110,GRY,"m")
    else:
        v=lerp(8e6,894e6,ez((t-1.6)/2.6)); c.text(1320,430,money(v),118,RED,"m")
        c.text(1320,590,"should be $8M",50,GRY,"h"); c.line([(1150,596),(1490,586)],6,RED,1.5,prog=cl((t-1.4)/0.3))
    if t>5.2: c.text(1320,880,"...of its OWN money",84,RED,"m",rot=-3,scale=pop(t,5.2))
    if t>7.0: c.text(590,230,"whole loan paid off\nYEARS early",56,INK,"h",rot=3,box=YEL,scale=pop(t,7.0))
    return 10*math.exp(-(t-4.2)*4) if t>4.2 else 0
def s7(c,tl,cu):
    guy(c,300,940,1.45,NAVY,0,"panic",0,[(-70,-150),(110,-120)])
    if tl<cu[1]+1:
        for i in range(4):
            u=(tl*0.5+i*0.25)%1; x,y=bez((440,620),(1250,500+i*40),180,u)
            c.rect(x-40,y-26,80,52,WHT,3,amp=1); c.line([(x-40,y-26),(x,y+4),(x+40,y-26)],3)
        bubble(c,560,250,"PLEASE\ngive it back!",58,(-150,190),pop(tl,0.5),"m",RED)
    if tl>cu[1]:
        k=ez((tl-cu[1])/1.3)
        for i,(x,su,sk,ha) in enumerate([(1130,TEAL,0,1),(1360,(150,110,60),3,3)]):
            guy(c,x,440,1.0,su,sk,"happy",ha,[(-80,-60),(40,-10)]); bag(c,lerp(x-110,520+i*110,k),lerp(400,700,k),1.0)
        c.text(1660,280,"returned",80,GRN,"m",rot=4,scale=pop(tl,cu[1]+0.4)); c.line([(1590,360),(1630,410),(1720,320)],13,GRN,1.2,prog=cl((tl-cu[1]-0.6)/0.3))
    if tl>cu[2]:
        k=pop(tl,cu[2])
        for dx,dy in((-120,0),(0,0),(120,0),(-60,-62),(60,-62),(0,-124)): bag(c,1420+dx*k,960+dy*k,0.95*k)
        for i,(x,su,sk,ha) in enumerate([(1250,PUR,1,2),(1600,BRN,2,4)]): guy(c,x,940,1.0,su,sk,"smug",ha,[(-60,-20),(60,-20)] if i else [(-50,-20),(70,-40)])
        c.text(1420,640,"kept ~$500 MILLION",76,RED,"m",rot=-3,box=WHT,scale=pop(tl,cu[2]+0.9))
    if tl>cu[3]+1.4: bubble(c,960,820,"you owed us\nthis anyway",52,(230,-10),pop(tl,cu[3]+1.4))
def bench(c,x,y,w,h): c.rect(x-w/2,y,w,h,(150,100,66)); c.rect(x-w/2-20,y-24,w+40,30,(120,78,50)); c.rect(x-w/2+40,y+40,w-80,h-80,(170,118,80),3)
def gavel(c,x,y,a):
    ca,sa=math.cos(a),math.sin(a); P=lambda px,py:(x+px*ca-py*sa,y+px*sa+py*ca)
    c.line([P(0,0),P(0,-150)],10,BRN,1); c.poly([P(-60,-190),P(60,-190),P(60,-140),P(-60,-140)],(110,70,46),4,amp=1)
def s8(c,tl,cu):
    tag(c,"2021")
    if tl<cu[1]: 
        guy(c,620,900,1.6,NAVY,0,"n",0,[(-70,-20),(130,-120)]); c.rect(800,560,220,270,WHT); c.text(910,690,"LAW\nSUIT",66,RED,"m"); 
        for i,(x,su,sk,ha) in enumerate([(1330,PUR,1,2),(1580,BRN,2,4)]): guy(c,x,900,1.5,su,sk,"smug",ha)
        return
    bang=cu[2]-1.6; hit=tl>bang
    guy(c,960,650,1.15,(40,40,48),4,"n",3,[(-90,-40),(150,-90)],tie=None,glasses=True,robe=True)
    bench(c,960,630,640,300)
    a=-1.1 if not hit else lerp(-1.1,0.5,cl((tl-bang)/0.12))
    if tl>bang-0.5: a=lerp(-0.3,-1.1,cl((tl-bang+0.5)/0.4)) if not hit else a
    gavel(c,1170,560,a+1.2)
    if hit and tl<bang+0.5:
        for i in range(8): an=i*0.785; c.line([(1290+60*math.cos(an),610+60*math.sin(an)),(1290+110*math.cos(an),610+110*math.sin(an))],6,RED)
    guy(c,270,960,1.15,NAVY,0,"panic" if hit else "n",0,[(-90,-150),(90,-150)] if hit else None)
    for i,(x,su,sk,ha) in enumerate([(1560,PUR,1,2),(1740,BRN,2,4)]): guy(c,x,960,1.0,su,sk,"happy" if hit else "n",ha,[(-40,-150),(40,-150)] if hit else None)
    if hit and tl<cu[2]+0.4: c.text(960,170,"LENDERS KEEP IT",120,RED,"m",rot=-3,box=WHT,scale=pop(tl,bang+0.1))
    if tl>cu[2]+0.4:
        t=tl-cu[2]-0.4; k=pop(t,0)
        c.poly([(480,50),(1440,50),(1440,50+320*k),(480,50+320*k)],(250,240,205)); 
        if t>0.3: c.text(960,110,"OLD NEW YORK RULE",58,BRN,"m")
        if t>1.6: c.text(960,190,"paid what you're owed",54,INK,"h",scale=pop(t,1.6))
        if t>3.0: c.text(960,255,"+ no idea it was a mistake",54,INK,"h",scale=pop(t,3.0))
        if t>5.0: c.text(960,335,"= IT'S YOURS",72,RED,"m",scale=pop(t,5.0))
    return 12*math.exp(-(tl-bang)*5) if hit else 0
def s9(c,tl,cu):
    tag(c,"2022")
    if tl<cu[1]:
        guy(c,900,900,1.7,NAVY,0,"n",0,[(-70,-20),(140,-250)]); c.rect(1010,400,240,300,WHT); c.text(1130,550,"APPEAL",58,RED,"m",rot=-8); return
    for i,(x,ha,sk) in enumerate([(700,3,4),(960,1,1),(1220,4,0)]): guy(c,x,540,1.05,(40,40,48),sk,"n",ha,None,tie=None,glasses=i!=1,robe=True)
    bench(c,960,520,900,260); c.text(960,650,"HIGHER COURT",60,(250,235,200),"m")
    st=cu[2]-2.2
    if tl>st: c.text(980,150,"REVERSED",125,RED,"m",rot=-9,box=1,scale=pop(tl,st,0.16))
    home=tl>cu[2]
    bank(c,260,1010,0.72,"CITIBANK"); guy(c,520,1000,0.9,NAVY,0,"happy" if home else "n",0,[(-50,-130),(60,-130)] if home else None)
    for i in range(4):
        k=ez((tl-cu[2]-i*0.25)/1.4) if home else 0
        x,y=bez((1500+i*90,980),(760-i*30,990),160,k); y-=abs(math.sin(k*math.pi*4))*30
        bag(c,x,y,0.8)
    if home: c.arrow((1400,800),(820,820),cl((tl-cu[2])/0.8),7,GRN,60)
    return 9*math.exp(-(tl-st)*5) if tl>st else 0
def s10(c,tl,cu):
    if tl<cu[1]:
        bank(c,700,820,1.2,"BANK"); c.line([(640,470),(690,560),(650,640),(720,760)],7,INK,2,prog=cl(tl/0.8))
        guy(c,1250,840,1.3,NAVY,0,"sad",0); c.rect(1190,540,120,26,WHT,3); c.text(960,170,"the damage was done",96,INK,"m",scale=pop(tl,0.3)); return
    if tl<cu[2]:
        t=tl-cu[1]
        c.poly([(560,90),(1360,70),(1380,1010),(580,1030)],WHT)
        c.text(970,160,"LOAN CONTRACT",70,INK,"m")
        for i in range(5): c.line([(650,260+i*56),(1290-(i*53)%160,258+i*56)],5,GRY,1.5,prog=cl((t-0.3-i*0.15)/0.4))
        if t>2.6:
            k=cl((t-2.6)/0.6); c.rect(630,580,700*k,190,YEL,0,None)
            c.text(980,630,"NEW CLAUSE:",56,RED,"m",scale=pop(t,3.0)); c.text(980,715,"mistaken payments\nmust be returned",52,INK,"h",scale=pop(t,3.6))
        for i in range(3): c.line([(650,840+i*56),(1250-(i*71)%200,838+i*56)],5,GRY,1.5,prog=cl((t-0.9-i*0.15)/0.4))
        guy(c,260,900,1.0,PUR,1,"n",2,[(-50,-20),(110,-110)]); guy(c,1660,900,1.0,TEAL,3,"n",0,[(-110,-110),(50,-20)])
        return
    t=tl-cu[2]
    x,y=960,300; sc=pop(t,0.1)*2.2
    c.poly([(x-20*sc,y-40*sc),(x-20*sc,y+22*sc),(x-4*sc,y+6*sc),(x+10*sc,y+36*sc),(x+22*sc,y+30*sc),(x+8*sc,y+2*sc),(x+28*sc,y)],WHT,6)
    if 0.5<t<1.2:
        for i in range(8): an=i*0.785; c.line([(x-44+50*math.cos(an),y-88+50*math.sin(an)),(x-44+90*math.cos(an),y-88+90*math.sin(an))],6,RED)
    c.text(960,560,"ONE WRONG CLICK.",130,INK,"m",scale=pop(t,0.6))
    if t>3.0: c.text(960,800,"THE $900 MILLION TYPO",120,RED,"m",rot=-3,box=WHT,scale=pop(t,3.0)); 
SC=[s1,s2,s3,s4,s5,s6,s7,s8,s9,s10]
META=json.load(open(os.path.dirname(os.path.abspath(__file__))+"/vo.json"))
def render(t,seed):
    i=0
    for j,m in enumerate(META):
        if t>=m["start"]: i=j
    m=META[i]; tl=t-m["start"]; c=Cv(seed)
    sh=SC[i](c,tl,[q-m["start"] for q in m["cues"]]) or 0
    im=c.im.reduce(SS)
    return im,sh,i,tl
if __name__=="__main__":
    import subprocess
    if sys.argv[1]=="sheet":
        ts=[float(x) for x in sys.argv[2:]]; cols=4; rows=(len(ts)+3)//4
        sheet=Image.new("RGB",(480*cols,270*rows))
        for k,t in enumerate(ts): sheet.paste(render(t,k)[0].resize((480,270)),((k%cols)*480,(k//cols)*270))
        sheet.save("sheet.jpg",quality=88)
    else:
        D=float(sys.argv[2]); p=subprocess.Popen(["ffmpeg","-y","-loglevel","error","-f","rawvideo","-pix_fmt","rgb24","-s","1920x1080","-r","24","-i","-","-c:v","libx264","-crf","17","-preset","medium","-pix_fmt","yuv420p","video.mp4"],stdin=subprocess.PIPE)
        N=int(D*24); cur=None
        for f in range(N):
            t=f/24
            if f%2==0: cur=render(t,(f//4)*7919+1)
            im,sh,i,tl=cur
            z=1.0+0.035*min(1,tl/12)+0.01; w,h=W/z,H/z
            ox=(W-w)/2+(random.uniform(-sh,sh) if sh>0.5 else 0); oy=(H-h)/2+(random.uniform(-sh,sh) if sh>0.5 else 0)
            fr=im.resize((W,H),Image.BILINEAR,box=(ox,oy,ox+w,oy+h))
            p.stdin.write(fr.tobytes())
        p.stdin.close(); p.wait()
