import numpy as np, wave
SR=44100; D=120; N=SR*D
L=np.zeros(N); Rr=np.zeros(N)
rng=np.random.default_rng(7)
def add(sig,t,g=1.0,pan=0.0):
    i=int(t*SR); s=sig[:max(0,min(len(sig),N-i))]
    L[i:i+len(s)]+=s*g*(1-max(0,pan)); Rr[i:i+len(s)]+=s*g*(1+min(0,pan))
def env(n,a=.005,r=.2):
    t=np.arange(n)/SR; return np.minimum(1,t/a)*np.exp(-t/r)
def tone(f,dur,a=.005,r=.2,kind='sin'):
    n=int(dur*SR); t=np.arange(n)/SR
    ph=2*np.pi*np.cumsum(np.full(n,f) if np.isscalar(f) else f)/SR
    w=np.sin(ph) if kind=='sin' else (2*((ph/(2*np.pi))%1)-1 if kind=='saw' else np.sign(np.sin(ph)))
    return w*env(n,a,r)
def kick():
    n=int(.35*SR); t=np.arange(n)/SR; f=50+120*np.exp(-t*30)
    return np.sin(2*np.pi*np.cumsum(f)/SR)*np.exp(-t*9)
def noise(d,r): n=int(d*SR); return rng.standard_normal(n)*env(n,.001,r)
def lp(x,k): # simple one-pole lowpass
    y=np.zeros_like(x); a=k; acc=0.
    for i in range(len(x)): acc+=a*(x[i]-acc); y[i]=acc
    return y
def mix(*a):
    n=max(len(x) for x in a); o=np.zeros(n)
    for x in a: o[:len(x)]+=x
    return o
def hp(x): return np.append(x[0],np.diff(x))
hat=hp(hp(noise(.06,.015)))*.5; snare=mix(hp(noise(.25,.07))*.7,tone(190,.15,r=.05)*.4)
K=kick()
# music
bpm=128; beat=60/bpm
prog=[(57,[69,72,76]),(53,[65,69,72]),(48,[67,72,76]),(55,[67,71,74])]
mf=lambda m:440*2**((m-69)/12)
bar=0; t=0.0
while t<D-0.01:
    root,ch=prog[(bar//1)%4]
    for b in range(4):
        tb=t+b*beat
        if tb>=D: break
        quiet = 3.6<=tb<4.0
        add(K,tb,.9 if not quiet else 0)
        add(hat,tb+beat/2,.35,.3)
        if b in(1,3): add(snare,tb,.35)
        for e in range(2):
            add(tone(mf(root-12),beat/2*0.95,a=.003,r=.18,kind='saw')*.5,tb+e*beat/2,.22)
        for s16 in range(4):
            n=ch[(b*4+s16)%3]+ (12 if s16==3 else 0)
            add(tone(mf(n),.18,a=.002,r=.07,kind='saw')*.4+tone(mf(n)*2,.18,r=.05)*.2,tb+s16*beat/4,.09,(-.4 if s16%2 else .4))
    # pad
    pad=sum(tone(mf(n),beat*4,a=.4,r=3) for n in ch)*.15
    add(pad,t,.25)
    bar+=1; t+=beat*4
music_gain=0.55
L*=music_gain; Rr*=music_gain
# SFX
def whoosh(d=1.2,up=True):
    n=int(d*SR); x=rng.standard_normal(n); t=np.linspace(0,1,n)
    k=(0.02+0.25*(t if up else 1-t)); y=np.zeros(n); acc=0
    for i in range(n): acc+=k[i]*(x[i]-acc); y[i]=acc
    return y*np.sin(np.pi*t)**1.5*2.2
def hit(): return mix(kick()*1.2,lp(noise(.6,.25),.08)*1.8,tone(55,.8,r=.5)*.5)
def pop(): n=int(.12*SR); t=np.arange(n)/SR; f=500+900*np.exp(-t*40); return np.sin(2*np.pi*np.cumsum(f)/SR)*env(n,.001,.04)*.8
def ding(): return sum(tone(f,1.4,r=.5)*g for f,g in [(1318.5,.5),(1975.5,.3),(2637,.15)])
def blip(f): return tone(f,.05,r=.02,kind='sq')*.12
def tick(hi=False): return mix(tone(1800 if hi else 1200,.04,r=.012)*(.7 if hi else .45),hp(noise(.02,.004))*.2)
WH=whoosh(1.0); WH2=whoosh(2.6); H=hit(); P=pop(); DG=ding()
for k in range(5): add(H,k*.72,.6); add(whoosh(.5),k*.72,.35)
add(whoosh(1.0),2.6,.6); add(H,3.6,1.1)
for i in range(5):
    s0=10+20*i
    add(WH,s0-.4,.6); add(H,s0+.2,.7)
    for c in (4,6.5,9): add(P,s0+c,.9)
    for k in range(10):
        add(tick(k>=7),s0+3+k,1.0)
    add(sum(tone(f,.6,a=.005,r=.25,kind='saw') for f in (220,277,330))*.35,s0+13,.8)
    add(WH2,s0+14.5,.55)
    add(H,s0+17.0,.6); add(DG,s0+17.0,.7)
    for k in range(12): add(blip(700+k*60),s0+17.9+k*.1,1)
add(H,110,1.0)
for k in range(20): add(blip(600+k*40),110.6+k*.1,1)
for j,f in enumerate((523.25,659.25,783.99,1046.5)): add(tone(f,1.2,r=.5,kind='saw')*.25+tone(f,1.2,r=.6)*.3,112.6+j*.09,.8)
add(H,115.2,.9); add(DG,115.2,.5)
# fade out end
fo=np.ones(N); fo[-int(3*SR):]=np.linspace(1,0,int(3*SR)); L*=fo; Rr*=fo
m=max(np.abs(L).max(),np.abs(Rr).max()); L=np.tanh(L/m*1.3)*.89; Rr=np.tanh(Rr/m*1.3)*.89
out=(np.stack([L,Rr],1)*32767).astype(np.int16)
with wave.open('audio.wav','wb') as w: w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(out.tobytes())
print('ok')
