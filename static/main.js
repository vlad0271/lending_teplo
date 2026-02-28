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
  const planCards   = document.querySelectorAll('.plan-card');
  const formWrap    = document.getElementById('order-form-wrap');
  const form        = document.getElementById('order-form');
  const cancelBtn   = document.getElementById('order-cancel');
  const msgEl       = document.getElementById('order-msg');

  const fPlanId     = document.getElementById('f-plan-id');
  const fPlanName   = document.getElementById('f-plan-name');
  const fPlanLabel  = document.getElementById('f-plan-label');

  function openForm(card) {
    fPlanId.value    = card.dataset.planId;
    fPlanName.value  = card.dataset.planName;
    fPlanLabel.textContent = card.dataset.planName + ' — ' + card.dataset.planPrice;

    // Reset state
    form.reset();
    fPlanId.value   = card.dataset.planId;
    fPlanName.value = card.dataset.planName;
    hideMsg();

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

  // Click on plan card (but not on inner button — handled separately)
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

  form.addEventListener('submit', async function (e) {
    e.preventDefault();

    const name  = document.getElementById('f-name').value.trim();
    const phone = document.getElementById('f-phone').value.trim();

    if (!name || !phone) {
      showMsg('Пожалуйста, заполните обязательные поля (имя и телефон).', 'error');
      return;
    }

    const submitBtn = form.querySelector('[type="submit"]');
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
      submitBtn.textContent = 'Отправить заявку';
    }
  });
})();
