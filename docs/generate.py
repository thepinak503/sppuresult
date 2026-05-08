#!/usr/bin/env python3
"""
Generate standalone index.html with embedded course/session data for GitHub Pages.
Usage: python3 docs/generate.py
"""
import urllib.request, urllib.parse, ssl, json, re, os, sys

SPPU_BASE = "https://onlineresults.unipune.ac.in"
DIR = os.path.dirname(os.path.abspath(__file__))

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

def fetch(url, data=None):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    if data:
        req.data = urllib.parse.urlencode(data).encode()
        req.method = "POST"
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        req.add_header("X-Requested-With", "XMLHttpRequest")
        req.add_header("Referer", f"{SPPU_BASE}/Result/Dashboard/Default")
    return urllib.request.urlopen(req, context=ssl_ctx, timeout=15).read().decode("utf-8", errors="replace")

def scrape():
    sessions_raw = json.loads(fetch(f"{SPPU_BASE}/Result/Dashboard/GetSession"))
    sessions = [[s.get("Exam_Name",""), s.get("Exam_Period","")] for s in sessions_raw]

    html = fetch(f"{SPPU_BASE}/Result/Dashboard/Default")
    tbody_start = html.find("<tbody")
    tbody_end = html.find("</tbody>", tbody_start)
    tbody = html[tbody_start:tbody_end] if tbody_start >= 0 else html

    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", tbody, re.DOTALL)
    courses = []
    for row in rows:
        tds = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
        if len(tds) < 4: continue
        name = re.sub(r"<[^>]+>", "", tds[1]).strip()
        date = re.sub(r"<[^>]+>", "", tds[2]).strip()
        if not name: continue
        m = re.search(r"Enterdetails\(['\"]([^'\"]+)['\"],\s*['\"]([^'\"]+)['\"]\)", tds[3])
        pn, pi = (m.group(1), m.group(2)) if m else ("", "")
        courses.append([name, date, pn, pi])
    return sessions, courses

