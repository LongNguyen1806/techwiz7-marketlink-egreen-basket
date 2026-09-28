# WEB APPLICATION ENGINEERING REVIEW STANDARD

**Document Type:** Engineering Quality & Security Review Standard  
**Purpose:** AI-assisted full-stack code review  
**Target:** Production-grade modern web applications  
**Primary Principle:** Security and correctness take precedence over elegance  
**Version:** 1.0  
**Status:** Baseline Standard

---

# 1. PURPOSE

This document defines a structured standard for reviewing a modern web application across:

- Functional correctness
- Authentication and authorization
- Application and API security
- Data integrity
- Backend performance
- Frontend performance
- Database performance
- Architecture
- Maintainability
- Accessibility
- UX resilience
- Testing
- Reliability
- Observability
- Production readiness
- Dependency and configuration security

The standard is designed to be consumed by an AI coding agent or reviewer together with the complete source code.

The AI reviewer MUST use this document as the review contract.

The AI reviewer MUST NOT replace objective engineering requirements with personal coding preferences.

---

# 2. REVIEW PHILOSOPHY

## 2.1 Priority Order

When engineering concerns conflict, use this priority order:

1. Security
2. Data integrity
3. Functional correctness
4. Reliability
5. Performance
6. Accessibility
7. Maintainability
8. Developer convenience
9. Cosmetic/style preferences

A visually elegant implementation with a security vulnerability is NOT acceptable.

A highly optimized implementation with incorrect business logic is NOT acceptable.

---

# 3. REVIEW PRINCIPLES

The reviewer MUST follow these rules.

## 3.1 Evidence-Based Findings

Every non-trivial finding MUST include:

- Finding ID
- Severity
- File/path
- Relevant function/class/component
- Evidence
- Why it is a problem
- Impact
- Recommended remediation
- Confidence
- Relevant standard/reference when applicable

Do not report vague statements such as:

> "This code may be insecure."

Instead provide concrete evidence.

---

## 3.2 Do Not Treat Preferences as Defects

The reviewer MUST NOT classify the following as defects without evidence of actual impact:

- Preference for one state-management library over another
- Preference for one folder structure
- Preference for class-based vs functional design
- Preference for repository pattern
- Preference for service classes
- Function length alone
- Number of files alone
- Personal naming preferences
- Framework preference
- Styling preference
- Optional design patterns

A recommendation becomes an engineering issue only when there is a demonstrable impact on:

- Security
- Correctness
- Performance
- Reliability
- Maintainability
- Accessibility
- Testability
- Operational safety

---

# 4. SEVERITY MODEL

## CRITICAL

Immediate release blocker.

Examples:

- Authentication bypass
- Authorization bypass
- IDOR/BOLA exposing sensitive data
- Remote code execution
- SQL injection with exploitable impact
- Critical secret exposure
- Major data corruption
- Privilege escalation
- Arbitrary file access
- Critical payment/business integrity failure

---

## HIGH

Serious production risk.

Examples:

- Significant authorization weakness
- Sensitive information exposure
- Race condition affecting business data
- Major N+1 query on high-traffic endpoint
- Missing transaction around critical multi-step operation
- Unsafe file upload
- Broken refresh-token security
- Severe denial-of-service vector
- Major production failure path

---

## MEDIUM

Important engineering issue that should be fixed.

Examples:

- Missing validation
- Inefficient query with limited current impact
- Missing rate limit on non-critical endpoint
- Weak error handling
- Missing important test coverage
- Maintainability issue that creates measurable risk

---

## LOW

Minor issue.

Examples:

- Small duplication
- Minor optimization
- Minor accessibility issue
- Non-critical refactoring

---

## INFORMATIONAL

Observation or optional improvement.

Examples:

- Alternative implementation
- Documentation improvement
- Optional optimization
- Architectural suggestion without current defect

---

# 5. CONFIDENCE

Every finding should have:

- HIGH — directly demonstrated by code/configuration
- MEDIUM — strong evidence but runtime confirmation would be useful
- LOW — possible issue requiring further investigation

Do not present LOW-confidence hypotheses as confirmed vulnerabilities.

---

