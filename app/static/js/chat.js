import { ApiClient } from './api.js';
import { ChartManager } from './charts.js';

const TIME_FMT = new Intl.DateTimeFormat(undefined, {
  hour: 'numeric',
  minute: '2-digit',
});

function formatTime(d = new Date()) {
  return TIME_FMT.format(d);
}

function escapeHtml(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// Lightweight markdown-ish renderer: bolds **...**, italics *...*
// and keeps line breaks. Intentionally not a full markdown lib to keep
// the bundle small — the analyst responses use this minimal set.
function renderAnswerText(text) {
  if (!text) return '';
  // Escape first, then apply safe inline transformations.
  const escaped = escapeHtml(text);
  return escaped
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>')
    .replace(/(^|\n)- (.+)/g, '$1• $2');
}

export const ChatDrawer = {
  currentDatasetId: null,
  currentDomain: null,
  history: [],
  isOpen: false,
  userInitials: 'You',

  init() {
    const triggerBtn = document.getElementById('btn-open-chat');
    const closeBtn = document.getElementById('btn-close-chat');
    const clearBtn = document.getElementById('btn-clear-chat');
    const sendBtn = document.getElementById('btn-chat-send');
    const inputEl = document.getElementById('chat-input');

    if (triggerBtn) {
      triggerBtn.addEventListener('click', () => this.toggle(true));
    }
    if (closeBtn) {
      closeBtn.addEventListener('click', () => this.toggle(false));
    }
    if (clearBtn) {
      clearBtn.addEventListener('click', () => this.clearConversation());
    }

    if (sendBtn && inputEl) {
      sendBtn.addEventListener('click', () => this.handleSend());
      inputEl.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          this.handleSend();
        }
      });
      this.autoresizeInput(inputEl);
    }
  },

  autoresizeInput(inputEl) {
    inputEl.addEventListener('input', () => {
      inputEl.style.height = 'auto';
      inputEl.style.height = Math.min(inputEl.scrollHeight, 120) + 'px';
      this.updateSendButtonState();
    });
  },

  updateSendButtonState() {
    const inputEl = document.getElementById('chat-input');
    const sendBtn = document.getElementById('btn-chat-send');
    if (!inputEl || !sendBtn) return;
    const hasText = inputEl.value.trim().length > 0;
    sendBtn.disabled = !hasText || !this.currentDatasetId;
  },

  async setDataset(datasetId) {
    this.currentDatasetId = datasetId;
    this.history = [];
    this.currentDomain = null;
    const messagesEl = document.getElementById('chat-messages');
    if (messagesEl) messagesEl.innerHTML = '';

    // Detect domain for the welcome card and status text.
    try {
      const au = await ApiClient.getAIUnderstanding(datasetId);
      if (au && au.domain) {
        this.currentDomain = au.domain;
        const statusEl = document.getElementById('chat-status-text');
        if (statusEl) {
          statusEl.textContent = `Analysing ${au.domain.replace(/_/g, ' ')} data`;
        }
      }
    } catch (e) {
      // ignore — welcome card has a generic fallback
    }

    this.renderWelcomeCard();
    this.updateSendButtonState();

    // Load suggested questions
    try {
      const data = await ApiClient.getSuggestedQuestions(datasetId);
      this.renderSuggestedQuestions(data.questions || []);
    } catch (e) {
      // ignore
    }
  },

  renderWelcomeCard() {
    const container = document.getElementById('chat-messages');
    if (!container) return;
    container.innerHTML = '';
    const domain = this.currentDomain || 'your';
    const domainLabel = domain.replace(/_/g, ' ');
    const welcome = document.createElement('div');
    welcome.className = 'chat-welcome animate-fade-in';
    welcome.innerHTML = `
      <div class="chat-welcome-emoji">👋</div>
      <h4>Hello! I'm your AI Analyst</h4>
      <p>I can answer natural-language questions about your <strong>${escapeHtml(domainLabel)}</strong> dataset — try one of the suggestions below or ask anything in your own words.</p>
      <div class="chat-welcome-meta">
        <span class="chat-welcome-pill"><span class="chat-welcome-pill-dot"></span> Read-only SQL</span>
        <span class="chat-welcome-pill"><span class="chat-welcome-pill-dot"></span> Cited insights</span>
        <span class="chat-welcome-pill"><span class="chat-welcome-pill-dot"></span> Auto charts</span>
      </div>
    `;
    container.appendChild(welcome);
  },

  toggle(open) {
    this.isOpen = open;
    const drawer = document.getElementById('chat-drawer');
    if (drawer) {
      if (open) {
        drawer.classList.add('active');
        // Autofocus the input when opened.
        setTimeout(() => document.getElementById('chat-input')?.focus(), 320);
      } else {
        drawer.classList.remove('active');
      }
    }
  },

  clearConversation() {
    this.history = [];
    this.renderWelcomeCard();
    this.updateSendButtonState();
  },

  renderSuggestedQuestions(questions) {
    const container = document.getElementById('chat-suggestions');
    if (!container) return;
    container.innerHTML = '';

    if (!questions || questions.length === 0) {
      container.parentElement.style.display = 'none';
      return;
    }
    container.parentElement.style.display = 'block';

    questions.forEach(q => {
      const chip = document.createElement('button');
      chip.className = 'chat-chip';
      chip.type = 'button';
      chip.innerText = q;
      chip.onclick = () => {
        const input = document.getElementById('chat-input');
        if (input) {
          input.value = q;
          this.updateSendButtonState();
          input.focus();
        }
      };
      container.appendChild(chip);
    });
  },

  async handleSend() {
    const inputEl = document.getElementById('chat-input');
    const query = inputEl.value.trim();
    if (!query || !this.currentDatasetId) return;

    inputEl.value = '';
    inputEl.style.height = 'auto';
    this.updateSendButtonState();

    // Remove welcome card if present
    const welcome = document.querySelector('.chat-welcome');
    if (welcome) welcome.remove();

    this.appendUserMessage(query);
    const typingId = this.showTypingIndicator();
    this.setStatus('thinking');

    try {
      const res = await ApiClient.askChat(this.currentDatasetId, query, this.history);
      this.removeTypingIndicator(typingId);
      this.appendAssistantMessage(res);
      this.setStatus('online');

      this.history.push({ role: 'user', content: query, timestamp: new Date().toISOString() });
      this.history.push({ role: 'assistant', content: res.answer_text, timestamp: new Date().toISOString() });

      if (res.suggested_followups) {
        this.renderSuggestedQuestions(res.suggested_followups);
      }
    } catch (err) {
      this.removeTypingIndicator(typingId);
      this.appendErrorMessage(err.message);
      this.setStatus('online');
    } finally {
      this.updateSendButtonState();
    }
  },

  setStatus(state) {
    const dot = document.querySelector('.chat-status-dot');
    const text = document.getElementById('chat-status-text');
    if (!dot || !text) return;
    if (state === 'thinking') {
      dot.style.background = 'var(--accent-amber)';
      dot.style.boxShadow = '0 0 8px rgba(245, 158, 11, 0.6)';
      text.textContent = 'Analysing…';
    } else {
      const domain = this.currentDomain || 'data';
      dot.style.background = 'var(--accent-emerald)';
      dot.style.boxShadow = '0 0 8px var(--accent-emerald-glow)';
      text.textContent = `Ready · ${domain.replace(/_/g, ' ')}`;
    }
  },

  appendUserMessage(text) {
    const container = document.getElementById('chat-messages');
    const msg = document.createElement('div');
    msg.className = 'chat-msg chat-msg-user';
    const initials = this.userInitials || 'You';
    msg.innerHTML = `
      <div class="chat-msg-avatar" title="You">${escapeHtml(initials[0] || 'Y')}</div>
      <div class="chat-msg-body">
        <div class="chat-msg-meta">
          <span class="chat-msg-meta-author">You</span>
          <span>·</span>
          <span>${formatTime()}</span>
        </div>
        <div class="chat-bubble chat-bubble-user">${renderAnswerText(text)}</div>
      </div>
    `;
    container.appendChild(msg);
    container.scrollTop = container.scrollHeight;
  },

  appendAssistantMessage(res) {
    const container = document.getElementById('chat-messages');
    const msg = document.createElement('div');
    msg.className = 'chat-msg chat-msg-assistant';
    const msgId = `msg_${Date.now()}`;

    let insightsHtml = '';
    if (res.insights && res.insights.length > 0) {
      insightsHtml =
        '<ul class="chat-insights">' +
        res.insights.map(i => `<li>${renderAnswerText(i)}</li>`).join('') +
        '</ul>';
    }

    let chartHtml = '';
    const chartId = `chat_chart_${Date.now()}`;
    if (res.chart_type && ['bar_chart', 'line_chart', 'pie_chart'].includes(res.chart_type) && res.data?.length > 1) {
      chartHtml = `<div class="chat-chart-wrap"><canvas id="${chartId}"></canvas></div>`;
    }

    const sqlBlockId = `sql_${Date.now()}`;
    const sqlHtml = res.sql_query
      ? `<div class="chat-sql-block" id="${sqlBlockId}">
           <div class="chat-sql-toggle" data-target="${sqlBlockId}">
             <span>
               <span class="chat-sql-toggle-icon">▶</span>
               View executed SQL
             </span>
             <button class="chat-action-btn chat-sql-copy" data-sql="${escapeHtml(res.sql_query)}" type="button" title="Copy SQL">
               <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                 <rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
               </svg>
               <span>Copy</span>
             </button>
           </div>
           <pre class="chat-sql-code"><code>${escapeHtml(res.sql_query)}</code></pre>
         </div>`
      : '';

    const latencyHtml = res.execution_time_ms
      ? `<span>·</span><span>${(res.execution_time_ms / 1000).toFixed(2)}s</span>`
      : '';

    msg.innerHTML = `
      <div class="chat-msg-avatar" title="AI Analyst">AI</div>
      <div class="chat-msg-body" data-msg-id="${msgId}">
        <div class="chat-msg-meta">
          <span class="chat-msg-meta-author">AI Analyst</span>
          <span>·</span>
          <span>${formatTime()}</span>
          ${latencyHtml}
        </div>
        <div class="chat-bubble chat-bubble-assistant">
          <div class="chat-answer">${renderAnswerText(res.answer_text)}</div>
          ${insightsHtml}
          ${chartHtml}
          ${sqlHtml}
        </div>
        <div class="chat-actions">
          <button class="chat-action-btn chat-copy-answer" data-msg-id="${msgId}" type="button" title="Copy answer">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
            </svg>
            <span>Copy</span>
          </button>
          <button class="chat-action-btn chat-thumbs-up" type="button" title="Helpful">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M7 10v11"/><path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H7V10l4.34-7.07A1 1 0 0 1 13 3.34L15 5.88Z"/>
            </svg>
          </button>
          <button class="chat-action-btn chat-thumbs-down dislike" type="button" title="Not helpful">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M17 14V3"/><path d="M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H17v12l-4.34 7.07A1 1 0 0 1 11 20.66L9 18.12Z"/>
            </svg>
          </button>
        </div>
      </div>
    `;
    container.appendChild(msg);
    container.scrollTop = container.scrollHeight;

    // Wire up the per-message interactions.
    msg.querySelector('.chat-sql-toggle')?.addEventListener('click', (e) => {
      // Ignore clicks on the inner copy button
      if (e.target.closest('.chat-sql-copy')) return;
      msg.querySelector('.chat-sql-block')?.classList.toggle('open');
    });
    msg.querySelector('.chat-sql-copy')?.addEventListener('click', (e) => {
      e.stopPropagation();
      const sql = e.currentTarget.dataset.sql;
      this.copyToClipboard(sql, e.currentTarget);
    });
    msg.querySelector('.chat-copy-answer')?.addEventListener('click', (e) => {
      const bubble = msg.querySelector('.chat-answer');
      this.copyToClipboard(bubble?.innerText || '', e.currentTarget);
    });
    msg.querySelector('.chat-thumbs-up')?.addEventListener('click', (e) => {
      e.currentTarget.classList.toggle('active');
      msg.querySelector('.chat-thumbs-down')?.classList.remove('active');
    });
    msg.querySelector('.chat-thumbs-down')?.addEventListener('click', (e) => {
      e.currentTarget.classList.toggle('active');
      msg.querySelector('.chat-thumbs-up')?.classList.remove('active');
    });

    // Render chart if present
    if (chartHtml) {
      setTimeout(() => {
        const rows = res.data || [];
        const firstRow = rows[0] || {};
        const keys = Object.keys(firstRow);
        const dim = keys[0];
        const metric = keys[1] || keys[0];

        if (res.chart_type === 'bar_chart') {
          ChartManager.renderBarChart(chartId, rows.map(r => ({ dimension_value: r[dim], [metric]: r[metric] })), dim, metric);
        } else if (res.chart_type === 'pie_chart') {
          ChartManager.renderDonutChart(chartId, rows.map(r => ({ dimension_value: r[dim], [metric]: r[metric] })), dim, metric);
        }
      }, 50);
    }
  },

  async copyToClipboard(text, btn) {
    try {
      await navigator.clipboard.writeText(text);
      if (btn) {
        const label = btn.querySelector('span');
        const original = label ? label.textContent : '';
        if (label) label.textContent = 'Copied!';
        btn.classList.add('active');
        setTimeout(() => {
          if (label) label.textContent = original || 'Copy';
          btn.classList.remove('active');
        }, 1500);
      }
    } catch (e) {
      // Fallback: select-and-copy for older browsers
      const ta = document.createElement('textarea');
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
    }
  },

  showTypingIndicator() {
    const container = document.getElementById('chat-messages');
    const typing = document.createElement('div');
    const id = `typing_${Date.now()}`;
    typing.id = id;
    typing.className = 'chat-msg chat-msg-assistant';
    typing.innerHTML = `
      <div class="chat-msg-avatar" title="AI Analyst">AI</div>
      <div class="chat-msg-body">
        <div class="chat-msg-meta">
          <span class="chat-msg-meta-author">AI Analyst</span>
          <span>·</span>
          <span>thinking…</span>
        </div>
        <div class="chat-bubble chat-bubble-assistant">
          <div class="chat-bubble-typing">
            <span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span>
          </div>
        </div>
      </div>
    `;
    container.appendChild(typing);
    container.scrollTop = container.scrollHeight;
    return id;
  },

  removeTypingIndicator(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
  },

  appendErrorMessage(errText) {
    const container = document.getElementById('chat-messages');
    const msg = document.createElement('div');
    msg.className = 'chat-msg chat-msg-assistant';
    msg.innerHTML = `
      <div class="chat-msg-avatar" title="AI Analyst">AI</div>
      <div class="chat-msg-body">
        <div class="chat-msg-meta">
          <span class="chat-msg-meta-author">AI Analyst</span>
          <span>·</span>
          <span>${formatTime()}</span>
        </div>
        <div class="chat-bubble chat-bubble-assistant chat-bubble-error">${escapeHtml(errText)}</div>
      </div>
    `;
    container.appendChild(msg);
    container.scrollTop = container.scrollHeight;
  }
};
