/* ── Smooth scroll helper ──────────────────────────── */
function scrollToSection(sectionId) {
  const el = document.getElementById(sectionId);
  if (el) el.scrollIntoView({ behavior: 'smooth' });
}

/* ── Sound toggle ──────────────────────────────────── */
(function () {
  const video      = document.getElementById('hero-video');
  const btn        = document.getElementById('sound-btn');
  const iconMuted  = document.getElementById('icon-muted');
  const iconSound  = document.getElementById('icon-sound');

  if (!video || !btn) return;

  btn.addEventListener('click', function () {
    video.muted = !video.muted;
    if (video.muted) {
      iconMuted.classList.remove('hidden');
      iconSound.classList.add('hidden');
      btn.title = 'Включить звук';
    } else {
      iconMuted.classList.add('hidden');
      iconSound.classList.remove('hidden');
      btn.title = 'Выключить звук';
    }
  });
})();

/* ── Plan selection & order form ───────────────────── */
(function () {
  const planCards      = document.querySelectorAll('.plan-card');
  const formWrap       = document.getElementById('order-form-wrap');
  const form           = document.getElementById('order-form');
  const cancelBtn      = document.getElementById('order-cancel');
  const msgEl          = document.getElementById('order-msg');
  const submitBtn      = form.querySelector('[type="submit"]');

  const fPlanId        = document.getElementById('f-plan-id');
  const fPlanName      = document.getElementById('f-plan-name');
  const fPlanLabel     = document.getElementById('f-plan-label');
  const fNodeIds       = document.getElementById('f-node-ids');

  const addrSection    = document.getElementById('address-section');
  const addrSectionLbl = document.getElementById('addr-section-label');
  const addrSearch     = document.getElementById('addr-search');
  const addrList       = document.getElementById('addr-list');
  const addrSummary    = document.getElementById('addr-summary');

  let nodesCache       = null;
  let currentPriceVal  = 0;
  let isPaid           = false;

  /* ── Load nodes from API (once) ── */
  async function loadNodes() {
    if (nodesCache !== null) return nodesCache;
    try {
      const resp = await fetch('/api/nodes');
      nodesCache = await resp.json();
    } catch {
      nodesCache = [];
    }
    return nodesCache;
  }

  /* ── Render address list (checkboxes for paid, radio for free) ── */
  function renderAddresses(nodes, multiSelect) {
    const inputType = multiSelect ? 'checkbox' : 'radio';
    addrList.innerHTML = nodes.map(function (n) {
      return (
        '<label class="addr-item" data-addr="' + n.address.toLowerCase() + '">' +
          '<input type="' + inputType + '" class="addr-input" name="addr_pick" value="' + n.id + '" />' +
          '<span>' + n.address + '</span>' +
        '</label>'
      );
    }).join('');

    addrList.querySelectorAll('.addr-input').forEach(function (inp) {
      inp.addEventListener('change', updateSummary);
    });
    updateSummary();
  }

  /* ── Update price summary ── */
  function updateSummary() {
    const checked = addrList.querySelectorAll('.addr-input:checked');
    const count   = checked.length;

    fNodeIds.value = Array.from(checked).map(function (inp) { return inp.value; }).join(',');

    if (count === 0) {
      addrSummary.textContent = isPaid ? 'Выберите хотя бы один адрес' : 'Выберите адрес';
      addrSummary.classList.remove('addr-summary--active');
    } else if (!isPaid) {
      const label = checked[0].closest('.addr-item').querySelector('span').textContent;
      addrSummary.textContent = 'Выбран: ' + label;
      addrSummary.classList.add('addr-summary--active');
    } else {
      const total = currentPriceVal * count;
      addrSummary.textContent =
        'Выбрано: ' + count + '\u00a0адр. × ' +
        currentPriceVal.toLocaleString('ru-RU') + '\u00a0₽ = ' +
        total.toLocaleString('ru-RU') + '\u00a0₽/мес';
      addrSummary.classList.add('addr-summary--active');
    }
  }

  /* ── Address search filter ── */
  addrSearch.addEventListener('input', function () {
    const q = this.value.toLowerCase().trim();
    addrList.querySelectorAll('.addr-item').forEach(function (item) {
      const match = !q || item.dataset.addr.includes(q);
      item.classList.toggle('addr-item--hidden', !match);
    });
  });

  /* ── Open form ── */
  async function openForm(card) {
    currentPriceVal = parseInt(card.dataset.planPriceValue, 10) || 0;
    isPaid          = currentPriceVal > 0;

    fPlanId.value   = card.dataset.planId;
    fPlanName.value = card.dataset.planName;
    fPlanLabel.textContent = card.dataset.planName + ' — ' + card.dataset.planPrice;

    form.reset();
    // restore hidden values cleared by reset
    fPlanId.value   = card.dataset.planId;
    fPlanName.value = card.dataset.planName;
    fNodeIds.value  = '';
    addrSearch.value = '';
    hideMsg();

    submitBtn.textContent = isPaid ? 'Перейти к оплате' : 'Отправить заявку';

    addrSectionLbl.innerHTML = isPaid
      ? 'Выберите адрес(а) домов <span class="req">*</span>'
      : 'Выберите адрес дома <span class="req">*</span>';
    addrSection.classList.remove('hidden');
    addrList.innerHTML = '<p class="addr-list__loading">Загрузка адресов…</p>';
    addrSummary.textContent = isPaid ? 'Выберите хотя бы один адрес' : 'Выберите адрес';
    addrSummary.classList.remove('addr-summary--active');
    const nodes = await loadNodes();
    renderAddresses(nodes, isPaid);

    formWrap.classList.remove('hidden');
    formWrap.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  function closeForm() {
    formWrap.classList.add('hidden');
    hideMsg();
  }

  function showMsg(text, type) {
    msgEl.textContent = text;
    msgEl.className = 'order-form__msg order-form__msg--' + type;
  }

  function hideMsg() {
    msgEl.className = 'order-form__msg hidden';
    msgEl.textContent = '';
  }

  /* ── Plan card clicks ── */
  planCards.forEach(function (card) {
    const btn = card.querySelector('.plan-card__btn');
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      openForm(card);
    });
    card.addEventListener('click', function () {
      openForm(card);
    });
  });

  cancelBtn.addEventListener('click', closeForm);

  /* ── Form submit ── */
  form.addEventListener('submit', async function (e) {
    e.preventDefault();

    const name  = document.getElementById('f-name').value.trim();
    const phone = document.getElementById('f-phone').value.trim();

    if (!name || !phone) {
      showMsg('Пожалуйста, заполните обязательные поля (имя и телефон).', 'error');
      return;
    }

    if (isPaid && !fNodeIds.value) {
      showMsg('Выберите хотя бы один адрес для подключения.', 'error');
      addrSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
      return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = 'Отправка…';
    hideMsg();

    try {
      const data = new FormData(form);
      const resp = await fetch('/order', { method: 'POST', body: data });
      const json = await resp.json();

      if (resp.ok && json.redirect_url) {
        window.location.href = json.redirect_url;
      } else if (resp.ok && json.ok) {
        showMsg(json.message || 'Заявка принята!', 'success');
        form.reset();
        fPlanId.value = '';
        fPlanName.value = '';
      } else {
        showMsg(json.message || 'Ошибка. Попробуйте ещё раз.', 'error');
      }
    } catch {
      showMsg('Нет соединения. Проверьте интернет и попробуйте ещё раз.', 'error');
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = isPaid ? 'Перейти к оплате' : 'Отправить заявку';
    }
  });
})();