# 6. REVIEW PHASES

The reviewer MUST inspect the application in the following order:

1. Repository structure
2. Configuration and secrets
3. Authentication
4. Authorization
5. API security
6. Input/output security
7. Business logic
8. Database integrity
9. Backend performance
10. Frontend performance
11. Accessibility
12. UX resilience
13. Architecture
14. Testing
15. Reliability
16. Observability
17. Dependencies
18. Production/deployment configuration

---

# 7. SECURITY STANDARD

Primary references:

- OWASP ASVS
- OWASP Top 10
- OWASP API Security Top 10
- OWASP Cheat Sheets

The reviewer SHOULD map significant findings to an applicable OWASP category.

---

# 8. AUTHENTICATION

## AUTH-001 — Password Storage

Inspect:

- Password hashing
- Password reset flow
- Password change flow
- Password policy
- Credential storage

PASS:

- Passwords are never stored in plaintext.
- Modern adaptive password hashing is used.

FAIL:

- Plaintext passwords
- Reversible password encryption
- Weak custom hashing

Severity: CRITICAL

---

## AUTH-002 — Login Validation

Inspect:

- Credential verification
- Account status
- Disabled accounts
- Deleted accounts
- Login failure handling

FAIL if an inactive/deleted account can authenticate.

Severity: HIGH

---

## AUTH-003 — Brute Force Protection

Inspect:

- Rate limiting
- Login throttling
- Account abuse protection
- Distributed attack considerations

FAIL if sensitive authentication endpoints have no reasonable abuse protection.

Severity: HIGH

---

## AUTH-004 — Session Expiration

Inspect:

- Access-token expiration
- Refresh-token expiration
- Session invalidation
- Logout behavior

FAIL if long-lived credentials are accepted indefinitely without justified architecture.

Severity: HIGH

---

## AUTH-005 — Refresh Token Security

Inspect:

- Rotation
- Revocation
- Reuse detection where applicable
- Secure storage
- Expiration
- Logout invalidation

Severity: HIGH

---

## AUTH-006 — Token Validation

Inspect:

- Signature
- Expiration
- Issuer
- Audience where applicable
- Algorithm
- Token type
- Revocation state

FAIL if attacker-controlled token properties can bypass validation.

Severity: CRITICAL

---

# 9. AUTHORIZATION

Authorization MUST be evaluated independently from authentication.

## AUTHZ-001 — Object-Level Authorization

For every endpoint accepting an object identifier, inspect whether the requester is authorized to access that specific object.

Examples:

- User
- Project
- Task
- Order
- Timesheet
- Report
- File
- Notification

FAIL:

```text
GET /api/tasks/123
```

returns another user's object solely because the ID is known.

Severity: CRITICAL

Reference: OWASP API Security — Broken Object Level Authorization.

---

## AUTHZ-002 — Function-Level Authorization

Inspect administrative and privileged endpoints.

Examples:

- Delete
- Approve
- Export
- Manage users
- Change role
- Lock/unlock
- Audit
- System settings

FAIL if a lower-privileged role can invoke a privileged operation.

Severity: CRITICAL

---

## AUTHZ-003 — Horizontal Privilege Escalation

Test whether one user can access another user's data.

Severity: CRITICAL

---

## AUTHZ-004 — Vertical Privilege Escalation

Test whether a lower role can perform higher-role actions.

Severity: CRITICAL

---

## AUTHZ-005 — Server-Side Enforcement

Permissions MUST be enforced on the server.

Frontend route guards are NOT sufficient.

Severity: CRITICAL

---

# 10. INPUT SECURITY

Inspect all external input:

- Query parameters
- Path parameters
- JSON bodies
- Forms
- Headers
- Cookies
- File uploads
- WebSocket messages

---

## INPUT-001 — SQL Injection

Inspect:

- Raw SQL
- `cursor.execute`
- Raw ORM queries
- Dynamic query construction
- String interpolation

PASS:

- Parameterized queries
- Safe ORM usage

Severity: CRITICAL

---

## INPUT-002 — XSS

Inspect:

- HTML rendering
- Rich text
- `dangerouslySetInnerHTML`
- DOM manipulation
- User-generated content

