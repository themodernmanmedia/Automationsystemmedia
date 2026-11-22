import math, random, sys, subprocess
from PIL import Image
import draw as D
from draw import *
class G: t=0.0
PI=math.pi
def sn(f,ph=0): return math.sin(G.t*f+ph)
def go(tl,t0,t1,a,b):
    u=cl((tl-t0)/(t1-t0)); return lerp(a,b,u),(0<u<1)
def guy(c,x,y,s=1.0,suit=NAVY,skin=0,mood="n",hair=0,arms=None,tie=RED,glasses=False,robe=False,
        walk=None,face=1,talk=False,lean=0,look=0,pid=0.0):
    t=G.t; sk=SK[skin]
    bob=-abs(math.sin(walk))*8*s if walk is not None else math.sin(t*2.6+pid)*2.5*s
    hx=x+lean*1.7*s; hy=y-178*s+bob*1.3; tx=x+lean*s
    hip=y-6*s+bob
    for i,sx in enumerate((-1,1)):
        hpx=x+sx*15*s
        if walk is None: foot=(x+sx*19*s,y+52*s); knee=((hpx+foot[0])/2,(hip+foot[1])/2)
        else:
            ph=walk+(0 if i==0 else PI)
            foot=(x+face*30*s*math.cos(ph),y+52*s-max(0,math.sin(ph))*20*s)
            knee=((hpx+foot[0])/2+face*10*s,(hip+foot[1])/2-3*s)
        c.line([(hpx,hip),knee,foot],6,INK,1.2); c.ell(foot[0]+face*7*s,foot[1]+4*s,17*s,8*s,INK,3)
    hands=[]
    for i,sx in enumerate((-1,1)):
        if arms and arms[i] is not None: ax,ay=arms[i]
        elif walk is not None: ax,ay=sx*48-face*28*math.cos(walk+(0 if i==0 else PI)),-12
        else: ax,ay=sx*62+2*math.sin(t*2+pid+i),-10
        sh=(tx+sx*40*s,y-98*s+bob); hd=(x+ax*s,y+ay*s+bob)
        el=((sh[0]+hd[0])/2+sx*8*s,(sh[1]+hd[1])/2+10*s)
        c.line([sh,el,hd],13*s,suit,1.2); c.line([sh,el,hd],3,INK,1.6); c.ell(hd[0],hd[1],12*s,12*s,sk,3); hands.append(hd)
    T=lambda px,py:(x+px*s+(lean*s if py<-60 else 0),y+py*s+bob)
    if robe: c.poly([T(-52,-112),T(52,-112),T(62,10),T(-62,10)],suit)
    else:
        c.poly([T(-46,-112),T(46,-112),T(38,0),T(-38,0)],suit)
        c.poly([T(-16,-112),T(16,-112),T(0,-70)],WHT,3)
        if tie: c.poly([T(-7,-108),T(7,-108),T(9,-58),T(0,-46),T(-9,-58)],tie,3)
    c.ell(hx,hy,62*s,58*s,sk)
    hc=[(60,42,34),(30,26,30),(170,110,50),(200,200,205),(110,60,40)][hair%5]
    Hh=lambda px,py:(hx+px*s,hy+py*s)
    if hair==0: c.poly([Hh(-60,-14),Hh(-40,-56),Hh(10,-66),Hh(56,-40),Hh(60,-10),Hh(20,-34),Hh(-30,-30)],hc,3)
    elif hair==1: c.poly([Hh(-62,10),Hh(-58,-44),Hh(0,-70),Hh(58,-44),Hh(62,10),Hh(46,-26),Hh(-46,-26)],hc,3)
    elif hair==2: c.ell(hx,hy-64*s,26*s,22*s,hc,3); c.poly([Hh(-58,-18),Hh(-30,-58),Hh(30,-58),Hh(58,-18),Hh(0,-36)],hc,3)
    elif hair==3:
        for sx in(-1,1): c.poly([Hh(sx*62,6),Hh(sx*66,-30),Hh(sx*40,-50),Hh(sx*46,-10)],hc,3)
    elif hair==4: c.poly([Hh(-60,-10),Hh(-50,-60),Hh(-20,-50),Hh(0,-74),Hh(22,-50),Hh(52,-60),Hh(60,-10),Hh(0,-30)],hc,3)
    fo=(face*7+look*9)*s; fx=hx+fo; ex=22*s; ey=hy-4*s
    blink=((t+pid*1.7)%3.3)<0.14
    if mood=="panic":
        for sx in(-1,1): c.ell(fx+sx*ex,ey,17*s,19*s,WHT,3); c.ell(fx+sx*ex+3*s*math.sin(t*20),ey+2,4*s,4*s,INK,2)
        c.ell(fx,hy+32*s,13*s,(11+6*abs(math.sin(t*12)))*s,(90,30,30),3)
        for sx,dy in((-1,-30),(1,-10)):
            dd=((t*60+dy)%30)*s; c.poly([(hx+sx*76*s,hy+dy*s+dd),(hx+sx*84*s,hy+(dy+18)*s+dd),(hx+sx*68*s,hy+(dy+18)*s+dd)],(140,200,240),2)
    elif mood=="happy":
        for sx in(-1,1): c.ell(fx+sx*ex,ey+6*s,11*s,11*s,None,4,a0=200,a1=340,n=8)
        if talk: c.ell(fx,hy+28*s,16*s,(5+9*abs(math.sin(t*13+pid)))*s,(90,30,30),3)
        else: c.ell(fx,hy+18*s,24*s,20*s,None,4,a0=20,a1=160,n=10)
    elif mood=="smug":
        c.poly([(fx-44*s,ey-12*s),(fx+44*s,ey-12*s),(fx+38*s,ey+12*s),(fx+6*s,ey+10*s),(fx,ey-2*s),(fx-6*s,ey+10*s),(fx-38*s,ey+12*s)],INK,2)
        if talk: c.ell(fx,hy+32*s,12*s,(4+7*abs(math.sin(t*13+pid)))*s,(90,30,30),3)
        else: c.line([(fx-10*s,hy+30*s),(fx+8*s,hy+33*s),(fx+24*s,hy+24*s)],4)
    else:
        for sx in(-1,1):
            if blink: c.line([(fx+sx*ex-7*s,ey),(fx+sx*ex+7*s,ey)],4,INK,0.8)
            else: c.ell(fx+sx*ex,ey,5*s,6*s,INK,2)
        if talk: c.ell(fx,hy+32*s,11*s,(3+9*abs(math.sin(t*13+pid)))*s,(90,30,30),3)
        elif mood=="sad": c.ell(fx,hy+40*s,16*s,12*s,None,4,a0=200,a1=340,n=8)
        else: c.line([(fx-12*s,hy+30*s),(fx+12*s,hy+30*s)],4)
    if glasses and mood!="smug":
        for sx in(-1,1): c.ell(fx+sx*ex,ey,19*s,17*s,None,3)
        c.line([(fx-4*s,ey),(fx+4*s,ey)],3)
    return {"L":hands[0],"R":hands[1],"head":(hx,hy)}
