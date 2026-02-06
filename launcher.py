from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import subprocess
import webbrowser
import sounddevice as sd
import os

app = FastAPI()

PROC = None  # holds the running CLI subprocess

HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Nathaniel's Language Buddy</title>
  <style>
    body { font-family: system-ui; max-width: 720px; margin: 40px auto; padding: 0 16px; background: #f78bab; color: #ffffff;}
    .row { margin: 12px 0; }
    button { padding: 10px 14px; font-size: 16px; }
    select { padding: 8px; font-size: 16px; }
    .status { margin-top: 16px; padding: 10px; background: #f6f6f6; border-radius: 8px; color: #000000;}
  </style>
</head>
<body>
  <h1>Happy Valentine's Day!!!</h1>
  <p>Please enjoy your little gift <3</p>

  <div class="row">
  <label>OpenAI API Key:</label><br/>
  <input id="api_key" type="password" placeholder="sk-..." style="width:100%;padding:8px;font-size:16px;">
</div>

  <div class="row">
    <label>Language:</label><br/>
    <select id="language">
      <option>French</option>
      <option>Chinese</option>
      <option>Spanish</option>
      <option>Italian</option>
      <option>German</option>
      <option>Japanese</option>
      <option>Swedish</option>
    </select>
  </div>

  <div class="row">
    <label>Level:</label><br/>
    <select id="level">
      <option>Beginner</option>
      <option selected>Intermediate</option>
      <option>Advanced</option>
    </select>
  </div>
  
  <div class="row">
  <label>Microphone:</label><br/>
  <select id="in_device"></select>
</div>

<div class="row">
  <label>Speaker:</label><br/>
  <select id="out_device"></select>
</div>


  <div class="row">
    <button onclick="start()">Start</button>
    <button onclick="stop()">Stop</button>
  </div>

  <div class="status" id="status">Status: Idle</div>




<script>
async function loadDevices() {
  const r = await fetch('/devices');
  const devs = await r.json();

  const inSel = document.getElementById('in_device');
  const outSel = document.getElementById('out_device');

  inSel.innerHTML = '';
  outSel.innerHTML = '';

  devs.forEach(d => {
    if (d.max_input_channels > 0) {
      const opt = document.createElement('option');
      opt.value = d.index;
      opt.text = `${d.index}: ${d.name}`;
      inSel.appendChild(opt);
    }
    if (d.max_output_channels > 0) {
      const opt = document.createElement('option');
      opt.value = d.index;
      opt.text = `${d.index}: ${d.name}`;
      outSel.appendChild(opt);
    }
  });
}

loadDevices();

async function start() {
  const language = document.getElementById('language').value;
  const level = document.getElementById('level').value;
  const in_device = parseInt(document.getElementById('in_device').value);
  const out_device = parseInt(document.getElementById('out_device').value);
  const api_key = document.getElementById('api_key').value;

  document.getElementById('status').innerText = "Status: starting...";

  const r = await fetch('/start', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({language, level, in_device, out_device, api_key})
  });
  const j = await r.json();
  document.getElementById('status').innerText = "Status: " + j.status;
}


async function stop() {
  document.getElementById('status').innerText = "Status: stopping...";
  const r = await fetch('/stop', {method: 'POST'});
  const j = await r.json();
  document.getElementById('status').innerText = "Status: " + j.status;
}
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def home():
    return HTML

@app.get("/devices")
def devices():
    devs = sd.query_devices()
    out = []
    for i, d in enumerate(devs):
        out.append({
            "index": i,
            "name": d["name"],
            "hostapi": d.get("hostapi"),
            "max_input_channels": d["max_input_channels"],
            "max_output_channels": d["max_output_channels"],
        })
    return out



@app.post("/start")
async def start(payload: dict):
    global PROC
    if PROC is not None and PROC.poll() is None:
        return {"status": "already running"}

    language = payload.get("language", "French")
    level = payload.get("level", "intermediate")
    in_device = str(payload.get("in_device", ""))
    out_device = str(payload.get("out_device", ""))
    api_key = payload.get("api_key", "")
    env = dict(os.environ)
    env["OPENAI_API_KEY"] = api_key

    cmd = ["python3", "cli_app.py", "--language", language, "--level", level]
    if in_device != "":
        cmd += ["--in", in_device]
    if out_device != "":
        cmd += ["--out", out_device]

    PROC = subprocess.Popen(
    ["python3", "cli_app.py", "--language", language, "--level", level, "--in", str(in_device), "--out", str(out_device)],
    env=env
)
    return {"status": f"Running (language={language}, level={level}, in={in_device}, out={out_device})"}


@app.post("/stop")
async def stop():
    global PROC
    if PROC is None or PROC.poll() is not None:
        return {"status": "Not running"}
    PROC.terminate()
    return {"status": "Terminated"}


if __name__ == "__main__":
    # Start server and open browser
    url = "http://127.0.0.1:8000"
    webbrowser.open(url)
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
