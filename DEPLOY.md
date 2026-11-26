# Sharing the Yard Control dashboard (Streamlit Community Cloud + login)

Main app file: `yard_gps_dashboard_hub_multi_v6_parking_hotspots.py`

Only 5 files get uploaded (see `.gitignore`): the app, `requirements.txt`,
`make_password_hash.py`, `DEPLOY.md` and `.gitignore`.
**`.streamlit/secrets.toml` (your API tokens) is never uploaded.**

---

## Step 1 — Create logins (on your PC)

For each person who should have access, run this in the `yard_ai` folder:

```powershell
.\.venv\Scripts\python.exe make_password_hash.py
```

It asks for a username and password and prints a line like:

```toml
ravi = "pbkdf2_sha256$200000$9f2c...$41ab..."
```

Open `.streamlit\secrets.toml` and add at the bottom:

```toml
[auth.users]
ravi = "pbkdf2_sha256$200000$...$..."
priya = "pbkdf2_sha256$200000$...$..."
```

Test on your PC — you should now see a sign-in screen:

```powershell
.\.venv\Scripts\python.exe -m streamlit run yard_gps_dashboard_hub_multi_v6_parking_hotspots.py
```

Give each person their username and password privately (not in a group chat).

---

## Step 2 — Put the code in a PRIVATE GitHub repository

1. Sign in at https://github.com and create a new repository
   (https://github.com/new). Name it e.g. `yard-control`, choose **Private**,
   don't add a README.
2. In the `yard_ai` folder run:

```powershell
git init -b main
git add .
git status
```

   `git status` must list **only** the 5 files above. If you see
   `secrets.toml`, `.venv` or `data`, stop and fix `.gitignore` first.

```powershell
git commit -m "Yard Control dashboard"
git remote add origin https://github.com/<your-github-username>/yard-control.git
git push -u origin main
```

---

## Step 3 — Deploy on Streamlit Community Cloud

1. Go to https://share.streamlit.io and sign in with GitHub.
2. **Create app → Deploy a public app from GitHub** (the app will still need a
   login, and you can restrict viewers in Step 4).
   - Repository: `<your-github-username>/yard-control`
   - Branch: `main`
   - Main file path: `yard_gps_dashboard_hub_multi_v6_parking_hotspots.py`
   - App URL: pick a name, e.g. `everest-yard-control`
3. Open **Advanced settings**:
   - **Python version:** the newest one offered (3.12 or later).
   - **Secrets:** paste the **whole contents** of your local
     `.streamlit\secrets.toml` (CNG, EV and `[auth.users]`). Layout:

```toml
[CNG]
URL = "..."

[CNG.TOKENS]
Mumbai = "..."
Pune = "..."
Delhi = "..."
Banglore = "..."
Kolkata = "..."
Chennai = "..."
Hyderabad = "..."

[EV]
URL = "..."
TOKEN = "..."

[auth.users]
ravi = "pbkdf2_sha256$..."
```

4. Click **Deploy**. After a few minutes you get a link like
   `https://everest-yard-control.streamlit.app` — that's what you share.

---

## Step 4 — (Recommended) Limit who can even open the page

In Streamlit Cloud: your app → **Share** (or Settings → Sharing) → set it so
only invited people can view, and add their email addresses. They then sign in
with that email first, and with their dashboard username/password second.

---

## Day-to-day

| Task | How |
|---|---|
| Add / remove a user | Edit **Secrets** of the app on Streamlit Cloud (and your local `secrets.toml`). The app restarts by itself. |
| Change the code | Edit the file on your PC, then `git add .` → `git commit -m "..."` → `git push`. The cloud app updates in about a minute. |
| Get new GPS positions | Click **↻ Refresh GPS now**. One click refreshes for everyone. |

## Things to know

- **Excel backup doesn't exist in the cloud.** The `data` folder isn't uploaded, so
  if the GPS API fails, the cloud app shows the error instead of Excel data.
- **The API calls now come from Streamlit's servers**, not your office. If the GPS
  provider only accepts calls from approved IP addresses, ask them to allow it.
- **Free apps sleep** after some days without visitors; the first visitor sees a
  "wake up" button and waits about a minute.
- Never commit `secrets.toml`. If a token ever leaks, ask the GPS provider for a new one.
