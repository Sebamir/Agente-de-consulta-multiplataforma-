/* ── Sesión ───────────────────────────────────────────────────────────────── */
function getSessionId() {
  let id = localStorage.getItem("agent_session_id");
  if (!id) {
    id = "sess_" + Math.random().toString(36).slice(2, 11);
    localStorage.setItem("agent_session_id", id);
  }
  return id;
}

let SESSION_ID = getSessionId();

/* ── DOM ──────────────────────────────────────────────────────────────────── */
const messagesEl = document.getElementById("messages");
const inputEl    = document.getElementById("input");
const sendBtn    = document.getElementById("btn-send");
const clearBtn   = document.getElementById("btn-clear");

/* ── Auto-resize del textarea ─────────────────────────────────────────────── */
inputEl.addEventListener("input", () => {
  inputEl.style.height = "auto";
  inputEl.style.height = Math.min(inputEl.scrollHeight, 160) + "px";
});

/* ── Enter para enviar (Shift+Enter = nueva línea) ────────────────────────── */
inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

sendBtn.addEventListener("click", sendMessage);

clearBtn.addEventListener("click", async () => {
  await fetch(`/api/session/${SESSION_ID}/clear`, { method: "POST" });
  messagesEl.innerHTML = "";
  appendAssistantWelcome();
});

/* ── Agregar mensaje del usuario ──────────────────────────────────────────── */
function appendUserMessage(text) {
  const div = document.createElement("div");
  div.className = "message user";
  div.innerHTML = `<div class="bubble">${escapeHtml(text)}</div>`;
  messagesEl.appendChild(div);
  scrollToBottom();
}

/* ── Crear bubble del asistente (vacío, se rellena con streaming) ─────────── */
function createAssistantBubble() {
  const wrapper = document.createElement("div");
  wrapper.className = "message assistant";
  const bubble = document.createElement("div");
  bubble.className = "bubble streaming";
  wrapper.appendChild(bubble);
  messagesEl.appendChild(wrapper);
  scrollToBottom();
  return bubble;
}

/* ── Crear acordeón de tool call ──────────────────────────────────────────── */
function createToolBlock(bubble, toolName, toolInput) {
  const block = document.createElement("div");
  block.className = "tool-block";

  // Formatear input: preferir SQL si existe
  const sql = toolInput.sql || toolInput.query || toolInput.statement;
  const inputText = sql ? sql.trim() : JSON.stringify(toolInput, null, 2);
  const inputLabel = sql ? "SQL" : "Input";

  block.innerHTML = `
    <div class="tool-header">
      <span>⚙ ${escapeHtml(toolName)}</span>
      <span class="tool-chevron">▶</span>
    </div>
    <div class="tool-body">
      <div class="tool-label">${inputLabel}</div>
      <pre class="tool-code">${escapeHtml(inputText)}</pre>
      <div class="tool-result" style="display:none">
        <div class="tool-label" style="margin-top:10px">Resultado</div>
        <pre class="tool-result-code"></pre>
      </div>
    </div>`;

  // Toggle acordeón
  block.querySelector(".tool-header").addEventListener("click", () => {
    block.classList.toggle("open");
  });

  bubble.appendChild(block);
  scrollToBottom();
  return block;
}

/* ── Enviar consulta ──────────────────────────────────────────────────────── */
async function sendMessage() {
  const prompt = inputEl.value.trim();
  if (!prompt || sendBtn.disabled) return;

  // Limpiar input
  inputEl.value = "";
  inputEl.style.height = "auto";
  sendBtn.disabled = true;

  appendUserMessage(prompt);
  const bubble = createAssistantBubble();

  let textContent = "";
  let currentToolBlock = null;

  try {
    const response = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: SESSION_ID, prompt }),
    });

    if (!response.ok) {
      throw new Error(`Error del servidor: ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop(); // guardar línea incompleta

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const raw = line.slice(6).trim();
        if (!raw) continue;

        let event;
        try { event = JSON.parse(raw); } catch { continue; }

        if (event.type === "text") {
          textContent += event.content;
          bubble.textContent = textContent;
          bubble.appendChild; // fuerza re-render
          // Re-agregar tool blocks si los hay (textContent los borra)
          scrollToBottom();
        }

        if (event.type === "tool_call") {
          currentToolBlock = createToolBlock(bubble, event.tool, event.input || {});
        }

        if (event.type === "tool_result" && currentToolBlock) {
          const resultEl = currentToolBlock.querySelector(".tool-result");
          const codeEl   = currentToolBlock.querySelector(".tool-result-code");
          // Truncar resultados muy largos
          const text = event.result || "(sin resultado)";
          codeEl.textContent = text.length > 600 ? text.slice(0, 600) + "\n… (truncado)" : text;
          resultEl.style.display = "block";
          scrollToBottom();
        }

        if (event.type === "done") {
          bubble.classList.remove("streaming");
        }

        if (event.type === "error") {
          bubble.classList.remove("streaming");
          bubble.classList.add("error-text");
          bubble.textContent = "Error: " + event.message;
          bubble.closest(".message").classList.add("error");
        }
      }
    }

  } catch (err) {
    bubble.classList.remove("streaming");
    bubble.textContent = "Error de conexión: " + err.message;
    bubble.closest(".message").classList.add("error");
  } finally {
    sendBtn.disabled = false;
    inputEl.focus();
    scrollToBottom();
  }
}

/* ── Utilidades ───────────────────────────────────────────────────────────── */
function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function appendAssistantWelcome() {
  messagesEl.innerHTML = `
    <div class="message assistant">
      <div class="bubble">
        Hola, soy tu agente de datos. Podés preguntarme sobre tus tablas de PostgreSQL
        o tus Google Sheets en lenguaje natural.<br><br>
        <strong>Ejemplos:</strong><br>
        • Listá todas las tablas disponibles<br>
        • Mostrá los últimos 10 registros de [tabla]<br>
        • ¿Qué spreadsheets tengo disponibles?<br>
        • Resumí las ventas por categoría
      </div>
    </div>`;
}
