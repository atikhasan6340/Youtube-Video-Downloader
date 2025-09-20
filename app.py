#!/usr/bin/env python3
# app.py — YouTube Downloader (No Login, Mobile-Friendly)

import os
import uuid
from flask import Flask, request, send_file, render_template_string, jsonify, abort, after_this_request
import yt_dlp

# ------------------------
# App & Directories
# ------------------------
APP_DIR = os.path.abspath(os.path.dirname(__file__))
TEMP_DOWNLOADS = os.path.join(APP_DIR, "temp_downloads")
os.makedirs(TEMP_DOWNLOADS, exist_ok=True)

app = Flask(__name__)

# ------------------------
# HTML Template
# ------------------------
INDEX_HTML = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>YouTube Video Downloader</title>
<style>
body { font-family: Arial; background:#1a1a1a; color:#fff; margin:0; display:flex; justify-content:center; align-items:center; min-height:100vh; }
.card { background:#2a2a2a; padding:20px; border-radius:12px; box-shadow:0 10px 25px rgba(0,0,0,0.5); width:95%; max-width:500px; text-align:center; box-sizing:border-box; }
.card h2 { color:#ff4444; margin-bottom:15px; font-size:1.5em; }
input[type=text], button { width:100%; padding:14px; margin:8px 0; border-radius:8px; font-size:1em; box-sizing:border-box; }
input[type=text] { border:1px solid #444; background:#1e1e1e; color:#fff; }
input:-webkit-autofill, input:-webkit-autofill:hover, input:-webkit-autofill:focus, input:-webkit-autofill:active { -webkit-box-shadow:0 0 0px 1000px #1e1e1e inset !important; -webkit-text-fill-color:#fff !important; }
button { background:#ff4444; color:#fff; border:none; cursor:pointer; }
button:disabled { opacity:0.6; cursor:default; }
.formatItem { padding:10px; margin:5px 0; background:#1e1e1e; border-radius:6px; cursor:pointer; transition:0.2s; word-break:break-word; }
.formatItem:hover { background:#ff4444; color:#fff; }
#formatPopup { display:none; position:fixed; top:50%; left:50%; transform:translate(-50%,-50%); background:#2a2a2a; padding:20px; border-radius:12px; box-shadow:0 8px 20px rgba(0,0,0,0.6); width:90%; max-width:350px; text-align:center; z-index:1000; }
#statusText { margin-top:10px; color:#ff4444; word-wrap:break-word; }
@media(max-width:400px){ .card{padding:15px;} input[type=text], button{font-size:0.95em; padding:12px;} #formatPopup{padding:15px;} }
</style>
</head>
<body>
<div class="card">
<h2>YouTube Video Downloader</h2>
<input id="url" type="text" placeholder="Paste YouTube link here" />
<button id="getFormatsBtn" onclick="fetchFormats()">Formats</button>
<button id="dlbtn" onclick="startDownload()" disabled>Download</button>
<div id="statusText"></div>
</div>

<div id="formatPopup">
<h3>Select Format</h3>
<div id="formatList"></div>
<button onclick="closeFormatPopup()">Cancel</button>
</div>

<script>
let selectedFormat = null;

async function fetchFormats(){
    const url = document.getElementById("url").value.trim();
    if(!url){ alert("Please enter a URL"); return; }

    const btn = document.getElementById("getFormatsBtn");
    btn.disabled = true;
    btn.innerHTML = "Loading... ⏳";

    const fd = new FormData();
    fd.append("url", url);

    try{
        let res = await fetch("/formats", { method:"POST", body: fd });
        let data = await res.json();

        if(data.formats.length === 0){
            alert("No mp4 formats available.");
            btn.disabled = false;
            btn.innerHTML = "Formats";
            return;
        }

        const formatList = document.getElementById("formatList");
        formatList.innerHTML = "";
        data.formats.forEach(f=>{
            let div = document.createElement("div");
            div.className = "formatItem";
            let size = f.filesize ? (f.filesize/1024/1024).toFixed(2)+" MB" : "";
            div.innerText = `${f.resolution} (${f.ext}) ${size}`;
            div.onclick = ()=>{
                selectedFormat = f.format_id;
                closeFormatPopup();
                document.getElementById("dlbtn").disabled = false;
            };
            formatList.appendChild(div);
        });

        document.getElementById("formatPopup").style.display = "block";

    }catch(e){
        alert("Failed to fetch formats");
    }finally{
        btn.disabled = false;
        btn.innerHTML = "Formats";
    }
}

function closeFormatPopup(){ document.getElementById("formatPopup").style.display = "none"; }

async function startDownload(){
    const url = document.getElementById("url").value.trim();
    if(!url || !selectedFormat){ alert("Please select a format"); return; }

    let btn = document.getElementById("dlbtn");
    btn.disabled = true;
    document.getElementById("statusText").innerText = "Preparing download... ⏳";

    try{
        let res = await fetch("/download_wait", {
            method:"POST",
            headers:{ 'Content-Type':'application/json' },
            body: JSON.stringify({ url:url, format: selectedFormat })
        });
        let j = await res.json();
        if(res.ok){
            const videoId = j.video_id;
            const link = document.createElement('a');
            link.href = `/download_file/${videoId}`;
            link.download = 'video.mp4';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);

            document.getElementById("statusText").innerText = "";
            btn.disabled = false;
            selectedFormat = null;
        } else {
            document.getElementById("statusText").innerText = "Download failed!";
            btn.disabled = false;
        }
    }catch(e){
        document.getElementById("statusText").innerText = "Error occurred!";
        btn.disabled = false;
    }
}
</script>
</body>
</html>
"""

# ------------------------
# Routes
# ------------------------
@app.route('/')
def index():
    return render_template_string(INDEX_HTML)

@app.route("/formats", methods=["POST"])
def formats():
    url = request.form.get("url")
    if not url:
        return jsonify({"error":"No URL provided"}), 400
    try:
        ydl_opts = {"quiet": True, "no_warnings": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            fmts = []
            for f in info.get("formats", []):
                if f.get("ext") != "mp4" or f.get("vcodec")=="none":
                    continue
                fmts.append({
                    "format_id": f["format_id"],
                    "ext": f["ext"],
                    "resolution": f.get("resolution") or f"{f.get('height','audio')}p",
                    "filesize": f.get("filesize"),
                })
            return jsonify({"title": info.get("title"), "formats": fmts})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/download_wait", methods=["POST"])
def download_wait():
    data = request.get_json() or {}
    url = data.get("url")
    fmt = data.get("format")
    if not url or not fmt:
        return jsonify({"error":"URL or format missing"}), 400

    video_id = uuid.uuid4().hex
    filepath = os.path.join(TEMP_DOWNLOADS, f"{video_id}.mp4")

    ydl_opts = {
        "format": fmt + "+bestaudio/best",
        "outtmpl": filepath,
        "merge_output_format":"mp4",
        "quiet": True,
        "no_warnings": True
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    return jsonify({"video_id": video_id})

@app.route("/download_file/<video_id>")
def download_file(video_id):
    path = os.path.join(TEMP_DOWNLOADS, f"{video_id}.mp4")
    if not os.path.exists(path):
        abort(404)

    @after_this_request
    def remove_file(response):
        try:
            os.remove(path)
        except Exception as e:
            print(f"Failed to remove file: {e}")
        return response

    return send_file(path, as_attachment=True)

# ------------------------
# Run App
# ------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
