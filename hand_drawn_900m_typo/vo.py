import soundfile as sf, numpy as np, json
from kokoro_onnx import Kokoro
k=Kokoro("../tts/kokoro-v1.0.onnx","../tts/voices-v1.0.bin")
S=[["In August 2020, one of the biggest banks in the world wired nine hundred million dollars to the wrong people.","By accident.","And when it asked for the money back, some of them said... no."],
["Here's how it happened.","A cosmetics company called Revlon owed money to a group of lenders. And Citibank was the middleman, the one who passes the payments along."],
["That day, the bank only needed to send about eight million dollars in interest.","Simple."],
["But the software was old, and confusing.","To keep the main loan balance from going out the door, an employee had to tick three separate boxes.","He ticked one."],
["Two more people checked the screen.","It's called a six eyes review.","All six eyes approved it."],
["The next morning, the numbers didn't add up.","Instead of eight million, the bank had sent almost nine hundred million dollars, of its own money, paying off the entire loan, years early."],
["Citibank sent out urgent messages. Please, give it back.","Some lenders did.","But others kept roughly five hundred million dollars.","Their argument? You owed us this money anyway."],
["So the bank sued.","And in 2021, a judge shocked Wall Street. The lenders could keep it.","Under an old New York rule, if you're paid what you're owed, and you had no idea it was a mistake, it's yours."],
["Citibank appealed.","And in 2022, a higher court reversed the decision.","The money finally went home."],
["But the damage was done.","Lenders everywhere rewrote their contracts, adding a new clause, to claw back mistaken payments.","One wrong click, and a whole industry changed its rules."]]
out=[];t=0.6;meta=[];sr=24000;out.append(np.zeros(int(sr*0.6),dtype=np.float32))
for sc in S:
    cues=[];t0=t
    for s in sc:
        a,sr=k.create(s,voice="am_michael",speed=1.04,lang="en-us")
        a=np.concatenate([a,np.zeros(int(sr*0.28),dtype=a.dtype)])
        cues.append(t); t+=len(a)/sr; out.append(a)
    out.append(np.zeros(int(sr*0.35),dtype=np.float32)); t+=0.35
    meta.append({"start":t0,"end":t,"cues":cues})
out.append(np.zeros(int(sr*2.0),dtype=np.float32))
sf.write("vo.wav",np.concatenate(out),sr); json.dump(meta,open("vo.json","w"))
print(t+2,[(round(m["start"],1),[round(c-m["start"],1) for c in m["cues"]]) for m in meta])
