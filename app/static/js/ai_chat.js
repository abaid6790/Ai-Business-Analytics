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

        streamAnswer(question);
    });

    function streamAnswer(question) {
        fetch(CHAT_ASK_STREAM_URL, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken,
            },
            body: JSON.stringify({ question, conversation_id: CONVERSATION_ID }),
        })
            .then((res) => {
                if (!res.ok) {
                    // Errors from this endpoint come back as JSON, not a stream.
                    return res.json().then((data) => {
                        throw new Error(data.error || "Something went wrong. Please try again.");
                    });
                }

                const headerConvId = res.headers.get("X-Conversation-Id");
                if (headerConvId) CONVERSATION_ID = parseInt(headerConvId, 10);

                const bubble = appendMessage("assistant", "");
                bubble.classList.add("chat-bubble-streaming");

                const reader = res.body.getReader();
                const decoder = new TextDecoder();

                function readChunk() {
                    return reader.read().then(({ done, value }) => {
                        if (done) {
                            bubble.classList.remove("chat-bubble-streaming");
                            setLoading(false);
                            return;
                        }
                        bubble.textContent += decoder.decode(value, { stream: true });
                        messagesEl.scrollTop = messagesEl.scrollHeight;
                        return readChunk();
                    });
                }
                return readChunk();
            })
            .catch((err) => {
                setLoading(false);
                appendMessage("assistant", err.message || "Something went wrong. Please try again.", true);
            });
    }

    function appendMessage(role, text, isError) {
        const wrapper = document.createElement("div");
        wrapper.className = `chat-message chat-message-${role}`;
        const bubble = document.createElement("div");
        bubble.className = "chat-bubble" + (isError ? " chat-bubble-error" : "");
        bubble.textContent = text;
        wrapper.appendChild(bubble);
        messagesEl.appendChild(wrapper);
        messagesEl.scrollTop = messagesEl.scrollHeight;
        return bubble;
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
