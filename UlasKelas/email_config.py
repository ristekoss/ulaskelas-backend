def resolve_notification_recipients(recipient_list, legacy_recipient):
    recipients = [recipient for recipient in recipient_list if recipient]
    if recipients:
        return recipients
    return [legacy_recipient] if legacy_recipient else []
