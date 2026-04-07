/**
 * SupportForm.jsx
 * 
 * Complete Web Support Form component for Customer Success FTE.
 * 
 * This is a standalone, embeddable React component that handles
 * customer support form submissions with full validation,
 * loading states, success feedback, and ticket ID display.
 * 
 * Features:
 * - Real-time form validation
 * - Loading and submission states
 * - Success state with ticket ID
 * - Error handling with retry
 * - Responsive design
 * - Accessible (ARIA compliant)
 * - Spam prevention (honeypot field)
 * 
 * Usage:
 *   import SupportForm from './SupportForm';
 *   
 *   // In your component tree:
 *   <SupportForm apiEndpoint="https://api.yoursite.com/support" />
 */

import React, { useState, useCallback } from 'react';

// =============================================================================
// STYLES (Inline for standalone component - can be extracted to CSS module)
// =============================================================================

const styles = {
  container: {
    maxWidth: '600px',
    margin: '0 auto',
    padding: '24px',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
  },
  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: '20px',
  },
  formGroup: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
  },
  label: {
    fontSize: '14px',
    fontWeight: '600',
    color: '#374151',
    display: 'flex',
    alignItems: 'center',
    gap: '4px',
  },
  required: {
    color: '#DC2626',
  },
  input: {
    padding: '10px 12px',
    fontSize: '16px',
    border: '1px solid #D1D5DB',
    borderRadius: '6px',
    outline: 'none',
    transition: 'border-color 0.15s ease-in-out, box-shadow 0.15s ease-in-out',
  },
  inputFocus: {
    borderColor: '#3B82F6',
    boxShadow: '0 0 0 3px rgba(59, 130, 246, 0.1)',
  },
  inputError: {
    borderColor: '#DC2626',
  },
  textarea: {
    padding: '10px 12px',
    fontSize: '16px',
    border: '1px solid #D1D5DB',
    borderRadius: '6px',
    outline: 'none',
    minHeight: '120px',
    resize: 'vertical',
    fontFamily: 'inherit',
  },
  select: {
    padding: '10px 12px',
    fontSize: '16px',
    border: '1px solid #D1D5DB',
    borderRadius: '6px',
    outline: 'none',
    backgroundColor: 'white',
    cursor: 'pointer',
  },
  row: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '16px',
  },
  helpText: {
    fontSize: '12px',
    color: '#6B7280',
  },
  errorText: {
    fontSize: '12px',
    color: '#DC2626',
  },
  submitButton: {
    padding: '12px 24px',
    fontSize: '16px',
    fontWeight: '600',
    color: 'white',
    backgroundColor: '#3B82F6',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
    transition: 'background-color 0.15s ease-in-out',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '8px',
  },
  submitButtonDisabled: {
    backgroundColor: '#9CA3AF',
    cursor: 'not-allowed',
  },
  submitButtonHover: {
    backgroundColor: '#2563EB',
  },
  successContainer: {
    textAlign: 'center',
    padding: '32px 24px',
    backgroundColor: '#F0FDF4',
    border: '1px solid #86EFAC',
    borderRadius: '8px',
  },
  successIcon: {
    width: '48px',
    height: '48px',
    color: '#22C55E',
    margin: '0 auto 16px',
  },
  successTitle: {
    fontSize: '20px',
    fontWeight: '700',
    color: '#166534',
    marginBottom: '8px',
  },
  successMessage: {
    fontSize: '14px',
    color: '#15803D',
    marginBottom: '16px',
  },
  ticketIdContainer: {
    backgroundColor: 'white',
    padding: '12px 16px',
    borderRadius: '6px',
    border: '1px solid #86EFAC',
    display: 'inline-block',
    marginBottom: '16px',
  },
  ticketIdLabel: {
    fontSize: '12px',
    color: '#6B7280',
    marginBottom: '4px',
  },
  ticketId: {
    fontSize: '18px',
    fontWeight: '700',
    color: '#166534',
    fontFamily: 'monospace',
  },
  newSubmissionButton: {
    padding: '10px 20px',
    fontSize: '14px',
    fontWeight: '500',
    color: '#166534',
    backgroundColor: 'transparent',
    border: '1px solid #86EFAC',
    borderRadius: '6px',
    cursor: 'pointer',
    transition: 'background-color 0.15s ease-in-out',
  },
  errorContainer: {
    padding: '16px',
    backgroundColor: '#FEF2F2',
    border: '1px solid #FECACA',
    borderRadius: '6px',
    marginBottom: '16px',
  },
  errorTitle: {
    fontSize: '14px',
    fontWeight: '600',
    color: '#DC2626',
    marginBottom: '8px',
  },
  errorMessage: {
    fontSize: '13px',
    color: '#B91C1C',
  },
  retryButton: {
    marginTop: '12px',
    padding: '8px 16px',
    fontSize: '14px',
    fontWeight: '500',
    color: '#DC2626',
    backgroundColor: 'white',
    border: '1px solid #FECACA',
    borderRadius: '4px',
    cursor: 'pointer',
  },
  spinner: {
    width: '20px',
    height: '20px',
    border: '2px solid #ffffff',
    borderTopColor: 'transparent',
    borderRadius: '50%',
    animation: 'spin 0.8s linear infinite',
  },
  characterCount: {
    textAlign: 'right',
    fontSize: '12px',
    color: '#6B7280',
  },
  characterCountWarning: {
    color: '#F59E0B',
  },
  characterCountError: {
    color: '#DC2626',
  },
  // Honeypot field - hidden from users
  honeypot: {
    position: 'absolute',
    left: '-9999px',
    opacity: 0,
  },
};

