/* 문자 사기 확인 — 화면 동작.
   가짜 로딩은 쓰지 않는다. 단계 표시는 실제 요청이 시작·끝날 때만 바뀐다.
   화면에 글자를 넣을 때는 textContent만 쓴다 (받은 내용을 HTML로 해석하지 않는다). */

"use strict";

const el = (id) => document.getElementById(id);

const ICONS = {
  // 위험: 느낌표가 든 삼각형
  danger:
    '<svg viewBox="0 0 24 24" role="img" aria-hidden="true"><path d="M12 2 1.5 21h21L12 2zm1 13h-2V9h2v6zm0 4h-2v-2h2v2z"/></svg>',
  // 주의: 느낌표가 든 동그라미
  caution:
    '<svg viewBox="0 0 24 24" role="img" aria-hidden="true"><path d="M12 2a10 10 0 100 20 10 10 0 000-20zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>',
  // 신호 없음: 돋보기 (체크 표시는 안전하다는 뜻으로 읽히므로 쓰지 않는다)
  clear:
    '<svg viewBox="0 0 24 24" role="img" aria-hidden="true"><path d="M10 2a8 8 0 105.3 14l5.4 5.4 1.4-1.4-5.4-5.4A8 8 0 0010 2zm0 2a6 6 0 110 12 6 6 0 010-12z"/></svg>',
};

const state = {
  meta: null,
  text: "",
  busy: false,
  level: null,
  fromImage: false,
};

/* ---------- 글씨 크기 / 고대비 (저장 실패해도 동작) ---------- */

function store(key, value) {
  try {
    localStorage.setItem(key, value);
  } catch (error) {
    /* 사생활 보호 모드 등에서 저장이 막혀도 그냥 넘어간다 */
  }
}

function restore(key) {
  try {
    return localStorage.getItem(key);
  } catch (error) {
    return null;
  }
}

function applySize(size) {
  document.documentElement.dataset.size = size;
  document.querySelectorAll("[data-size-set]").forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.sizeSet === size));
  });
}

function applyContrast(on) {
  if (on) {
    document.documentElement.dataset.contrast = "high";
  } else {
    delete document.documentElement.dataset.contrast;
  }
  el("contrast-toggle").setAttribute("aria-pressed", String(on));
}

function setupPrefs() {
  const saved = restore("textSize");
  applySize(["normal", "large", "xlarge"].includes(saved) ? saved : "normal");
  applyContrast(restore("highContrast") === "on");

  document.querySelectorAll("[data-size-set]").forEach((button) => {
    button.addEventListener("click", () => {
      applySize(button.dataset.sizeSet);
      store("textSize", button.dataset.sizeSet);
    });
  });

  el("contrast-toggle").addEventListener("click", () => {
    const next = el("contrast-toggle").getAttribute("aria-pressed") !== "true";
    applyContrast(next);
    store("highContrast", next ? "on" : "off");
  });
}

/* ---------- 단계 표시 ---------- */

function setStep(id, label, stateName, visible) {
  const step = el(id);
  if (visible !== undefined) step.hidden = !visible;
  const badge = step.querySelector(".step-state");
  badge.textContent = label;
  badge.dataset.state = stateName;
}

function say(message) {
  el("live-status").textContent = message;
}

/* 단계 번호는 실제로 하는 일만 세어서 매긴다.
   사진을 넣었으면  1 글자 읽기 / 2 위험 신호 검사 / 3 한 번 더 보기
   글자를 넣었으면  1 위험 신호 검사 / 2 한 번 더 보기 */
function numberSteps(withOcr) {
  const order = withOcr
    ? ["step-ocr", "step-rule", "step-llm"]
    : ["step-rule", "step-llm"];
  order.forEach((id, index) => {
    el(id).querySelector(".step-no").textContent = `${index + 1}단계`;
  });
}

function showProgress(withOcr) {
  el("progress").hidden = false;
  setStep("step-ocr", "기다리는 중", "wait", withOcr);
  setStep("step-rule", "기다리는 중", "wait", true);
  setStep("step-llm", "기다리는 중", "wait", false);
  numberSteps(withOcr);
  say("");
}

/* ---------- 서버 호출 ---------- */

async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok && data.error) throw new Error(data.error);
  if (!response.ok) throw new Error("확인하는 중에 문제가 생겼어요. 잠시 뒤 다시 해 주세요.");
  return data;
}

async function postImage(file) {
  const form = new FormData();
  form.append("image", file);
  const response = await fetch("/api/ocr", { method: "POST", body: form });
  const data = await response.json().catch(() => ({}));
  if (!response.ok && data.error) throw new Error(data.error);
  if (!response.ok) throw new Error("사진을 읽는 중에 문제가 생겼어요.");
  return data;
}

/* ---------- 결과 그리기 ---------- */

