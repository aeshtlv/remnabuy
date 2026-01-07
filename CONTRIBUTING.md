## Contributing

Thanks for considering contributing to RemnaBuy.

### Development setup

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or: .venv\Scripts\activate  # Windows
pip install -r requirements.txt
cp env.sample .env
python -m src.main
```

### Pull requests

- Keep PRs small and focused.
- Update `README.md` / `README_EN.md` and `env.sample` if you add new env vars.
- Update RU/EN locales when changing user-facing text.
- Never commit secrets (`.env`, tokens, private URLs).