// =============================================================================
// ICONS (SVG Components)
// =============================================================================

const CheckCircleIcon = ({ style }) => (
  <svg
    style={style}
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
    strokeWidth={2}
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
    />
  </svg>
);

const ExclamationCircleIcon = ({ style }) => (
  <svg
    style={style}
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
    strokeWidth={2}
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
    />
  </svg>
);

const SpinnerIcon = ({ style }) => (
  <svg style={style} fill="none" viewBox="0 0 24 24">
    <circle
      cx="12"
      cy="12"
      r="10"
      stroke="currentColor"
      strokeWidth="3"
      strokeOpacity="0.25"
    />
    <path
      fill="currentColor"
      d="M12 2a10 10 0 0 1 10 10h-2a8 8 0 0 0-8-8V2z"
      strokeOpacity="0.75"
    />
  </svg>
);

const SendIcon = ({ style }) => (
  <svg
    style={style}
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
    strokeWidth={2}
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
    />
  </svg>
);

// =============================================================================
// CONSTANTS
// =============================================================================

const CATEGORIES = [
  { value: 'technical', label: 'Technical Issue' },
  { value: 'billing', label: 'Billing & Payments' },
  { value: 'account', label: 'Account Access' },
  { value: 'feature_request', label: 'Feature Request' },
  { value: 'bug_report', label: 'Bug Report' },
  { value: 'general', label: 'General Inquiry' },
  { value: 'other', label: 'Other' },
];

const PRIORITIES = [
  { value: 'low', label: 'Low - General question' },
  { value: 'medium', label: 'Medium - Need help soon' },
  { value: 'high', label: 'High - Business impact' },
  { value: 'critical', label: 'Critical - System down' },
];

const DESCRIPTION_MIN_LENGTH = 10;
const DESCRIPTION_MAX_LENGTH = 5000;

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

function validateEmail(email) {
  const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return re.test(email);
}

