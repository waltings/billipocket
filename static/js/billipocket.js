// Billipocket Frontend Library
(function() {
  'use strict';

  // Global utilities
  window.BilliPocket = {
    // Flash message helper
    showMessage: function(message, type = 'info') {
      const alertClass = type === 'error' ? 'danger' : type;
      const iconClass = {
        'success': 'bi-check-circle',
        'danger': 'bi-x-circle',
        'warning': 'bi-exclamation-triangle',
        'info': 'bi-info-circle'
      }[alertClass] || 'bi-info-circle';

      const alertHtml = `
        <div class="alert alert-${alertClass} alert-dismissible fade show" role="alert">
          <i class="${iconClass} me-2"></i>
          ${message}
          <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
      `;

      const container = document.querySelector('.flash-messages') || 
                       document.querySelector('.container-fluid');
      if (container) {
        container.insertAdjacentHTML('afterbegin', alertHtml);
      }
    },

    // CSRF token helper
    getCsrfToken: function() {
      const token = document.querySelector('meta[name=csrf-token]');
      return token ? token.getAttribute('content') : '';
    },

    // Form validation helper
    validateForm: function(form) {
      const requiredFields = form.querySelectorAll('[required]');
      let isValid = true;

      requiredFields.forEach(field => {
        if (!field.value.trim()) {
          field.classList.add('is-invalid');
          isValid = false;
        } else {
          field.classList.remove('is-invalid');
        }
      });

      return isValid;
    },

    // AJAX helper
    ajax: function(url, options = {}) {
      const defaults = {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': this.getCsrfToken()
        }
      };

      return fetch(url, { ...defaults, ...options })
        .then(response => {
          if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
          }
          return response.json();
        });
    },

    // Number formatting
    formatCurrency: function(amount, currency = '€') {
      return parseFloat(amount).toFixed(2) + currency;
    },

    // Date formatting
    formatDate: function(dateString) {
      const date = new Date(dateString);
      return date.toLocaleDateString('et-EE');
    }
  };

  // Global form enhancement
  document.addEventListener('DOMContentLoaded', function() {
    // Auto-dismiss alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
    alerts.forEach(alert => {
      setTimeout(() => {
        const bsAlert = new bootstrap.Alert(alert);
        bsAlert.close();
      }, 5000);
    });

    // Global form validation
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
      form.addEventListener('submit', function(e) {
        if (!BilliPocket.validateForm(this)) {
          e.preventDefault();
          BilliPocket.showMessage('Palun täida kõik kohustuslikud väljad', 'error');
        }
      });
    });

    // Loading states for buttons (skip buttons with bp-processing class or in modals)
    const buttons = document.querySelectorAll('button[type="submit"], a.btn');
    buttons.forEach(button => {
      button.addEventListener('click', function(e) {
        // Skip if button has custom handling or is in a modal
        if (this.classList.contains('bp-processing') || 
            this.closest('.modal') || 
            this.id === 'submitClientBtn') {
          return;
        }
        
        if (this.type === 'submit') {
          // Show loading state but don't disable button immediately
          const originalContent = this.innerHTML;
          this.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Laen...';
          
          // Disable AFTER a short delay so form can submit
          setTimeout(() => {
            this.disabled = true;
          }, 100);
          
          // Restore after delay as failsafe
          setTimeout(() => {
            this.innerHTML = originalContent;
            this.disabled = false;
          }, 5000);
        } else if (this.href && !this.href.includes('#')) {
          // Handle link buttons
          const originalContent = this.innerHTML;
          this.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Laen...';
          this.disabled = true;
          
          setTimeout(() => {
            this.innerHTML = originalContent;
            this.disabled = false;
          }, 5000);
        }
      });
    });

    // Enhanced tooltips
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));

    // Auto-focus first form field
    const firstInput = document.querySelector('form input:not([type="hidden"]):not([readonly]):not([disabled])');
    if (firstInput && !firstInput.value) {
      firstInput.focus();
    }
  });

  // Chart initialization (if Chart.js is available)
  const ctx = document.getElementById('revenueChart');
  if (ctx && typeof Chart !== 'undefined') {
    new Chart(ctx, {
      type: 'line',
      data: {
        labels: ['J','F','M','A','M','J','J','A','S','O','N','D'],
        datasets: [{
          label: 'Käive',
          tension: 0.35,
          fill: true,
          borderColor: 'rgb(17, 214, 222)',
          backgroundColor: 'rgba(17, 214, 222, 0.1)',
          data: [9.3,10.1,8.7,11.2,12.8,13.4,12.1,12.9,14.2,15.0,14.6,16.3]
        }]
      },
      options: {
        responsive: true,
        plugins: {
          legend: {
            display: false
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            ticks: {
              callback: function(value) {
                return value + 'k€';
              }
            }
          }
        }
      }
    });
  }

})();