def paper(c,p,w,h,txt,size,col=RED):
    c.rect(p[0]-w/2,p[1]-h,w,h,WHT,4); c.text(p[0],p[1]-h/2,txt,size,col,"m")
LD=[(PUR,1,2),(TEAL,3,0),(BRN,2,4)]
# ---------------- scenes ----------------
def s1(c,tl,cu):
    bank(c,360,930,1.5,"BIG BANK"); no=cu[2]+2.6; isno=tl>no; leave=max(0,tl-no-0.5)
    for i,(x,y) in enumerate([(1240,930),(1490,950),(1740,930)]):
        su,sk,ha=LD[i]; rain=3.6<tl<cu[2]
        if leave>0:
            guy(c,x+leave*330,y,1.4,su,sk,"smug",ha,[(-30,-60),(30,-60)],walk=tl*11+i,face=1,pid=i); bag(c,x+leave*330,y-40-abs(math.sin(tl*11+i))*8,1.1)
        elif isno:
            guy(c,x,y,1.4,su,sk,"smug",ha,[(-20,-50),(20,-50)],lean=7*sn(11,i),talk=i==1,pid=i); bag(c,x+7*sn(11,i),y-40,1.1)
        elif tl>cu[2]:
            guy(c,x,y,1.4,su,sk,"happy",ha,[(-20,-50),(20,-50)],look=-1,pid=i); bag(c,x,y-40,1.1)
        elif rain:
            hop=abs(sn(7,i*1.3))*34
            guy(c,x,y-hop,1.4,su,sk,"happy",ha,[(-34,-150+22*sn(9,i)),(34,-150+22*sn(9,i+2))],pid=i)
        else: guy(c,x,y,1.4,su,sk,"n",ha,None,talk=(int(tl*1.2)%3==i),look=(1-i)*0.8,pid=i)
    if 3.0<tl<cu[1]+1.5:
        for i in range(14):
            q=(tl-3.0)*0.45+i*0.09; u=q%1.0
            if q<0.3: continue
            px,py=bez((420,500),(1490,560),300+40*math.sin(i),u); bill(c,px,py,1.5,u*6+i)
    if tl>2.6:
        v=900e6*ez((tl-3.4)/3.2); c.text(960,120,money(v),140,RED if v>8.9e8 else INK,"m",scale=pop(tl,2.6))
    if cu[1]<tl<cu[2]: c.text(960,620,"BY ACCIDENT.",120,RED,"m",rot=-7,box=WHT,scale=pop(tl,cu[1]))
    if tl>cu[2]:
        x,mv=go(tl,cu[2],cu[2]+1.5,400,820)
        if leave>0: guy(c,820+leave*200,960,1.4,NAVY,0,"panic",0,[(80,-120+20*sn(14)),(110,-90-20*sn(14))],walk=tl*15,pid=9)
        else: guy(c,x,960,1.4,NAVY,0,"panic" if isno else "sad",0,None if mv else [(70,-95+14*sn(8)),(95,-62-14*sn(8))],walk=tl*10 if mv else None,talk=not mv,pid=9)
        if cu[2]+1.3<tl<no: bubble(c,820,360,"can we have\nthat back?",56,(-10,170),pop(tl,cu[2]+1.3))
    if isno and leave<0.6: bubble(c,1490,400,"NO.",150,(0,190),pop(tl,no),"m",RED)
