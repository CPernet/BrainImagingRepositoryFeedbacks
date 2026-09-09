(function () {
  const container = document.querySelector("[data-feedback-widget]");
  if (!container) {
    return;
  }

  const endpoint = container.getAttribute("data-endpoint") || "/api/feedback";

  if (!document.getElementById("feedback-widget-styles")) {
    const style = document.createElement("style");
    style.id = "feedback-widget-styles";
    style.textContent = `
      .feedback-widget { display: grid; gap: 0.9rem; }
      .feedback-widget h2 { margin: 0; font-size: 1.3rem; }
      .feedback-widget p { margin: 0; color: #475569; }
      .feedback-widget label { display: grid; gap: 0.35rem; font-weight: 600; }
      .feedback-widget input,
      .feedback-widget select,
      .feedback-widget textarea {
        border: 1px solid #cbd5e1;
        border-radius: 8px;
        font: inherit;
        padding: 0.75rem;
      }
      .feedback-widget textarea { min-height: 140px; resize: vertical; }
      .feedback-widget button {
        background: #2563eb;
        border: 0;
        border-radius: 8px;
        color: #fff;
        cursor: pointer;
        font: inherit;
        font-weight: 700;
        padding: 0.85rem 1rem;
      }
      .feedback-widget button:disabled {
        background: #94a3b8;
        cursor: progress;
      }
      .feedback-widget-status {
        min-height: 1.4rem;
        color: #0f766e;
        font-weight: 600;
      }
      .feedback-widget-status.error { color: #b91c1c; }
    `;
    document.head.appendChild(style);
  }

  container.innerHTML = `
    <form class="feedback-widget">
      <h2>Share feedback about this repository</h2>
      <p>Feedback is stored as JSON, converted into a GitHub issue payload, and included in topic summaries.</p>
      <label>
        Name
        <input name="name" type="text" placeholder="Optional">
      </label>
      <label>
        Email
        <input name="email" type="email" placeholder="Optional">
      </label>
      <label>
        Category
        <select name="category">
          <option value="general">General</option>
          <option value="bug">Bug</option>
          <option value="documentation">Documentation</option>
          <option value="data access">Data access</option>
          <option value="usability">Usability</option>
          <option value="feature request">Feature request</option>
        </select>
      </label>
      <label>
        Message
        <textarea name="message" required placeholder="Describe your feedback"></textarea>
      </label>
      <button type="submit">Send feedback</button>
      <div class="feedback-widget-status" aria-live="polite"></div>
    </form>
  `;

  const form = container.querySelector("form");
  const button = container.querySelector("button");
  const status = container.querySelector(".feedback-widget-status");
  const localFileMessage = "To send feedback, run python -m backend.app from the project folder, then open http://127.0.0.1:8000/.";

  if (window.location.protocol === "file:") {
    status.textContent = localFileMessage;
  }

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    if (window.location.protocol === "file:") {
      status.textContent = localFileMessage;
      status.classList.add("error");
      return;
    }
    status.textContent = "Submitting feedback…";
    status.classList.remove("error");
    button.disabled = true;

    const formData = new FormData(form);
    const payload = {
      name: formData.get("name"),
      email: formData.get("email"),
      category: formData.get("category"),
      message: formData.get("message"),
      source_url: window.location.href
    };

    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Unable to submit feedback");
      }
      form.reset();
      status.textContent = `Thanks! Feedback captured under topic "${data.feedback.topic}".`;
    } catch (error) {
      status.textContent = error.message;
      status.classList.add("error");
    } finally {
      button.disabled = false;
    }
  });
}());
