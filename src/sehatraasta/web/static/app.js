// Presentation only: focus, honest submitting feedback, and the browser print dialog.
if (document.body.classList.contains('interface-app')) {
  // Older Android WebViews lack :focus-visible. Keep keyboard focus without tap outlines.
  document.addEventListener('keydown', event => {
    if (event.key === 'Tab') document.body.classList.add('keyboard-navigation');
  });
  const clearKeyboardFocus = () => document.body.classList.remove('keyboard-navigation');
  document.addEventListener('touchstart', clearKeyboardFocus, {passive: true});
  document.addEventListener('mousedown', clearKeyboardFocus);
  const menu = document.querySelector('.app-menu');
  document.addEventListener('click', event => {
    if (menu && menu.open && !menu.contains(event.target)) menu.open = false;
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && menu && menu.open) {
      menu.open = false;
      menu.querySelector('summary').focus();
    }
  });
  window.srDismissOverlay = () => {
    if (menu && menu.open) { menu.open = false; return true; }
    return false;
  };
  let fullHeight = window.innerHeight;
  const keyboardLayout = () => {
    const height = window.visualViewport ? window.visualViewport.height : window.innerHeight;
    fullHeight = Math.max(fullHeight, height);
    const editing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName);
    document.body.classList.toggle('keyboard-open', editing && height < fullHeight * .72);
  };
  window.addEventListener('resize', keyboardLayout);
  if (window.visualViewport) window.visualViewport.addEventListener('resize', keyboardLayout);
  document.addEventListener('focusout', () => setTimeout(keyboardLayout, 100));
}
const scanner = document.querySelector('[data-qr-scanner]');
if (scanner && window.SRAndroid && window.SRAndroid.scanQR) {
  scanner.querySelector('[data-scan-camera]').addEventListener('click', () => window.SRAndroid.scanQR(false, scanner.dataset.prompt));
  scanner.querySelector('[data-scan-image]').addEventListener('click', () => window.SRAndroid.scanQR(true, scanner.dataset.prompt));
  window.srQRResult = (payload, status) => {
    const field = document.querySelector('[name=payload]');
    if (typeof payload === 'string' && payload.length <= 200 && field) {
      field.value = payload;
      field.dispatchEvent(new Event('input', { bubbles: true }));
      field.focus();
    }
    scanner.querySelector('[data-scan-status]').textContent = scanner.dataset[status] || scanner.dataset.invalid;
  };
}
const summary = document.querySelector('#errors');
if (summary) summary.focus();
document.querySelectorAll('[data-print]').forEach(button => {
  button.addEventListener('click', () => {
    if (window.SRAndroid) window.SRAndroid.printDocument();
    else window.print();
  });
});
// Android streams exports to the system save dialog without a public storage permission.
if (window.SRAndroid) {
  document.querySelectorAll('form[data-download]').forEach(form => {
    form.addEventListener('submit', event => {
      if (event.submitter && event.submitter.value === 'language') return;
      event.preventDefault();
      const data = new FormData(form);
      if (event.submitter && event.submitter.name) data.set(event.submitter.name, event.submitter.value);
      window.SRAndroid.saveDownload(form.action, new URLSearchParams(data).toString());
    });
  });
}
document.querySelectorAll('form:not([data-download])').forEach(form => {
  form.addEventListener('submit', event => {
    if (event.defaultPrevented) return;
    if (event.submitter && event.submitter.value === 'language') return;
    if (form.dataset.submitting === 'yes') { event.preventDefault(); return; }
    form.dataset.submitting = 'yes';
    const status = form.querySelector('.submission');
    if (status) status.hidden = false;
    form.setAttribute('aria-busy', 'true');
    if (event.submitter) event.submitter.setAttribute('aria-disabled', 'true');
  });
});
window.addEventListener('pageshow', () => {
  document.querySelectorAll('form').forEach(form => {
    delete form.dataset.submitting;
    form.removeAttribute('aria-busy');
    form.querySelectorAll('[aria-disabled]').forEach(button => button.removeAttribute('aria-disabled'));
    const status = form.querySelector('.submission');
    if (status) status.hidden = true;
  });
});

// Plain select/text inputs remain usable when JavaScript is unavailable.
function enhanceFields(root) {
  root.querySelectorAll('[data-preset]').forEach(group => {
    const select = group.querySelector('select');
    const custom = group.querySelector('[data-custom]');
    const update = () => {
      custom.hidden = select.value !== '__custom__';
      custom.querySelector('input').required = select.required && !custom.hidden;
    };
    select.addEventListener('change', () => {
      update();
      if (!custom.hidden) custom.querySelector('input').focus();
    });
    update();
  });
  root.querySelectorAll('[data-year-picker]').forEach(picker => {
    const input = document.getElementById(picker.dataset.target);
    const currentYear = new Date().getFullYear();
    let firstYear = Math.floor((Number(input.value) || currentYear - 24) / 12) * 12;
    const grid = picker.querySelector('[data-year-grid]');
    const draw = () => {
      while (grid.firstChild) grid.removeChild(grid.firstChild);
      picker.querySelector('[data-year-range]').textContent = firstYear + '–' + (firstYear + 11);
      for (let year = firstYear; year < firstYear + 12; year++) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'secondary';
        button.textContent = String(year);
        button.setAttribute('aria-pressed', String(Number(input.value) === year));
        button.addEventListener('click', () => {
          input.value = String(year);
          input.dispatchEvent(new Event('input', {bubbles:true}));
          picker.open = false;
          input.focus();
        });
        grid.append(button);
      }
      picker.querySelector('[data-years-back]').disabled = firstYear <= 12;
    };
    picker.querySelector('[data-years-back]').addEventListener('click', () => { firstYear -= 12; draw(); });
    picker.querySelector('[data-years-next]').addEventListener('click', () => { firstYear += 12; draw(); });
    picker.addEventListener('toggle', () => {
      if (picker.open) { firstYear = Math.max(1, Math.floor((Number(input.value) || currentYear - 24) / 12) * 12); draw(); }
    });
    picker.hidden = false;
    draw();
  });
}
enhanceFields(document);