def s2(c,tl,cu):
    if tl<cu[1]:
        c.text(960,430,"Here's how it happened",120,INK,"m",scale=pop(tl,0.1))
        x,_=go(tl,0.1,cu[1],250,1700); c.line([(430,540),(max(440,min(x,1490)),548)],9,RED,2)
        h=guy(c,x,860,1.2,NAVY,0,"happy",0,[None,(40,-250)],walk=tl*11,pid=9); c.line([h["R"],(h["R"][0]-10,560)],8,YEL,1); return
    t=tl-cu[1]
    if pop(t,0.3):
        c.rect(150,470,240,250,(240,170,180)); c.poly([(130,470),(270,380),(410,470)],(214,120,140))
        c.rect(240,570,30,80,YEL,3); c.poly([(240,570),(270,570),(270,540),(245,525)],RED,3)
        c.text(270,770,"REVLON",56,INK,"m"); c.text(270,820,"(cosmetics company)",34,GRY)
        guy(c,470,720,0.8,(200,90,120),4,"n",1,[None,(70,-150+20*sn(9))] if t<2.5 else None,talk=t<2.5,pid=5)
    if t>2.6:
        for i,x in enumerate([1470,1640,1810]):
            xx,mv=go(t,2.6+i*0.15,3.9+i*0.15,x+600,x); su,sk,ha=LD[i]
            guy(c,xx,720,0.95,su,sk,"n",ha,None if mv or t<4.4 else [(-50,-10),(40,-120+14*sn(10,i))],walk=t*11+i if mv else None,face=-1,pid=i)
        c.text(1640,830,"LENDERS",56,INK,"m",scale=pop(t,3.8))
        c.arrow((330,330),(1600,460),cl((t-3.4)/0.9),6,RED,300); c.text(960,150,"owes them $$$",60,RED,"h",scale=pop(t,3.8))
    if t>5.8:
        k=pop(t,5.8); bank(c,960,760,1.0*k,"CITIBANK")
        if t>7.0: c.text(960,840,"the middleman",64,BLU,"m",rot=-3,scale=pop(t,7.0))
        if t>7.6:
            u=((t-7.6)/3.3)%1; x=lerp(420,1500,u)
            h=guy(c,x,990,0.85,NAVY,0,"happy",0,[None,(30,-240)],walk=t*12,pid=9); bill(c,h["R"][0],h["R"][1]-22,1.3,0.1*sn(12))
