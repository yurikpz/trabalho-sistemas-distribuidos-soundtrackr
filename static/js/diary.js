// EDITAR E EXCLUIR DO DIÁRIO

// ABRE SELETOR NATIVO DE DATA, COM FALLBACKS ROBUSTOS
async function editDiaryDate(id, currentDate) {
  // IMPUT DATE + SHOWPICKER
  const input = document.createElement("input");
  input.type = "date";
  input.style.position = "fixed";
  input.style.left = "-9999px";
  input.style.top = "0";
  input.value = (currentDate && currentDate.includes("-"))
    ? currentDate
    : new Date().toISOString().split("T")[0];

  document.body.appendChild(input);

  let usedFallbackPrompt = false;

  const onChange = async () => {
    const newDate = input.value;
    input.remove();

    if (!newDate || newDate === currentDate) return;

    try {
      const res = await fetch("/diary/update", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id, listenedAt: newDate }),
      });

      if (res.ok) {
        showToast(" Data atualizada");
        setTimeout(() => location.reload(), 400);
      } else {
        alert("Erro ao atualizar.");
      }
    } catch (e) {
      alert("Erro de conexão.");
      console.error(e);
    }
  };

  // SE O USUÁRIO CANCELAR O SELETOR, NADA ACONTECE, SE O BROWSER BLOQUEAR CAIMOS NO PROMPT
  input.addEventListener("change", onChange, { once: true });

  try {
    if (typeof input.showPicker === "function") {
      input.showPicker();            
    } else {
      input.click();                 // FALLBACK
      // SE NADA ABRIR EM 400MS, CAI NO PROMPT
      setTimeout(() => {
        // SE AINDA NÃO USOU ESCOLHER NADA E O IMPUT ESTÁ NO DOM, USA O PROMPT
        if (document.body.contains(input) && !input.value) {
          usedFallbackPrompt = true;
          input.remove();
          legacyPromptFlow();
        }
      }, 400);
    }
  } catch (e) {
    // SE O BROWSER BLOQUEAR, USA O PROMPT
    input.remove();
    usedFallbackPrompt = true;
    legacyPromptFlow();
  }

  function legacyPromptFlow() {
    const val = prompt("Nova data (YYYY-MM-DD):", currentDate || "");
    if (!val) return;
    // Validação mínima
    const ok = /^\d{4}-\d{2}-\d{2}$/.test(val);
    if (!ok) {
      alert("Use o formato YYYY-MM-DD, por favor.");
      return;
    }
    //REAPROVEIRA O CAMINHO DO OnChange
    (async () => {
      try {
        const res = await fetch("/diary/update", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id, listenedAt: val }),
        });

        if (res.ok) {
          showToast(" Data atualizada");
          setTimeout(() => location.reload(), 400);
        } else {
          alert("Erro ao atualizar.");
        }
      } catch (e) {
        alert("Erro de conexão.");
        console.error(e);
      }
    })();
  }
}

// REMOVE REGISTRO DO DIÁRIO
async function deleteDiaryEntry(id) {
  if (!confirm("Excluir este registro do diário?")) return;

  try {
    const res = await fetch("/diary/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id }),
    });

    if (res.ok) {
      showToast("Removido do diário");
      setTimeout(() => location.reload(), 400);
    } else {
      alert("Erro ao excluir.");
    }
  } catch (e) {
    console.error(e);
    alert("Erro ao conectar.");
  }
}


function showToast(msg) {
  if (window.showToastFromMainJS) {
    window.showToastFromMainJS(msg);
    return;
  }

  const t = document.createElement("div");
  t.className = "toast";
  t.textContent = msg;
  document.body.appendChild(t);

  setTimeout(() => t.classList.add("show"), 50);
  setTimeout(() => {
    t.classList.remove("show");
    setTimeout(() => t.remove(), 300);
  }, 2000);
}
