from utils.email import send_email

if __name__ == "__main__":
    send_email(
        to="example@example.com",
        subject="Email Title",
        body="This is the main body of the email.",
    )