def s3(c,tl,cu):
    tag(c,"AUG 11, 2020",BLU); desk(c,620,800,560); ok=tl>cu[1]
    x,mv=go(tl,0,1.3,-120,620); hop=abs(math.sin((tl-cu[1])*8))*40*math.exp(-(tl-cu[1])*2.5) if ok else 0
    arms=None if mv else ([(-70,-20),(130,-190+10*sn(10))] if ok else [(-70,-20),(120,-80+26*sn(5))])
    guy(c,x,800-hop,1.25,NAVY,0,"happy" if ok else "n",0,arms,walk=tl*11 if mv else None,talk=(not mv and tl<cu[1]),pid=9)
    k=pop(tl,1.4)
    if k:
        x,y=1320,470+10*sn(2.5); s=k
        c.poly([(x-330*s,y-170*s),(x+330*s,y-170*s),(x+330*s,y+170*s),(x-330*s,y+170*s)],WHT); c.line([(x-330*s,y-170*s),(x,y+10*s),(x+330*s,y-170*s)],5)
        c.text(x,y+85*s,"$8 MILLION",84,GRN,"m",scale=s); c.text(1320,720,"interest payment",72,INK,"h",scale=pop(tl,2.6))
    if ok:
        c.text(1320,880,"Simple.",110,INK,"m",rot=-4,scale=pop(tl,cu[1])); c.line([(1560,870),(1600,920),(1690,810)],12,GRN,1.5,prog=cl((tl-cu[1]-0.3)/0.4))
def s4(c,tl,cu):
    monitor(c,1060,470,1180,640,(216,224,214))
    c.rect(470,150,1180,56,(90,110,150),3); c.text(1060,177,"LOAN SYSTEM  v1.0   (c) 1990-something",36,WHT)
    for i in range(5): c.line([(520,250+i*22),(900+((i*97)%300),250+i*22)],3,GRY,1)
    c.rect(1380,240,220,90,(200,200,200),3); c.text(1490,285,"HELP ???",34,INK)
    t=tl-cu[1]; tick=cu[2]+0.9
    for i,l in enumerate(["FRONT","FUND","PRINCIPAL"]):
        k=pop(t,1.6+i*0.75)
        if not k: continue
        y=430+i*120; c.rect(560,y-34,68,68,WHT,6); c.text(670,y,l,70,INK,"m","lm",scale=k)
        if tl>tick:
            if i==2: c.line([(568,y),(590,y+26),(640,y-40)],12,GRN,1.2,prog=cl((tl-tick)/0.25))
            elif tl>cu[2]+1.6: c.text(594,y,"?",70,RED,"m",scale=pop(tl,cu[2]+1.6+i*0.2))
    if t>4.0: c.text(1330,520,"tick ALL\nTHREE!",72,RED,"m",rot=6,scale=pop(t,4.0)); c.arrow((1180,470),(1010,440),cl((t-4.3)/0.4),6,RED,-40)
    if tl>cu[2]:
        u=ez((tl-cu[2])/0.8); x,y=lerp(1400,605,u),lerp(820,690,u)
        c.poly([(x,y),(x,y+62),(x+16,y+46),(x+30,y+76),(x+42,y+70),(x+28,y+42),(x+48,y+40)],WHT,4)
    if tl>cu[2]+1.9: c.text(1250,720,"he ticked ONE.",84,RED,"m",rot=-5,box=WHT,scale=pop(tl,cu[2]+1.9))
    out=cu[2]+2.6
    if tl<1.5: x,mv=go(tl,0,1.5,-120,250); guy(c,x,960,1.25,NAVY,0,"n",0,None,walk=tl*11,pid=9)
    elif tl>out: x,mv=go(tl,out,out+1.6,250,-160); guy(c,x,960,1.25,NAVY,0,"happy",0,None,walk=tl*11,face=-1,pid=9)
    elif tl>cu[2]: guy(c,250,960,1.25,NAVY,0,"happy" if tl>tick else "n",0,[None,(150,-150+(18 if abs(tl-tick)<0.12 else 0))],pid=9)
    elif t>0: guy(c,250,960,1.25,NAVY,0,"sad",0,[None,(46+10*sn(13),-262)],look=0.8,lean=4*sn(2),pid=9)
    else: guy(c,250,960,1.25,NAVY,0,"n",0,None,look=0.8,pid=9)
