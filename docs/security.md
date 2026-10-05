# Compliance, Security & Governance

## 1. Important Compliance Policy
- **Zero Unauthorized Scraping / Automation**: No automated scraping of LinkedIn, bypassing CAPTCHAs, or unauthorized browser bot automation.
- **Manual LinkedIn Preparation**: Prepares personalized copy with verified deep links for the user to execute manually (`ACTION_STATUS = MANUAL_REQUIRED`).
- **Human-in-the-Loop Approval**: No external communication or application is submitted without explicit user review.
- **Email Idempotency**: All dispatches use idempotency keys (`candidate_id + job_id + action_type`) to prevent accidental duplicate sends.
- **Zero Hallucination Guarantee**: Factual resume tailoring only highlights verified skills and projects.
