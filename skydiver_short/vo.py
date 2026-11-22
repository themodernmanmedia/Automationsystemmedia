import soundfile as sf, numpy as np, json
from kokoro_onnx import Kokoro
k=Kokoro("tts/kokoro-v1.0.onnx","tts/voices-v1.0.bin")
S=["In 2013, a skydiver jumped from twelve thousand five hundred feet over England.",
"Seconds later, another jumper spun out of control, and struck the back of his helmet, knocking him out cold.",
"He was now falling at around a hundred and twenty miles an hour, completely limp.",
"Two friends noticed he wasn't answering their hand signals.",
"So they flew over, grabbed him, turned him the right way up, and pulled his parachute.",
"He came to just before reaching the ground, and landed safely, with no memory of the fall."]
out=[];t=0;meta=[]
for s in S:
    a,sr=k.create(s,voice="am_michael",speed=1.08,lang="en-us")
    a=np.concatenate([a,np.zeros(int(sr*0.22),dtype=a.dtype)])
    meta.append({"text":s,"start":t,"dur":len(a)/sr}); t+=len(a)/sr; out.append(a)
sf.write("vo.wav",np.concatenate(out),sr); json.dump(meta,open("vo.json","w"),indent=1)
print(sr,t,[round(m["dur"],2) for m in meta])
