const commands = {
  codex: 'codex mcp add markdownSourceGraph --url http://127.0.0.1:8811/mcp\ncodex mcp list',
  claude: 'claude mcp add --transport http markdown-source-graph --scope project http://127.0.0.1:8811/mcp\nclaude mcp list',
  gemini: 'gemini mcp add --transport http --scope project markdown-source-graph http://127.0.0.1:8811/mcp\ngemini mcp list'
};

const toast = document.querySelector('.toast');
let toastTimer;

function showToast() {
  clearTimeout(toastTimer);
  toast.classList.add('show');
  toastTimer = setTimeout(() => toast.classList.remove('show'), 1600);
}

document.addEventListener('click', async (event) => {
  const copyButton = event.target.closest('.copy');
  if (copyButton) {
    const text = copyButton.parentElement.querySelector('code').textContent;
    await navigator.clipboard.writeText(text);
    showToast();
  }

  const clientTab = event.target.closest('.client-tab');
  if (clientTab) {
    document.querySelectorAll('.client-tab').forEach((tab) => tab.classList.toggle('active', tab === clientTab));
    document.querySelector('#client-command').textContent = commands[clientTab.dataset.client];
  }

  const previewTab = event.target.closest('.preview-tab');
  if (previewTab) {
    document.querySelectorAll('.preview-tab').forEach((tab) => tab.classList.toggle('active', tab === previewTab));
    const image = document.querySelector('#dashboard-preview');
    image.style.opacity = '0.25';
    image.src = previewTab.dataset.image;
    image.onload = () => { image.style.opacity = '1'; };
  }
});

const menuButton = document.querySelector('.menu-button');
const navigation = document.querySelector('#site-nav');
menuButton.addEventListener('click', () => {
  const open = navigation.classList.toggle('open');
  menuButton.setAttribute('aria-expanded', String(open));
});
navigation.addEventListener('click', () => {
  navigation.classList.remove('open');
  menuButton.setAttribute('aria-expanded', 'false');
});