Severity: HIGH/CRITICAL depending on exploitability and scope.

---

## INPUT-003 — Command Injection

Inspect:

- `subprocess`
- Shell commands
- `os.system`
- `shell=True`
- Dynamic command arguments

Severity: CRITICAL

---

## INPUT-004 — Path Traversal

Inspect file paths originating from users.

Examples:

```text
../../
..\..\ 
absolute paths
encoded traversal
```

Severity: CRITICAL/HIGH

---

## INPUT-005 — SSRF

Inspect any feature that allows the server to request a user-supplied URL.

Examples:

- URL preview
- Webhook tester
- Image importer
- Remote file importer

Severity: HIGH/CRITICAL

---

# 11. FILE UPLOAD SECURITY

Inspect:

- File size limits
- Extension validation
- MIME validation
- Magic-byte validation
- Filename sanitization
- Storage location
- Executable file handling
- Path traversal
- Access control
- Virus scanning where required

Never trust the client-provided filename or MIME type.

Severity: HIGH/CRITICAL depending on impact.

---

# 12. API SECURITY

Reference: OWASP API Security Top 10.

## API-001 — Object-Level Authorization

Must be enforced for every object access.

## API-002 — Authentication

All protected endpoints must enforce authentication.

## API-003 — Property-Level Authorization

Do not blindly accept privileged fields from clients.

Example:

```json
{
  "role": "ADMIN",
  "is_verified": true
}
```

The server MUST determine whether the requester may modify these fields.

## API-004 — Resource Consumption

Inspect:

- Pagination limits
- Request body size
- Upload limits
- Expensive operations
- Report generation
- Export endpoints
- Rate limits

Reject unreasonable values.

## API-005 — Function-Level Authorization

Verify role/permission requirements server-side.

## API-006 — Business Flow Abuse

Inspect sensitive flows:

- Login
- Password reset
- Registration
- Order creation
- Payment
- Approval
- Export
- Invitation
- Verification
- Bulk operations

## API-007 — Security Misconfiguration

Inspect:

- Debug mode
- CORS
- Allowed hosts
- Error output
- HTTP headers
- Documentation exposure
- Default credentials

## API-008 — Injection

Inspect all external input.

## API-009 — Inventory

Inspect:

- Deprecated endpoints
- Debug endpoints
- Unused admin endpoints
- Test endpoints
- API versions

## API-010 — Unsafe Consumption

Inspect external API integrations for:

- TLS validation
- Input validation
- Timeouts
- Response validation
- Error handling

---

# 13. CSRF, CORS AND BROWSER SECURITY

Inspect:

- CSRF protection
- Cookie security
- `HttpOnly`
- `Secure`
- `SameSite`
- CORS allowlist
- Origin validation
- Referer/origin checks where appropriate

Never use:

```text
Access-Control-Allow-Origin: *
```

with credentialed cross-origin authentication unless the architecture explicitly supports it safely.

---

# 14. SECURITY HEADERS

Inspect applicable headers:

- Content-Security-Policy
- Strict-Transport-Security
- X-Content-Type-Options
- Referrer-Policy
- Permissions-Policy
- Frame protections

Do not enable policies blindly; verify compatibility with the application.

---

# 15. SECRETS MANAGEMENT

Search the repository for:

- API keys
- Passwords
- JWT secrets
- Database credentials
- SMTP credentials
- Private keys
- Cloud credentials
- OAuth secrets
- Tokens

FAIL:

```python
SECRET_KEY = "real-secret"
```

Severity: CRITICAL if a real credential is exposed.

Also inspect:

- `.env`
- `.gitignore`
- CI/CD configuration
- Docker configuration
- logs

---

# 16. DATA PROTECTION

Inspect:

- Sensitive data returned by APIs
- Sensitive fields in serializers
- Logs
- Error messages
- URLs
- Browser storage
- Backups
- Export files

Do not expose:

- Password hashes
- Reset tokens
- Refresh tokens
- Private keys
- Internal secrets
- Unnecessary personal information

---

# 17. BUSINESS LOGIC

The reviewer MUST inspect whether security controls can be bypassed through alternate flows.

