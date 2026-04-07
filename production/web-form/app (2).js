/**
 * Customer Success FTE — Web Support Form JavaScript
 * 
 * Handles:
 * - Form validation (real-time)
 * - Form submission to API
 * - Success state display
 * - Ticket status lookup
 * - Mobile navigation toggle
 * - Navbar scroll effect
 */

// =============================================================================
// CONFIGURATION
// =============================================================================

const API_BASE_URL = 'http://localhost:8000'; // Change to production URL

// =============================================================================
// NAVIGATION
// =============================================================================

document.addEventListener('DOMContentLoaded', () => {
    initNavbar();
    initSupportForm();
    initTicketLookup();
});

function initNavbar() {
    const navbar = document.getElementById('navbar');
    const toggle = document.getElementById('navToggle');
    const links = document.getElementById('navLinks');

    // Scroll effect
    if (navbar) {
        window.addEventListener('scroll', () => {
            navbar.classList.toggle('scrolled', window.scrollY > 20);
        });
    }

    // Mobile toggle
    if (toggle && links) {
        toggle.addEventListener('click', () => {
            links.classList.toggle('active');
        });

        // Close on link click
        links.querySelectorAll('.nav-link').forEach(link => {
            link.addEventListener('click', () => {
                links.classList.remove('active');
            });
        });
    }
}

// =============================================================================
// SUPPORT FORM
// =============================================================================

function initSupportForm() {
    const form = document.getElementById('supportForm');
    if (!form) return;

    const fields = {
        name: {
            el: document.getElementById('name'),
            error: document.getElementById('nameError'),
            validate: (v) => {
                if (!v.trim()) return 'Name is required';
                if (v.trim().length < 2) return 'Name must be at least 2 characters';
                if (!/^[\p{L}\s'-]+$/u.test(v.trim())) return 'Name contains invalid characters';
                return '';
            }
        },
        email: {
            el: document.getElementById('email'),
            error: document.getElementById('emailError'),
            validate: (v) => {
                if (!v.trim()) return 'Email is required';
                if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v)) return 'Please enter a valid email';
                return '';
            }
        },
        subject: {
            el: document.getElementById('subject'),
            error: document.getElementById('subjectError'),
            validate: (v) => {
                if (!v.trim()) return 'Subject is required';
                if (v.trim().length < 5) return 'Subject must be at least 5 characters';
                return '';
            }
        },
        description: {
            el: document.getElementById('description'),
            error: document.getElementById('descriptionError'),
            validate: (v) => {
                if (!v.trim()) return 'Description is required';
                if (v.trim().length < 10) return 'Description must be at least 10 characters';
                if (v.length > 5000) return 'Description cannot exceed 5000 characters';
                return '';
            }
        },
        phone: {
            el: document.getElementById('phone'),
            error: document.getElementById('phoneError'),
            validate: (v) => {
                if (!v) return '';
                if (!/^[\d\s\-\+\(\)]{10,20}$/.test(v)) return 'Please enter a valid phone number';
                return '';
            }
        }
    };

    // Character counter
    const descEl = document.getElementById('description');
    const charCount = document.getElementById('charCount');
    if (descEl && charCount) {
        descEl.addEventListener('input', () => {
            charCount.textContent = descEl.value.length;
            if (descEl.value.length > 4500) {
                charCount.style.color = '#EF4444';
            } else if (descEl.value.length > 3500) {
                charCount.style.color = '#F59E0B';
            } else {
                charCount.style.color = '';
            }
        });
    }

    // Real-time validation on blur
    Object.entries(fields).forEach(([name, field]) => {
        if (field.el) {
            field.el.addEventListener('blur', () => {
                validateField(name, field);
            });
            field.el.addEventListener('input', () => {
                if (field.error && field.error.textContent) {
                    validateField(name, field);
                }
            });
        }
    });

    function validateField(name, field) {
        const error = field.validate(field.el.value);
        if (field.error) {
            field.error.textContent = error;
        }
        if (field.el) {
            field.el.classList.toggle('error', !!error);
        }
        return !error;
    }

    // Form submission
    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        // Validate all fields
        let isValid = true;
        Object.entries(fields).forEach(([name, field]) => {
            if (!validateField(name, field)) {
                isValid = false;
            }
        });

        // Check honeypot
        const honeypot = document.getElementById('honeypot');
        if (honeypot && honeypot.value) {
            return; // Spam detected
        }

        if (!isValid) {
            const banner = document.getElementById('formErrorBanner');
            if (banner) banner.style.display = 'flex';
            // Focus first error field
            const firstError = form.querySelector('.error');
            if (firstError) firstError.focus();
            return;
        }

        // Hide error banner
        const banner = document.getElementById('formErrorBanner');
        if (banner) banner.style.display = 'none';

        // Show loading state
        const submitBtn = document.getElementById('submitBtn');
        const btnText = submitBtn.querySelector('.btn-text');
        const btnLoading = submitBtn.querySelector('.btn-loading');

        submitBtn.disabled = true;
        btnText.style.display = 'none';
        btnLoading.style.display = 'flex';

        // Build request data
        const data = {
            name: document.getElementById('name').value.trim(),
            email: document.getElementById('email').value.trim(),
            subject: document.getElementById('subject').value.trim(),
            description: document.getElementById('description').value.trim(),
            category: document.getElementById('category').value,
            priority: document.getElementById('priority').value,
        };

        const phone = document.getElementById('phone').value.trim();
        if (phone) data.phone = phone;

        const company = document.getElementById('company').value.trim();
        if (company) data.company = company;

        const orderId = document.getElementById('orderId').value.trim();
        if (orderId) data.order_id = orderId;

        // Submit to API
        try {
            const response = await fetch(`${API_BASE_URL}/support/submit`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.detail || result.error || 'Submission failed');
            }

            // Show success
            showSuccess(result);

        } catch (error) {
            console.error('Form submission error:', error);
            const banner = document.getElementById('formErrorBanner');
            if (banner) {
                banner.style.display = 'flex';
                banner.querySelector('span').textContent = error.message || 'Unable to submit. Please try again.';
            }
        } finally {
            submitBtn.disabled = false;
            btnText.style.display = '';
            btnLoading.style.display = 'none';
        }
    });
}

