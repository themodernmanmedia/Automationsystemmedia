import bpy, math, random, sys, os
from mathutils import Vector, Euler
R=math.radians
FPS=24
T=[0,6.0,12.66,17.62,21.10,25.93,32.6]
OUT=os.path.dirname(os.path.abspath(__file__))+"/frames"
bpy.ops.wm.read_factory_settings(use_empty=True)
S=bpy.context.scene
S.render.engine='CYCLES'; S.cycles.samples=int(os.environ.get("SPP","24")); S.cycles.use_denoising=True
S.cycles.max_bounces=3; S.cycles.diffuse_bounces=2; S.cycles.glossy_bounces=2
S.render.resolution_x=720; S.render.resolution_y=1280; S.render.fps=FPS
S.render.image_settings.file_format='PNG'; S.view_settings.view_transform='Standard'
S.render.use_persistent_data=True
col=S.collection

def mat(name,c,rough=0.55,emis=0.0,metal=0.0):
    m=bpy.data.materials.new(name); m.use_nodes=True
    b=m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value=(*c,1); b.inputs["Roughness"].default_value=rough
    b.inputs["Metallic"].default_value=metal
    if emis:
        b.inputs["Emission Color"].default_value=(*c,1); b.inputs["Emission Strength"].default_value=emis
    return m
def fin(o,m,parent=None,smooth=True):
    if m: o.data.materials.append(m)
    if smooth:
        for p in o.data.polygons: p.use_smooth=True
    if parent: o.parent=parent
    return o
def sphere(r,loc,m,parent=None,scale=(1,1,1)):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r,location=loc,segments=24,ring_count=12)
    o=bpy.context.object; o.scale=scale; return fin(o,m,parent)
def cyl(r,d,loc,m,parent=None,rot=(0,0,0),verts=20):
    bpy.ops.mesh.primitive_cylinder_add(radius=r,depth=d,location=loc,rotation=rot,vertices=verts)
    return fin(bpy.context.object,m,parent)
def box(size,loc,m,parent=None,bevel=0.04,rot=(0,0,0)):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc,rotation=rot)
    o=bpy.context.object; o.scale=size
    if bevel:
        bpy.ops.object.transform_apply(scale=True)
        b=o.modifiers.new("b",'BEVEL'); b.width=bevel; b.segments=4
    return fin(o,m,parent)
def empty(loc=(0,0,0),parent=None):
    e=bpy.data.objects.new("e",None); col.objects.link(e); e.location=loc
    if parent: e.parent=parent
    return e
def capsule(r,L,m,parent):
    cyl(r,L,(0,0,-L/2),m,parent); sphere(r,(0,0,0),m,parent); sphere(r,(0,0,-L),m,parent)

# ---------- world ----------
W=bpy.data.worlds.new("w"); S.world=W; W.use_nodes=True
nt=W.node_tree; bg=nt.nodes["Background"]
tc=nt.nodes.new("ShaderNodeTexCoord"); sp=nt.nodes.new("ShaderNodeSeparateXYZ"); ramp=nt.nodes.new("ShaderNodeValToRGB")
mp=nt.nodes.new("ShaderNodeMapRange"); mp.inputs[1].default_value=-0.25; mp.inputs[2].default_value=1
nt.links.new(tc.outputs["Generated"],sp.inputs[0]); nt.links.new(sp.outputs["Z"],mp.inputs[0]); nt.links.new(mp.outputs[0],ramp.inputs[0])
cr=ramp.color_ramp; cr.elements[0].position=0.0; cr.elements[0].color=(0.62,0.80,0.95,1)
cr.elements[1].position=1.0; cr.elements[1].color=(0.05,0.22,0.62,1)
e=cr.elements.new(0.22); e.color=(0.80,0.90,0.98,1)
nt.links.new(ramp.outputs[0],bg.inputs[0]); bg.inputs[1].default_value=0.75
bpy.ops.object.light_add(type='SUN',rotation=(R(40),R(15),R(30))); SUN=bpy.context.object; SUN.data.energy=3.0; SUN.data.angle=R(3)

