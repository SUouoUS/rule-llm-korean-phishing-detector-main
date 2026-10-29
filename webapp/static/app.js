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

/* ---------- 소리로 듣기 (브라우저 내장 음성, 외부 서비스 없음) ---------- */

/* 브라우저에 들어 있는 음성 합성만 쓴다. 글자가 바깥으로 나가지 않는다. */
const speech = {
  supported:
    typeof window !== "undefined" &&
    "speechSynthesis" in window &&
    typeof window.SpeechSynthesisUtterance === "function",
  speaking: false,
  queued: 0,
};

/* 목소리는 이 PC에 깔린 것 중에서만 고를 수 있다. 브라우저가 음색을 만들지는 못한다.
   그래서 여성 목소리를 먼저 고르되, 사람이 직접 고를 수 있는 칸도 같이 둔다.

   이름으로 거르는 이유: SpeechSynthesisVoice 에는 성별 정보가 없다.
   - SunHi / InJoon 은 엣지의 자연스러운(Natural) 한국어 목소리. SunHi 가 여성이다.
   - Heami 는 윈도우 기본 한국어 여성 목소리.
   - Yuna 는 macOS 한국어 여성 목소리.
   - Google 한국의 는 크롬 한국어 여성 목소리. */
const FEMALE_VOICE_HINTS = ["sunhi", "heami", "yuna", "sora", "google 한국", "female", "여성"];
const MALE_VOICE_HINTS = ["injoon", "minsu", "male", "남성"];

function koreanVoices() {
  const voices = window.speechSynthesis.getVoices() || [];
  return voices.filter((voice) => (voice.lang || "").toLowerCase().startsWith("ko"));
}

function voiceScore(voice) {
  const name = `${voice.name} ${voice.voiceURI || ""}`.toLowerCase();
  let score = 0;
  if (FEMALE_VOICE_HINTS.some((hint) => name.includes(hint))) score += 10;
  if (MALE_VOICE_HINTS.some((hint) => name.includes(hint))) score -= 10;
  // 엣지의 Natural/Online 목소리가 훨씬 부드럽다.
  if (name.includes("natural") || name.includes("online")) score += 4;
  return score;
}

function koreanVoice() {
  const chosen = restore("voiceName");
  const voices = koreanVoices();
  if (!voices.length) return null;

  if (chosen) {
    const match = voices.find((voice) => voice.name === chosen);
    if (match) return match;
  }
  return voices.slice().sort((a, b) => voiceScore(b) - voiceScore(a))[0];
}

function fillVoicePicker() {
  const voices = koreanVoices();
  const wrap = el("voice-pick-wrap");
  const picker = el("voice-pick");

  // 한국어 목소리가 하나뿐이거나 없으면 고를 것이 없으므로 칸을 숨긴다.
  if (voices.length < 2) {
    wrap.hidden = true;
    return;
  }

  const current = (koreanVoice() || {}).name;
  picker.textContent = "";
  voices
    .slice()
    .sort((a, b) => voiceScore(b) - voiceScore(a))
    .forEach((voice) => {
      const option = document.createElement("option");
      option.value = voice.name;
      option.textContent = voice.name;
      if (voice.name === current) option.selected = true;
      picker.appendChild(option);
    });
  wrap.hidden = false;
}

/* 결과 제목, 제목 아래 안내, "왜 위험한지" 설명을 차례로 모은다.
   원문에서 찾은 표현(깨진 주소 등)은 소리로 들으면 알아듣기 어려우므로 뺀다. */
function spokenText() {
  const parts = [el("result-title").textContent.trim()];

  const notice = el("result-notice");
  if (!notice.hidden && notice.textContent.trim()) {
    parts.push(notice.textContent.trim());
  }

  document.querySelectorAll("#reasons li").forEach((item) => {
    const title = item.querySelector(".reason-title");
    const body = item.querySelector(".reason-body");
    if (title) parts.push(title.textContent.trim());
    if (body) parts.push(body.textContent.trim());
  });

  return parts.filter(Boolean);
}

/* 크롬은 긴 문장을 읽다가 중간에 멈춘다. 문장 단위로 끊어서 차례로 넘긴다. */
function toChunks(parts) {
  const chunks = [];
  parts.forEach((part) => {
    // 뒤돌아보기(lookbehind)는 구형 사파리에서 스크립트 전체를 깨뜨리므로 쓰지 않는다.
    // 문장 끝 부호를 남긴 채로 끊기 위해 부호를 캡처해 다시 붙인다.
    part
      .split(/([.!?])\s+/)
      .reduce((sentences, piece, index) => {
        if (index % 2 === 0) sentences.push(piece);
        else sentences[sentences.length - 1] += piece;
        return sentences;
      }, [])
      .map((sentence) => sentence.trim())
      .filter(Boolean)
      .forEach((sentence) => {
        if (sentence.length <= 120) {
          chunks.push(sentence);
          return;
        }
        for (let at = 0; at < sentence.length; at += 120) {
          chunks.push(sentence.slice(at, at + 120));
        }
      });
  });
  return chunks;
}

function setSpeakingState(on) {
  speech.speaking = on;
  const button = el("speak");
  button.setAttribute("aria-pressed", String(on));
  el("speak-label").textContent = on ? "그만 듣기" : "소리로 듣기";
}

function stopSpeaking() {
  if (!speech.supported) return;
  speech.queued = 0;
  window.speechSynthesis.cancel();
  setSpeakingState(false);
}

function startSpeaking() {
  const chunks = toChunks(spokenText());
  if (!chunks.length) return;

  const synth = window.speechSynthesis;
  synth.cancel();

  const voice = koreanVoice();
  speech.queued = chunks.length;
  setSpeakingState(true);

  chunks.forEach((chunk) => {
    const utterance = new SpeechSynthesisUtterance(chunk);
    utterance.lang = "ko-KR";
    utterance.rate = 0.92; // 천천히
    utterance.pitch = 1.08; // 조금 높고 부드럽게
    if (voice) utterance.voice = voice;
    utterance.onend = () => {
      speech.queued -= 1;
      if (speech.queued <= 0) setSpeakingState(false);
    };
    utterance.onerror = () => stopSpeaking();
    synth.speak(utterance);
  });
}

function setupSpeech() {
  const row = el("speak-row");
  if (!speech.supported) {
    row.hidden = true; // 지원하지 않는 브라우저에서는 아예 보이지 않는다
    return;
  }
  row.hidden = false;

  el("speak").addEventListener("click", () => {
    if (speech.speaking) stopSpeaking();
    else startSpeaking();
  });

  el("voice-pick").addEventListener("change", (event) => {
    store("voiceName", event.target.value);
    stopSpeaking();
  });

  // 크롬과 엣지는 목소리 목록을 조금 늦게 채운다. 채워지면 고르는 칸을 다시 만든다.
  fillVoicePicker();
  if (typeof window.speechSynthesis.addEventListener === "function") {
    window.speechSynthesis.addEventListener("voiceschanged", fillVoicePicker);
  }

  window.addEventListener("beforeunload", stopSpeaking);
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
  stopSpeaking();
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
  setupSpeech();

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
    stopSpeaking();
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
