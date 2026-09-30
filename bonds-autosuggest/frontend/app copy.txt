(() => {
  "use strict";

  const input = document.getElementById("search-input");
  const list = document.getElementById("suggestion-list");
  const chipRow = document.getElementById("chip-row");
  const dslJson = document.getElementById("dsl-json");
  const dslEmpty = document.getElementById("dsl-empty");
  const toggleJsonBtn = document.getElementById("toggle-json");
  const connDot = document.getElementById("conn-dot");
  const clearBtn = document.getElementById("clear-btn");
  const llmBtn = document.getElementById("llm-convert-btn");
  const llmStatus = document.getElementById("llm-status");
  const llmJson = document.getElementById("llm-json");

  let ws = null;
  let reconnectDelay = 400;
  let debounceTimer = null;
  let suggestions = [];
  let selectedIndex = -1;
  let replaceSpan = [0, 0];
  let currentToken = "";
  let jsonVisible = false;

  // -------------------------------------------------------------- socket --
  function connect() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${proto}://${location.host}/ws`);

    ws.onopen = () => {
      connDot.classList.add("online");
      connDot.classList.remove("offline");
      reconnectDelay = 400;
      requestSuggestions();
    };
    ws.onclose = () => {
      connDot.classList.remove("online");
      connDot.classList.add("offline");
      setTimeout(connect, reconnectDelay);
      reconnectDelay = Math.min(reconnectDelay * 1.6, 5000);
    };
    ws.onerror = () => {
      try { ws.close(); } catch (e) { /* noop */ }
    };
    ws.onmessage = (evt) => {
      let data;
      try { data = JSON.parse(evt.data); } catch (e) { return; }
      if (data.action === "llm_parse") {
        handleLlmResult(data);
        return;
      }
      if (data.error) { console.warn("suggester error:", data.error); return; }
      render(data);
    };
  }

  function requestSuggestions() {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({
      action: "suggest",
      text: input.value,
      cursor: input.selectionStart,
    }));
  }

  function debouncedRequest() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(requestSuggestions, 60);
  }

  // -------------------------------------------------------------- render --
  function render(data) {
    suggestions = data.suggestions || [];
    selectedIndex = suggestions.length ? 0 : -1;
    replaceSpan = data.replace_span || [input.selectionStart, input.selectionStart];
    currentToken = data.current_token || "";
    renderList();
    renderChips(data.parsed);
    clearBtn.hidden = input.value.trim().length === 0;
  }

  function highlight(text, needle) {
    if (!needle) return escapeHtml(text);
    const idx = text.toLowerCase().indexOf(needle.toLowerCase());
    if (idx === -1) return escapeHtml(text);
    return (
      escapeHtml(text.slice(0, idx)) +
      "<mark>" + escapeHtml(text.slice(idx, idx + needle.length)) + "</mark>" +
      escapeHtml(text.slice(idx + needle.length))
    );
  }

  function escapeHtml(s) {
    return s.replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  function renderList() {
    list.innerHTML = "";
    if (!suggestions.length) {
      list.hidden = true;
      return;
    }
    suggestions.forEach((s, i) => {
      const li = document.createElement("li");
      li.className = `kind-${s.kind}` + (i === selectedIndex ? " active" : "");
      li.innerHTML =
        `<span class="tag" style="background:${s.color}">${escapeHtml(s.slot_label)}</span>` +
        `<span class="sug-text">${highlight(s.display, currentToken)}</span>`;
      li.addEventListener("mousedown", (e) => {
        e.preventDefault(); // keep focus on input, don't fire blur-hide first
        selectedIndex = i;
        applySelected();
      });
      list.appendChild(li);
    });
    list.hidden = false;
  }

  function renderChips(parsed) {
    chipRow.innerHTML = "";
    const chips = (parsed && parsed.chips) || [];
    if (!chips.length) {
      dslEmpty.hidden = false;
    } else {
      dslEmpty.hidden = true;
    }
    chips.forEach((c) => {
      const el = document.createElement("div");
      el.className = "chip";
      el.innerHTML =
        `<span class="dot" style="background:${c.color}"></span>` +
        `<span class="label">${escapeHtml(c.label)}</span>` +
        `<span class="value">${escapeHtml(c.text)}</span>`;
      chipRow.appendChild(el);
    });
    if (jsonVisible) {
      dslJson.textContent = JSON.stringify((parsed && parsed.dsl) || {}, null, 2);
    }
  }

  // ------------------------------------------------------------ actions --
  function applySelected() {
    if (selectedIndex < 0 || selectedIndex >= suggestions.length) return;
    const s = suggestions[selectedIndex];
    const val = input.value;
    const [start, end] = replaceSpan;
    const newVal = val.slice(0, start) + s.insert + val.slice(end);
    input.value = newVal;
    const newCursor = start + s.insert.length;
    input.setSelectionRange(newCursor, newCursor);
    input.focus();
    requestSuggestions();
  }

  function moveSelection(delta) {
    if (!suggestions.length) return;
    selectedIndex = (selectedIndex + delta + suggestions.length) % suggestions.length;
    renderList();
  }

  // ------------------------------------------------------------- events --
  input.addEventListener("input", debouncedRequest);
  input.addEventListener("click", debouncedRequest);
  input.addEventListener("keyup", (e) => {
    if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) debouncedRequest();
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); moveSelection(1); return; }
    if (e.key === "ArrowUp") { e.preventDefault(); moveSelection(-1); return; }
    // Tab = accept the highlighted suggestion and keep refining.
    if (e.key === "Tab" && suggestions.length && !list.hidden) {
      e.preventDefault();
      applySelected();
      return;
    }
    // Enter = submit the finished query (phase 2: convert with AI),
    // distinct from Tab's "accept and keep typing".
    if (e.key === "Enter") {
      e.preventDefault();
      suggestions = [];
      renderList();
      submitQuery();
      return;
    }
    if (e.key === "Escape") {
      suggestions = [];
      renderList();
    }
  });

  input.addEventListener("blur", () => {
    setTimeout(() => { list.hidden = true; }, 120);
  });
  input.addEventListener("focus", () => {
    if (suggestions.length) list.hidden = false;
  });

  toggleJsonBtn.addEventListener("click", () => {
    jsonVisible = !jsonVisible;
    dslJson.hidden = !jsonVisible;
    toggleJsonBtn.textContent = jsonVisible ? "hide JSON" : "show JSON";
    if (jsonVisible) requestSuggestions();
  });

  clearBtn.addEventListener("click", () => {
    input.value = "";
    input.focus();
    requestSuggestions();
  });

  // ---------------------------------------------------- phase 2: LLM DSL --
  function handleLlmResult(data) {
    llmBtn.disabled = false;
    llmBtn.textContent = "Convert with AI →";
    llmBtn.classList.remove("pulse");
    if (data.error) {
      llmStatus.hidden = false;
      llmStatus.className = "error";
      llmStatus.textContent = data.error;
      llmJson.hidden = true;
      return;
    }
    llmStatus.hidden = false;
    llmStatus.className = "ok";
    llmStatus.textContent = "Parsed by the LLM:";
    llmJson.hidden = false;
    llmJson.textContent = JSON.stringify(data.dsl, null, 2);
  }

  function submitQuery() {
    if (!input.value.trim()) return;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      llmStatus.hidden = false;
      llmStatus.className = "error";
      llmStatus.textContent = "Not connected to the server yet — try again in a moment.";
      return;
    }
    llmBtn.disabled = true;
    llmBtn.textContent = "Converting…";
    llmBtn.classList.add("pulse");
    llmStatus.hidden = true;
    llmJson.hidden = true;
    llmBtn.scrollIntoView({ behavior: "smooth", block: "nearest" });
    ws.send(JSON.stringify({ action: "llm_parse", text: input.value }));
  }

  llmBtn.addEventListener("click", submitQuery);

  document.querySelectorAll(".examples li").forEach((li) => {
    li.addEventListener("click", () => {
      input.value = li.dataset.example;
      input.focus();
      input.setSelectionRange(input.value.length, input.value.length);
      requestSuggestions();
    });
  });

  connect();
})();
