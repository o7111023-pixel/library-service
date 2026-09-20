from datetime import date

from celery import shared_task

from borrowings.models import Borrowing
from notifications.telegram import send_telegram_message


@shared_task
def check_overdue_borrowings():
    overdue_borrowings = Borrowing.objects.filter(
        expected_return_date__lt=date.today(),
        actual_return_date__isnull=True,
    )

    for borrowing in overdue_borrowings:
        send_telegram_message(
            f"⚠️ Overdue borrowing!\n"
            f"User: {borrowing.user.email}\n"
            f"Book: {borrowing.book.title}\n"
            f"Expected return: {borrowing.expected_return_date}"
        )

    return overdue_borrowings.count()
