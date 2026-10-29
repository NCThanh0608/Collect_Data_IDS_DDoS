(() => {
  const dashboard = document.querySelector(".dashboard");
  if (!dashboard) return;

  const elements = {
    state: document.getElementById("syslog-state"),
    received: document.getElementById("received-total"),
    rate: document.getElementById("receive-rate"),
    disallowed: document.getElementById("disallowed-total"),
    queueDiscarded: document.getElementById("queue-discarded-total"),
    kernelUdpErrors: document.getElementById("kernel-udp-errors"),
    writeFailed: document.getElementById("write-failed-total"),
    messages: document.getElementById("recent-messages"),
    probe: document.getElementById("probe-button"),
    result: document.getElementById("probe-result"),
  };
  let pendingProbe = null;

  function renderMessages(messages) {
    const rows = messages.map((message) => {
      const row = document.createElement("li");
      const detail = document.createElement("span");
      const body = document.createElement("span");
      detail.className = "log-detail";
      body.className = "log-message";
      detail.textContent = `${message.timestamp_utc} · ${message.source_ip} · ${message.app || message.hostname}`;
      body.textContent = message.message;
      row.append(detail, body);
      return row;
    });
    if (!rows.length) {
      const empty = document.createElement("li");
      empty.className = "log-empty";
      empty.textContent = "Chưa có bản tin.";
      rows.push(empty);
    }
    elements.messages.replaceChildren(...rows);
  }

  async function refresh() {
    try {
      const response = await fetch(dashboard.dataset.statusUrl, { cache: "no-store" });
      if (!response.ok) throw new Error("Chưa có số liệu Syslog");
      const data = await response.json();
      const logStalled = data.status === "log_stalled";
      elements.state.textContent = logStalled ? "Lỗi ghi log" : "Đang nhận";
      elements.state.className = logStalled ? "state state-offline" : "state state-online";
      elements.received.textContent = Number(data.received_total).toLocaleString("vi-VN");
      elements.rate.textContent = data.rate_per_second == null
        ? "—"
        : Number(data.rate_per_second).toLocaleString("vi-VN");
      elements.disallowed.textContent = Number(data.disallowed_total).toLocaleString("vi-VN");
      elements.queueDiscarded.textContent = Number(data.queue_discarded_total).toLocaleString("vi-VN");
      elements.kernelUdpErrors.textContent = data.kernel_udp_errors == null
        ? "—"
        : Number(data.kernel_udp_errors).toLocaleString("vi-VN");
      elements.writeFailed.textContent = data.write_failed_total == null
        ? "—"
        : Number(data.write_failed_total).toLocaleString("vi-VN");
      renderMessages(data.messages || []);

      if (pendingProbe) {
        const found = (data.messages || []).some((item) => item.message.includes(pendingProbe.id));
        if (found) {
          elements.result.textContent = `Đã nhận bản tin thử ${pendingProbe.id.slice(0, 8)}.`;
          pendingProbe = null;
        } else if (Date.now() - pendingProbe.sentAt > 12000) {
          elements.result.textContent = "Không xác nhận được trong 20 log mới nhất; khi flood, bản tin có thể đã bị đẩy khỏi danh sách.";
          pendingProbe = null;
        }
      }
    } catch (_) {
      elements.state.textContent = "Chưa có số liệu";
      elements.state.className = "state state-offline";
      if (pendingProbe && Date.now() - pendingProbe.sentAt > 12000) {
        elements.result.textContent = "Đã gửi nhưng không xác nhận được bản tin thử trong 12 giây.";
        pendingProbe = null;
      }
    }
  }

  elements.probe.addEventListener("click", async () => {
    elements.probe.disabled = true;
    try {
      const response = await fetch(dashboard.dataset.probeUrl, { method: "POST" });
      if (!response.ok) throw new Error("Không gửi được bản tin thử");
      const data = await response.json();
      pendingProbe = { id: data.probe_id, sentAt: Date.now() };
      elements.result.textContent = "Đã gửi UDP, đang chờ thấy bản tin trong log…";
      await refresh();
    } catch (_) {
      elements.result.textContent = "Không gửi được bản tin Syslog từ web server.";
    } finally {
      elements.probe.disabled = false;
    }
  });

  refresh();
  setInterval(refresh, 3000);
})();
