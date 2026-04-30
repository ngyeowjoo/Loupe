# 📊 PPTX Brand Checker

A web app that checks PowerPoint presentations against your company's brand guidelines — fonts, colors, font sizes, layout consistency, and more.

**Built with:** Python · Streamlit · No external dependencies beyond `streamlit`

---

## Features

- ✅ Font family validation
- ✅ Color compliance (perceptual ΔE comparison against your brand palette)
- ✅ Font size limits (title & body, min/max)
- ✅ Layout consistency across slides
- ✅ Empty slide detection
- ✅ Excessive bullet-point warning
- ✅ Slide dimension check (widescreen vs standard)
- ✅ Downloadable HTML report

---

## Run locally

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/pptx-brand-checker.git
cd pptx-brand-checker

# 2. Create a virtual environment (optional but recommended)
python -m venv .venv
source .venv/bin/activate      # macOS/Linux
.venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run
streamlit run app.py
```

The app opens at `http://localhost:8501`.

---

## Deploy to Streamlit Cloud

1. **Push this repo to GitHub** (public or private).

2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.

3. Click **New app** → select your repo → set:
   - **Branch:** `main`
   - **Main file:** `app.py`

4. Click **Deploy** — done! You'll get a public URL like  
   `https://YOUR_USERNAME-pptx-brand-checker-app-XXXX.streamlit.app`

> Streamlit Cloud is free for public repos and supports private repos on paid plans.

---

## Customising brand guidelines

All settings live in the **sidebar** at runtime — no code changes needed:

| Setting | Description |
|---|---|
| Allowed fonts | Comma-separated font family names |
| Slide dimensions | Widescreen / Standard / Any |
| Min/Max font sizes | Separate limits for title and body text |
| Brand colors | Add hex codes; compared using CIE ΔE |
| Color tolerance | ΔE threshold — ~10 strict, ~25 lenient |
| Checks to run | Toggle individual checks on/off |

---

## Project structure

```
pptx-brand-checker/
├── app.py               # Main Streamlit application
├── requirements.txt     # Python dependencies
├── .streamlit/
│   └── config.toml      # Theme configuration
└── README.md
```

---

## License

MIT