def s5(c,tl,cu):
    P=[(430,NAVY,0,0,False),(960,(110,90,70),3,1,True),(1490,(90,60,90),2,2,False)]
    for i,(x,su,sk,ha,gl) in enumerate(P):
        xx,mv=(x,False) if i==0 else go(tl,0.2+i*0.3,1.5+i*0.35,x+1300,x)
        hit=cu[2]+0.5+i*0.5; pre=cl((tl-hit+0.45)/0.3); dn=cl((tl-hit+0.1)/0.1)
        arms=None
        if not mv and tl>hit-0.45: arms=[None,(70,lerp(lerp(-10,-270,pre),-70,dn))]
        nod=5*sn(6,i) if (cu[1]<tl<cu[2]) else 0
        h=guy(c,xx,760+nod,1.55,su,sk,"n",ha,arms,glasses=gl,walk=tl*10+i if mv else None,face=-1 if mv else 1,pid=i*2.1)
        hx,hy=h["head"]
        if not mv:
            for j,sx in enumerate((-1,1)):
                ex=hx+sx*34; c.ell(ex,hy-6,26,28,WHT,4); c.ell(ex+9*sn(3.2,i),hy-4,8,9,INK,2)
                if tl>cu[1]+0.3+(i*2+j)*0.22: c.text(ex,hy-150,str(i*2+j+1),70,BLU,"m",scale=pop(tl,cu[1]+0.3+(i*2+j)*0.22))
        if arms and tl<hit+0.25: c.rect(h["R"][0]-34,h["R"][1]-10,68,44,GRN,4)
        if tl>hit: c.text(x,690,"APPROVED",76,GRN,"m",rot=-12+i*9,box=1,scale=pop(tl,hit,0.18))
    if tl>cu[1]: c.text(960,960,'the "six eyes" review',84,INK,"m",scale=pop(tl,cu[1]))
def s6(c,tl,cu):
    t=tl-cu[1]; pan=t>3.2
    c.rect(70,150,260,280,(190,222,244)); c.line([(200,150),(200,430)],5); c.line([(70,290),(330,290)],5)
    c.ell(200,lerp(400,230,ez(tl/3)),46,46,YEL,4)
    if tl<3: tag(c,"NEXT MORNING",BLU)
    desk(c,560,820,560)
    monitor(c,1320,440,900,520); c.text(1320,250,"TOTAL SENT:",60,INK,"m")
    if t<1.2: c.text(1320,440,"$8,000,000 ?",110,GRY,"m")
    else:
        v=lerp(8e6,894e6,ez((t-1.6)/2.6)); c.text(1320,430,money(v),118,RED,"m")
        c.text(1320,590,"should be $8M",50,GRY,"h"); c.line([(1150,596),(1490,586)],6,RED,1.5,prog=cl((t-1.4)/0.3))
    if t>5.2: c.text(1320,880,"...of its OWN money",84,RED,"m",rot=-3,scale=pop(t,5.2))
    if t>7.0: c.text(590,230,"whole loan paid off\nYEARS early",56,INK,"h",rot=3,box=YEL,scale=pop(t,7.0))
    if not pan:
        x,mv=go(tl,0,2.0,-140,520); sip=(not mv) and (tl%2.2)<0.9
        h=guy(c,x,820,1.25,NAVY,0,"happy" if t<1.4 else "n",0,[None,(30,-200) if sip else (70,-70)],walk=tl*10 if mv else None,look=1,pid=9)
        c.rect(h["R"][0]-4,h["R"][1]-52,44,50,WHT,4)
    else:
        q=t-3.2; jump=abs(math.sin(q*6))*70*math.exp(-q*2) if q<1 else 0
        x=520+(190*math.sin((q-0.8)*3.2) if q>0.8 else 0); f=1 if math.cos((q-0.8)*3.2)>0 else -1
        guy(c,x,820-jump,1.25,NAVY,0,"panic",0,[(-90,-160+34*sn(17)),(90,-160-34*sn(17))],walk=tl*17 if q>0.8 else None,face=f,pid=9)
        cx,cy=bez((580,620),(760,812),300,cl(q/0.7)); c.rect(cx,cy-40,44,40,WHT,4)
        if q>0.7: c.poly([(750,822),(700,828),(650,818),(710,810)],(120,80,50),2)
    return 10*math.exp(-(t-4.2)*4) if t>4.2 else 0
