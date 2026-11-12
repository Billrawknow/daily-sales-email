"""
Daily Sales Email
-----------------
Reads the shop's sales CSV (updated by the cashier during the day), works out:
  1. total revenue
  2. number of transactions (receipts)
  3. top-selling item
  4. items that dropped below their restock level
and emails the owner a formatted HTML summary through Gmail.

Files:
    sales.csv   time, receipt_no, item, quantity, unit_price   (today's sales)
    stock.csv   item, stock_before_today, restock_level         (for restock alerts)
    .env        GMAIL_ADDRESS, GMAIL_APP_PASSWORD, REPORT_TO     (never commit this)

Usage:
    python daily_sales_report.py --preview   # build the email and save preview.html - nothing is sent
    python daily_sales_report.py             # send the email
Schedule it for 6 PM with Windows Task Scheduler (see README).
"""

import argparse
import csv
import logging
import os
import smtplib
import ssl
import sys
from collections import defaultdict
from datetime import datetime
from email.message import EmailMessage
from html import escape
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")

SHOP_NAME = os.getenv("SHOP_NAME", "Baraka Mini Mart")
SALES_FILE = HERE / "sales.csv"
STOCK_FILE = HERE / "stock.csv"
PREVIEW_FILE = HERE / "preview.html"
logging.basicConfig(filename=HERE / "email_log.txt", level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(message)s")


class ReportError(Exception):
    """A problem the shop owner (or whoever set this up) can understand and fix."""


# ---------------------------------------------------------------- reading data

def read_csv(path, required):
    if not path.exists():
        raise ReportError(f"{path.name} not found. It must be in the same folder as this script.")
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = [c for c in required if c not in (reader.fieldnames or [])]
        if missing:
            raise ReportError(f"{path.name} is missing column(s): {', '.join(missing)}")
        return list(reader)


def load_sales(path=SALES_FILE):
    rows, skipped = [], []
    for n, row in enumerate(read_csv(path, ["receipt_no", "item", "quantity", "unit_price"]), start=2):
        try:
            qty = int(float(row["quantity"]))
            price = float(str(row["unit_price"]).replace(",", ""))
            if qty <= 0 or price < 0 or not row["item"].strip():
                raise ValueError
        except (ValueError, TypeError):
            skipped.append(n)           # line number in the file, as seen in Excel
            continue
        rows.append({"receipt": row["receipt_no"].strip() or f"line{n}", "item": row["item"].strip(),
                     "qty": qty, "amount": qty * price})
    return rows, skipped


def load_stock(path=STOCK_FILE):
    if not path.exists():
        return {}                       # restock alerts are skipped if there's no stock file
    stock = {}
    for row in read_csv(path, ["item", "stock_before_today", "restock_level"]):
        try:
            stock[row["item"].strip()] = (int(float(row["stock_before_today"])), int(float(row["restock_level"])))
        except (ValueError, TypeError):
            continue
    return stock


# ---------------------------------------------------------------- the four metrics

def calculate(sales, stock):
    if not sales:
        raise ReportError("sales.csv has no valid sales rows for today.")
    qty_by_item, revenue_by_item = defaultdict(int), defaultdict(float)
    for s in sales:
        qty_by_item[s["item"]] += s["qty"]
        revenue_by_item[s["item"]] += s["amount"]
    top_item = max(qty_by_item, key=lambda i: (qty_by_item[i], revenue_by_item[i]))
    low_stock = []
    for item, (before, restock_level) in sorted(stock.items()):
        remaining = before - qty_by_item.get(item, 0)
        if remaining < restock_level:
            low_stock.append({"item": item, "remaining": remaining, "restock_level": restock_level})
    return {
        "revenue": sum(s["amount"] for s in sales),
        "transactions": len({s["receipt"] for s in sales}),
        "top_item": top_item,
        "top_qty": qty_by_item[top_item],
        "top_revenue": revenue_by_item[top_item],
        "low_stock": low_stock,
        "items": sorted(qty_by_item, key=lambda i: -revenue_by_item[i]),
        "qty_by_item": qty_by_item,
        "revenue_by_item": revenue_by_item,
    }


# ---------------------------------------------------------------- the email

def kes(amount):
    return f"KES {amount:,.0f}"


def build_html(m, day):
    """HTML with inline styles only - email apps (Gmail, Outlook) ignore <style> blocks."""
    card = ("background:#ffffff;border:1px solid #e3e6ea;border-radius:10px;padding:14px 16px;"
            "width:50%;vertical-align:top;")
    label = "color:#6b7280;font-size:13px;margin:0 0 4px;"
    value = "color:#111827;font-size:22px;font-weight:bold;margin:0;"
    if m["low_stock"]:
        rows = "".join(
            f'<tr><td style="padding:6px 8px;border-top:1px solid #f3c7c3;">{escape(s["item"])}</td>'
            f'<td style="padding:6px 8px;border-top:1px solid #f3c7c3;text-align:right;"><b>{s["remaining"]}</b></td>'
            f'<td style="padding:6px 8px;border-top:1px solid #f3c7c3;text-align:right;">{s["restock_level"]}</td></tr>'
            for s in m["low_stock"])
        restock = (
            '<div style="background:#fdecec;border:1px solid #f3c7c3;border-radius:10px;padding:14px 16px;margin-top:16px;">'
            f'<p style="margin:0 0 8px;color:#a42a2a;font-weight:bold;">&#9888; Restock needed: {len(m["low_stock"])} item(s)</p>'
            '<table style="border-collapse:collapse;width:100%;font-size:14px;color:#5b1a1a;">'
            '<tr><th style="text-align:left;padding:6px 8px;">Item</th><th style="text-align:right;padding:6px 8px;">Left</th>'
            f'<th style="text-align:right;padding:6px 8px;">Restock at</th></tr>{rows}</table></div>')
    else:
        restock = ('<div style="background:#e9f5ec;border:1px solid #bfe3c9;border-radius:10px;padding:14px 16px;'
                   'margin-top:16px;color:#24603a;font-weight:bold;">&#10003; All items are above their restock level.</div>')
    item_rows = "".join(
        f'<tr><td style="padding:6px 8px;border-top:1px solid #eef0f3;">{escape(i)}</td>'
        f'<td style="padding:6px 8px;border-top:1px solid #eef0f3;text-align:right;">{m["qty_by_item"][i]}</td>'
        f'<td style="padding:6px 8px;border-top:1px solid #eef0f3;text-align:right;">{kes(m["revenue_by_item"][i])}</td></tr>'
        for i in m["items"])
    return f"""<!DOCTYPE html>
<html><body style="margin:0;background:#f4f5f7;font-family:Arial,Helvetica,sans-serif;">
<div style="max-width:560px;margin:0 auto;padding:20px;">
  <h2 style="color:#1f4e79;margin:0 0 4px;">{escape(SHOP_NAME)}: Daily Sales Summary</h2>
  <p style="color:#6b7280;margin:0 0 16px;">{day:%A %d %B %Y}</p>
  <table role="presentation" style="width:100%;border-collapse:separate;border-spacing:8px;margin:0 -8px;">
    <tr>
      <td style="{card}"><p style="{label}">Total revenue</p><p style="{value}">{kes(m["revenue"])}</p></td>
      <td style="{card}"><p style="{label}">Transactions</p><p style="{value}">{m["transactions"]}</p></td>
    </tr>
    <tr>
      <td style="{card}" colspan="2"><p style="{label}">Top-selling item</p>
        <p style="{value}">{escape(m["top_item"])}</p>
        <p style="color:#374151;font-size:14px;margin:4px 0 0;">{m["top_qty"]} sold &middot; {kes(m["top_revenue"])}</p></td>
    </tr>
  </table>
  {restock}
  <h3 style="color:#1f4e79;font-size:15px;margin:20px 0 6px;">All items sold today</h3>
  <table style="border-collapse:collapse;width:100%;font-size:14px;background:#fff;border:1px solid #e3e6ea;">
    <tr style="background:#1f4e79;color:#fff;"><th style="text-align:left;padding:8px;">Item</th>
      <th style="text-align:right;padding:8px;">Qty</th><th style="text-align:right;padding:8px;">Revenue</th></tr>
    {item_rows}
  </table>
  <p style="color:#9ca3af;font-size:12px;margin-top:16px;">Sent automatically at {datetime.now():%H:%M}.</p>
</div></body></html>"""


def build_text(m, day):
    """Plain-text version for phones and email apps that don't show HTML."""
    lines = [f"{SHOP_NAME}: Daily Sales Summary, {day:%A %d %B %Y}", "",
             f"Total revenue:   {kes(m['revenue'])}",
             f"Transactions:    {m['transactions']}",
             f"Top-selling:     {m['top_item']} ({m['top_qty']} sold, {kes(m['top_revenue'])})", ""]
    if m["low_stock"]:
        lines.append("RESTOCK NEEDED:")
        lines += [f"  - {s['item']}: {s['remaining']} left (restock at {s['restock_level']})" for s in m["low_stock"]]
    else:
        lines.append("All items are above their restock level.")
    return "\n".join(lines)


def build_message(m, day, sender, recipient):
    msg = EmailMessage()
    alert = f" | {len(m['low_stock'])} to restock" if m["low_stock"] else ""
    msg["Subject"] = f"Daily sales {day:%d %b}: {kes(m['revenue'])}, {m['transactions']} sales{alert}"
    msg["From"] = f"{SHOP_NAME} Reports <{sender}>"
    msg["To"] = recipient
    msg.set_content(build_text(m, day))
    msg.add_alternative(build_html(m, day), subtype="html")
    return msg


def send(msg):
    sender = os.getenv("GMAIL_ADDRESS", "").strip()
    password = os.getenv("GMAIL_APP_PASSWORD", "").replace(" ", "").strip()   # App Passwords work with or without spaces
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context(), timeout=30) as server:
            server.login(sender, password)
            server.send_message(msg)
    except smtplib.SMTPAuthenticationError:
        raise ReportError("Gmail rejected the login. Check GMAIL_ADDRESS and GMAIL_APP_PASSWORD in .env - "
                          "it must be a 16-character App Password, not your normal Gmail password.")
    except smtplib.SMTPRecipientsRefused:
        raise ReportError(f"Gmail refused the recipient address '{msg['To']}'. Check REPORT_TO in .env.")
    except (smtplib.SMTPException, OSError) as err:
        raise ReportError(f"Couldn't send the email ({type(err).__name__}). Check the internet connection.")


