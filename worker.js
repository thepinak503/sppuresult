// Cloudflare Worker — SPPU Result Proxy
// Using HTTP because SPPU's SSL cert has incomplete chain (526 error)
const SPPU = 'http://onlineresults.unipune.ac.in';
const REVAL = 'https://pun.unipune.ac.in';
let sppuCookie = '';
let revalCookie = '';

async function handleRequest(request) {
  const url = new URL(request.url);
  const path = url.pathname;

  const cors = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, X-Requested-With',
  };

  if (request.method === 'OPTIONS') return new Response(null, { headers: cors });

  try {
    if (path === '/api/sessions') {
      const r = await fetch(`${SPPU}/Result/Dashboard/GetSession`, { headers: h() });
      saveCookie(r);
      const text = await r.text();
      let d;
      try { d = JSON.parse(text); } catch (e) { return errResponse('SPPU returned non-JSON for sessions', r.status, text, cors); }
      return jsonResponse(d, cors);
    }

    if (path === '/api/courses') {
      const period = url.searchParams.get('period');
      let target = `${SPPU}/Result/Dashboard/Default`;
      if (period) target += `?Exam_Period=${period}`;
      const r = await fetch(target, { headers: h() });
      saveCookie(r);
      const html = await r.text();
      return jsonResponse({ html }, cors);
    }

    if (path === '/api/captcha') {
      const r = await fetch(`${SPPU}/Result/Dashboard/RFCTLN`, {
        method: 'POST',
        headers: h(),
      });
      saveCookie(r);
      const text = await r.text();
      let d;
      try { d = JSON.parse(text); } catch (e) { return errResponse('SPPU returned non-JSON for captcha', r.status, text, cors); }
      return jsonResponse(d, cors);
    }

    if (path === '/api/result') {
      const fd = await request.formData();
      const params = new URLSearchParams();
      for (const [k, v] of fd.entries()) params.append(k, v.toString());
      const r = await fetch(`${SPPU}/SPPU%20ONLINE%20RESULT%20DISPLAY`, {
        method: 'POST',
        headers: { ...h(), 'Content-Type': 'application/x-www-form-urlencoded' },
        body: params.toString(),
      });
      const ct = r.headers.get('Content-Type') || 'application/pdf';
      const cd = r.headers.get('Content-Disposition') || '';
      const buf = await r.arrayBuffer();
      return new Response(buf, {
        headers: { 'Content-Type': ct, 'Content-Disposition': cd, 'Access-Control-Allow-Origin': '*' },
      });
    }

    if (path === '/api/reval/courses') {
      const r = await fetch(`${REVAL}/revalresult/`, { headers: rh() });
      saveRevalCookie(r);
      const html = await r.text();
      const courses = [];
      const gridMatch = html.match(/<table[^>]*id="grdColleges"[^>]*>(.*?)<\/table>/s);
      if (gridMatch) {
        const rows = gridMatch[1].match(/<tr[^>]*>(.*?)<\/tr>/gs) || [];
        for (const row of rows) {
          if (/HeaderStyle|PagerStyle|FooterStyle|GridViewFooterStyle/.test(row)) continue;
          const cells = row.match(/<td[^>]*>(.*?)<\/td>/gs) || [];
          if (cells.length < 3) continue;
          const course = cells[0].replace(/<[^>]+>/g, '').trim();
          const subject = cells[1].replace(/<[^>]+>/g, '').trim();
          if (!course || !subject || course === '...') continue;
          const etMatch = cells[2].match(/__doPostBack\(&#39;([^&#]+?)&#39;/);
          if (!etMatch) continue;
          courses.push({ course, subject, event_target: etMatch[1] });
        }
      }
      // Paginate through remaining pages — follow actual pager links (like Android scraper)
      let vs = (html.match(/__VIEWSTATE[^>]*value="([^"]*)"/) || [])[1] || '';
      let ev = (html.match(/__EVENTVALIDATION[^>]*value="([^"]*)"/) || [])[1] || '';
      let vsg = (html.match(/__VIEWSTATEGENERATOR[^>]*value="([^"]*)"/) || [])[1] || '';
      const seen = new Set(courses.map(c => `${c.course}|${c.subject}|${c.event_target}`));
      let currentHtml = html;
      let currentPage = 1;
      for (let iter = 0; iter < 50; iter++) {
        const pager = [...currentHtml.matchAll(/__doPostBack\(&#39;(.+?)&#39;,\s*&#39;(.+?)&#39;/g)];
        let nextPage = null, nextTarget = '', nextArg = '';
        for (const m of pager) {
          const target = m[1], arg = m[2];
          const pm = arg.match(/Page\$(\d+)/);
          if (pm) {
            const pn = parseInt(pm[1]);
            if (pn > currentPage && (nextPage === null || pn < nextPage)) {
              nextPage = pn;
              nextTarget = target;
              nextArg = arg;
            }
          }
        }
        if (nextPage === null) break;
        const fd = new URLSearchParams();
        fd.set('__VIEWSTATE', vs);
        fd.set('__EVENTVALIDATION', ev);
        fd.set('__VIEWSTATEGENERATOR', vsg);
        fd.set('__EVENTTARGET', nextTarget);
        fd.set('__EVENTARGUMENT', nextArg);
        const pr = await fetch(`${REVAL}/revalresult/`, { method: 'POST', headers: { ...rh(), 'Content-Type': 'application/x-www-form-urlencoded' }, body: fd.toString() });
        saveRevalCookie(pr);
        const ph = await pr.text();
        if (!ph) break;
        vs = (ph.match(/__VIEWSTATE[^>]*value="([^"]*)"/) || [])[1] || '';
        ev = (ph.match(/__EVENTVALIDATION[^>]*value="([^"]*)"/) || [])[1] || '';
        vsg = (ph.match(/__VIEWSTATEGENERATOR[^>]*value="([^"]*)"/) || [])[1] || '';
        const pg = ph.match(/<table[^>]*id="grdColleges"[^>]*>(.*?)<\/table>/s);
        if (pg) {
          const prs = pg[1].match(/<tr[^>]*>(.*?)<\/tr>/gs) || [];
          for (const row of prs) {
            if (/HeaderStyle|PagerStyle|FooterStyle|GridViewFooterStyle/.test(row)) continue;
            const cells = row.match(/<td[^>]*>(.*?)<\/td>/gs) || [];
            if (cells.length < 3) continue;
            const course = cells[0].replace(/<[^>]+>/g, '').trim();
            const subject = cells[1].replace(/<[^>]+>/g, '').trim();
            if (!course || !subject || course === '...') continue;
            const etMatch = cells[2].match(/__doPostBack\(&#39;([^&#]+?)&#39;/);
            if (!etMatch) continue;
            const key = `${course}|${subject}|${etMatch[1]}`;
            if (!seen.has(key)) {
              seen.add(key);
              courses.push({ course, subject, event_target: etMatch[1] });
            }
          }
        }
        currentPage = nextPage;
        currentHtml = ph;
      }
      return jsonResponse(courses, cors);
    }

    if (path === '/api/reval/view') {
      const fd = await request.formData();
      const et = fd.get('event_target') || '';
      const r = await fetch(`${REVAL}/revalresult/`, { headers: rh() });
      saveRevalCookie(r);
      let html = await r.text();
      const vs = (html.match(/__VIEWSTATE[^>]*value="([^"]*)"/) || [])[1] || '';
      const ev = (html.match(/__EVENTVALIDATION[^>]*value="([^"]*)"/) || [])[1] || '';
      const vsg = (html.match(/__VIEWSTATEGENERATOR[^>]*value="([^"]*)"/) || [])[1] || '';
      const formData = new URLSearchParams();
      formData.set('__VIEWSTATE', vs);
      formData.set('__EVENTVALIDATION', ev);
      formData.set('__VIEWSTATEGENERATOR', vsg);
      formData.set('__EVENTTARGET', et);
      formData.set('__EVENTARGUMENT', '');
      const r2 = await fetch(`${REVAL}/revalresult/`, { method: 'POST', headers: { ...rh(), 'Content-Type': 'application/x-www-form-urlencoded' }, body: formData.toString() });
      saveRevalCookie(r2);
      const html2 = await r2.text();
      const vs2 = (html2.match(/__VIEWSTATE[^>]*value="([^"]*)"/) || [])[1] || '';
      const ev2 = (html2.match(/__EVENTVALIDATION[^>]*value="([^"]*)"/) || [])[1] || '';
      const vsg2 = (html2.match(/__VIEWSTATEGENERATOR[^>]*value="([^"]*)"/) || [])[1] || '';
      const examMatch = html2.match(/<select[^>]*id="cboExamName"[^>]*>.*?<option[^>]*selected[^>]*value="([^"]*)"/s);
      const exam_val = examMatch ? examMatch[1] : '';
      return jsonResponse({ vs: vs2, ev: ev2, vsg: vsg2, exam_val }, cors);
    }

    if (path === '/api/reval') {
      const fd = await request.formData();
      const et = fd.get('event_target') || '';
      const sb = fd.get('search_by') || 'Seat No';
      const sv = fd.get('search_value') || '';
      if (!et || !sv) return jsonResponse({ error: 'Missing event_target or search_value' }, cors);
      // Full flow: view form + search result
      let r = await fetch(`${REVAL}/revalresult/`, { headers: rh() });
      saveRevalCookie(r);
      let html = await r.text();
      let vs = (html.match(/__VIEWSTATE[^>]*value="([^"]*)"/) || [])[1] || '';
      let ev = (html.match(/__EVENTVALIDATION[^>]*value="([^"]*)"/) || [])[1] || '';
      let vsg = (html.match(/__VIEWSTATEGENERATOR[^>]*value="([^"]*)"/) || [])[1] || '';
      let fd1 = new URLSearchParams();
      fd1.set('__VIEWSTATE', vs); fd1.set('__EVENTVALIDATION', ev);
      fd1.set('__VIEWSTATEGENERATOR', vsg); fd1.set('__EVENTTARGET', et);
      fd1.set('__EVENTARGUMENT', '');
      let r2 = await fetch(`${REVAL}/revalresult/`, { method: 'POST', headers: { ...rh(), 'Content-Type': 'application/x-www-form-urlencoded' }, body: fd1.toString() });
      saveRevalCookie(r2);
      let html2 = await r2.text();
      vs = (html2.match(/__VIEWSTATE[^>]*value="([^"]*)"/) || [])[1] || '';
      ev = (html2.match(/__EVENTVALIDATION[^>]*value="([^"]*)"/) || [])[1] || '';
      vsg = (html2.match(/__VIEWSTATEGENERATOR[^>]*value="([^"]*)"/) || [])[1] || '';
      const examVal = extractExamVal(html2);
      let fd2 = new URLSearchParams();
      fd2.set('__VIEWSTATE', vs); fd2.set('__EVENTVALIDATION', ev);
      fd2.set('__VIEWSTATEGENERATOR', vsg); fd2.set('__EVENTTARGET', '');
      fd2.set('__EVENTARGUMENT', ''); fd2.set('cboExamName', examVal);
      fd2.set('cboSearchBy', sb); fd2.set('txtSearch', sv);
      fd2.set('btnShow', 'Submit');
      let r3 = await fetch(`${REVAL}/revalresult/`, { method: 'POST', headers: { ...rh(), 'Content-Type': 'application/x-www-form-urlencoded' }, body: fd2.toString() });
      saveRevalCookie(r3);
      const html3 = await r3.text();
      const extracted = extractRevalResult(html3);
      if (extracted) return jsonResponse({ html: extracted }, cors);
      const bodyMatch = html3.match(/<body[^>]*>([\s\S]*)<\/body>/);
      const body = bodyMatch ? bodyMatch[1].replace(/<script[^>]*>[\s\S]*?<\/script>|<style[^>]*>[\s\S]*?<\/style>/g, '').trim() : html3;
      return jsonResponse({ html: body.length > 100 ? body : html3 }, cors);
    }

    if (path === '/api/reval/result') {
      const fd = await request.formData();
      const formData = new URLSearchParams();
      formData.set('__VIEWSTATE', fd.get('vs') || '');
      formData.set('__EVENTVALIDATION', fd.get('ev') || '');
      formData.set('__VIEWSTATEGENERATOR', fd.get('vsg') || '');
      formData.set('__EVENTTARGET', '');
      formData.set('__EVENTARGUMENT', '');
      formData.set('cboExamName', fd.get('exam_val') || '');
      formData.set('cboSearchBy', fd.get('search_by') || 'Seat No');
      formData.set('txtSearch', fd.get('search_value') || '');
      formData.set('btnShow', 'Submit');
      const r = await fetch(`${REVAL}/revalresult/`, { method: 'POST', headers: { ...rh(), 'Content-Type': 'application/x-www-form-urlencoded' }, body: formData.toString() });
      saveRevalCookie(r);
      const html = await r.text();
      const extracted = extractRevalResult(html);
      if (extracted) return jsonResponse({ html: extracted }, cors);
      const bodyMatch = html.match(/<body[^>]*>([\s\S]*)<\/body>/);
      const body = bodyMatch ? bodyMatch[1].replace(/<script[^>]*>[\s\S]*?<\/script>|<style[^>]*>[\s\S]*?<\/style>/g, '').trim() : html;
      return jsonResponse({ html: body.length > 100 ? body : html }, cors);
    }

    return new Response('Not Found', { status: 404 });
  } catch (err) {
    return errResponse(err.message, 500, '', cors);
  }
}

function h() {
  const headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': `${SPPU}/Result/Dashboard/Default`,
    'X-Requested-With': 'XMLHttpRequest',
  };
  if (sppuCookie) headers['Cookie'] = sppuCookie;
  return headers;
}

function rh() {
  const headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': `${REVAL}/revalresult/`,
  };
  if (revalCookie) headers['Cookie'] = revalCookie;
  return headers;
}

function saveCookie(r) {
  const sc = r.headers.get('Set-Cookie');
  if (sc) {
    const p = sc.split(';')[0];
    if (p.includes('=')) sppuCookie = p;
  }
}

function extractExamVal(html) {
  const selectedMatch = html.match(/<select[^>]*id="cboExamName"[^>]*>.*?<option[^>]*selected[^>]*value="([^"]*)"/s);
  if (selectedMatch) return selectedMatch[1];
  const firstMatch = html.match(/<select[^>]*id="cboExamName"[^>]*>.*?<option[^>]*value="([^"]*)"/s);
  return firstMatch ? firstMatch[1] : '';
}

function extractRevalResult(html) {
  let cleaned = html.replace(/<script[^>]*>[\s\S]*?<\/script>|<style[^>]*>[\s\S]*?<\/style>|<link[^>]*>/g, '');
  cleaned = cleaned.replace(/<input[^>]*type="hidden"[^>]*>/g, '');
  cleaned = cleaned.replace(/<img[^>]*>/g, '');
  cleaned = cleaned.replace(/<!--[\s\S]*?-->/g, '');

  // Look for a table with result column headers
  const tableRegex = /<table[^>]*>(?:(?!<\/table>)[\s\S])*?<\/table>/gi;
  let match;
  const candidates = [];
  while ((match = tableRegex.exec(cleaned)) !== null) {
    const tc = match[0];
    if (/SubCode|SubName|Obt[^a-z]|Chng[^a-z]|Remarks/i.test(tc)) {
      candidates.push(tc);
    }
  }

  if (candidates.length > 0) {
    // Pick the largest table
    let best = candidates.reduce((a, b) => a.length >= b.length ? a : b);
    const idx = cleaned.indexOf(best);
    const before = cleaned.substring(Math.max(0, idx - 800), idx);
    let studentInfo = '';
    const siMatch = before.match(/(Seat\s*(?:No|Number)[^<]*(?:<[^>]*>)*[^<]*?(?:S\d[\d\/]*[A-Z]?)?)/i);
    if (siMatch) studentInfo = siMatch[1];
    const nmMatch = before.match(/(Name[^<]*(?:<[^>]*>)*[^<]*?[A-Z][a-zA-Z\s]+)/i);
    if (nmMatch) studentInfo += '<br>' + nmMatch[1];
    const prnMatch = before.match(/(PRN[^<]*(?:<[^>]*>)*[^<]*?(?:\d+[A-Z]?)?)/i);
    if (prnMatch) studentInfo += '<br>' + prnMatch[1];
    let wrap = '<div class="reval-result">';
    if (studentInfo) wrap += '<div class="rv-student-info">' + studentInfo.trim() + '</div>';
    wrap += best + '</div>';
    return wrap;
  }

  // Fallback: look for content area
  const contentPatterns = [
    /<td[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)<\/td>/i,
    /<div[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)<\/div>/i,
    /<td[^>]*id="[^"]*content[^"]*"[^>]*>(.*?)<\/td>/i,
    /<div[^>]*id="[^"]*content[^"]*"[^>]*>(.*?)<\/div>/i,
  ];
  for (const pat of contentPatterns) {
    const m = cleaned.match(pat);
    if (m && m[1].trim().length > 100) {
      return '<div class="reval-result">' + m[1].trim() + '</div>';
    }
  }
  return null;
}

function saveRevalCookie(r) {
  const sc = r.headers.get('Set-Cookie');
  if (sc) {
    const p = sc.split(';')[0];
    if (p.includes('=')) revalCookie = p;
  }
}

function jsonResponse(data, cors) {
  return new Response(JSON.stringify(data), { headers: { ...cors, 'Content-Type': 'application/json' } });
}

function errResponse(msg, status, body, cors) {
  return new Response(JSON.stringify({ error: msg, status, snippet: body.substring(0, 200) }), {
    status: 500, headers: { ...cors, 'Content-Type': 'application/json' },
  });
}

export default { fetch: handleRequest };