# ---------- ground ----------
gm=bpy.data.materials.new("ground"); gm.use_nodes=True; n=gm.node_tree
bs=n.nodes["Principled BSDF"]; bs.inputs["Roughness"].default_value=1
tco=n.nodes.new("ShaderNodeTexCoord"); vor=n.nodes.new("ShaderNodeTexVoronoi"); vor.inputs["Scale"].default_value=0.006
rp=n.nodes.new("ShaderNodeValToRGB"); c=rp.color_ramp
c.elements[0].color=(0.10,0.30,0.07,1); c.elements[1].color=(0.45,0.50,0.15,1)
for p,cc in((0.35,(0.16,0.42,0.10,1)),(0.6,(0.25,0.50,0.14,1)),(0.8,(0.55,0.47,0.22,1))):
    q=c.elements.new(p); q.color=cc
n.links.new(tco.outputs["Object"],vor.inputs["Vector"]); n.links.new(vor.outputs["Color"],rp.inputs[0])
cd=n.nodes.new("ShaderNodeCameraData"); mr=n.nodes.new("ShaderNodeMapRange"); mr.inputs[1].default_value=3000; mr.inputs[2].default_value=40000
mix=n.nodes.new("ShaderNodeMixRGB"); mix.inputs[2].default_value=(0.72,0.85,0.97,1)
n.links.new(cd.outputs["View Distance"],mr.inputs[0]); n.links.new(mr.outputs[0],mix.inputs[0]); n.links.new(rp.outputs[0],mix.inputs[1])
n.links.new(mix.outputs[0],bs.inputs["Base Color"])
bpy.ops.mesh.primitive_plane_add(size=120000); GROUND=bpy.context.object; GROUND.data.materials.append(gm)
# trees for landing
random.seed(4)
TREES=empty(parent=GROUND)
tm=mat("tree",(0.07,0.28,0.08),0.9); trm=mat("trunk",(0.25,0.15,0.07),0.9)
for i in range(40):
    a=random.uniform(0,6.28); r=random.uniform(14,90); h=random.uniform(4,8)
    x,y=r*math.cos(a),r*math.sin(a)
    cyl(0.25,h*0.4,(x,y,h*0.2),trm,TREES)
    sphere(h*0.3,(x,y,h*0.62),tm,TREES,scale=(1,1,1.3))

# ---------- clouds ----------
cm=mat("cloud",(1,1,1),1.0,emis=0.08)
random.seed(7); CLOUDS=[]
BOXH=260.0
for i in range(46):
    a=random.uniform(0,6.28); r=random.uniform(28,170)
    base=Vector((r*math.cos(a),r*math.sin(a),random.uniform(-BOXH,BOXH)))
    root=empty()
    s=random.uniform(7,18)
    for j in range(7):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3,radius=s*random.uniform(0.45,1.0),
            location=(random.uniform(-1.4,1.4)*s,random.uniform(-1.0,1.0)*s,random.uniform(-0.3,0.35)*s))
        o=bpy.context.object; o.scale=(1,1,0.6); fin(o,cm,root)
    CLOUDS.append((root,base))
# speed streaks
stm=mat("streak",(1,1,1),1,emis=0.6); STREAKS=[]
for i in range(16):
    a=random.uniform(0,6.28); r=random.uniform(3.5,11)
    o=cyl(0.008,random.uniform(1.0,2.5),(0,0,0),stm)
    STREAKS.append((o,Vector((r*math.cos(a),r*math.sin(a),random.uniform(-25,25))),random.uniform(0.8,1.3)))