# ---------------------------------------------------------------- main

def main():
    parser = argparse.ArgumentParser(description="Email today's sales summary.")
    parser.add_argument("--preview", action="store_true", help="save preview.html instead of sending")
    args = parser.parse_args()
    day = datetime.now()
    try:
        sales, skipped = load_sales()
        metrics = calculate(sales, load_stock())
        if skipped:
            print(f"Note: skipped {len(skipped)} unreadable row(s) in sales.csv (line {', '.join(map(str, skipped))}).")

        print(build_text(metrics, day), "\n")
        if args.preview:
            PREVIEW_FILE.write_text(build_html(metrics, day), encoding="utf-8")
            print(f"Preview saved to {PREVIEW_FILE.name} - open it in your browser. Nothing was sent.")
            return

        sender, recipient = os.getenv("GMAIL_ADDRESS", "").strip(), os.getenv("REPORT_TO", "").strip()
        if not sender or not os.getenv("GMAIL_APP_PASSWORD") or not recipient:
            raise ReportError("Add GMAIL_ADDRESS, GMAIL_APP_PASSWORD and REPORT_TO to the .env file.")
        send(build_message(metrics, day, sender, recipient))
        print(f"Sent to {recipient}")
        logging.info("SENT to %s | revenue %s | %s transactions | %s low-stock",
                     recipient, kes(metrics["revenue"]), metrics["transactions"], len(metrics["low_stock"]))
    except ReportError as err:
        logging.error("FAILED | %s", err)
        sys.exit(f"Sorry: {err}")


if __name__ == "__main__":
    main()
