# Daily Sales Email

A Python script that emails a Nairobi shop owner a **daily sales summary every evening at 6 PM**. It reads the sales CSV his cashier updates during the day and sends a clean, phone-friendly HTML email with the four numbers he cares about:

1. **Total revenue**
2. **Number of transactions** (receipts)
3. **Top-selling item**
4. **Restock alert** for any item that has dropped below its restock level

AI Masterclass 2, Week 5: Day 23 (email automation) and Day 24 (scheduling and run logging).

It runs **by itself every evening**, with no one needing to start it, and records every run in `run_log.txt`.

![Email on a phone](screenshots/email-phone.png)

## Pricing

**One-off build fee: KES 12,000**, plus a **monthly retainer of KES 1,500** once it runs on a schedule.

I'd charge **one-off** for the build because the shop owner pays for a working result: the script set up on the shop's computer, his items and restock levels entered, Gmail connected, and the 6 PM email scheduled and confirmed arriving. Once it works, it keeps working with no running costs (Gmail is free and nothing is hosted).

Once it runs **automatically every day**, the **retainer** makes sense: I check `run_log.txt` weekly for errors and fix problems before the owner notices a missing email. It covers adding new items or changing restock levels, fixing it if the computer or Gmail settings change, adding a weekly or monthly summary, and quick support. Most small shops will take the one-off, and the retainer suits owners who'd rather not touch any files themselves.

## Set it up on the shop's computer (3 steps)

1. **Install Python** from [python.org/downloads](https://www.python.org/downloads/). During installation, tick **"Add python.exe to PATH"**.
2. **Double-click `setup.bat`** in this folder. It installs what the report needs and opens Notepad so you can fill in the Gmail address, the Gmail [App Password](https://myaccount.google.com/apppasswords) and who should receive the report. **Save, close Notepad**, and it schedules the email for **6:00 PM every day**.
3. **Double-click `send_test_report.bat`** to send one report now and check it arrives.

That's it. From now on the summary arrives every evening at 6 PM while the computer is on and the owner is logged in. To stop it, double-click `remove_schedule.bat`.

The **Gmail App Password** is a 16-character code, not the normal Gmail password. It needs **2-Step Verification** turned on first in the Google account.

## Files

| File | What it is |
|---|---|
| `sales.csv` | Today's sales, updated by the cashier: `time, receipt_no, item, quantity, unit_price` |
| `stock.csv` | Stock before today and the restock level for each item: `item, stock_before_today, restock_level` |
| `daily_sales_report.py` | Reads the files, calculates the metrics, sends the email and writes the run log |
| `setup.bat` | One-time setup: installs requirements, creates `.env`, schedules the 6 PM task |
| `send_test_report.bat` | Sends a report now (for testing) |
| `run_daily_report.bat` | What Windows Task Scheduler runs at 6 PM |
| `remove_schedule.bat` | Stops the automatic daily email |
| `run_log.txt` | One line per run, written by the script |
| `.env` | Gmail address, App Password and recipients. **Never committed** (it's in `.gitignore`). |

The sample `sales.csv` has 18 rows from 15 receipts of realistic Kenyan shop items (Unga Pembe, Kimbo, Brookside milk and so on).

## How the metrics are worked out

- **Revenue:** quantity × unit price, summed over every row.
- **Transactions:** the number of **different receipt numbers**, so one customer buying 3 items counts once.
- **Top-selling item:** the most units sold. Ties are broken by revenue.
- **Restock alert:** `stock_before_today − quantity sold today`. If that's below the item's restock level, it's flagged in red.

Rows the cashier typed wrongly (e.g. letters in the quantity) are skipped and reported, instead of crashing the script or counting wrong.

## Run log

Every run, whether manual, scheduled, a preview or a failure, adds **one line** to `run_log.txt`:

```
date       | time     | status  | rows     | how       | detail
```

Proof from this project, with two manual runs followed by the automatic 6 PM run:
```
(replace this block with your real run_log.txt)
```

What the different results look like:
```
2026-11-17 | 22:24:09 | SUCCESS |  18 rows | manual    | preview only, nothing sent
2026-11-17 | 22:24:09 | SUCCESS |  18 rows | manual    | sent to owner@example.com | revenue KES 11,460, 15 transactions, 2 to restock
2026-11-17 | 18:00:01 | SUCCESS |  18 rows | scheduled | sent to owner@example.com | revenue KES 11,460, 15 transactions, 2 to restock
2026-11-17 | 18:00:01 | ERROR   |  18 rows | scheduled | Gmail rejected the login. Check GMAIL_ADDRESS and GMAIL_APP_PASSWORD in .env ...
```

**Checking it's working:** open `run_log.txt` and look for a `scheduled` line for each day. A missing day means the computer was off at 6 PM. An `ERROR` line says exactly what to fix. Unexpected crashes are logged too, so a failure is never silent.

## Testing

Preview the email without sending anything (it saves `preview.html` to open in a browser):
```bash
python daily_sales_report.py --preview
```

Send it now:
```bash
python daily_sales_report.py
```

Run the scheduled task immediately, through Task Scheduler itself, instead of waiting until 6 PM:
```bat
schtasks /Run /TN "Daily Sales Email"
```
This adds a line marked `scheduled` to `run_log.txt`, which proves the schedule works.

## Linux / Mac (cron)

Run `crontab -e` and add this line to send at 6 PM daily. Change the path to your folder:
```
0 18 * * * cd /home/you/daily-sales-email && /usr/bin/python3 daily_sales_report.py --scheduled
```

## Running it for clients without their computer

Task Scheduler only works while the shop's computer is on. For a client who wants the report even when the computer is off, the next step is to run it on a server, e.g. a **Render Cron Job** set to `0 15 * * *` (6 PM in Kenya is 15:00 UTC). The sales data would then need to live online too, e.g. a Google Sheet the cashier updates instead of a CSV on the shop computer.

## Errors handled

| Problem | What happens |
|---|---|
| Wrong Gmail password (e.g. the normal password instead of an App Password) | Clear message saying an App Password is needed |
| `.env` incomplete | Lists what to add |
| No internet | "Couldn't send the email… check the internet connection" |
| `sales.csv` missing, wrong columns, or no valid rows | Plain-English message |
| A badly typed row | Skipped and reported by line number |
| `stock.csv` missing | The email still sends, without restock alerts |

## Stack

Python · csv · smtplib (Gmail SMTP with an App Password) · email (HTML + plain-text) · python-dotenv · Windows Task Scheduler (schtasks) / cron