def generate(sessions, courses):
    template_path = os.path.join(DIR, "..", "index.html")
    with open(template_path) as f:
        html = f.read()

    # Find script block
    script_start = html.find("<script>")
    script_end = html.find("</script>", script_start)
    if script_start < 0 or script_end < 0:
        print("ERROR: No <script> block found in index.html")
        sys.exit(1)

    # Build embedded data injection to insert after script opening
    embedded_data = f"\n// Embedded data (auto-generated on {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')})\n"
    embedded_data += f"const ES={json.dumps(sessions, separators=(',',':'))};\n"
    # Escape & in course names for HTML safety
    escaped_courses = [[c[0].replace('&', '&amp;'), c[1], c[2], c[3]] for c in courses]
    embedded_data += f"const EC={json.dumps(escaped_courses, separators=(',',':'))};\n"

    # Inject after <script>
    inject_point = script_start + len("<script>")
    html = html[:inject_point] + embedded_data + html[inject_point:]

    # Now modify init() to add fallback logic
    # Replace: const A=window.location.origin;
    # With: const A=...; let SB='default',aC='all',tm=null,cL=false,ED=null,EP=false;
    # But we need to be careful about existing variables

    # Add standalone detection: try fetching /api/sessions, if fails use embedded
    html = html.replace(
        "try{let r=await fetch(A+'/api/sessions',{signal:AbortSignal.timeout(10000)});if(r.ok){let d=await r.json();const sel=$('sessS');sel.innerHTML='<option value=\"\">All Sessions</option>';if(Array.isArray(d))d.forEach(s=>{if(s.Exam_Period&&s.Exam_Name){const o=document.createElement('option');o.value=s.Exam_Period;o.textContent=s.Exam_Name;sel.appendChild(o)}})}}catch(ex){if(typeof navigator!=='undefined'&&!navigator.onLine){so();return}console.warn('Sessions:',ex.message);$('sessS').innerHTML='<option value=\"\">All Sessions</option>'}",
        "try{let r=await fetch(A+'/api/sessions',{signal:AbortSignal.timeout(10000)});if(r.ok){let d=await r.json();const sel=$('sessS');sel.innerHTML='<option value=\"\">All Sessions</option>';if(Array.isArray(d))d.forEach(s=>{if(s.Exam_Period&&s.Exam_Name){const o=document.createElement('option');o.value=s.Exam_Period;o.textContent=s.Exam_Name;sel.appendChild(o)}})}else throw new Error('Not OK')}catch(ex){if(typeof navigator!=='undefined'&&!navigator.onLine){so();return}try{if(ES&&ES.length){const sel=$('sessS');sel.innerHTML='<option value=\"\">All Sessions</option>';ES.forEach(s=>{if(s[1]){const o=document.createElement('option');o.value=s[1];o.textContent=s[0];sel.appendChild(o)}});EP=true}}catch(e2){}console.warn('Sessions:',ex.message)}"
    )

    # Replace: await lC('')
    # With: await lC('', true)  to signal embedded mode
    html = html.replace(
        "if(typeof navigator!=='undefined'&&!navigator.onLine){so();return}\nawait lC('')",
        "if(typeof navigator!=='undefined'&&!navigator.onLine){so();return}\nawait lC('')"
    )

    # Modify lC to accept embedded flag
    # Change: async function lC(p){
    html = html.replace(
        "async function lC(p){const a=$('ca');hE();a.innerHTML=sk(10);try{let r=await fetch(A+'/api/courses'+(p?'?period='+p:''),{signal:AbortSignal.timeout(30000)});if(!r.ok){e('Server Error ('+r.status+')','HTTP '+r.status,'','w','Retry',()=>lC(p));a.innerHTML='<div class=\"empty\"><div class=\"ei\">&#9888;</div><h3>Server Error</h3><button class=\"btn btn-p\" onclick=\"loadCourses(document.getElementById(\\'sessS\\').value)\" style=\"margin-top:12px;padding:9px 20px;border:none;border-radius:8px;font-size:12px;font-weight:600;background:var(--accent);color:#fff;cursor:pointer\">Retry</button></div>';return}",
        "function eC(d){C=[];const sn=new Set();d.forEach(c=>{const n=c[0],dt=c[1];if(!n||sn.has(n))return;sn.add(n);C.push({name:n,date:dt,displayDate:fd(dt),recent:ir(dt),pn:c[2],pi:c[3],cat:classify(n)})});if(!C.length)e('No Courses','Could not extract courses.','','w');aC='all';FC=sL([...C]);bCS();rC();$('stT').textContent=C.length;$('stW').textContent=C.filter(c=>c.recent).length;$('cBadge').textContent=C.length}\nasync function lC(p){const a=$('ca');hE();a.innerHTML=sk(10);try{if(EC&&EP){eC(EC);return}let r=await fetch(A+'/api/courses'+(p?'?period='+p:''),{signal:AbortSignal.timeout(30000)});if(!r.ok){e('Server Error ('+r.status+')','HTTP '+r.status,'','w','Retry',()=>lC(p));a.innerHTML='<div class=\"empty\"><div class=\"ei\">&#9888;</div><h3>Server Error</h3><button class=\"btn btn-p\" onclick=\"loadCourses(document.getElementById(\\'sessS\\').value)\" style=\"margin-top:12px;padding:9px 20px;border:none;border-radius:8px;font-size:12px;font-weight:600;background:var(--accent);color:#fff;cursor:pointer\">Retry</button></div>';return}"
    )

    # Modify the second part of lC where it catches and uses embedded
    # Replace: pC(h)}catch(ex){
    html = html.replace(
        "pC(h)}catch(ex){if(typeof navigator!=='undefined'&&!navigator.onLine){so();a.innerHTML='<div class=\"empty\"><div class=\"ei\">&#128246;</div><h3>No Internet</h3><p>You appear to be offline.</p></div>';return}if(ex.name==='AbortError'||ex.message?.includes('timed out')||ex.message?.includes('Timeout')){e('Timeout (504)','SPPU took too long.','30s timeout.','d','Retry',()=>lC(p));a.innerHTML='<div class=\"empty\"><div class=\"ei\">&#9202;</div><h3>Timeout</h3><button class=\"btn btn-p\" onclick=\"loadCourses(document.getElementById(\\'sessS\\').value)\" style=\"margin-top:12px;padding:9px 20px;border:none;border-radius:8px;font-size:12px;font-weight:600;background:var(--accent);color:#fff;cursor:pointer\">Retry</button></div>'}",
        "if(typeof EC!=='undefined'&&EC&&EC.length){eC(EC);return}pC(h)}catch(ex){if(typeof EC!=='undefined'&&EC&&EC.length){eC(EC);return}if(typeof navigator!=='undefined'&&!navigator.onLine){so();a.innerHTML='<div class=\"empty\"><div class=\"ei\">&#128246;</div><h3>No Internet</h3><p>You appear to be offline.</p></div>';return}if(ex.name==='AbortError'||ex.message?.includes('timed out')||ex.message?.includes('Timeout')){e('Timeout (504)','SPPU took too long.','30s timeout.','d','Retry',()=>lC(p));a.innerHTML='<div class=\"empty\"><div class=\"ei\">&#9202;</div><h3>Timeout</h3><button class=\"btn btn-p\" onclick=\"loadCourses(document.getElementById(\\'sessS\\').value)\" style=\"margin-top:12px;padding:9px 20px;border:none;border-radius:8px;font-size:12px;font-weight:600;background:var(--accent);color:#fff;cursor:pointer\">Retry</button></div>'}"
    )

    # Modify the form action to submit directly to SPPU when no server
    # Replace the form submit handler to detect standalone mode
    html = html.replace(
        "$('rF').action=A+'/api/result';",
        "$('rF').action=A+'/api/result';if(EP&&!A.includes('localhost')&&!A.includes('192.168')&&!A.includes('127.0')){$('rF').action='https://onlineresults.unipune.ac.in/SPPU%20ONLINE%20RESULT%20DISPLAY';$('rF').target='_blank'}"
    )

    # Modify captcha loading to try proxies when no server
    # Add proxy attempt before the catch block in lCap
    html = html.replace(
        "}catch(ex){if(ex.name==='AbortError'||ex.message?.includes('timeout')){le.innerHTML='&#9888; Timeout';e('Captcha Timeout','Captcha server timed out.','','d','Retry',lCap)}else{le.innerHTML='&#9888; Failed';e('Captcha Failed',ex.message,'','w','Retry',lCap)}}cL=false",
        "}catch(ex){if(ex.name==='AbortError'||ex.message?.includes('timeout')){le.innerHTML='&#9888; Timeout';e('Captcha Timeout','Captcha server timed out.','','d','Retry',lCap)}else if(EP){le.innerHTML='&#9888; Offline';if(confirm('Captcha requires a server. Open SPPU site to get captcha manually?')){window.open('https://onlineresults.unipune.ac.in/Result/Dashboard/Default','_blank')}}else{le.innerHTML='&#9888; Failed';e('Captcha Failed',ex.message,'','w','Retry',lCap)}}cL=false"
    )

    output_path = os.path.join(DIR, "index.html")
    with open(output_path, "w") as f:
        f.write(html)
    print(f"Generated {output_path} ({len(html)} bytes, {len(courses)} courses, {len(sessions)} sessions)")

if __name__ == "__main__":
    print("Scraping SPPU...")
    sessions, courses = scrape()
    print(f"Got {len(sessions)} sessions, {len(courses)} courses")
    generate(sessions, courses)
