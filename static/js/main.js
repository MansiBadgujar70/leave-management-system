/**
 * main.js — Leave Management System
 * Client-side interactivity: sidebar toggle, auto-dismiss alerts,
 * form enhancements, and small UI utilities.
 */

document.addEventListener('DOMContentLoaded', function () {

  // ─── SIDEBAR TOGGLE (mobile) ────────────────────────────────────────────────
  const toggleBtn  = document.getElementById('sidebarToggle');
  const sidebar    = document.getElementById('sidebar');
  const contentWrapper = document.getElementById('content-wrapper');

  if (toggleBtn && sidebar) {
    toggleBtn.addEventListener('click', function () {
      sidebar.classList.toggle('show');
    });

    // Close sidebar if user clicks outside it on mobile
    document.addEventListener('click', function (e) {
      if (window.innerWidth <= 768) {
        if (!sidebar.contains(e.target) && !toggleBtn.contains(e.target)) {
          sidebar.classList.remove('show');
        }
      }
    });
  }

  // ─── AUTO-DISMISS FLASH ALERTS after 5 seconds ─────────────────────────────
  const alerts = document.querySelectorAll('.alert.alert-dismissible');
  alerts.forEach(function (alert) {
    setTimeout(function () {
      const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
      bsAlert.close();
    }, 5000);
  });

  // ─── FORM SUBMISSION PROTECTION (prevent double-submit) ────────────────────
  // Adds a spinner to submit buttons on form submit
  const forms = document.querySelectorAll('form');
  forms.forEach(function (form) {
    form.addEventListener('submit', function () {
      const submitBtn = form.querySelector('button[type="submit"]');
      if (submitBtn && !submitBtn.disabled) {
        submitBtn.disabled = true;
        const originalHTML = submitBtn.innerHTML;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Processing…';

        // Re-enable after 10 seconds as a fallback (in case of validation error)
        setTimeout(function () {
          submitBtn.disabled = false;
          submitBtn.innerHTML = originalHTML;
        }, 10000);
      }
    });
  });

  // ─── TOOLTIP INITIALIZATION ─────────────────────────────────────────────────
  const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
  tooltipTriggerList.forEach(function (el) {
    new bootstrap.Tooltip(el);
  });

  // ─── ACTIVE NAV LINK HIGHLIGHTING ──────────────────────────────────────────
  // (Handled via Jinja in base.html, but this adds a fallback)
  const currentPath = window.location.pathname;
  document.querySelectorAll('.sidebar-link').forEach(function (link) {
    if (link.getAttribute('href') === currentPath) {
      link.classList.add('active');
    }
  });

  // ─── DATE FIELD MIN VALIDATION ─────────────────────────────────────────────
  // Automatically set the minimum date for start_date to today
  const startDateField = document.getElementById('startDate');
  if (startDateField) {
    const today = new Date().toISOString().split('T')[0];
    startDateField.setAttribute('min', today);

    // When start date changes, update end date minimum
    startDateField.addEventListener('change', function () {
      const endDateField = document.getElementById('endDate');
      if (endDateField) {
        endDateField.setAttribute('min', this.value);
        if (endDateField.value && endDateField.value < this.value) {
          endDateField.value = this.value;
        }
      }
    });
  }

  // ─── SEARCH INPUT: auto-submit on clear ────────────────────────────────────
  const searchInput = document.querySelector('input[name="search"]');
  if (searchInput) {
    searchInput.addEventListener('keyup', function (e) {
      // If user clears the field and presses backspace, auto-submit
      if (e.key === 'Escape') {
        this.value = '';
        this.closest('form').submit();
      }
    });
  }

  // ─── CARD HOVER MICRO-ANIMATION ────────────────────────────────────────────
  document.querySelectorAll('.stat-card').forEach(function (card, i) {
    card.style.animationDelay = (i * 0.08) + 's';
  });

  document.querySelectorAll('.card-custom').forEach(function (card, i) {
    card.style.animationDelay = (i * 0.06) + 's';
  });

});
