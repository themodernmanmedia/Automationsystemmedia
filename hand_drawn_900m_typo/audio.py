import json, numpy as np, soundfile as sf
vo,sr=sf.read("vo.wav"); N=len(vo); t=np.arange(N)/sr; M=json.load(open("vo.json"))
rng=np.random.default_rng(2)
def note(f,dur,amp=1.0):
    tt=np.arange(int(dur*sr))/sr
    return amp*(np.sin(2*np.pi*f*tt)+0.3*np.sin(4*np.pi*f*tt))*np.exp(-tt*5)
mus=np.zeros(N); beat=60/100
scale=[220.0,261.63,293.66,329.63,392.0,440.0,523.25]
pat=[0,2,4,2,5,4,2,1, 0,3,4,3,6,4,3,1]
i=0; tt_=0.0
while tt_<N/sr-1:
    f=scale[pat[i%16]]; a=note(f,0.5,0.5); s=int(tt_*sr); mus[s:s+len(a)]+=a[:N-s]
    if i%4==0:
        b=note([110,110,98,130.81][(i//4)%4],1.0,0.7); mus[s:s+len(b)]+=b[:N-s]
    i+=1; tt_+=beat/2
mus*=0.085
def sfx(t0,f,dur,amp,nz=0.3,drop=6):
    x=np.zeros(N); s=int(t0*sr); n=int(dur*sr); q=np.arange(n)/sr
    y=np.sin(2*np.pi*f*q*np.exp(-q*drop))*np.exp(-q/dur*5)+nz*rng.standard_normal(n)*np.exp(-q*40)
    x[s:s+n]=y[:max(0,N-s)]*amp; return x
c=lambda i,j:M[i]["cues"][j]
fx=sfx(c(0,1),90,0.4,0.5)+sfx(c(0,2)+2.6,70,0.5,0.6)
fx+=sfx(c(3,2)+0.9,900,0.08,0.3,0.1,0)
for k in range(3): fx+=sfx(c(4,2)+0.5+k*0.5,110,0.25,0.5)
fx+=sfx(c(5,1)+4.2,60,0.7,0.6)+sfx(c(7,2)-1.6,140,0.3,0.8,0.6)+sfx(c(8,2)-2.2,100,0.35,0.7)+sfx(c(9,2)+0.5,900,0.08,0.35,0.1,0)
mix=np.tanh((vo*1.05+mus+fx*0.5)*1.05); sf.write("mix.wav",mix,sr); print(N/sr)
