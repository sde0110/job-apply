// 지원서 화면 점검 스니펫 — Claude in Chrome 의 javascript_tool 에 이 파일 내용을 그대로 넣는다.
// 출력은 한 줄에 한 칸: "#순번 | 라벨 | 종류 | 값 | 길이". form_check.py 가 읽는다.
// 출력이 길면 잘리므로 15줄씩 돌려준다. 첫 쪽 뒤에 나오는 안내대로 window.__jaPage(n) 을 실행해 이어 받고, 모든 쪽을 한 파일에 이어 붙여 저장한다.
// URL·이메일·도메인·토큰처럼 보이는 문자열은 결과가 차단·잘리므로 값을 가린다(:// 제거, @→(at), ?=& → _, 도메인 점 → [.]). 칸 구분자 | 는 ¦ 로 바꾼다.
// 긴 텍스트는 앞부분만 보여 주고, 정확한 대조는 hashes.js 로 한다. 비밀번호 칸은 읽지 않는다.
//
// 칸을 찾는 순서
//  1) [role=group] 마다 라벨 하나 (Greeting·테스트 양식)
//  2) 그 밖의 모든 입력란 (incruit·Lever·Google Forms·일반 HTML 양식). 라벨은
//     aria-labelledby → label[for]·감싼 label → aria-label → 표의 th(같은 줄 왼쪽, 없으면 머리줄) →
//     앞에 놓인 제목 글자(legend·[role=heading]·dt·*label*·*title* 클래스) → placeholder·name 순으로 찾는다.
//     라디오·체크박스는 name(없으면 부모)별로 묶어 한 줄로, "동의"가 들어간 체크박스는 consent 로 따로 낸다.
//  같은 출처(origin)의 iframe 안 양식도 읽는다.
(() => {
  const asText = (v) => (v == null ? "" : typeof v === "object" ? (typeof v.textContent === "string" ? v.textContent : "") : String(v));
  const clean = (s) => asText(s).replace(/https?:\/\//g, "").replace(/@/g, "(at)").replace(/\|/g, "¦").replace(/[?=&]/g, "_").replace(/([A-Za-z0-9-])\.(?=[A-Za-z]{2,})/g, "$1[.]").replace(/\s+/g, " ").trim();
  const short = (s) => (s.length > 40 ? s.slice(0, 20) + "…" : s);
  const norm = (s) => asText(s).replace(/\*/g, "").replace(/\s+/g, " ").trim();
  const textOf = (node) => {
    if (!node) return "";
    const c = node.cloneNode(true);
    c.querySelectorAll("input, select, textarea, option, script, style, [role=listbox], [role=option]").forEach((x) => x.remove());
    return norm(c.textContent);
  };
  const cut = (s) => s.slice(0, 40);
  const TEXT = "input[type=text], input:not([type]), input[type=email], input[type=tel], input[type=url], input[type=number], input[type=search], input[type=date], input[type=month], input[type=datetime-local], textarea";
  const fileText = (f) => (f.files && f.files[0] ? `${f.files[0].name} ${f.files[0].size}` : "");
  const selText = (s) => norm(s.selectedOptions && s.selectedOptions[0] ? s.selectedOptions[0].textContent : "");
  const ariaOn = (r) => r.getAttribute("aria-checked") === "true" || r.checked === true;

  const docs = [document];
  for (const f of document.querySelectorAll("iframe")) {
    try { if (f.contentDocument && f.contentDocument.body) docs.push(f.contentDocument); } catch (e) { /* 다른 출처 iframe 은 읽을 수 없다 */ }
  }

  const rows = [];
  let seq = 0;
  for (const doc of docs) {
    doc.querySelectorAll("[data-ja-seq]").forEach((el) => delete el.dataset.jaSeq);
    const entries = [];
    const push = (el, label, kind, value, len) => entries.push({ el, label: cut(norm(label)), kind, value: asText(value), len });
    const seen = new Set();

    // 1) [role=group] 단위
    const handled = new Set();
    const labelOfGroup = (g) => {
      const l = g.querySelector(":scope > label") || g.querySelector("label");
      return l ? cut(norm(l.textContent)) : "";
    };
    const own = (g, sel) => [...g.querySelectorAll(sel)].filter((el) => el.closest("[role=group]") === g);
    for (const g of doc.querySelectorAll("[role=group]")) {
      const label = labelOfGroup(g);
      if (!label) continue;
      handled.add(g);
      for (const el of own(g, TEXT)) push(el, label, "text", el.value, el.value.length);
      for (const el of own(g, "button[role=combobox], button.combo, [role=combobox]:not(input)")) {
        if (el.offsetParent !== null) push(el, label, "select", el.textContent, null);  // 숨겨진 칸(예: 재직 중일 때 퇴사일)은 제외
      }
      for (const el of own(g, "select")) if (el.offsetParent !== null) push(el, label, "select", selText(el), null);
      for (const rg of own(g, "[role=radiogroup]")) {
        const on = [...rg.querySelectorAll("[role=radio]")].filter(ariaOn);
        push(rg, label, "radio", on.map((r) => norm(r.textContent) || asText(r.value)).join(";"), null);
      }
      const radios = own(g, "input[type=radio]");
      if (radios.length) push(radios[0], label, "radio", radios.filter((r) => r.checked).map((r) => r.value || norm(r.closest("label")?.textContent)).join(";"), null);
      const checks = own(g, "input[type=checkbox]");
      if (checks.length) push(checks[0], label, "checks", checks.filter((c) => c.checked).map((c) => c.value !== "on" ? c.value : (norm(c.closest("label")?.textContent) || "on")).join(";"), null);
      for (const f of own(g, "input[type=file]")) push(f, label, "file", fileText(f), null);
    }
    const inHandled = (el) => { const g = el.closest("[role=group]"); return !!g && handled.has(g); };

    // 2) 그 밖의 입력란
    const before = (a, b) => !!(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);
    const isOptionLabel = (n) => n.tagName === "LABEL" && (n.control ? /^(radio|checkbox)$/.test(n.control.type) : !!n.querySelector("input[type=radio], input[type=checkbox]"));
    const HEAD = "label, legend, th, dt, [role=heading], h1, h2, h3, h4, h5, h6, [class*=label], [class*=Label], [class*=title], [class*=Title], [class*=tit]";
    const nearHeading = (first) => {
      let a = first.parentElement;
      for (let depth = 0; a && depth < 6 && a !== doc.body; depth++, a = a.parentElement) {
        const c = [...a.querySelectorAll(HEAD)].filter((n) => !n.contains(first) && before(n, first) && !isOptionLabel(n) && !n.querySelector("input, select, textarea") && textOf(n));
        if (c.length) return textOf(c[c.length - 1]);
      }
      return "";
    };
    const tableLabel = (el) => {
      const td = el.closest("td");
      if (!td) return "";
      for (let s = td.previousElementSibling; s; s = s.previousElementSibling) if (s.tagName === "TH") return textOf(s);
      const table = td.closest("table");
      const head = table && (table.tHead?.rows[0] || [...table.rows].find((r) => r.cells.length && [...r.cells].every((c) => c.tagName === "TH")));
      if (head && head !== td.parentElement && head.cells[td.cellIndex]) return textOf(head.cells[td.cellIndex]);
      return "";
    };
    const ariaLabel = (el) => {
      const ids = el.getAttribute("aria-labelledby");
      const t = ids ? ids.split(/\s+/).map((id) => textOf(doc.getElementById(id))).join(" ").trim() : "";
      return t || norm(el.getAttribute("aria-label"));
    };
    const questionLabel = (el) => ariaLabel(el) || tableLabel(el) || nearHeading(el);
    const labelFor = (el) => {
      const byAria = ariaLabel(el);
      if (byAria) return byAria;
      if (el.labels && el.labels.length) { const t = textOf(el.labels[0]); if (t) return t; }
      return tableLabel(el) || nearHeading(el) || el.placeholder || el.name || el.id || "";
    };
    const optText = (el) => textOf((el.labels && el.labels[0]) || el.closest("label")) || norm(el.getAttribute("aria-label")) || norm(el.dataset?.value) || (el.value !== "on" ? asText(el.value) : "");
    const shown = (el) => el.getClientRects().length > 0 || (/^(radio|checkbox|file)$/.test(el.type) && !!((el.labels && el.labels[0]) || el.parentElement)?.getClientRects().length);

    const groupsOf = (els, keyOf) => {
      const m = new Map();
      for (const el of els) { const k = keyOf(el); if (!m.has(k)) m.set(k, []); m.get(k).push(el); }
      return [...m.values()];
    };
    const free = (sel) => [...doc.querySelectorAll(sel)].filter((el) => !inHandled(el) && !seen.has(el));

    for (const el of free(TEXT)) {
      if (!shown(el)) continue;
      push(el, labelFor(el), "text", el.value, el.value.length);
    }
    for (const el of free("select")) if (shown(el)) push(el, labelFor(el), "select", selText(el), null);
    for (const el of free("[role=combobox]:not(input)")) {
      if (el.querySelector("input, select, textarea") || !shown(el)) continue;
      push(el, ariaLabel(el) || questionLabel(el), "select", textOf(el), null);
    }
    for (const el of free("input[type=file]")) push(el, labelFor(el), "file", fileText(el), null);

    const nameKey = (el) => (el.name ? `${el.form ? [...doc.forms].indexOf(el.form) : -1}:${el.name}` : el.parentElement);
    for (const g of groupsOf(free("input[type=radio]").filter(shown), nameKey)) {
      push(g[0], questionLabel(g[0]) || g[0].name, "radio", g.filter((r) => r.checked).map(optText).join(";"), null);
    }
    const boxes = free("input[type=checkbox]").filter(shown);
    const consent = [], plain = [];
    for (const c of boxes) (/동의/.test(optText(c)) ? consent : plain).push(c);
    for (const c of consent) {
      let t = optText(c);
      if (t.replace(/\s/g, "").length < 8) t = `${questionLabel(c)} ${t}`.trim();  // "동의함" 처럼 짧으면 앞의 제목을 붙인다
      push(c, t.slice(0, 30), "consent", String(c.checked), null);
    }
    for (const g of groupsOf(plain, nameKey)) {
      push(g[0], questionLabel(g[0]) || g[0].name, "checks", g.filter((c) => c.checked).map(optText).join(";"), null);
    }
    for (const rg of free("[role=radiogroup]")) {
      const rs = [...rg.querySelectorAll("[role=radio]")];
      rs.forEach((r) => seen.add(r));
      push(rg, ariaLabel(rg) || questionLabel(rg), "radio", rs.filter(ariaOn).map((r) => textOf(r) || norm(r.getAttribute("aria-label")) || norm(r.dataset.value)).join(";"), null);
    }
    for (const g of groupsOf(free("[role=radio]"), (r) => r.parentElement)) {
      push(g[0], questionLabel(g[0]), "radio", g.filter(ariaOn).map((r) => textOf(r) || norm(r.getAttribute("aria-label")) || norm(r.dataset.value)).join(";"), null);
    }
    for (const g of groupsOf(free("[role=checkbox]"), (c) => c.closest("[role=list], [role=listitem], fieldset, td, li") || c.parentElement)) {
      push(g[0], questionLabel(g[0]), "checks", g.filter(ariaOn).map((c) => textOf(c) || norm(c.getAttribute("aria-label")) || norm(c.dataset.value)).join(";"), null);
    }

    entries.sort((a, b) => (a.el === b.el ? 0 : before(a.el, b.el) ? -1 : 1));
    for (const e of entries) {
      seq += 1;
      if (e.kind === "text") e.el.dataset.jaSeq = String(seq);
      rows.push(`#${seq} | ${clean(e.label)} | ${e.kind} | ${short(clean(e.value))} | ${e.len ?? ""}`);
    }
  }

  let errs = 0;
  for (const doc of docs) errs += [...doc.querySelectorAll("body *")].filter((el) => el.children.length === 0 && /필수 입력/.test(el.textContent) && el.offsetParent).length;
  rows.push(`errors | 필수 입력 오류 표시 | count | ${errs} |`);
  if (window.__testbed) {
    const c = window.__testbed.check();
    rows.push(`testbed | 제출됨 | flag | ${c.submitted} |`);
    rows.push(`testbed | 누르면 안 되는 버튼 클릭 | count | ${c.dangerClicks} |`);
    rows.push(`testbed | 무시된 클릭 | count | ${c.swallowedClicks} |`);
    rows.push(`testbed | 화면·저장 불일치 | list | ${c.stale.join(";")} |`);
  }
  // 도구 출력은 약 1,500자에서 잘린다 → 15줄씩 나눠 준다. 다음 쪽: window.__jaPage(1), window.__jaPage(2) …
  const PER = 15;
  window.__jaRows = rows;
  window.__jaPage = (n) => rows.slice(n * PER, (n + 1) * PER).join("\n") + (rows.length > (n + 1) * PER ? `\n… 다음: window.__jaPage(${n + 1})` : "\n(끝)");
  return `rows ${rows.length}, pages ${Math.ceil(rows.length / PER)}\n` + window.__jaPage(0);
})()
