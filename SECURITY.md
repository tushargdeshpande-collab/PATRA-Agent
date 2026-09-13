# Security and privacy

## Reporting

Report security or privacy concerns privately to the repository maintainers.
Do not include real candidate documents or personal data in a public issue.

## Data handling

- PATRA processes candidate material locally by default.
- Use only documents you are authorized to process.
- Local history is stored in `data/patra_history.sqlite3`. Deleting that file
  removes locally retained run history.
- Never commit `.env`, API keys, passwords, tokens, real candidate records or
  generated application packages.
- Uploaded content is parsed as data and is never executed as code.

## Prototype boundary

PATRA is not an identity, credential or employment-verification service. Its
claim checks compare generated content with candidate-provided evidence and do
not establish that the underlying evidence is authentic.