# ---------- skydiver (original stylised design) ----------
def diver(suit,accent,helmet,cam=False):
    ms=mat("suit",suit,0.7); ma=mat("acc",accent,0.6); mh=mat("helm",helmet,0.25)
    mv=mat("visor",(0.02,0.03,0.05),0.08,metal=0.6); mg=mat("glove",(0.06,0.06,0.07),0.6); mr_=mat("rig",(0.08,0.09,0.12),0.7)
    d={}; root=empty(); d["root"]=root
    box((0.44,0.26,0.58),(0,0,0),ms,root,0.09)
    box((0.46,0.27,0.07),(0,0,-0.08),ma,root,0.03)            # chest stripe
    box((0.36,0.15,0.46),(0,0.19,0.03),mr_,root,0.05)         # container
    for sx in(-1,1): box((0.05,0.28,0.5),(sx*0.13,0.0,0.03),mr_,root,0.015)  # harness straps
    hd=empty((0,0,0.47),root); d["head"]=hd
    sphere(0.175,(0,0,0),mh,hd); sphere(0.15,(0,-0.07,-0.01),mv,hd,scale=(0.95,0.75,0.6))
    box((0.05,0.36,0.03),(0,0,0.165),ma,hd,0.01)             # helmet stripe
    if cam: box((0.07,0.1,0.06),(0,-0.03,0.2),mr_,hd,0.01)
    for side,sx in(("L",1),("R",-1)):
        sh=empty((sx*0.29,0,0.2),root); d["sh"+side]=sh; capsule(0.075,0.3,ms,sh)
        el=empty((0,0,-0.3),sh); d["el"+side]=el; capsule(0.065,0.27,ms,el); sphere(0.08,(0,0,-0.31),mg,el)
        hp=empty((sx*0.12,0,-0.3),root); d["hip"+side]=hp; capsule(0.095,0.4,ms,hp)
        kn=empty((0,0,-0.4),hp); d["kn"+side]=kn; capsule(0.08,0.38,ms,kn)
        box((0.14,0.26,0.11),(0,-0.05,-0.43),mg,kn,0.03)
    return d
def pose(d,p):
    for k,v in p.items(): d[k].rotation_euler=Euler((R(v[0]),R(v[1]),R(v[2])),'XYZ')
def lerp(a,b,u): return a+(b-a)*u
def sm(u): u=max(0,min(1,u)); return u*u*(3-2*u)
def mixp(a,b,u): return {k:tuple(lerp(a[k][i],b[k][i],u) for i in range(3)) for k in a}
def BOX(t=0,ph=0):
    w=math.sin(t*7+ph)*3
    return dict(shL=(8,-88+w,0),shR=(8,88-w,0),elL=(0,-80,0),elR=(0,80,0),hipL=(18,-14,0),hipR=(18,14,0),
                knL=(48+w,0,0),knR=(48-w,0,0),head=(-18,0,0))
def LIMP(t=0):
    a=math.sin(t*5.1)*14; b=math.sin(t*3.7+1)*12; c=math.sin(t*4.3+2)*10
    return dict(shL=(-105+a,-28,0),shR=(-95+b,30,0),elL=(-25+c,0,0),elR=(-35-a,0,0),hipL=(-62+b,-10,0),hipR=(-50+c,12,0),
                knL=(38+a,0,0),knR=(55+b,0,0),head=(18+c*0.6,b*0.8,0))
def WAVE(t,ph=0):
    p=BOX(t,ph); w=math.sin(t*11+ph)
    p["shR"]=(-25,115,0); p["elR"]=(0,45+35*w,0); return p
def REACH(t):
    p=BOX(t); p["shL"]=(-70,-20,0); p["shR"]=(-70,20,0); p["elL"]=(-10,0,0); p["elR"]=(-10,0,0); return p
def HANG(t):
    s=math.sin(t*2)*4
    return dict(shL=(0,-158,0),shR=(0,158,0),elL=(0,-12,0),elR=(0,12,0),hipL=(-12+s,-5,0),hipR=(-8-s,5,0),knL=(18,0,0),knR=(14,0,0),head=(-10,0,0))
def TUCK(t):
    return dict(shL=(-40,-30,0),shR=(-40,30,0),elL=(-70,0,0),elR=(-70,0,0),hipL=(-70,-8,0),hipR=(-70,8,0),knL=(80,0,0),knR=(80,0,0),head=(-10,0,0))