def s7(c,tl,cu):
    kept=tl>cu[2]
    hop=abs(sn(8))*30 if tl<cu[1] else 0
    guy(c,300,940-hop,1.45,NAVY,0,"panic",0,[(-70,-160+24*sn(12)),(110,-130-24*sn(12))] if not kept else [(90,-110+12*sn(7)),(120,-70-12*sn(7))],talk=True,face=1,look=1 if kept else 0,pid=9)
    if tl<cu[1]+1:
        for i in range(4):
            u=(tl*0.5+i*0.25)%1; x,y=bez((440,620),(1250,500+i*40),180,u)
            c.rect(x-40,y-26,80,52,WHT,3,amp=1); c.line([(x-40,y-26),(x,y+4),(x+40,y-26)],3)
        bubble(c,560,250,"PLEASE\ngive it back!",58,(-150,190),pop(tl,0.5),"m",RED)
    for i,(x0,su,sk,ha) in enumerate([(1130,TEAL,0,1),(1360,(150,110,60),3,3)]):
        if tl<cu[1]: guy(c,x0,440,1.0,su,sk,"n",ha,[(-50,-40),(50,-40)],look=-1,pid=i+3); bag(c,x0,410,0.9)
        else:
            x,mv=go(tl,cu[1]+i*0.2,cu[1]+1.5+i*0.2,x0,620+i*210)
            h=guy(c,x,440,1.0,su,sk,"happy",ha,[(-60,-50),None] if mv else [(-70,-20),(40,-170+20*sn(9,i))],walk=tl*11+i if mv else None,face=-1,pid=i+3)
            bag(c,x-66,410 if mv else 492,0.9)
    if tl>cu[1]+0.4: c.text(1660,280,"returned",80,GRN,"m",rot=4,scale=pop(tl,cu[1]+0.4)); c.line([(1590,360),(1630,410),(1720,320)],13,GRN,1.2,prog=cl((tl-cu[1]-0.6)/0.3))
    if kept:
        k=pop(tl,cu[2])
        for dx,dy in((-120,0),(0,0),(120,0),(-60,-62),(60,-62),(0,-124)): bag(c,1420+dx*k,960+dy*k,0.95*k)
        say=tl>cu[3]+1.4
        h=guy(c,1250,940,1.0,PUR,1,"smug",2,[(-50,-20),(70,-60)],lean=5*sn(9) if say else 0,talk=say,face=-1,pid=0)
        bag(c,h["R"][0],h["R"][1]-18-abs(sn(6))*70,0.6)
        guy(c,1600,940,1.0,BRN,2,"smug",4,[(-60,-20),(40,-150+16*sn(8))],lean=5*sn(9,1) if say else 0,face=-1,pid=2)
        c.text(1420,640,"kept ~$500 MILLION",76,RED,"m",rot=-3,box=WHT,scale=pop(tl,cu[2]+0.9))
        if say: bubble(c,930,810,"you owed us\nthis anyway",52,(240,-10),pop(tl,cu[3]+1.4))
def s8(c,tl,cu):
    tag(c,"2021")
    if tl<cu[1]:
        x,mv=go(tl,0,1.1,-160,620); h=guy(c,x,900,1.6,NAVY,0,"n",0,[None,(130,-150)],walk=tl*12 if mv else None,talk=not mv,pid=9)
        paper(c,(h["R"][0]+80,h["R"][1]+110),220,270,"LAW\nSUIT",66)
        for i,x in enumerate([1330,1580]): guy(c,x+cl(tl/1.1)*40,900,1.5,LD[i*2][0],LD[i*2][1],"smug",LD[i*2][2],lean=cl(tl/1.1)*8,face=-1,pid=i)
        return
    bang=cu[2]-1.6; hit=tl>bang; rule=tl>cu[2]+0.4
    a=-1.1
    if tl>bang-0.5: a=lerp(-0.3,-1.1,cl((tl-bang+0.5)/0.4))
    if hit: a=lerp(-1.1,0.5,cl((tl-bang)/0.12))
    if rule: a=0.5
    guy(c,960,650,1.15,(40,40,48),4,"n",3,[(-90,-40) if not rule else (-110,-230+10*sn(6)),(150,-90)],tie=None,glasses=True,robe=True,talk=(tl<bang-0.5 or rule),lean=3*sn(2.2),pid=7)
    bench(c,960,630,640,300); gavel(c,1170,560,a+1.2)
    if hit and tl<bang+0.5:
        for i in range(8): an=i*0.785; c.line([(1290+60*math.cos(an),610+60*math.sin(an)),(1290+110*math.cos(an),610+110*math.sin(an))],6,RED)
    q=tl-bang
    guy(c,270,960,1.15,NAVY,0,"panic" if hit else "n",0,[(-70,-235+8*sn(15)),(70,-235-8*sn(15))] if hit else None,lean=10*sn(5) if hit else 0,look=1,pid=9)
    for i,x in enumerate([1560,1740]):
        hop=abs(math.sin(q*7+i))*45 if hit and not rule else 0
        guy(c,x,960-hop,1.0,LD[i*2][0],LD[i*2][1],"happy" if hit else "n",LD[i*2][2],[(-40,-150+20*sn(10,i)),(40,-150-20*sn(10,i))] if hit else None,look=-1,face=-1,pid=i)
    if hit and not rule: c.text(960,170,"LENDERS KEEP IT",120,RED,"m",rot=-3,box=WHT,scale=pop(tl,bang+0.1))
    if rule:
        t=tl-cu[2]-0.4; k=pop(t,0)
        c.poly([(480,50),(1440,50),(1440,50+320*k),(480,50+320*k)],(250,240,205))
        if t>0.3: c.text(960,110,"OLD NEW YORK RULE",58,BRN,"m")
        if t>1.6: c.text(960,190,"paid what you're owed",54,INK,"h",scale=pop(t,1.6))
        if t>3.0: c.text(960,255,"+ no idea it was a mistake",54,INK,"h",scale=pop(t,3.0))
        if t>5.0: c.text(960,335,"= IT'S YOURS",72,RED,"m",scale=pop(t,5.0))
    return 12*math.exp(-(tl-bang)*5) if hit else 0
