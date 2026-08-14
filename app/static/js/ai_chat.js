document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("chatForm");
    if (!form) return; // not on the chat page

    const input = document.getElementById("chatInput");
    const messagesEl = document.getElementById("chatMessages");
    const sendBtn = document.getElementById("chatSendBtn");
    const csrfToken = document.querySelector('meta[name="csrf-token"]').content;

    form.addEventListener("submit", function (e) {
        e.preventDefault();
        const question = input.value.trim();
        if (!question) return;

        removeEmptyState();
        appendMessage("user", question);
        input.value = "";
        setLoading(true);
        const thinkingEl = appendThinking();

        fetch(CHAT_ASK_URL, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken,
            },
            body: JSON.stringify({ question, conversation_id: CONVERSATION_ID }),
        })
            .then((res) => res.json().then((data) => ({ ok: res.ok, data })))
            .then(({ ok, data }) => {
                thinkingEl.remove();
                setLoading(false);
                if (!ok) {
                    appendMessage("assistant", data.error || "Something went wrong. Please try again.", true);
                    return;
                }
                CONVERSATION_ID = data.conversation_id;
                appendMessage("assistant", data.answer);
            })
            .catch(() => {
                thinkingEl.remove();
                setLoading(false);
                appendMessage("assistant", "Something went wrong. Please try again.", true);
            });
    });

    function appendMessage(role, text, isError) {
        const wrapper = document.createElement("div");
        wrapper.className = `chat-message chat-message-${role}`;
        const bubble = document.createElement("div");
        bubble.className = "chat-bubble" + (isError ? " chat-bubble-error" : "");
        bubble.textContent = text;
        wrapper.appendChild(bubble);
        messagesEl.appendChild(wrapper);
        messagesEl.scrollTop = messagesEl.scrollHeight;
        return wrapper;
    }

    function appendThinking() {
        const wrapper = document.createElement("div");
        wrapper.className = "chat-message chat-message-assistant";
        wrapper.innerHTML = '<div class="chat-bubble chat-bubble-thinking"><span class="dot"></span><span class="dot"></span><span class="dot"></span></div>';
        messagesEl.appendChild(wrapper);
        messagesEl.scrollTop = messagesEl.scrollHeight;
        return wrapper;
    }

    function removeEmptyState() {
        const el = document.getElementById("chatEmptyState");
        if (el) el.remove();
    }

    function setLoading(isLoading) {
        sendBtn.disabled = isLoading;
        input.disabled = isLoading;
    }
});
