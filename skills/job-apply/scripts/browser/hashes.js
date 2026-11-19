// 긴 텍스트 입력란의 SHA-256 앞 16자리 — inspect.js 를 먼저 실행해야 순번(data-ja-seq)이 붙는다.
// 도구는 최상위 await 로만 비동기 결과를 돌려준다(앞의 await 를 지우지 말 것).
// 출력: "순번 해시" 를 공백으로 이어 붙인 한 줄 (해시만 있어야 결과 차단을 피한다). 40자를 넘는 칸만 (40자 이하는 inspect.js 가 값을 그대로 보여 준다).
await (async () => {
  const h = async (s) => [...new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s)))]
    .map((b) => b.toString(16).padStart(2, "0")).join("").slice(0, 16);
  const out = [];
  for (const el of document.querySelectorAll("[data-ja-seq]")) {
    if (el.value.length > 40) out.push(`${el.dataset.jaSeq} ${await h(el.value)}`);
  }
  return out.join(" ");
})()
