# Link Checking Documentation

LoquiLex includes automated link checking for documentation to prevent broken links from being introduced.

## How It Works

The link checker uses [markdown-link-check](https://github.com/tcort/markdown-link-check) to validate all hyperlinks in:
- `README.md`
- All `*.md` files in the `docs/` directory

## Local Usage

Run the link checker locally:

```bash
make link-check
```

This will:
1. Install `markdown-link-check` if needed
2. Check all markdown links using the configuration in `.markdown-link-check.json`
3. Report any dead links and exit with code 1 if found

## CI Integration

Link checking previously ran automatically in CI as part of the "Documentation Quality" job. That job has been disabled by the maintainers and link checking is no longer enforced in CI by default. You can still run the check locally using `make link-check` if needed.

## Configuration

The link checker configuration is in `.markdown-link-check.json`:

### Ignored URLs
The following URL patterns are ignored (allowlisted):
- `http://localhost:*` and `https://localhost:*`
- `http://127.0.0.1:*` and `https://127.0.0.1:*`
- `ws://localhost:*` and `wss://localhost:*`
- `ws://127.0.0.1:*` and `wss://127.0.0.1:*`

### CI-only Ignored Test Domains
We intentionally ignore two placeholder/test domains which are known to be unreachable from some CI environments or blocked by corporate firewalls:

- `this-domain-definitely-does-not-exist-12345.com`
- `this-domain-does-not-exist-12345.com`

These entries live in the project root file `.markdown-link-check.json` under the `ignorePatterns` array. To remove or change these rules:

1. Edit `.markdown-link-check.json` and remove the corresponding `pattern` entries.
2. Run `make link-check` locally to confirm there are no regressions.
3. Open a PR and explain why the domains were re-enabled so reviewers can confirm network accessibility.

### Timeouts and Retries
- 20-second timeout per link
- 3 retry attempts with 30-second delays
- Handles 429 (rate limit) responses with retry-after headers

## Common Issues

### False Positives
If a URL is incorrectly flagged as broken:
1. Check if it's a localhost/dev URL that should be allowlisted
2. Add patterns to the `ignorePatterns` array in `.markdown-link-check.json`

### Adding New Documentation
When creating new markdown files with links:
1. Run `make link-check` locally before committing
2. Ensure all external links are valid
3. Use relative paths for internal documentation links

### Placeholder Documentation
For planned documentation that doesn't exist yet, create placeholder files with:
```markdown
# Title

*This documentation is under development.*

TODO: Brief description of planned content.
```

This prevents broken internal links while maintaining the link structure.

## Troubleshooting

### NPM Not Found
The link checker will attempt to install Node.js if npm is not available, but this requires sudo access. For development environments, install Node.js manually.

### Link Check Timeouts
If external links frequently timeout:
1. Check network connectivity
2. Consider increasing the timeout in `.markdown-link-check.json`
3. Add problematic domains to the ignore patterns if they're unreliable

### CI Failures
If the Documentation Quality job fails:
1. Check the CI logs for specific broken links
2. Fix or allowlist the problematic URLs
3. Re-run the CI or push a fix

## Best Practices

1. **Use relative links** for internal documentation
2. **Test links locally** before pushing changes
3. **Keep external links minimal** and use reliable sources
4. **Create placeholder files** instead of leaving broken internal links
5. **Review link check results** in CI failures to understand what broke