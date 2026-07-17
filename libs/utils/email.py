from typing import Optional
from urllib.parse import quote

from utils.shutil import shell_open
from utils.template import render_template


def send_email(
    to: str = "", subject: str = "", body: str = "", cc: str = "", use_gmail_web=False
):
    subject = quote(subject, safe="")
    body = body.replace("\r\n", "\n").replace("\n", "\r\n")
    body = quote(body, safe="")
    if use_gmail_web:
        url = f"https://mail.google.com/mail/?view=cm&fs=1&to={to}&su={subject}&body={body}&bcc={cc}"
    else:
        url = f"mailto:{to}?subject={subject}&body={body}"
    shell_open(url)


def send_email_md(
    file_path: Optional[str] = None,
    content: Optional[str] = None,
    to: str = "",
    context=None,
):
    if content is None:
        assert file_path is not None
        with open(file_path, "r", encoding="utf-8") as f:
            s = f.read()
            content = render_template(s, context=context)

    subject = ""
    cc = ""
    gmail = False
    body = ""

    i = 0
    lines = content.strip().splitlines()
    print(lines)
    if lines[0] == "---":
        i = 1
        while lines[i] != "---":
            if lines[i].strip() != "":
                k, v = lines[i].split(":", maxsplit=2)
                if k.lower() == "cc" or k.lower() == "bcc":
                    cc = v.strip().strip('"')
                elif k.lower() == "subject":
                    subject = v.strip()
                elif k.lower() == "to":
                    if not to:
                        to = v.strip().strip('"')
                elif k.lower() == "gmail":
                    gmail = True
            i += 1
        i += 1

    while lines[i].strip() == "":  # skip empty lines
        i += 1

    while i < len(lines):
        body += lines[i] + "\n"
        i += 1

    print("body:", body)

    send_email(
        body=body,
        cc=cc,
        use_gmail_web=gmail,
        subject=subject,
        to=to,
    )
