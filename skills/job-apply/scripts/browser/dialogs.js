// 알림창(alert·confirm·prompt) 가드 — 지원서 탭을 열거나 페이지가 바뀔 때마다 javascript_tool 에 이 파일 내용을 그대로 넣는다.
// 알림창이 뜨면 Claude in Chrome 의 다음 명령이 모두 막힌다. 이 가드는 창을 띄우지 않고 내용과 응답을 기록한다.
//
// - confirm 은 기본으로 false(취소)를 돌려준다. 제출·삭제·접수·최종·등록 같은 말이 든 창에는 어떤 경우에도 true 를 주지 않는다.
// - 임시저장처럼 예상한 확인 한 번만: window.__jaDialogs.allowOnce("임시저장")  → 다음에 그 글자가 든 confirm 하나만 true.
// - 되돌릴 수 없는 확인(지원 등록, 최종제출) 한 번만: window.__jaDialogs.allowRiskyOnce("최종제출")
//   → 사용자가 이번 요청에서 그 동작을 맡겼고, 직전에 값을 다시 확인했을 때만 쓴다. 쓴 사실을 status.md 에 적는다.
// - alert 는 띄우지 않고 기록한다(비밀번호 오류, 필수 입력 누락, 저장 완료 같은 안내가 여기로 온다). prompt 는 null.
// - 같은 출처의 팝업(window.open)과 iframe 에도 자동으로 건다. 다른 출처 팝업(주소 검색 등)에는 걸 수 없다 → 기록에 남기고 사용자에게 넘긴다.
// - 기록 보기: window.__jaDialogs.read()  → 클릭·저장 뒤마다 확인한다. 페이지가 바뀌어도 같은 탭·같은 출처면 이어서 보인다.
// - 사용자에게 탭을 넘기기 전에 반드시: window.__jaDialogs.restore()  → 원래 알림창으로 되돌린다.
//   (되돌리지 않으면 사용자가 직접 누른 임시저장 확인도 소리 없이 취소되고, 오류 알림도 보이지 않는다.)
// 페이지를 이동하면 덮어쓴 함수가 사라진다. 이동한 뒤에는 `!!window.__jaDialogs` 로 확인하고 다시 넣는다.
// window.confirm 을 직접 `() => true` 로 덮어쓰지 않는다.
(() => {
  if (window.__jaDialogs && window.__jaDialogs.on) return `알림창 가드 이미 켜짐 — 기록 ${window.__jaDialogs.log.length}건, window.__jaDialogs.read()`;
  const DANGER = /제출|삭제|접수|최종|취소|탈퇴|결제|등록|지원하시겠|변경할 수 없|수정할 수 없|수정이 불가|되돌릴 수 없|submit|delete|remove/i;
  // "추후 최종제출을 하여야 완료됩니다" 처럼 아직 제출이 아니라는 안내 문장은 위험 판정에서 뺀다 (incruit 임시저장 확인 문구).
  const NOT_YET = /(추후|별도로|따로|반드시)?\s*최종\s*제출(을|은)?\s*(하여야|해야|하셔야|눌러야)[^.?!\n]*/g;
  const risky = (text) => DANGER.test(text.replace(NOT_YET, ""));
  const KEY = "__jaDialogLog";
  const clean = (s) => String(s ?? "").replace(/https?:\/\//g, "").replace(/@/g, "(at)").replace(/\|/g, "¦").replace(/[=&]/g, "_").replace(/\s+/g, " ").trim().slice(0, 80);
  const load = () => { try { return JSON.parse(sessionStorage.getItem(KEY) || "[]"); } catch (e) { return []; } };
  const log = load();
  const save = () => { try { sessionStorage.setItem(KEY, JSON.stringify(log.slice(-50))); } catch (e) { /* 저장소를 못 쓰면 이 페이지 안에서만 기록 */ } };
  const allow = [];
  const originals = new Map();
  const timers = new Set();
  let readUpTo = log.length;

  const record = (where, type, msg, answer) => {
    log.push({ t: new Date().toTimeString().slice(0, 8), where, type, msg: clean(msg), answer: String(answer) });
    save();
  };
  const install = (w, where) => {
    if (w.__jaGuard) return;
    originals.set(w, natives(w));
    w.alert = (m) => { record(where, "alert", m, "-"); };
    w.confirm = (m) => {
      const text = String(m ?? "");
      let ok = false;
      const i = allow.findIndex((a) => text.includes(a.text));
      if (i >= 0) {
        const a = allow.splice(i, 1)[0];
        ok = a.risky || !risky(text);
      }
      record(where, "confirm", text, ok);
      return ok;
    };
    w.prompt = (m) => { record(where, "prompt", m, "null"); return null; };
    const open = w.open;
    w.open = function (...args) {
      const p = open.apply(this, args);
      if (p) watchPopup(p);
      return p;
    };
    w.__jaGuard = true;
  };
  // 원래 함수: 이미 다른 코드가 덮어썼으면(예: 예전 방식의 confirm = () => false) 숨은 iframe 에서 진짜 함수를 가져온다.
  const isNative = (f) => typeof f === "function" && /\[native code\]/.test(Function.prototype.toString.call(f));
  const natives = (w) => {
    const o = { alert: w.alert, confirm: w.confirm, prompt: w.prompt, open: w.open };
    if (["alert", "confirm", "prompt", "open"].every((k) => isNative(o[k]))) return o;
    const f = w.document.createElement("iframe");
    f.style.display = "none";
    f.setAttribute("data-ja-natives", "");
    w.document.documentElement.appendChild(f);
    for (const k of ["alert", "confirm", "prompt", "open"]) if (!isNative(o[k])) o[k] = f.contentWindow[k].bind(w);
    return o;
  };
  const every = (ms, fn) => { const id = setInterval(() => fn(id), ms); timers.add(id); };
  const watchPopup = (p) => {
    let warned = false;
    every(100, (id) => {
      try {
        if (p.closed) { clearInterval(id); timers.delete(id); return; }
        if (!p.__jaGuard && p.document && p.document.readyState !== "loading") install(p, "popup");
      } catch (e) {
        if (!warned) { record("popup", "warn", "다른 출처 팝업이라 알림창을 막을 수 없음", "-"); warned = true; }
      }
    });
  };
  const frames = () => {
    for (const f of document.querySelectorAll("iframe:not([data-ja-natives])")) {
      try { if (f.contentWindow && f.contentWindow.document) install(f.contentWindow, "iframe"); } catch (e) { /* 다른 출처 iframe */ }
    }
  };

  install(window, "page");
  frames();
  every(500, frames);

  window.__jaDialogs = {
    on: true,
    log,
    allowOnce(text) { allow.push({ text: String(text), risky: false }); return `다음 "${text}" 확인 한 번만 허락 (제출·삭제·등록 등이 든 창은 제외)`; },
    allowRiskyOnce(text) { allow.push({ text: String(text), risky: true }); return `되돌릴 수 없는 "${text}" 확인 한 번 허락 — 사용자가 맡긴 동작인지 다시 확인할 것`; },
    read(all = false) {
      const items = all ? log : log.slice(readUpTo);
      readUpTo = log.length;
      return items.length ? items.map((x) => `${x.t} | ${x.where} | ${x.type} | ${x.msg} | ${x.answer}`).join("\n") : "(새 알림 없음)";
    },
    restore() {
      timers.forEach((id) => clearInterval(id));
      timers.clear();
      for (const [w, o] of originals) {
        try { Object.assign(w, o); delete w.__jaGuard; } catch (e) { /* 닫힌 창 */ }
      }
      originals.clear();
      this.on = false;
      return `알림창 원래대로 — 이번 기록 ${log.length}건`;
    },
  };
  return `알림창 가드 켜짐 — 지난 기록 ${log.length}건. 클릭 뒤 window.__jaDialogs.read(), 넘기기 전 window.__jaDialogs.restore()`;
})()
