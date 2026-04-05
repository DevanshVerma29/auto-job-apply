# Jobber — Usage Guide

Jobber is an AI agent that autonomously applies to jobs on your behalf using browser automation, powered by Claude.

---

## Quick Start

```bash
# 1. Clone and enter the repo
git clone https://github.com/your-username/jobber.git
cd jobber

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install Playwright browser drivers
playwright install chromium

# 5. Add your Anthropic API key
echo 'ANTHROPIC_API_KEY="your-key-here"' > .env

# 6. Fill in your personal info and resume path
nano jobber_fsm/user_preferences/user_preferences.txt

# 7. In a SEPARATE terminal — quit Chrome fully first, then launch it in debug mode
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir=/tmp/chrome-debug-profile

# 8. Back in your main terminal — run the agent
python -u -m jobber_fsm
```

When prompted, enter a task like:
```
Search for Content Designer jobs on LinkedIn in India (remote, Gurgaon, Delhi, Bangalore). Apply to the first relevant listing using resume at /path/to/resume.pdf
```

---

## Prerequisites

- **Python 3.8+** (3.14 supported — all deps compatible)
- **pip**
- **Google Chrome**
- **Anthropic API key** with credits — [console.anthropic.com](https://console.anthropic.com/)

---

## user_preferences.txt

Located at `jobber_fsm/user_preferences/user_preferences.txt`. Fill in your details before running:

```
Personal Info:
First Name: Your Name
Last Name: Your Last Name
Email: you@example.com
Phone Number: +91 XXXXXXXXXX
Address: City, Country
Occupation: Your Role

Resume File to Upload Path = /absolute/path/to/your/resume.pdf

Skills:
...

Work Experience:
...
```

> This file is gitignored — your personal info will not be committed.

---

## Notes

- **Chrome must be quit completely** before launching in debug mode — if it's already open, the debug flag will be ignored and the agent won't connect
- The `--user-data-dir` flag is required — without it Chrome won't bind the debug port
- Run Chrome in a **separate terminal** and keep it open while the agent is running
- The agent takes input interactively — do not pipe commands via `echo |` (causes EOF loop)
- Anthropic API credits are required — a free-tier key with no balance will fail at runtime

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `Could not resolve authentication method` | `.env` file missing or `ANTHROPIC_API_KEY` not set |
| `Your credit balance is too low` | Add credits at console.anthropic.com/settings/billing |
| `Opening in existing browser session` | Quit Chrome fully (Cmd+Q), then relaunch with the debug flags |
| `DevTools requires a non-default data directory` | Add `--user-data-dir=/tmp/chrome-debug-profile` to the Chrome launch command |
| Port 9222 not open | Verify with `lsof -i :9222` — if empty, Chrome didn't launch correctly |
| `EOF when reading a line` (endless loop) | Don't pipe input — run interactively and type the command manually |
| Import errors | Re-run `pip install -r requirements.txt` inside your venv |