def SPINP(t):
    a=math.sin(t*9)*25
    return dict(shL=(a,-120,0),shR=(-a,70,0),elL=(0,-30,0),elR=(0,60,0),hipL=(-30+a,-25,0),hipR=(40-a,20,0),knL=(60,0,0),knR=(20,0,0),head=(0,a,0))

HERO=diver((0.95,0.33,0.05),(1,0.85,0.1),(0.95,0.95,0.95),cam=True)
F1=diver((0.02,0.55,0.60),(1,1,1),(0.1,0.12,0.15))
F2=diver((0.42,0.16,0.70),(0.3,0.9,0.5),(0.9,0.2,0.2))
YEL=diver((0.92,0.78,0.08),(0.1,0.1,0.1),(0.15,0.3,0.8))
FAR=(0,0,9000)
def place(d,loc,rot): d["root"].location=loc; d["root"].rotation_euler=Euler(tuple(R(x) for x in rot),'XYZ')

# ---------- canopy ----------
CAN=empty(parent=HERO["root"])
c1=mat("can1",(0.95,0.33,0.05),0.8); c2=mat("can2",(0.97,0.97,0.97),0.8); lm=mat("line",(0.9,0.9,0.9),0.8)
for i in range(7):
    x=(i-3)*0.78; z=6.0-abs(i-3)**2*0.07
    box((0.76,2.6,0.34),(x,0.2,z),c1 if i%2==0 else c2,CAN,0.12,rot=(R(-6),R((i-3)*5.5),0))
for sx in(-1,1):
    for x,y in((sx*2.6,-0.9),(sx*2.6,1.3),(sx*1.0,-0.9),(sx*1.0,1.3)):
        a=Vector((sx*0.2,0.12,0.3)); b=Vector((x,y,5.55-abs(x)*0.1)); dvec=b-a
        o=cyl(0.012,dvec.length,(a+b)/2,lm,CAN,verts=6); o.rotation_euler=dvec.to_track_quat('Z','Y').to_euler()

# ---------- plane ----------
PL=empty()
pw=mat("pw",(0.95,0.95,0.96),0.35); pr=mat("pr",(0.8,0.1,0.1),0.4); pk=mat("pk",(0.02,0.02,0.03),0.6); pg=mat("pg",(0.15,0.25,0.35),0.1)
sphere(1.0,(0,0,0),pw,PL,scale=(5.2,1.0,1.05))
box((10.6,2.05,0.14),(0,0,-0.25),pr,PL,0.05)
box((2.0,13,0.16),(0.9,0,0.95),pw,PL,0.06)
box((1.3,4.4,0.1),(-4.6,0,0.35),pw,PL,0.04); box((1.5,0.1,1.7),(-4.6,0,1.0),pr,PL,0.04,rot=(0,R(-20),0))
box((1.15,0.2,1.25),(-0.9,-0.92,-0.02),pk,PL,0.03)       # open door
box((1.3,1.7,0.5),(3.4,0,0.45),pg,PL,0.1)                # windscreen
for sx in(-1,1): cyl(0.05,1.6,(0.9,sx*0.6,0.2),pk,PL)
sphere(0.25,(5.15,0,0),pk,PL); PROP=empty((5.3,0,0),PL)
box((0.05,2.6,0.2),(0,0,0),pk,PROP,0.02); box((0.05,0.2,2.6),(0,0,0),pk,PROP,0.02)
for sx in(-1,1):
    cyl(0.04,0.9,(1.0,sx*0.8,-1.2),pk,PL); cyl(0.28,0.16,(1.0,sx*0.8,-1.65),pk,PL,rot=(R(90),0,0))

bpy.ops.object.camera_add(); CAM=bpy.context.object; S.camera=CAM; CAM.data.clip_end=200000; CAM.data.lens=30
def look(pos,target,roll=0,lens=30):
    CAM.location=pos; dv=Vector(target)-Vector(pos)
    e=dv.to_track_quat('-Z','Y').to_euler(); CAM.rotation_euler=e; CAM.rotation_euler.rotate_axis('Z',R(roll)); CAM.data.lens=lens