// Progressive enhancement only. Validation and saving stay on the server.
const intake = document.querySelector('[data-intake]');
if (intake) {
  document.querySelectorAll('.intake-nav a, #errors a').forEach(link => {
    link.addEventListener('click', () => {
      const target = document.getElementById(link.hash.slice(1));
      const details = target && (target.closest('[data-record-section]') || target.querySelector('[data-record-section]'));
      if (details) details.open = true;
    });
  });
  const mode = intake.querySelector('#mode');
  const showMode = () => intake.querySelectorAll('[data-patient-mode]').forEach(group => {
    group.hidden = group.dataset.patientMode !== mode.value;
  });
  mode.addEventListener('change', showMode);
  showMode();
  const refreshOrders = () => {
    const orders = [...intake.querySelectorAll('[data-repeat="orders"] [data-rows] > [data-row]')];
    intake.querySelectorAll('[data-repeat="results"] [data-rows] select[name$=".order_key"]').forEach(select => {
      const selected = select.value;
      const emptyLabel = select.options[0].text;
      while (select.firstChild) select.removeChild(select.firstChild);
      select.append(new Option(emptyLabel, ''));
      orders.forEach((row, index) => {
        const name = row.querySelector('input[name$=".name"]').value;
        select.add(new Option(intake.dataset.orderLabel + ' ' + (index + 1) + (name ? ' · ' + name : ''), row.dataset.row));
      });
      if (selected && !orders.some(row => row.dataset.row === selected)) select.add(new Option(intake.dataset.removedLabel, selected));
      select.value = selected;
    });
  };
  intake.querySelectorAll('[data-repeat]').forEach(section => {
    const rows = section.querySelector('[data-rows]');
    const add = section.querySelector('[data-add-row]');
    // A result can retain a removed order's key after server validation.
    // Do not reuse that key and silently link the result to a different new order.
    const linkedKeys = section.dataset.repeat === 'orders'
      ? [...intake.querySelectorAll('select[name$=".order_key"]')]
          .map(select => Number(select.value)).filter(Number.isSafeInteger)
      : [];
    let nextKey = Math.max(-1, ...[...rows.children].map(row => Number(row.dataset.row)), ...linkedKeys) + 1;
    const renumber = () => [...rows.children].forEach((row, index) => {
      row.querySelectorAll('[data-row-number]').forEach(label => { label.textContent = index + 1; });
      row.querySelector('[data-remove-row]').hidden = false;
    });
    add.hidden = false;
    renumber();
    add.addEventListener('click', () => {
      const fragment = section.querySelector('[data-prototype]').content.cloneNode(true);
      const key = String(nextKey++);
      fragment.querySelectorAll('*').forEach(element => {
        [...element.attributes].forEach(attribute => {
          if (attribute.value.includes('__ROW__')) element.setAttribute(attribute.name, attribute.value.split('__ROW__').join(key));
        });
      });
      rows.append(fragment);
      enhanceFields(rows.lastElementChild);
      renumber();
      refreshOrders();
      rows.lastElementChild.querySelector('input:not([type=hidden]),select,textarea').focus();
    });
    rows.addEventListener('click', event => {
      const button = event.target.closest('[data-remove-row]');
      if (!button) return;
      const row = button.closest('[data-row]');
      const next = row.nextElementSibling || row.previousElementSibling;
      const removedIDs = new Set([...row.querySelectorAll('[id]')].map(element => element.id));
      document.querySelectorAll('#errors a').forEach(link => {
        if (removedIDs.has(link.hash.slice(1))) link.closest('li').remove();
      });
      if (summary && !summary.querySelector('li')) summary.hidden = true;
      row.remove();
      renumber();
      refreshOrders();
      intake.querySelector('[data-row-status]').textContent = intake.dataset.removedMessage;
      if (next) next.querySelector('input:not([type=hidden]),select,textarea').focus();
      else add.focus();
    });
  });
  intake.querySelector('[data-repeat="orders"]').addEventListener('input', refreshOrders);
  refreshOrders();
}

// Keep current report choices when changing language before submitting the form.
const reportSelection = document.querySelector('[data-report-selection]');
if (reportSelection) {
  document.querySelectorAll('.language-nav a').forEach(link => {
    link.addEventListener('click', event => {
      event.preventDefault();
      const choices = new URLSearchParams(new FormData(reportSelection));
      choices.delete('preview');
      choices.set('lang', link.getAttribute('lang'));
      window.location.href = window.location.pathname + '?' + choices.toString();
    });
  });
}
