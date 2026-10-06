// Save unfinished input on this device. Completed records still pass server validation.
const visitForm = document.querySelector('[data-autosave-url]');
if (visitForm) {
  const note = visitForm.querySelector('[data-autosave-status]');
  let dirty = false, pending = null, timer = null, stopped = false, submitting = false;
  async function saveVisit() {
    if (pending) return pending;
    if (!dirty || stopped) return true;
    dirty = false;
    note.textContent = visitForm.dataset.saving;
    const values = new FormData(visitForm);
    values.set('csrf', visitForm.dataset.autosaveToken);
    values.delete('intent');
    pending = fetch(visitForm.dataset.autosaveUrl, {
      method: 'POST', body: new URLSearchParams(values), credentials: 'same-origin'
    }).then(async response => {
      if (!response.ok) throw new Error('save failed');
      const result = await response.json();
      visitForm.elements.unfinished_id.value = result.draft_id;
      visitForm.elements.unfinished_revision.value = result.revision;
      history.replaceState(null, '', result.resume_url);
      note.textContent = dirty ? visitForm.dataset.saving : visitForm.dataset.saved;
      note.setAttribute('role', 'status');
      return true;
    }).catch(() => {
      dirty = true;
      note.textContent = visitForm.dataset.failed;
      note.setAttribute('role', 'alert');
      return false;
    }).finally(() => { pending = null; });
    return pending;
  }
  async function flushVisit() {
    clearTimeout(timer);
    if (pending && !await pending) return false;
    while (dirty) if (!await saveVisit()) return false;
    return true;
  }
  function changed() {
    if (stopped) return;
    dirty = true;
    note.textContent = visitForm.dataset.saving;
    clearTimeout(timer);
    timer = setTimeout(async () => {
      if (await saveVisit() && dirty) timer = setTimeout(saveVisit, 350);
    }, 350);
  }
  visitForm.addEventListener('input', changed);
  visitForm.addEventListener('change', changed);
  visitForm.addEventListener('click', event => {
    if (event.target.closest('[data-add-row], [data-remove-row]')) changed();
  });
  visitForm.addEventListener('submit', async event => {
    event.preventDefault();
    if (submitting) return;
    submitting = true;
    stopped = true;
    clearTimeout(timer);
    if (pending && !await pending) { submitting = false; stopped = false; return; }
    const intent = document.createElement('input');
    intent.type = 'hidden'; intent.name = 'intent';
    intent.value = event.submitter ? event.submitter.value : 'save';
    intent.dataset.visitIntent = 'yes';
    visitForm.appendChild(intent);
    if (intent.value !== 'language') {
      visitForm.setAttribute('aria-busy', 'true');
      visitForm.querySelector('.submission').hidden = false;
    }
    visitForm.submit();
  }, true);
  document.addEventListener('click', async event => {
    const link = event.target.closest('a[href]');
    if (!link || stopped || (!dirty && !pending) || event.ctrlKey || event.metaKey || event.shiftKey || link.target) return;
    const target = new URL(link.href, location.href);
    if (target.origin !== location.origin || (target.hash && target.pathname === location.pathname)) return;
    event.preventDefault();
    if (await flushVisit()) { stopped = true; location.href = link.href; }
  });
  const dismissOverlay = window.srDismissOverlay;
  window.srDismissOverlay = () => {
    if (dismissOverlay && dismissOverlay()) return true;
    if (dirty || pending) {
      flushVisit().then(saved => { if (saved) { stopped = true; history.back(); } });
      return true;
    }
    return false;
  };
  window.addEventListener('beforeunload', event => {
    if ((dirty || pending) && !stopped) { event.preventDefault(); event.returnValue = ''; }
  });
  document.addEventListener('visibilitychange', () => { if (document.hidden) saveVisit(); });
  window.addEventListener('pageshow', event => {
    if (event.persisted) {
      stopped = false; submitting = false;
      visitForm.querySelectorAll('[data-visit-intent]').forEach(input => input.remove());
    }
  });
}