def s9(c,tl,cu):
    tag(c,"2022")
    if tl<cu[1]:
        x,_=go(tl,0,cu[1],-200,2150); h=guy(c,x,900,1.7,NAVY,0,"n",0,[None,(110,-260)],walk=tl*16,pid=9)
        paper(c,(h["R"][0]+60,h["R"][1]+20),240,300,"APPEAL",58); return
    st=cu[2]-2.2; home=tl>cu[2]
    for i,(x,ha,sk) in enumerate([(700,3,4),(960,1,1),(1220,4,0)]):
        conf=tl<st-0.5
        arms=None
        if i==1 and tl>st-0.5: arms=[None,(60,lerp(lerp(-10,-250,cl((tl-st+0.5)/0.3)),-60,cl((tl-st+0.08)/0.08)))]
        guy(c,x,540,1.05,(40,40,48),sk,"n",ha,arms,tie=None,glasses=i!=1,robe=True,lean=(1-i)*9*(0.5+0.5*sn(3)) if conf else 0,talk=conf and int(tl*1.5)%3==i,look=(1-i) if conf else 0,pid=i*3.3)
    bench(c,960,520,900,260); c.text(960,650,"HIGHER COURT",60,(250,235,200),"m")
    if tl>st: c.text(980,150,"REVERSED",125,RED,"m",rot=-9,box=1,scale=pop(tl,st,0.16))
    bank(c,260,1010,0.72,"CITIBANK")
    hop=abs(sn(8))*40 if home else 0
    guy(c,520,1000-hop,0.9,NAVY,0,"happy" if tl>st else "sad",0,[(-50,-140+16*sn(10)),(60,-140-16*sn(10))] if tl>st else None,look=1,pid=9)
    for i in range(4):
        k=cl((tl-cu[2]-i*0.25)/1.6) if home else 0
        x=lerp(1500+i*90,720-i*40,k); y=985-abs(math.sin(k*PI*5))*46*(1 if 0<k<1 else 0)
        bag(c,x,y,0.8)
    if home: c.arrow((1400,800),(820,820),cl((tl-cu[2])/0.8),7,GRN,60)
    return 9*math.exp(-(tl-st)*5) if tl>st else 0
