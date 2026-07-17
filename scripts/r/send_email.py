import argparse

from utils.email import send_email


def _main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--to", required=True)
    parser.add_argument("-s", "--subject", required=True)
    parser.add_argument("--body-file", required=True)
    parser.add_argument("--use-gmail-web", action="store_true")

    args = parser.parse_args()

    with open(args.body_file, "r", encoding="utf-8") as f:
        body = f.read()

    send_email(
        to=args.to,
        subject=args.subject,
        body=body,
        use_gmail_web=args.use_gmail_web,
    )


if __name__ == "__main__":
    _main()
