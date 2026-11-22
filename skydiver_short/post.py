import json, numpy as np, soundfile as sf
meta=json.load(open("vo.json")); vo,sr=sf.read("vo.wav"); D=32.6; N=int(D*sr)
rng=np.random.default_rng(1); t=np.arange(N)/sr
def lp(x,a):
    y=np.empty_like(x); acc=0.0
    for i in range(len(x)): acc+=a*(x[i]-acc); y[i]=acc
    return y
noise=rng.standard_normal(N)
wind=lp(noise,0.06)-lp(noise,0.004)
wind*= (1+0.35*np.sin(2*np.pi*0.7*t)+0.2*np.sin(2*np.pi*1.9*t+1))
def env(pts): return np.interp(t,[p[0] for p in pts],[p[1] for p in pts])
wenv=env([(0,0.15),(2.3,0.2),(5,0.9),(24.6,1.0),(25.2,0.25),(30.5,0.15),(32.6,0.0)])
wind=wind/np.abs(wind).max()*0.30*wenv
eng=(np.sign(np.sin(2*np.pi*85*t))*0.5+np.sin(2*np.pi*42*t))
eng=lp(eng,0.05)*env([(0,0.10),(3,0.10),(6,0.0),(32.6,0)])
def hit(t0,f,dur,amp):
    x=np.zeros(N); i=int(t0*sr); n=int(dur*sr); tt=np.arange(n)/sr
    s=np.sin(2*np.pi*f*tt*np.exp(-tt*6))*np.exp(-tt/dur*5)+0.4*lp(rng.standard_normal(n),0.2)*np.exp(-tt*25)
    x[i:i+n]=s[:N-i]*amp; return x
fx=hit(10.25,95,0.5,0.8)+hit(24.65,60,0.9,0.7)+hit(30.53,70,0.35,0.35)
mix=wind+eng+fx; mix[:len(vo)]+=vo*1.0
mix=np.tanh(mix*1.1); sf.write("mix.wav",mix,sr)
# captions
def ts(x): h=int(x//3600); m=int(x//60)%60; s=x%60; return f"{h}:{m:02d}:{s:05.2f}"
L=["[Script Info]","ScriptType: v4.00+","PlayResX: 1080","PlayResY: 1920","","[V4+ Styles]",
"Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
"Style: C,Inter Display,92,&H00FFFFFF,&H00FFFFFF,&H00101010,&H80000000,-1,0,0,0,100,100,0,0,1,7,3,2,60,60,430,1","","[Events]",
"Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
for m in meta:
    words=m["text"].split(); chunks=[]; cur=[]
    for w in words:
        cur.append(w)
        if len(cur)==3 or w[-1] in ",." or len(" ".join(cur))>13: chunks.append(cur); cur=[]
    if cur: chunks.append(cur)
    speech=m["dur"]-0.3; tot=sum(len(" ".join(c))+2 for c in chunks); a=m["start"]
    for c in chunks:
        d=speech*(len(" ".join(c))+2)/tot
        txt=" ".join(c).strip(",.").upper()
        L.append(f"Dialogue: 0,{ts(a)},{ts(a+d)},C,,0,0,0,,{{\\fscx85\\fscy85\\t(0,90,\\fscx100\\fscy100)}}{txt}"); a+=d
open("cap.ass","w").write("\n".join(L)+"\n"); print(len(L))
