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
      // Extract course + event_target from grid
      const courses = [];
      const gridMatch = html.match(/<table[^>]*id="grdColleges"[^>]*>(.*?)<\/table>/s);
      if (gridMatch) {
        const rows = gridMatch[1].match(/<tr[^>]*>(.*?)<\/tr>/gs) || [];
        for (const row of rows) {
          if (/HeaderStyle|PagerStyle|FooterStyle/.test(row)) continue;
          const cells = row.match(/<td[^>]*>(.*?)<\/td>/gs) || [];
          if (cells.length < 3) continue;
          const course = cells[0].replace(/<[^>]+>/g, '').trim();
          const subject = cells[1].replace(/<[^>]+>/g, '').trim();
          const etMatch = cells[2].match(/__doPostBack\([^']*['"]([^'"]+?)['"]/);
          const event_target = etMatch ? etMatch[1] : '';
          courses.push({ course, subject, event_target });
        }
      }
      // Handle pagination
      const pages = [...html.matchAll(/__doPostBack\(.*?grdColleges.*?Page\$(\d+)/g)].map(m => parseInt(m[1]));
      const maxPage = Math.max(...pages, 1);
      for (let p = 2; p <= maxPage; p++) {
        const formData = new URLSearchParams();
        const vsMatch = html.match(/__VIEWSTATE[^>]*value="([^"]*)"/);
        const evMatch = html.match(/__EVENTVALIDATION[^>]*value="([^"]*)"/);
        const vsgMatch = html.match(/__VIEWSTATEGENERATOR[^>]*value="([^"]*)"/);
        if (!vsMatch) break;
        formData.set('__VIEWSTATE', vsMatch[1]);
        formData.set('__EVENTVALIDATION', evMatch ? evMatch[1] : '');
        formData.set('__VIEWSTATEGENERATOR', vsgMatch ? vsgMatch[1] : '');
        formData.set('__EVENTTARGET', 'grdColleges');
        formData.set('__EVENTARGUMENT', `Page$${p}`);
        const r2 = await fetch(`${REVAL}/revalresult/`, { method: 'POST', headers: { ...rh(), 'Content-Type': 'application/x-www-form-urlencoded' }, body: formData.toString() });
        saveRevalCookie(r2);
        const html2 = await r2.text();
        html = html2;
        const gridMatch2 = html2.match(/<table[^>]*id="grdColleges"[^>]*>(.*?)<\/table>/s);
        if (gridMatch2) {
          const rows2 = gridMatch2[1].match(/<tr[^>]*>(.*?)<\/tr>/gs) || [];
          for (const row of rows2) {
            if (/HeaderStyle|PagerStyle|FooterStyle/.test(row)) continue;
            const cells = row.match(/<td[^>]*>(.*?)<\/td>/gs) || [];
            if (cells.length < 3) continue;
            const course = cells[0].replace(/<[^>]+>/g, '').trim();
            const subject = cells[1].replace(/<[^>]+>/g, '').trim();
            const etMatch = cells[2].match(/__doPostBack\([^']*['"]([^'"]+?)['"]/);
            const event_target = etMatch ? etMatch[1] : '';
            courses.push({ course, subject, event_target });
          }
        }
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