function paintSegments(view, segments) {
  view.textContent = "";
  segments.forEach((piece) => {
    if (piece.mark) {
      const mark = document.createElement("mark");
      mark.textContent = piece.text;
      view.appendChild(mark);
    } else {
      view.appendChild(document.createTextNode(piece.text));
    }
  });
}

function renderMessage(segments) {
  paintSegments(el("message-view"), segments);
}

function renderChecks(checks) {
  const list = el("checks");
  list.textContent = "";
  checks.forEach((check) => {
    const item = document.createElement("li");
    const name = document.createElement("span");
    name.textContent = check.name;
    // 세 가지 상태: 찾음 / 없음 / 있는 것 같음(사진에서 주소를 정확히 못 읽음)
    const state = check.state || (check.found ? "found" : "none");
    const labels = { found: "찾음", none: "없음" };
    const found = document.createElement("span");
    found.className = "check-state";
    found.dataset.found = state;
    found.textContent = check.label || labels[state] || "없음";
    item.append(name, found);
    list.appendChild(item);
  });
}

function renderReasons(reasons) {
  const list = el("reasons");
  list.textContent = "";
  el("reasons-block").hidden = reasons.length === 0;

  reasons.forEach((reason) => {
    const item = document.createElement("li");

    const title = document.createElement("p");
    title.className = "reason-title";
    title.textContent = reason.title;

    const body = document.createElement("p");
    body.className = "reason-body";
    body.textContent = reason.body;

    item.append(title, body);

    if (reason.matches && reason.matches.length) {
      const found = document.createElement("p");
      found.className = "reason-matches";
      found.appendChild(document.createTextNode("문자에서 찾은 부분: "));
      reason.matches.slice(0, 8).forEach((match) => {
        const chip = document.createElement("span");
        chip.textContent = match;
        found.appendChild(chip);
      });
      item.appendChild(found);
    }
    list.appendChild(item);
  });
}

function renderVerdict(verdict, notice) {
  const result = el("result");
  result.dataset.level = verdict.level;
  state.level = verdict.level;
  el("verdict-icon").innerHTML = ICONS[verdict.icon] || "";
  el("verdict-badge").textContent = verdict.badge;
  el("result-title").textContent = verdict.headline;

  const noticeBox = el("result-notice");
  if (notice) {
    noticeBox.textContent = notice;
    noticeBox.hidden = false;
  } else {
    noticeBox.hidden = true;
  }
}

function renderActions() {
  const wrap = el("action-buttons");
  wrap.textContent = "";
  el("guidance").hidden = true;

  // 위험 신호를 찾지 못했을 때는 "이미 무엇을 하셨나요?"를 묻지 않는다.
  // 물어볼 일이 없는데 물으면 공연히 불안하게 만든다.
  const needed = state.level === "danger" || state.level === "caution";
  el("actions-block").hidden = !needed;
  if (!needed) return;

  state.meta.actions.forEach((action) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = action.label;
    button.setAttribute("aria-pressed", "false");
    button.addEventListener("click", () => {
      wrap.querySelectorAll("button").forEach((other) => {
        other.setAttribute("aria-pressed", String(other === button));
      });
      showGuidance(action.key);
    });
    wrap.appendChild(button);
  });
}

function showGuidance(key) {
  const detail = state.meta.action_details.find((item) => item.key === key);
  if (!detail) return;
  el("guidance-heading").textContent = detail.heading;
  const list = el("guidance-steps");
  list.textContent = "";
  detail.steps.forEach((step) => {
    const item = document.createElement("li");
    item.textContent = step;
    list.appendChild(item);
  });
  el("guidance").hidden = false;
}

/* ---------- 검사 흐름 ---------- */

function showError(message) {
  const box = el("form-error");
  box.textContent = message;
  box.hidden = false;
  el("form-error").scrollIntoView({ block: "nearest" });
}

function clearError() {
  el("form-error").hidden = true;
  el("form-error").textContent = "";
}

function setBusy(busy) {
  state.busy = busy;
  el("submit").disabled = busy;
  el("ocr-confirm").disabled = busy;
  el("submit").textContent = busy ? "검사하고 있어요" : "검사하기";
}