def env(t,vel,gz,streak=True):
    for root,base in CLOUDS:
        p=base+Vector(vel)*t
        p.z=((p.z+BOXH)%(2*BOXH))-BOXH; p.x=((p.x+200)%400)-200
        if abs(p.x)<22 and abs(p.y)<22: p.y+=45
        root.location=p
    for o,base,sp in STREAKS:
        if streak:
            z=((base.z+70*sp*t+25)%50)-25; o.location=(base.x,base.y,z)
        else: o.location=FAR
    GROUND.location=(0,0,gz)

def apply(f):
    t=f/FPS
    for d in(HERO,F1,F2,YEL): place(d,FAR,(0,0,0))
    PL.location=FAR; CAN.scale=(0.001,)*3
    if t<T[1]:                                   # 1: exit from aircraft
        env(t,(-38,0,0),-3800,False); PL.location=(0,0,0); PL.rotation_euler=(R(math.sin(t*1.3)*1.5),0,0)
        PROP.rotation_euler=(t*47,0,0)
        door=Vector((-0.9,-1.0,-0.1))
        for d,t0,ph in((HERO,2.3,0),(YEL,3.1,1),(F1,3.8,2),(F2,4.4,3)):
            u=t-t0
            if u<0: continue
            p=door+Vector((-9*u*u-1.5*u,-1.6*u-0.3*math.sin(ph)*u,-4.6*u*u+0.4*u))
            k=sm(u/1.3); pose(d,mixp(TUCK(t),BOX(t,ph),k)); place(d,p,(lerp(10,90,k),0,lerp(-90,-70,k)+ph*8))
        k=sm((t-2.3)/3.2)
        hp=HERO["root"].location if t>2.3 else door
        tgt=Vector((-0.5,0,0)).lerp(Vector(hp),k*0.75)
        look((-13+2*sm(t/2.5)-6*k,-8+1.5*sm(t/2.5),2.2-3.5*k),tgt,lens=30)
    elif t<T[2]:                                 # 2: collision
        u=t-T[1]; hit=4.25; env(t,(0,0,55),-3300)
        if u<hit:
            pose(HERO,BOX(t)); place(HERO,(0,0,math.sin(t*2)*0.06),(90+math.sin(t*3)*3,math.sin(t*2.2)*4,0))
        else:
            k=sm((u-hit)/0.9); pose(HERO,mixp(BOX(t),LIMP(t),k))
            place(HERO,(0,-0.4*k,-0.5*k),(90+25*k,k*180,(u-hit)*40))
        v=u/hit
        if u<hit: yp=Vector((lerp(-2.5,0.25,v)+math.sin(u*5)*0.5*(1-v),lerp(3.5,-0.25,v),lerp(9,0.75,v*v)))
        else: yp=Vector((0.25+(u-hit)*1.8,-0.25-(u-hit)*1.2,0.75-(u-hit)*2.2))
        pose(YEL,SPINP(t)); place(YEL,yp,(70+u*210,u*150,u*320))
        sh=math.exp(-(u-hit)*6)*0.25 if u>=hit else 0
        a=R(-55+u*14)
        look((4.6*math.cos(a)+sh*math.sin(t*90),4.6*math.sin(a)-0.5,-1.3+u*0.25+sh*math.cos(t*70)),(0,-0.1,0.9-0.12*u),lens=28)
    elif t<T[3]:                                 # 3: limp freefall
        u=t-T[2]; env(t,(0,0,60),-2700)
        pose(HERO,LIMP(t)); place(HERO,(0,0,0),(90+math.sin(t*1.7)*22,180+math.sin(t*1.1)*25,u*55))
        a=R(200+u*26); rr=lerp(2.5,3.6,sm(u/5))
        look((rr*math.cos(a),rr*math.sin(a),lerp(-2.6,1.6,sm(u/4.6))),(0,0,0),roll=math.sin(u)*6,lens=26)
    elif t<T[4]:                                 # 4: hand signals
        u=t-T[3]; env(t,(0,0,60),-2200)
        pose(HERO,LIMP(t)); place(HERO,(0,0,0),(90+math.sin(t*1.7)*15,180+math.sin(t*1.1)*18,30+u*20))
        pose(F1,WAVE(t,0)); place(F1,(1.7,2.0,1.5+math.sin(t*2)*0.1),(75,0,-140))
        pose(F2,WAVE(t,2)); place(F2,(-1.6,2.4,2.3+math.sin(t*2+1)*0.1),(75,0,145))
        look((0.5-u*0.25,-5.2,-0.6),(0,0.9,1.0),lens=25)
    elif t<T[5]:                                 # 5: rescue + deployment
        u=t-T[4]; env(t,(0,0,60),-1500); pull=3.55
        k=sm(u/1.4); roll=lerp(180,0,sm((u-1.5)/1.5)); up=max(0,u-pull)
        hz=9*up*up
        if up>0:
            q=sm(up/0.5); pose(HERO,mixp(BOX(t),HANG(t),q)); place(HERO,(0,0,hz),(lerp(90,0,q),0,0))
            CAN.scale=(lerp(0.15,1,q),lerp(0.15,1,q),lerp(0.3,1,q))
        else:
            pose(HERO,mixp(LIMP(t),BOX(t),sm((u-1.5)/1.5)*0.8)); place(HERO,(0,0,0),(90+math.sin(t*1.7)*10*(1-k),roll,0))
        for d,sx in((F1,1),(F2,-1)):
            away=sm(up/0.6)
            p=Vector((sx*lerp(1.7,1.05,k)+sx*away*1.2,lerp(2.1,0.15,k),lerp(1.6+0.4*(sx<0),0.12,k)))
            pose(d,mixp(BOX(t,sx),REACH(t),k*(1-away))); place(d,p,(lerp(75,90,k),0,-sx*lerp(140,90,k)))
        look((2.2-u*0.5,-5.4,lerp(2.6,-1.5,sm(up/1.0))),(0,0,min(hz,14)*0.75+0.2),lens=lerp(26,22,sm(up)))
    else:                                        # 6: canopy ride + landing
        u=t-T[5]; land=4.6; env(u,(0,0,0),0,False)
        for root,base in CLOUDS: root.location=(base.x*2.2,abs(base.y)*2+160,90+abs(base.z)*0.5)
        h=max(0,(land-u))*5.2; kk=sm((u-land)/0.35); kc=sm((u-land)/1.2)
        GROUND.location=(0,0,-0.93-h)
        sw=math.sin(u*1.6)*5*(1-kk)
        p=HANG(t)
        if u>land:
            p=mixp(p,dict(p,shL=(0,-25,0),shR=(0,25,0),hipL=(-25,-5,0),hipR=(5,5,0),knL=(35,0,0),knR=(10,0,0)),kc)
        pose(HERO,p); place(HERO,(0,0,-0.12*kk*(1-kc)),(sw*0.5,sw,20))
        CAN.scale=(1,1,1); CAN.location=(0,0,0)
        if u>land: CAN.scale=(1,lerp(1,0.7,kc),lerp(1,0.25,kc)); CAN.location=(0,lerp(0,2.5,kc),0)
        a=R(-100+u*9)
        look((9.5*math.cos(a),9.5*math.sin(a),lerp(1.5,0.6,sm(u/land))),(0,0,lerp(2.9,2.2,sm(u/land))),lens=24)

if __name__=="__main__":
    a,b=int(sys.argv[-3]),int(sys.argv[-2]); step=int(sys.argv[-1])
    os.makedirs(OUT,exist_ok=True)
    for f in range(a,b,step):
        fp=f"{OUT}/{f:04d}.png"
        if os.path.exists(fp): continue
        apply(f); S.render.filepath=fp; bpy.ops.render.render(write_still=True)