def s10(c,tl,cu):
    if tl<cu[1]:
        bank(c,700,820,1.2,"BANK"); c.line([(640,470),(690,560),(650,640),(720,760)],7,INK,2,prog=cl(tl/0.8))
        x,_=go(tl,0,cu[1],1500,1220); h=guy(c,x,840,1.3,NAVY,0,"sad",0,[None,(30+10*sn(9),-270)],walk=tl*5,face=-1,lean=-6,pid=9)
        c.text(960,170,"the damage was done",96,INK,"m",scale=pop(tl,0.3)); return
    if tl<cu[2]:
        t=tl-cu[1]
        c.poly([(560,90),(1360,70),(1380,1010),(580,1030)],WHT); c.text(970,160,"LOAN CONTRACT",70,INK,"m")
        for i in range(5): c.line([(650,260+i*56),(1290-(i*53)%160,258+i*56)],5,GRY,1.5,prog=cl((t-0.3-i*0.15)/0.4))
        if t>2.6:
            k=cl((t-2.6)/0.6); c.rect(630,580,700*k,190,YEL,0,None)
            c.text(980,630,"NEW CLAUSE:",56,RED,"m",scale=pop(t,3.0)); c.text(980,715,"mistaken payments\nmust be returned",52,INK,"h",scale=pop(t,3.6))
        for i in range(3): c.line([(650,840+i*56),(1250-(i*71)%200,838+i*56)],5,GRY,1.5,prog=cl((t-0.9-i*0.15)/0.4))
        for i,(xf,x0,su,sk,ha) in enumerate([(430,-150,PUR,1,2),(1510,2070,TEAL,3,0)]):
            x,mv=go(t,0,1.1,x0,xf); f=1 if i==0 else -1; wr=(not mv) and t<5.2
            arms=[None,(120+14*sn(16,i),-150+10*sn(11))] if i==0 else [(-120+14*sn(16,i),-150+10*sn(11)),None]
            h=guy(c,x,900,1.1,su,sk,"n" if wr else "happy",ha,arms if not mv else None,walk=t*11 if mv else None,face=f,look=f,lean=f*5 if wr else 0,pid=i)
            if not mv: hd=h["R"] if i==0 else h["L"]; c.line([hd,(hd[0]+f*36,hd[1]+30)],7,BLU,0.8)
        return
    t=tl-cu[2]
    x,y=960,300; sc=pop(t,0.1)*2.2
    c.poly([(x-20*sc,y-40*sc),(x-20*sc,y+22*sc),(x-4*sc,y+6*sc),(x+10*sc,y+36*sc),(x+22*sc,y+30*sc),(x+8*sc,y+2*sc),(x+28*sc,y)],WHT,6)
    if 0.5<t<1.2:
        for i in range(8): an=i*0.785; c.line([(x-44+50*math.cos(an),y-88+50*math.sin(an)),(x-44+90*math.cos(an),y-88+90*math.sin(an))],6,RED)
    c.text(960,560,"ONE WRONG CLICK.",130,INK,"m",scale=pop(t,0.6))
    if t>3.0: c.text(860,800,"THE $900 MILLION TYPO",100,RED,"m",rot=-3,box=WHT,scale=pop(t,3.0))
    gx,mv=go(t,1.2,2.8,2100,1790)
    guy(c,gx,1000,0.85,NAVY,0,"happy" if not mv else "n",0,None if mv else [(-60,-10),(-50,-250+0*t)] if False else (None if mv else [(-90+24*sn(9),-250),None]),walk=t*11 if mv else None,face=-1,pid=9)
SC=[s1,s2,s3,s4,s5,s6,s7,s8,s9,s10]
def render(t,seed):
    G.t=t; i=0
    for j,m in enumerate(META):
        if t>=m["start"]: i=j
    m=META[i]; tl=t-m["start"]; c=Cv(seed)
    sh=SC[i](c,tl,[q-m["start"] for q in m["cues"]]) or 0
    return c.im.reduce(SS),sh,i,tl
if __name__=="__main__":
    if sys.argv[1]=="sheet":
        ts=[float(x) for x in sys.argv[2:]]; cols=4; rows=(len(ts)+3)//4
        sheet=Image.new("RGB",(480*cols,270*rows))
        for k,t in enumerate(ts): sheet.paste(render(t,k)[0].resize((480,270)),((k%cols)*480,(k//cols)*270))
        sheet.save("sheet.jpg",quality=88)
    else:
        Dur=float(sys.argv[2]); p=subprocess.Popen(["ffmpeg","-y","-loglevel","error","-f","rawvideo","-pix_fmt","rgb24","-s","1920x1080","-r","24","-i","-","-c:v","libx264","-crf","20","-preset","medium","-pix_fmt","yuv420p","video2.mp4"],stdin=subprocess.PIPE)
        cur=None
        for f in range(int(Dur*24)):
            t=f/24
            if f%2==0: cur=render(t,(f//4)*7919+1)
            im,sh,i,tl=cur
            z=1.0+0.035*min(1,tl/12)+0.01; w,h=W/z,H/z
            ox=(W-w)/2+(random.uniform(-sh,sh) if sh>0.5 else 0); oy=(H-h)/2+(random.uniform(-sh,sh) if sh>0.5 else 0)
            p.stdin.write(im.resize((W,H),Image.BILINEAR,box=(ox,oy,ox+w,oy+h)).tobytes())
        p.stdin.close(); p.wait()
