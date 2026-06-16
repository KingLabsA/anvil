# Anvil Security Guide

This guide covers security best practices for deploying and using Anvil.

## 🔐 Critical Security Configuration

### 1. Environment Variables

**NEVER commit `.env` files to version control!**

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
chmod 600 .env  # Restrict permissions
```

### 2. Secret Key Generation

Generate a strong secret key for JWT tokens:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Add to `.env`:
```
ANVIL_SECRET_KEY=your-generated-secret-key
```

### 3. Database Security

**Development (SQLite):**
```
DATABASE_URL=sqlite:///./anvil.db
```

**Production (PostgreSQL):**
```
DATABASE_URL=postgresql://user:strong_password@localhost:5432/anvil
```

**PostgreSQL Security Checklist:**
- [ ] Use strong, unique passwords
- [ ] Enable SSL/TLS connections
- [ ] Restrict database user permissions
- [ ] Use connection pooling
- [ ] Regular backups
- [ ] Enable audit logging

### 4. API Keys

Store API keys securely:
```
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
HF_TOKEN=hf_...
```

**Best Practices:**
- [ ] Use separate API keys for development and production
- [ ] Rotate keys regularly
- [ ] Monitor API usage and costs
- [ ] Set usage limits
- [ ] Never share keys in code or commits

## 🔒 Authentication & Authorization

### JWT Tokens

Anvil uses JWT (JSON Web Tokens) for authentication:

- **Access Token**: Short-lived (24 hours default)
- **Refresh Token**: Long-lived (30 days default)

**Configuration:**
```
ACCESS_TOKEN_EXPIRE_MINUTES=1440
REFRESH_TOKEN_EXPIRE_DAYS=30
```

**Security Recommendations:**
- [ ] Use HTTPS in production
- [ ] Store tokens securely (httpOnly cookies)
- [ ] Implement token revocation
- [ ] Monitor for token theft
- [ ] Use strong secret keys

### OAuth2 Integration

Configure OAuth2 providers:

**GitHub:**
```
GITHUB_CLIENT_ID=your-client-id
GITHUB_CLIENT_SECRET=your-client-secret
```

**Google:**
```
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
```

**Security Checklist:**
- [ ] Use official OAuth2 libraries
- [ ] Validate state parameters
- [ ] Use HTTPS for callbacks
- [ ] Store secrets securely
- [ ] Implement proper error handling

## 🛡️ API Security

### Rate Limiting

Protect against abuse:

```
RATE_LIMIT_MAX_REQUESTS=100
RATE_LIMIT_WINDOW_SECONDS=60
```

**Recommendations:**
- [ ] Implement per-user rate limits
- [ ] Use sliding window algorithm
- [ ] Return 429 status with retry-after header
- [ ] Monitor rate limit hits
- [ ] Implement IP-based limits

### CORS Configuration

**Development:**
```
CORS_ORIGINS=*
```

**Production:**
```
CORS_ORIGINS=https://anvil.example.com,https://app.anvil.example.com
```

**Security Checklist:**
- [ ] Never use `*` in production
- [ ] Specify exact origins
- [ ] Use HTTPS origins only
- [ ] Restrict allowed methods
- [ ] Restrict allowed headers

### Input Validation

All API endpoints validate input:

- [ ] Use Pydantic models for validation
- [ ] Sanitize user input
- [ ] Validate file uploads
- [ ] Limit request sizes
- [ ] Use parameterized queries (prevent SQL injection)

## 🔐 Network Security

### HTTPS/TLS

**ALWAYS use HTTPS in production!**

**Nginx Configuration:**
```nginx
server {
    listen 443 ssl http2;
    server_name anvil.example.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    # Modern TLS configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;
    
    # HSTS
    add_header Strict-Transport-Security "max-age=63072000" always;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Let's Encrypt (Free SSL):**
```bash
sudo certbot --nginx -d anvil.example.com
```

### Firewall Configuration

**UFW (Ubuntu):**
```bash
sudo ufw allow 443/tcp  # HTTPS
sudo ufw allow 22/tcp   # SSH
sudo ufw enable
```

**Security Checklist:**
- [ ] Block all unnecessary ports
- [ ] Use fail2ban for brute force protection
- [ ] Implement IP whitelisting for admin access
- [ ] Use VPN for internal access
- [ ] Regular security audits

## 🔍 Monitoring & Logging

### Application Logs

Configure logging:
```
LOG_LEVEL=INFO  # Use DEBUG for development
```

**Log Security Events:**
- [ ] Failed login attempts
- [ ] Rate limit violations
- [ ] API key usage
- [ ] Suspicious activity
- [ ] System errors

### Monitoring Tools

**Prometheus + Grafana:**
```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'anvil'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/api/metrics'
```

**Security Monitoring:**
- [ ] Set up alerts for suspicious activity
- [ ] Monitor API usage patterns
- [ ] Track failed authentication attempts
- [ ] Monitor resource usage
- [ ] Implement anomaly detection

## 🔐 Data Protection

### Sensitive Data

**NEVER store in plain text:**
- Passwords
- API keys
- Tokens
- Personal information
- Financial data

**Use encryption:**
- At rest: Use encrypted databases
- In transit: Use TLS/SSL
- In memory: Minimize exposure

### Backups

**Regular Backups:**
```bash
# PostgreSQL
pg_dump anvil > backup_$(date +%Y%m%d).sql

# SQLite
cp anvil.db backup_$(date +%Y%m%d).db
```

**Backup Security:**
- [ ] Encrypt backups
- [ ] Store backups securely
- [ ] Test restore procedures
- [ ] Implement retention policies
- [ ] Use off-site storage

## 🛠️ Security Tools

### Dependency Scanning

```bash
# Python
pip-audit

# Node.js
npm audit

# General
snyk test
```

### Vulnerability Scanning

```bash
# Trivy (comprehensive)
trivy fs .

# Bandit (Python)
bandit -r src/

# ESLint Security (JavaScript)
npm install -g eslint-plugin-security
```

### Secret Scanning

```bash
# GitLeaks
gitleaks detect --source .

# TruffleHog
trufflehog filesystem .
```

## 📋 Security Checklist

### Pre-Deployment

- [ ] All secrets in environment variables
- [ ] Strong secret key generated
- [ ] HTTPS configured
- [ ] CORS properly configured
- [ ] Rate limiting enabled
- [ ] Input validation implemented
- [ ] SQL injection prevention
- [ ] XSS prevention
- [ ] CSRF protection
- [ ] File upload validation
- [ ] Dependencies scanned
- [ ] Security headers configured

### Production

- [ ] HTTPS enforced
- [ ] HSTS enabled
- [ ] Security headers set
- [ ] Monitoring configured
- [ ] Logging enabled
- [ ] Backups configured
- [ ] Incident response plan
- [ ] Regular security audits
- [ ] Penetration testing
- [ ] Compliance requirements met

### Ongoing

- [ ] Regular dependency updates
- [ ] Security patch monitoring
- [ ] Log review
- [ ] Access review
- [ ] Backup testing
- [ ] Security training
- [ ] Incident response drills
- [ ] Compliance audits

## 🚨 Incident Response

### If Compromised

1. **Immediate Actions:**
   - Rotate all secrets and API keys
   - Revoke all active tokens
   - Check logs for unauthorized access
   - Assess data exposure

2. **Investigation:**
   - Identify attack vector
   - Determine scope of breach
   - Check for persistence mechanisms
   - Document timeline

3. **Recovery:**
   - Patch vulnerability
   - Restore from clean backup
   - Implement additional security measures
   - Monitor for further attacks

4. **Notification:**
   - Notify affected users (if required)
   - Report to authorities (if required)
   - Document incident
   - Update security policies

### Contact Information

- Security Team: security@fableforge.ai
- Incident Response: incident@fableforge.ai

## 📚 Additional Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CIS Benchmarks](https://www.cisecurity.org/cis-benchmarks/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [Python Security Best Practices](https://python-security.readthedocs.io/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)

## 🔒 Compliance

### GDPR

- [ ] Data minimization
- [ ] Right to access
- [ ] Right to erasure
- [ ] Data portability
- [ ] Privacy by design
- [ ] Data protection impact assessment

### SOC 2

- [ ] Security controls implemented
- [ ] Availability measures in place
- [ ] Processing integrity ensured
- [ ] Confidentiality protected
- [ ] Privacy maintained

### HIPAA (if applicable)

- [ ] PHI encryption
- [ ] Access controls
- [ ] Audit controls
- [ ] Integrity controls
- [ ] Transmission security

---

**Last Updated:** 2026-06-15
**Version:** 1.0.0
**Maintained by:** FableForge Security Team