Examples:

- Approving without validation
- Deleting after permission removal
- Editing a locked record
- Reusing an expired action
- Duplicate submission
- Negative quantities
- Invalid status transitions
- Skipping required workflow states

Business rules MUST be enforced server-side.

---

# 18. TRANSACTION AND CONCURRENCY SAFETY

Inspect critical operations for race conditions.

Potential solutions:

- Database transactions
- Row-level locking
- Unique constraints
- Optimistic locking
- Atomic updates
- Idempotency keys

Examples:

```text
check → modify
read → calculate → write
approve → update
reserve → decrement
```

These operations require concurrency analysis.

Severity: HIGH if business integrity can be affected.

---

# 19. DATABASE QUALITY

Inspect:

- Schema integrity
- Foreign keys
- Unique constraints
- Check constraints
- Nullability
- Indexes
- Referential integrity
- Cascading behavior
- Transaction boundaries

Do not rely exclusively on application-level validation for database invariants.

---

# 20. DATABASE PERFORMANCE

Inspect:

- N+1 queries
- Missing indexes
- Unnecessary joins
- Full-table scans
- Large result sets
- `SELECT *`
- Repeated queries
- Inefficient aggregation
- Unnecessary serialization queries

For ORM-based applications inspect equivalents of:

- `select_related`
- `prefetch_related`
- `exists`
- `count`
- `only`
- `defer`
- annotations
- bulk operations

Do not add indexes without evidence that they support actual query patterns.

---

# 21. BACKEND PERFORMANCE

Inspect:

- N+1 queries
- CPU-heavy operations
- Blocking I/O
- Repeated external calls
- Unnecessary serialization
- Large response payloads
- Missing pagination
- Missing caching
- Expensive report generation
- Synchronous work that should be asynchronous

---

# 22. API PERFORMANCE

Inspect:

- Response size
- Pagination
- Filtering
- Sorting
- Search
- Compression
- Cache headers
- Duplicate requests
- Request waterfall
- Query count

The reviewer SHOULD identify endpoints likely to degrade with data growth.

---

# 23. CACHING

For each cache, document:

- What is cached
- Cache key
- TTL
- Invalidation strategy
- Consistency requirements
- Failure behavior
- Stampede protection where needed

Do not introduce caching solely because it sounds faster.

Caching must have a demonstrated purpose.

---

# 24. FRONTEND PERFORMANCE

For React/Vite or equivalent applications inspect:

- Component rendering
- State granularity
- Unnecessary re-renders
- Expensive calculations
- Dependency arrays
- Large component trees
- Bundle size
- Code splitting
- Lazy loading
- Dynamic imports
- Asset optimization

---

# 25. FRONTEND NETWORK PERFORMANCE

Inspect:

- Duplicate API requests
- N+1 frontend requests
- Request waterfalls
- Large payloads
- Unnecessary polling
- Missing caching
- Missing request cancellation
- Repeated fetches caused by lifecycle errors

---

# 26. CORE WEB VITALS

Target reference:

## LCP

Good:

```text
<= 2.5 seconds
```

Needs Improvement:

```text
> 2.5s and <= 4s
```

Poor:

```text
> 4s
```

## INP

Good:

```text
<= 200ms
```

Needs Improvement:

```text
> 200ms and <= 500ms
```

Poor:

```text
> 500ms
```

## CLS

Good:

```text
<= 0.1
```

Needs Improvement:

```text
> 0.1 and <= 0.25
```

Poor:

```text
> 0.25
```

Important:

Static code review MUST NOT claim that Core Web Vitals have been achieved.

Runtime measurement is required.

---

# 27. FRONTEND SECURITY

Inspect:

- XSS
- DOM injection
- unsafe HTML rendering
- token storage
- CSRF
- CORS
- CSP
- open redirects
- insecure dependencies
- exposed environment variables

Client-side environment variables MUST NOT contain secrets intended to remain confidential.

---

# 28. ACCESSIBILITY

Target:

**WCAG 2.2 AA**

Inspect:

