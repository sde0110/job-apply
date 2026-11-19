// 지원서 화면 점검 스니펫 — Claude in Chrome 의 javascript_tool 에 이 파일 내용을 그대로 넣는다.
// 출력은 한 줄에 한 칸: "#순번 | 라벨 | 종류 | 값 | 길이". form_check.py 가 읽는다.
// 출력이 길면 잘리므로 15줄씩 돌려준다. 첫 쪽 뒤에 나오는 안내대로 window.__jaPage(n) 을 실행해 이어 받고, 모든 쪽을 한 파일에 이어 붙여 저장한다.
// URL·이메일·도메인·토큰처럼 보이는 문자열은 결과가 차단·잘리므로 값을 가린다(:// 제거, @→(at), ?=& → _, 도메인 점 → [.]).
// 긴 텍스트는 앞부분만 보여 주고, 정확한 대조는 hashes.js 로 한다.
(() => {
  const clean = (s) => String(s ?? "").replace(/https?:\/\//g, "").replace(/@/g, "(at)").replace(/[?=&]/g, "_").replace(/([A-Za-z0-9-])\.(?=[A-Za-z]{2,})/g, "$1[.]").replace(/\s+/g, " ").trim();
  const short = (s) => (s.length > 40 ? s.slice(0, 20) + "…" : s);
  const labelOf = (g) => {
    const l = g.querySelector(":scope > label") || g.querySelector("label");
    return l ? l.textContent.replace(/\*/g, "").replace(/\s+/g, " ").trim().slice(0, 40) : "";
  };
  const own = (g, sel) => [...g.querySelectorAll(sel)].filter((el) => el.closest("[role=group]") === g);
  const rows = [];
  let seq = 0;
  const add = (label, kind, value, len) => rows.push(`#${++seq} | ${clean(label)} | ${kind} | ${short(clean(value))} | ${len ?? ""}`);

  for (const g of document.querySelectorAll("[role=group]")) {
    const label = labelOf(g);
    if (!label) continue;
    for (const el of own(g, "input[type=text], input:not([type]), input[type=email], input[type=tel], input[type=url], textarea")) {
      el.dataset.jaSeq = String(seq + 1);
      add(label, "text", el.value, el.value.length);
    }
    for (const el of own(g, "button[role=combobox], button.combo, [role=combobox]:not(input)")) {
      if (el.offsetParent !== null) add(label, "select", el.textContent, null);  // 숨겨진 칸(예: 재직 중일 때 퇴사일)은 제외
    }
    for (const rg of own(g, "[role=radiogroup]")) {
      const on = [...rg.querySelectorAll("[role=radio]")].filter((r) => r.getAttribute("aria-checked") === "true" || r.checked);
      add(label, "radio", on.map((r) => r.textContent.trim() || r.value).join(";"), null);
    }
    const radios = own(g, "input[type=radio]");
    if (radios.length) add(label, "radio", radios.filter((r) => r.checked).map((r) => r.value || r.closest("label")?.textContent.trim()).join(";"), null);
    const checks = own(g, "input[type=checkbox]");
    if (checks.length) add(label, "checks", checks.filter((c) => c.checked).map((c) => c.value !== "on" ? c.value : (c.closest("label")?.textContent.trim() || "on")).join(";"), null);
    for (const f of own(g, "input[type=file]")) {
      const file = f.files && f.files[0];
      add(label, "file", file ? `${file.name} ${file.size}` : "", null);
    }
  }
  for (const c of document.querySelectorAll("input[type=checkbox]")) {
    const t = (c.closest("label")?.textContent || "").replace(/\s+/g, " ").trim();
    if (/동의/.test(t) && !c.closest("[role=group]")) add(t.slice(0, 30), "consent", String(c.checked), null);
  }
  const errs = [...document.querySelectorAll("body *")].filter((el) => el.children.length === 0 && /필수 입력/.test(el.textContent) && el.offsetParent).length;
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
