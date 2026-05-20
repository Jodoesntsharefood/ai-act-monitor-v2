import json
    new_set = set(json.dumps(i, ensure_ascii=False) for i in new)

    added = new_set - old_set
    removed = old_set - new_set

    lines = []

    if added:
        lines.append("新增或变更:\n")
        for item in added:
            lines.append(item)

    if removed:
        lines.append("\n删除或旧状态:\n")
        for item in removed:
            lines.append(item)

    return "\n".join(lines)



def send_email(subject, body):
    msg = MIMEMultipart()
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(msg)



def main():
    current = fetch_current_status()
    previous = load_previous_status()

    if previous is None:
        print("首次运行，保存初始数据")
        save_status(current)
        return

    if current != previous:
        print("检测到变化，发送邮件")

        diff = generate_diff(previous, current)

        send_email(
            subject="AI Act Standards 状态变化通知",
            body=diff,
        )

        save_status(current)
    else:
        print("没有变化")


if __name__ == "__main__":
    main()