- Semantic HTML
- Keyboard navigation
- Focus management
- Visible focus
- Labels
- Form error association
- ARIA correctness
- Color contrast
- Screen-reader compatibility
- Modal accessibility
- Table accessibility
- Image alternative text
- Reduced-motion considerations

Do not use ARIA when native HTML already provides the required semantics.

---

# 29. UX RESILIENCE

Every significant feature should be reviewed for:

- Initial state
- Loading state
- Empty state
- Success state
- Error state
- Permission denied state
- Expired session
- Network failure
- Validation failure
- Retry behavior

A feature that works only on the happy path is incomplete.

---

# 30. RESPONSIVE DESIGN

Inspect:

- Desktop
- Tablet
- Mobile
- Narrow viewport
- Large viewport
- Touch targets
- Overflow
- Tables
- Forms
- Dialogs
- Navigation

Do not judge responsiveness solely from CSS declarations. Review actual layout behavior.

---

# 31. ARCHITECTURE

Inspect:

- Separation of concerns
- Dependency direction
- Business logic placement
- Controller/view responsibility
- Serializer responsibility
- Service responsibility
- Query/data-access responsibility
- Frontend component responsibility
- State management
- Circular dependencies

The reviewer MUST NOT demand unnecessary architectural patterns.

Use the simplest architecture that satisfies:

- Correctness
- Security
- Maintainability
- Testability
- Performance

---

# 32. CODE QUALITY

Inspect:

- Duplication
- Dead code
- Unreachable code
- Excessive coupling
- Hidden side effects
- Global mutable state
- Magic values
- Inconsistent error handling
- Misleading names
- Excessive complexity

Do not mark code as defective merely because it is not stylistically identical to the reviewer’s preferred style.

---

# 33. ERROR HANDLING

Inspect for:

- Bare `except`
- Catch-all exception handling
- Silent failures
- Leaked stack traces
- Database errors exposed to clients
- Internal filesystem paths
- Secrets in error responses
- Incorrect HTTP status codes

Production responses should expose enough information for the client while avoiding unnecessary internal details.

---

# 34. LOGGING

Logs MUST NOT contain:

- Passwords
- Access tokens
- Refresh tokens
- API secrets
- Private keys
- Sensitive personal data unless justified

Inspect:

- Log levels
- Structured logging
- Correlation/request IDs
- Error context
- Audit logging for security-sensitive operations

---

# 35. AUDIT LOGGING

Sensitive actions should be auditable where business requirements require it.

Examples:

- Login/security events
- Role changes
- Permission changes
- Delete operations
- Approval/rejection
- Lock/unlock
- Configuration changes
- Export of sensitive information

Audit records should contain sufficient context to reconstruct the event without exposing secrets.

---

# 36. RELIABILITY

Inspect:

- Timeouts
- Retry policies
- Idempotency
- External dependency failures
- Database connection failures
- Redis failures
- Queue failures
- Graceful degradation
- Transaction rollback

Never retry unsafe operations blindly.

---

# 37. ASYNCHRONOUS PROCESSING

For long-running operations inspect whether asynchronous processing is appropriate.

Examples:

- Large report generation
- Large exports
- Email batches
- Image processing
- Heavy data imports
- Scheduled jobs

Inspect:

- Retry
- Failure handling
- Duplicate execution
- Job locking
- Monitoring
- Dead-letter handling where appropriate

---

# 38. WEBSOCKET / REAL-TIME SECURITY

If WebSockets are used, inspect:

- Authentication
- Authorization
- Origin validation
- Ticket/session validation
- Ticket expiration
- One-time-use semantics
- Connection limits
- Message validation
- Rate limiting
- Disconnect handling

Short-lived one-time connection tickets SHOULD be used where appropriate.

---

# 39. DEPENDENCY SECURITY

Inspect:

- Outdated dependencies
- Known vulnerabilities
- Unused dependencies
- Duplicate libraries
- Dependency pinning
- Lock files

Recommended tools may include:

- npm audit
- pip-audit
- Dependabot
- OSV
- SCA tooling

Do not treat every outdated dependency as a vulnerability.

---

# 40. CONFIGURATION SECURITY

Inspect:

