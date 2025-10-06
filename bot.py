# lab_hours_bot_flask.py
import re
import pandas as pd
from datetime import datetime
from flask import Flask, request
from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings, TurnContext
from botbuilder.schema import Activity, ActivityTypes

# -----------------------
# CONFIGURATION
# -----------------------
APP_ID = "YOUR_AZURE_APP_ID"         # Replace with your Azure App ID
APP_PASSWORD = "YOUR_AZURE_APP_PASSWORD"  # Replace with your Azure App Password
LOG_FILE = "hours_log.csv"

# -----------------------
# FLASK SETUP
# -----------------------
app = Flask(__name__)
adapter = BotFrameworkAdapter(BotFrameworkAdapterSettings(APP_ID, APP_PASSWORD))

# -----------------------
# HELPER FUNCTIONS
# -----------------------
def parse_entry(text):
    """
    Parse messages like "14:30-16:30 doing tasks".
    Returns start, end, duration_hours, description.
    """
    match = re.match(r"(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})\s*(.*)", text)
    if not match:
        return None
    start_str, end_str, description = match.groups()
    start_t = datetime.strptime(start_str, "%H:%M")
    end_t = datetime.strptime(end_str, "%H:%M")
    duration = (end_t - start_t).seconds / 3600
    return start_str, end_str, duration, description.strip()

def log_entry(start, end, duration, description):
    today = datetime.now()
    new_row = {
        "Date": today.strftime("%Y-%m-%d"),
        "Month": today.month,
        "Year": today.year,
        "Start": start,
        "End": end,
        "Hours": round(duration, 2),
        "Task": description,
    }
    df = pd.DataFrame([new_row])
    try:
        df_existing = pd.read_csv(LOG_FILE)
        df = pd.concat([df_existing, df], ignore_index=True)
    except FileNotFoundError:
        pass
    df.to_csv(LOG_FILE, index=False)

def get_summary(month=None, year=None):
    try:
        df = pd.read_csv(LOG_FILE)
    except FileNotFoundError:
        return "No entries logged yet."

    if month and year:
        df = df[(df["Month"] == month) & (df["Year"] == year)]

    if df.empty:
        return "No entries found for that period."

    lines = []
    for _, row in df.iterrows():
        lines.append(f"{row['Date']} {row['Start']}-{row['End']} ({row['Hours']}h): {row['Task']}")
    total = df["Hours"].sum()
    lines.append(f"\nTotal hours: {total:.2f}")
    return "\n".join(lines)

# -----------------------
# BOT HANDLER
# -----------------------
async def on_message(turn_context: TurnContext):
    text = turn_context.activity.text.strip()
    
    # Handle "show" command
    if text.lower().startswith("show"):
        m = re.match(r"show\s*(\d{1,2})-(\d{4})", text.lower())
        if m:
            month, year = map(int, m.groups())
            summary = get_summary(month, year)
        else:
            summary = get_summary()
        await turn_context.send_activity(summary)
        return

    # Handle hour entry
    entry = parse_entry(text)
    if entry:
        start, end, duration, desc = entry
        log_entry(start, end, duration, desc)
        await turn_context.send_activity(f"Logged {duration:.2f}h ({start}-{end}): {desc}")
    else:
        await turn_context.send_activity(
            "Please write in the format 'HH:MM-HH:MM task' or 'show [MM-YYYY]'"
        )

# -----------------------
# FLASK ROUTE
# -----------------------
@app.route("/api/messages", methods=["POST"])
def messages():
    body = request.json
    activity = Activity().deserialize(body)
    auth_header = request.headers.get("Authorization", "")
    task = adapter.process_activity(activity, auth_header, on_message)
    return "", 200

# -----------------------
# ENTRY POINT
# -----------------------
if __name__ == "__main__":
    app.run(debug=True)