function showSuccess(data) {
    const form = document.getElementById('supportForm');
    const successMsg = document.getElementById('successMessage');
    const ticketDisplay = document.getElementById('ticketIdDisplay');
    const etaText = document.getElementById('etaText');

    if (form) form.style.display = 'none';
    if (successMsg) successMsg.style.display = 'block';
    if (ticketDisplay) ticketDisplay.textContent = data.ticket_id;
    if (etaText && data.estimated_response_time) {
        etaText.textContent = `Estimated response time: ${data.estimated_response_time}`;
    }

    // Scroll to success message
    if (successMsg) {
        successMsg.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
}

function resetForm() {
    const form = document.getElementById('supportForm');
    const successMsg = document.getElementById('successMessage');

    if (form) {
        form.reset();
        form.style.display = '';
    }
    if (successMsg) {
        successMsg.style.display = 'none';
    }

    // Reset error states
    document.querySelectorAll('.error').forEach(el => el.classList.remove('error'));
    document.querySelectorAll('.error-msg').forEach(el => el.textContent = '');

    // Reset char counter
    const charCount = document.getElementById('charCount');
    if (charCount) charCount.textContent = '0';

    // Scroll to form
    if (form) {
        form.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
}

// Make resetForm available globally
window.resetForm = resetForm;

// =============================================================================
// TICKET STATUS LOOKUP
// =============================================================================

function initTicketLookup() {
    const form = document.getElementById('ticketLookupForm');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const ticketId = document.getElementById('lookupTicketId').value.trim();
        const email = document.getElementById('lookupEmail').value.trim();
        const errorEl = document.getElementById('ticketError');
        const resultEl = document.getElementById('ticketResult');

        if (!ticketId) {
            if (errorEl) {
                errorEl.textContent = 'Please enter a ticket ID';
                errorEl.classList.add('visible');
            }
            return;
        }

        // Hide previous results/errors
        if (errorEl) errorEl.classList.remove('visible');
        if (resultEl) resultEl.classList.remove('visible');

        // Build URL
        const params = new URLSearchParams();
        if (email) params.append('email', email);

        try {
            const response = await fetch(`${API_BASE_URL}/support/status/${encodeURIComponent(ticketId)}?${params}`);

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Ticket not found');
            }

            const data = await response.json();
            displayTicketResult(data, resultEl);

        } catch (error) {
            if (errorEl) {
                errorEl.textContent = error.message;
                errorEl.classList.add('visible');
            }
        }
    });
}

function displayTicketResult(data, container) {
    if (!container) return;

    const statusClass = `ticket-status-badge--${data.status}`;

    container.innerHTML = `
        <div class="ticket-result-header">
            <span class="ticket-status-badge ${statusClass}">
                <span class="status-dot"></span>
                ${capitalizeFirst(data.status)}
            </span>
            <span style="font-size:14px;color:#6B7280;">${data.ticket_id}</span>
        </div>
        <div class="ticket-details">
            <div class="ticket-detail">
                <span class="ticket-detail-label">Subject</span>
                <span class="ticket-detail-value">${escapeHtml(data.subject)}</span>
            </div>
            <div class="ticket-detail">
                <span class="ticket-detail-label">Category</span>
                <span class="ticket-detail-value">${capitalizeFirst(data.category)}</span>
            </div>
            <div class="ticket-detail">
                <span class="ticket-detail-label">Priority</span>
                <span class="ticket-detail-value">${capitalizeFirst(data.priority)}</span>
            </div>
            <div class="ticket-detail">
                <span class="ticket-detail-label">Created</span>
                <span class="ticket-detail-value">${formatDate(data.created_at)}</span>
            </div>
        </div>
        ${data.public_message ? `
            <div style="margin-top:16px;padding:12px 16px;background:#F9FAFB;border-radius:8px;font-size:14px;color:#374151;">
                <strong style="display:block;margin-bottom:4px;font-size:12px;color:#6B7280;text-transform:uppercase;">Response:</strong>
                ${escapeHtml(data.public_message)}
            </div>
        ` : ''}
    `;

    container.classList.add('visible');
}

// =============================================================================
// UTILITIES
// =============================================================================

function capitalizeFirst(str) {
    if (!str) return '';
    return str.charAt(0).toUpperCase() + str.slice(1).replace('_', ' ');
}

function formatDate(dateStr) {
    if (!dateStr) return '—';
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    });
}

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