- Production debug settings
- Allowed hosts
- CORS
- Database configuration
- Redis configuration
- TLS
- Secure cookies
- Environment variables
- Secret management
- Error reporting
- File permissions

---

# 41. PRODUCTION READINESS

Inspect:

- Health check
- Readiness check where applicable
- Graceful shutdown
- Database migrations
- Static assets
- Media storage
- Backup strategy
- Restore strategy
- Monitoring
- Error tracking
- Logging
- Configuration separation

---

# 42. TESTING STANDARD

Inspect for appropriate levels of:

## Unit Tests

Business logic and isolated functions.

## Integration Tests

Database and service interactions.

## API Tests

Authentication, authorization, validation, error handling.

## E2E Tests

Critical user journeys.

## Security Tests

At minimum test:

- Unauthorized access
- Horizontal privilege escalation
- Vertical privilege escalation
- IDOR/BOLA
- Invalid input
- Expired token
- Revoked token
- Rate limiting where applicable

---

# 43. TEST QUALITY

A test is not considered sufficient merely because it exists.

Inspect:

- Positive cases
- Negative cases
- Boundary values
- Permission cases
- Concurrency-sensitive cases
- Error paths
- Empty data
- Large data
- Invalid state transitions

---

# 44. PERFORMANCE TESTING

For important endpoints, review whether performance has been measured.

Potential metrics:

- p50 latency
- p95 latency
- p99 latency
- throughput
- database query count
- CPU
- memory
- error rate

Do not invent performance measurements from source code.

---

# 45. SECURITY SCANNING

Where tooling is available, review results from:

- SAST
- Dependency scanning
- Secret scanning
- DAST
- Container scanning
- Infrastructure scanning

Tool output must be validated before being classified as a confirmed defect.

---

# 46. AI REVIEW BEHAVIOR

The AI reviewer MUST:

1. Read architecture/configuration before judging implementation details.
2. Trace data flow for security-sensitive operations.
3. Trace authorization from request to database object.
4. Check both frontend and backend enforcement.
5. Consider attacker-controlled input.
6. Consider concurrency.
7. Consider data growth.
8. Consider failure conditions.
9. Distinguish confirmed defects from hypotheses.
10. Avoid unnecessary refactoring.
11. Avoid changing working business behavior without evidence.
12. Prefer minimal, targeted fixes.
13. Preserve existing API contracts unless change is required.
14. Identify assumptions explicitly.

---

# 47. FALSE POSITIVE CONTROL

Before reporting an issue, AI MUST ask internally:

1. Is this actually reachable?
2. Is the input attacker-controlled?
3. Is there already a control elsewhere?
4. Is the endpoint protected by another middleware/permission layer?
5. Is the behavior intentional according to the business requirement?
6. Does the alleged issue have measurable impact?
7. Can the issue be demonstrated from available evidence?

If evidence is insufficient, classify as:

```text
NEEDS VERIFICATION
```

rather than a confirmed vulnerability.

---

# 48. FINDING FORMAT

Every finding MUST use this structure:

```text
[FINDING-ID]
Severity:
Confidence:

Title:

File:
Line/Function:

Evidence:

Impact:

Attack/Failure Scenario:

Recommended Fix:

Validation Method:

Reference:
```

Example:

```text
[AUTHZ-001]
Severity: CRITICAL
Confidence: HIGH

Title:
Missing object-level authorization on task detail endpoint

File:
tasks/views.py

Function:
TaskDetailView.get()

Evidence:
The object is retrieved by primary key without checking whether
the authenticated user is authorized to access that task.

Impact:
An authenticated user may access another user's task by changing
the task identifier.

Attack Scenario:
GET /api/tasks/100
GET /api/tasks/101

Recommended Fix:
Perform server-side object-level authorization before returning
the object.

Validation Method:
Create two users and verify that User A cannot retrieve User B's task.

Reference:
OWASP API Security — Broken Object Level Authorization
```

---

# 49. REVIEW SUMMARY FORMAT

The final report MUST contain:

```text
# Executive Summary

# Critical Findings

# High Findings

# Medium Findings

# Low Findings

# Informational Findings

# Security Assessment

# Backend Assessment

# Frontend Assessment

# Database Assessment

# Performance Assessment

# Accessibility Assessment

# Architecture Assessment

# Testing Assessment

# Production Readiness

# Release Blockers

# Recommended Fix Order
```

---

# 50. RELEASE BLOCKERS

A release MUST be considered blocked if confirmed findings include:

- Authentication bypass
- Authorization bypass
- Critical IDOR/BOLA
- Privilege escalation
- Remote code execution
- Critical injection
- Major secret exposure
- Critical data corruption
- Critical business-logic bypass
- Severe uncontrolled file access

The reviewer MUST list the exact blocking findings.

Do not block a release solely for stylistic or subjective reasons.

---

# 51. PERFORMANCE REVIEW RULE

The AI MUST distinguish:

## Static Findings

Examples:

- N+1 query pattern
- Huge bundle import
- Missing pagination
- Duplicate requests

from:

## Runtime Measurements

Examples:

- LCP
- INP
- CLS
- p95 latency
- memory usage
- CPU utilization

Static code review MUST NOT invent runtime measurements.

---

# 52. SECURITY REVIEW RULE

The AI MUST distinguish:

## Confirmed Vulnerability

Evidence demonstrates the vulnerable path.

## Potential Vulnerability

Code indicates a risk but runtime/configuration evidence is incomplete.

## Needs Verification

Insufficient information.

Never present a potential issue as a confirmed exploit.

---

# 53. CHANGE SAFETY

When proposing fixes:

- Preserve business behavior.
- Preserve existing API contracts unless necessary.
- Avoid unnecessary rewrites.
- Avoid introducing new dependencies without justification.
- Prefer framework-native security controls.
- Prefer database constraints for database invariants.
- Prefer centralized authorization mechanisms where appropriate.
- Add regression tests for security fixes.

---

# 54. REVIEW COMPLETION CRITERIA

A review is complete only when the AI has inspected:

- Authentication
- Authorization
- API endpoints
- Sensitive business flows
- Input validation
- Database access
- Database constraints
- Frontend security
- Frontend performance
- Backend performance
- Dependency security
- Configuration
- Error handling
- Logging
- Testing
- Production configuration

The AI MUST explicitly identify areas that could not be reviewed because required source/configuration/runtime information was unavailable.

---

# 55. RECOMMENDED EXTERNAL STANDARDS

The reviewer SHOULD use current versions of:

- OWASP Application Security Verification Standard (ASVS)
- OWASP Top 10
- OWASP API Security Top 10
- OWASP Cheat Sheet Series
- WCAG 2.2
- Core Web Vitals
- HTTP specifications
- Framework security documentation
- Database vendor security/performance documentation

When an exact version matters, state the version used.

---

# 56. FINAL QUALITY GATE

The final report MUST answer these questions:

```text
1. Can an unauthorized user access another user's data?

2. Can a lower-privileged user perform a higher-privileged action?

3. Can an attacker manipulate object IDs to access protected resources?

4. Can untrusted input reach SQL, shell, HTML, filesystem, or URL operations unsafely?

5. Can critical business operations be executed twice or concurrently in an unsafe way?

6. Are sensitive credentials or tokens exposed?

7. Are important database invariants enforced?

8. Are expensive endpoints protected against uncontrolled resource consumption?

9. Are frontend and backend performance bottlenecks identifiable?

10. Are critical user flows resilient to loading, error, empty, and permission states?

11. Is the application accessible to keyboard and assistive-technology users?

12. Are critical behaviors covered by automated tests?

13. Is production configuration safe?

14. Are remaining issues confirmed defects, potential risks, or preferences?

15. What exact findings block production release?
```

---

# 57. GOLDEN RULE

The reviewer MUST follow this principle:

> **Do not optimize for code that merely looks professional. Optimize for software that is secure, correct, measurable, maintainable, resilient, and production-safe.**

A finding must be supported by evidence.

A recommendation must have a reason.

A security claim must have a demonstrable attack or failure path.

A performance claim must distinguish static analysis from runtime measurement.

A refactoring suggestion must not be presented as a defect unless there is measurable engineering impact.

---

# END OF STANDARD