function validatePhone(phone) {
  if (!phone) return true; // Optional field
  const re = /^[\d\s\-\+\(\)]{10,20}$/;
  return re.test(phone);
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

function SupportForm({
  apiEndpoint = '/api/support',
  onSuccess,
  onError,
  embeddable = false,
}) {
  // Form state
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    phone: '',
    company: '',
    subject: '',
    category: 'general',
    priority: 'medium',
    description: '',
    orderId: '',
    honeypot: '', // Spam prevention
  });

  // UI state
  const [errors, setErrors] = useState({});
  const [touched, setTouched] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [submissionError, setSubmissionError] = useState(null);
  const [ticketId, setTicketId] = useState(null);
  const [estimatedTime, setEstimatedTime] = useState('');

  // Focus tracking for better UX
  const [focusedField, setFocusedField] = useState(null);

  // Character count for description
  const descriptionLength = formData.description.length;
  const descriptionPercent = (descriptionLength / DESCRIPTION_MAX_LENGTH) * 100;

  /**
   * Handle field change with validation
   */
  const handleChange = useCallback((e) => {
    const { name, value } = e.target;
    
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));

    // Clear error when user starts typing
    if (errors[name]) {
      setErrors((prev) => ({
        ...prev,
        [name]: null,
      }));
    }
  }, [errors]);

  /**
   * Handle field blur for validation
   */
  const handleBlur = useCallback((e) => {
    const { name } = e.target;
    setTouched((prev) => ({
      ...prev,
      [name]: true,
    }));
    setFocusedField(null);
    validateField(name, formData[name]);
  }, [formData]);

  /**
   * Validate individual field
   */
  const validateField = (name, value) => {
    let error = null;

    switch (name) {
      case 'name':
        if (!value || !value.trim()) {
          error = 'Name is required';
        } else if (value.trim().length < 2) {
          error = 'Name must be at least 2 characters';
        } else if (!/^[\p{L}\s'-]+$/u.test(value.trim())) {
          error = 'Name contains invalid characters';
        }
        break;

      case 'email':
        if (!value || !value.trim()) {
          error = 'Email is required';
        } else if (!validateEmail(value)) {
          error = 'Please enter a valid email address';
        }
        break;

      case 'phone':
        if (value && !validatePhone(value)) {
          error = 'Please enter a valid phone number';
        }
        break;

      case 'subject':
        if (!value || !value.trim()) {
          error = 'Subject is required';
        } else if (value.trim().length < 5) {
          error = 'Subject must be at least 5 characters';
        }
        break;

      case 'description':
        if (!value || !value.trim()) {
          error = 'Description is required';
        } else if (value.trim().length < DESCRIPTION_MIN_LENGTH) {
          error = `Description must be at least ${DESCRIPTION_MIN_LENGTH} characters`;
        } else if (value.length > DESCRIPTION_MAX_LENGTH) {
          error = `Description cannot exceed ${DESCRIPTION_MAX_LENGTH} characters`;
        }
        break;

      default:
        break;
    }

    setErrors((prev) => ({
      ...prev,
      [name]: error,
    }));

    return !error;
  };

  /**
   * Validate entire form
   */
  const validateForm = () => {
    const fields = ['name', 'email', 'subject', 'description'];
    let isValid = true;

    fields.forEach((field) => {
      if (!validateField(field, formData[field])) {
        isValid = false;
      }
    });

    // Check honeypot (spam detection)
    if (formData.honeypot) {
      console.warn('Spam detected - honeypot field filled');
      isValid = false;
    }

    return isValid;
  };

  /**
   * Handle form submission
   */
  const handleSubmit = async (e) => {
    e.preventDefault();
    
    // Mark all fields as touched
    const allTouched = {};
    Object.keys(formData).forEach((key) => {
      allTouched[key] = true;
    });
    setTouched(allTouched);

    // Validate form
    if (!validateForm()) {
      // Scroll to first error
      const firstErrorField = Object.keys(errors).find((key) => errors[key]);
      if (firstErrorField) {
        document.getElementById(firstErrorField)?.focus();
      }
      return;
    }

    // Submit
    setIsSubmitting(true);
    setSubmissionError(null);

    try {
      const response = await fetch(apiEndpoint + '/submit', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: formData.name.trim(),
          email: formData.email.trim(),
          phone: formData.phone?.trim() || null,
          company: formData.company?.trim() || null,
          subject: formData.subject.trim(),
          category: formData.category,
          priority: formData.priority,
          description: formData.description.trim(),
          order_id: formData.orderId?.trim() || null,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || data.error || 'Submission failed');
      }

      // Success
      setTicketId(data.ticket_id);
      setEstimatedTime(data.estimated_response_time);
      setIsSubmitted(true);

      if (onSuccess) {
        onSuccess(data);
      }
    } catch (error) {
      console.error('Form submission error:', error);
      setSubmissionError({
        title: 'Submission Failed',
        message: error.message || 'Unable to submit your request. Please try again.',
      });

      if (onError) {
        onError(error);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  /**
   * Reset form for new submission
   */
  const handleNewSubmission = () => {
    setFormData({
      name: '',
      email: '',
      phone: '',
      company: '',
      subject: '',
      category: 'general',
      priority: 'medium',
      description: '',
      orderId: '',
      honeypot: '',
    });
    setErrors({});
    setTouched({});
    setIsSubmitted(false);
    setSubmissionError(null);
    setTicketId(null);
    setEstimatedTime('');
  };

  /**
   * Get input style based on state
   */
  const getInputStyle = (fieldName, baseStyle) => {
    let style = { ...baseStyle };

    if (focusedField === fieldName && !errors[fieldName]) {
      style = { ...style, ...styles.inputFocus };
    }

    if (touched[fieldName] && errors[fieldName]) {
      style = { ...style, ...styles.inputError };
    }

    return style;
  };

  // =============================================================================
  // SUCCESS STATE
  // =============================================================================

  if (isSubmitted) {
    return (
      <div style={styles.container} role="region" aria-label="Support form success">
        <div style={styles.successContainer}>
          <CheckCircleIcon style={styles.successIcon} />
          
          <h2 style={styles.successTitle}>
            Request Submitted Successfully!
          </h2>
          
          <p style={styles.successMessage}>
            Thank you for contacting us. We've sent a confirmation email with
            your ticket details. Our team will respond within{' '}
            <strong>{estimatedTime}</strong>.
          </p>

          <div style={styles.ticketIdContainer}>
            <div style={styles.ticketIdLabel}>Your Ticket ID</div>
            <div style={styles.ticketId} data-testid="ticket-id">
              {ticketId}
            </div>
          </div>

          <div>
            <p style={{ fontSize: '13px', color: '#6B7280', marginBottom: '12px' }}>
              Need to check your ticket status? Use the ticket ID above or reply
              to the confirmation email.
            </p>
          </div>

          <button
            type="button"
            style={styles.newSubmissionButton}
            onClick={handleNewSubmission}
            onMouseOver={(e) => (e.target.style.backgroundColor = '#DCFCE7')}
            onMouseOut={(e) => (e.target.style.backgroundColor = 'transparent')}
          >
            Submit Another Request
          </button>
        </div>
      </div>
    );
  }

  // =============================================================================
  // FORM STATE
  // =============================================================================

  return (
    <div style={styles.container} role="region" aria-label="Support form">
      {/* Error Banner */}
      {submissionError && (
        <div style={styles.errorContainer} role="alert">
          <div style={styles.errorTitle}>
            <ExclamationCircleIcon
              style={{ width: '20px', height: '20px', display: 'inline', marginRight: '8px', verticalAlign: 'text-bottom' }}
            />
            {submissionError.title}
          </div>
          <div style={styles.errorMessage}>{submissionError.message}</div>
          <button
            type="button"
            style={styles.retryButton}
            onClick={() => setSubmissionError(null)}
          >
            Try Again
          </button>
        </div>
      )}

      <form style={styles.form} onSubmit={handleSubmit} noValidate>
        {/* Name and Email Row */}
        <div style={styles.row}>
          {/* Name */}
          <div style={styles.formGroup}>
            <label htmlFor="name" style={styles.label}>
              Full Name
              <span style={styles.required} aria-hidden="true">*</span>
            </label>
            <input
              type="text"
              id="name"
              name="name"
              value={formData.name}
              onChange={handleChange}
              onBlur={handleBlur}
              onFocus={() => setFocusedField('name')}
              style={getInputStyle('name', styles.input)}
              placeholder="John Doe"
              required
              aria-required="true"
              aria-invalid={!!errors.name}
              aria-describedby={errors.name ? 'name-error' : undefined}
              disabled={isSubmitting}
            />
            {touched.name && errors.name && (
              <span id="name-error" style={styles.errorText} role="alert">
                {errors.name}
              </span>
            )}
          </div>

          {/* Email */}
          <div style={styles.formGroup}>
            <label htmlFor="email" style={styles.label}>
              Email Address
              <span style={styles.required} aria-hidden="true">*</span>
            </label>
            <input
              type="email"
              id="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              onBlur={handleBlur}
              onFocus={() => setFocusedField('email')}
              style={getInputStyle('email', styles.input)}
              placeholder="john@example.com"
              required
              aria-required="true"
              aria-invalid={!!errors.email}
              aria-describedby={errors.email ? 'email-error' : undefined}
              disabled={isSubmitting}
            />
            {touched.email && errors.email && (
              <span id="email-error" style={styles.errorText} role="alert">
                {errors.email}
              </span>
            )}
          </div>
        </div>

        {/* Phone and Company Row */}
        <div style={styles.row}>
          {/* Phone */}
          <div style={styles.formGroup}>
            <label htmlFor="phone" style={styles.label}>
              Phone Number
              <span style={{ color: '#6B7280', fontWeight: 'normal' }}>(optional)</span>
            </label>
            <input
              type="tel"
              id="phone"
              name="phone"
              value={formData.phone}
              onChange={handleChange}
              onBlur={handleBlur}
              onFocus={() => setFocusedField('phone')}
              style={getInputStyle('phone', styles.input)}
              placeholder="+1 (555) 123-4567"
              aria-invalid={!!errors.phone}
              aria-describedby={errors.phone ? 'phone-error' : undefined}
              disabled={isSubmitting}
            />
            {touched.phone && errors.phone && (
              <span id="phone-error" style={styles.errorText} role="alert">
                {errors.phone}
              </span>
            )}
          </div>

          {/* Company */}
          <div style={styles.formGroup}>
            <label htmlFor="company" style={styles.label}>
              Company
              <span style={{ color: '#6B7280', fontWeight: 'normal' }}>(optional)</span>
            </label>
            <input
              type="text"
              id="company"
              name="company"
              value={formData.company}
              onChange={handleChange}
              onBlur={handleBlur}
              onFocus={() => setFocusedField('company')}
              style={getInputStyle('company', styles.input)}
              placeholder="Your company name"
              disabled={isSubmitting}
            />
          </div>
        </div>

        {/* Subject */}
        <div style={styles.formGroup}>
          <label htmlFor="subject" style={styles.label}>
            Subject
            <span style={styles.required} aria-hidden="true">*</span>
          </label>
          <input
            type="text"
            id="subject"
            name="subject"
            value={formData.subject}
            onChange={handleChange}
            onBlur={handleBlur}
            onFocus={() => setFocusedField('subject')}
            style={getInputStyle('subject', styles.input)}
            placeholder="Brief summary of your issue"
            required
            aria-required="true"
            aria-invalid={!!errors.subject}
            aria-describedby={errors.subject ? 'subject-error' : undefined}
            disabled={isSubmitting}
          />
          {touched.subject && errors.subject && (
            <span id="subject-error" style={styles.errorText} role="alert">
              {errors.subject}
            </span>
          )}
        </div>

        {/* Category and Priority Row */}
        <div style={styles.row}>
          {/* Category */}
          <div style={styles.formGroup}>
            <label htmlFor="category" style={styles.label}>
              Category
            </label>
            <select
              id="category"
              name="category"
              value={formData.category}
              onChange={handleChange}
              onBlur={handleBlur}
              onFocus={() => setFocusedField('category')}
              style={styles.select}
              disabled={isSubmitting}
            >
              {CATEGORIES.map((cat) => (
                <option key={cat.value} value={cat.value}>
                  {cat.label}
                </option>
              ))}
            </select>
          </div>

          {/* Priority */}
          <div style={styles.formGroup}>
            <label htmlFor="priority" style={styles.label}>
              Priority
            </label>
            <select
              id="priority"
              name="priority"
              value={formData.priority}
              onChange={handleChange}
              onBlur={handleBlur}
              onFocus={() => setFocusedField('priority')}
              style={styles.select}
              disabled={isSubmitting}
            >
              {PRIORITIES.map((pri) => (
                <option key={pri.value} value={pri.value}>
                  {pri.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Description */}
        <div style={styles.formGroup}>
          <label htmlFor="description" style={styles.label}>
            Description
            <span style={styles.required} aria-hidden="true">*</span>
          </label>
          <textarea
            id="description"
            name="description"
            value={formData.description}
            onChange={handleChange}
            onBlur={handleBlur}
            onFocus={() => setFocusedField('description')}
            style={getInputStyle('description', styles.textarea)}
            placeholder="Please describe your issue in detail. Include any error messages, steps to reproduce, or relevant context."
            required
            aria-required="true"
            aria-invalid={!!errors.description}
            aria-describedby={errors.description ? 'description-error' : 'description-help'}
            disabled={isSubmitting}
          />
          <div style={styles.characterCount}>
            <span
              style={{
                ...(descriptionPercent > 90
                  ? styles.characterCountError
                  : descriptionPercent > 75
                  ? styles.characterCountWarning
                  : {}),
              }}
            >
              {descriptionLength} / {DESCRIPTION_MAX_LENGTH} characters
            </span>
          </div>
          {touched.description && errors.description && (
            <span id="description-error" style={styles.errorText} role="alert">
              {errors.description}
            </span>
          )}
          {!errors.description && (
            <span id="description-help" style={styles.helpText}>
              Provide as much detail as possible to help us resolve your issue quickly.
            </span>
          )}
        </div>

        {/* Order ID (Optional) */}
        <div style={styles.formGroup}>
          <label htmlFor="orderId" style={styles.label}>
            Order/Reference ID
            <span style={{ color: '#6B7280', fontWeight: 'normal' }}>(optional)</span>
          </label>
          <input
            type="text"
            id="orderId"
            name="orderId"
            value={formData.orderId}
            onChange={handleChange}
            onBlur={handleBlur}
            onFocus={() => setFocusedField('orderId')}
            style={getInputStyle('orderId', styles.input)}
            placeholder="e.g., ORD-12345"
            disabled={isSubmitting}
          />
        </div>

        {/* Honeypot Field (Spam Prevention) - Hidden */}
        <div style={styles.honeypot} aria-hidden="true">
          <label htmlFor="honeypot">
            Don't fill this out if you're human:
          </label>
          <input
            type="text"
            id="honeypot"
            name="honeypot"
            value={formData.honeypot}
            onChange={handleChange}
            tabIndex={-1}
            autoComplete="off"
          />
        </div>

        {/* Submit Button */}
        <button
          type="submit"
          style={{
            ...styles.submitButton,
            ...(isSubmitting ? styles.submitButtonDisabled : {}),
          }}
          disabled={isSubmitting}
          onMouseOver={(e) => {
            if (!isSubmitting) {
              e.target.style.backgroundColor = styles.submitButtonHover.backgroundColor;
            }
          }}
          onMouseOut={(e) => {
            if (!isSubmitting) {
              e.target.style.backgroundColor = styles.submitButton.backgroundColor;
            }
          }}
        >
          {isSubmitting ? (
            <>
              <SpinnerIcon style={styles.spinner} />
              Submitting...
            </>
          ) : (
            <>
              <SendIcon style={{ width: '20px', height: '20px' }} />
              Submit Request
            </>
          )}
        </button>
      </form>

      {/* CSS Animation for spinner */}
      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}

export default SupportForm;
