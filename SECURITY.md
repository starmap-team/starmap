# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| latest  | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability within StarMap, please send an email to the project maintainers. All security vulnerabilities will be promptly addressed.

**Please do NOT report security vulnerabilities through public GitHub issues.**

### What to include

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### Response timeline

- **Acknowledgment**: within 48 hours
- **Assessment**: within 1 week
- **Fix release**: depends on severity, typically within 2 weeks for critical issues

## Security Best Practices

- Never commit `.env` files or secrets to the repository
- Use `.env.example` as a template for local configuration
- Production secrets must be managed through `.env.production` (not tracked by git)
- All API keys should be rotated if accidentally exposed
- Use the provided `.pre-commit-config.yaml` hooks to prevent accidental secret commits