async function runCheck(text) {
  state.text = text;
  el("result").hidden = true;
  el("ocr-edit").hidden = true;
  setBusy(true);

  try {
    setStep("step-rule", "검사하는 중", "run");
    say("위험 신호를 찾고 있어요.");
    const rule = await postJson("/api/rule", { text, from_image: state.fromImage });

    setStep("step-rule", "끝", "done");
    renderMessage(rule.segments);
    renderChecks(rule.checks);

    if (!rule.needs_llm) {
      // 위험 신호를 이미 찾았으므로 3단계를 부르지 않는다. 그 사실을 그대로 쓴다.
      setStep("step-llm", "필요 없음 (위험 신호를 이미 찾았어요)", "skip", true);
      renderVerdict(rule.verdict, rule.notice || null);
      renderReasons(rule.reasons);
      say("검사를 마쳤어요.");
      finish();
      return;
    }

    // Rule이 아무 신호도 못 찾았을 때만 한 번 더 확인한다.
    setStep("step-llm", "한 번 더 꼼꼼히 보고 있어요", "run", true);
    say("위험 신호는 못 찾았어요. 한 번 더 꼼꼼히 보고 있어요. 몇 초 걸립니다.");

    const llm = await postJson("/api/llm", { text, from_image: state.fromImage });
    setStep("step-llm", llm.available ? "끝" : "건너뜀", llm.available ? "done" : "skip");
    renderVerdict(llm.verdict, llm.notice || null);
    renderReasons(llm.reasons || []);
    say("검사를 마쳤어요.");
    finish();
  } catch (error) {
    setStep("step-rule", "실패", "fail");
    showError(error.message);
    el("progress").hidden = true;
  } finally {
    setBusy(false);
  }
}

function finish() {
  renderActions();
  el("result").hidden = false;
  el("result-title").focus({ preventScroll: true });
  el("result").scrollIntoView({ behavior: "smooth", block: "start" });
}

async function handleSubmit(event) {
  event.preventDefault();
  if (state.busy) return;
  clearError();

  const file = el("image").files[0];
  const typed = el("message").value.trim();

  if (file) {
    state.fromImage = true;
    showProgress(true);
    setBusy(true);
    setStep("step-ocr", "글자를 읽고 있어요", "run");
    say("사진에서 글자를 읽고 있어요. 처음 한 번은 조금 더 걸립니다.");
    try {
      const result = await postImage(file);
      setStep("step-ocr", "끝", "done");
      el("ocr-notice").textContent = result.notice;
      el("ocr-text").value = result.text;

      // 주소처럼 보이는 줄이 있으면 형광펜으로 보여 주고 고치도록 안내한다.
      if (result.url_hint && result.segments) {
        el("ocr-url-notice").textContent = result.url_hint_notice;
        paintSegments(el("ocr-preview"), result.segments);
        el("ocr-url-hint").hidden = false;
      } else {
        el("ocr-url-hint").hidden = true;
      }

      el("ocr-edit").hidden = false;
      el("ocr-text").focus();
      say("읽은 글자를 확인해 주세요.");
    } catch (error) {
      setStep("step-ocr", "실패", "fail");
      showError(error.message);
      el("progress").hidden = true;
    } finally {
      setBusy(false);
    }
    return;
  }

  if (!typed) {
    showError("확인할 문자를 넣어 주세요. 문자를 붙여 넣거나 캡처 사진을 올려 주세요.");
    el("message").focus();
    return;
  }
  if (state.meta && typed.length > state.meta.max_text_length) {
    showError(
      `문자가 너무 길어요. ${state.meta.max_text_length}글자까지 확인할 수 있어요. 지금은 ${typed.length}글자예요.`
    );
    return;
  }

  // 직접 붙여 넣은 글자에는 '깨진 주소' 보정을 쓰지 않는다.
  state.fromImage = false;
  showProgress(false);
  runCheck(typed);
}

function setupSamples() {
  const wrap = el("sample-buttons");
  state.meta.samples.forEach((sample) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = sample.label;
    button.addEventListener("click", () => {
      el("image").value = "";
      el("message").value = sample.text;
      clearError();
      el("message").focus();
    });
    wrap.appendChild(button);
  });
}

async function init() {
  setupPrefs();

  el("check-form").addEventListener("submit", handleSubmit);
  el("ocr-confirm").addEventListener("click", () => {
    const text = el("ocr-text").value.trim();
    if (!text) {
      showError("읽은 글자가 비어 있어요. 문자를 직접 넣어 주세요.");
      return;
    }
    clearError();
    runCheck(text);
  });
  el("restart").addEventListener("click", () => {
    el("message").value = "";
    el("image").value = "";
    el("ocr-text").value = "";
    el("result").hidden = true;
    el("progress").hidden = true;
    el("ocr-edit").hidden = true;
    el("actions-block").hidden = true;
    el("ocr-url-hint").hidden = true;
    state.level = null;
    state.fromImage = false;
    clearError();
    el("message").focus();
    window.scrollTo({ top: 0, behavior: "smooth" });
  });

  try {
    const response = await fetch("/api/meta");
    state.meta = await response.json();
  } catch (error) {
    showError("화면을 준비하지 못했어요. 새로 고침을 해 주세요.");
    return;
  }

  setupSamples();
  if (!state.meta.ocr_available) {
    el("ocr-unavailable").hidden = false;
    el("image").disabled = true;
  }
}

init();
