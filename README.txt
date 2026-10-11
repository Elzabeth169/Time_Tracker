StudyClock
==========

A small, offline desktop time tracker for Windows. It uses Python's built-in
Tkinter UI and SQLite storage; it has no third-party packages and makes no
network connections.

Run
---
Double-click "Launch StudyClock.bat". Python 3 must be installed. If Windows
does not find Python, install it from python.org and run the launcher again.

Use
---
1. Add a task, such as Studying, Reading, or Design.
2. Choose a task and a preset timer, or select Custom… (1–600 minutes).
3. Start focus. Pause/resume as needed, or finish early to save the elapsed
   focus time.
4. Open Dashboard and choose Daily, Weekly, or Monthly to see stacked time by
   task. Daily shows today's focus minutes across the 24 clock hours (0–60
   minutes per hour). Weekly shows this week's days and total hours per day on
   a 24-hour scale. Monthly shows the last 6 months on a scale up to 744 hours
   (31 days).

Data and privacy
----------------
Task names and completed sessions are stored locally at:
%LOCALAPPDATA%\StudyClock\studyclock.db

No account or internet connection is used. An unfinished session is discarded
if the app is closed; finished and early-finished sessions are saved. Sessions
recorded by older versions are kept; their daily chart time is assigned to the
hour the session started because older versions did not save hourly detail.
