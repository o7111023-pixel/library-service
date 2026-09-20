from django.db import models

from borrowings.models import Borrowing


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PAID = "PAID", "Paid"

    class Type(models.TextChoices):
        PAYMENT = "PAYMENT", "Payment"
        FINE = "FINE", "Fine"

    status = models.CharField(
        max_length=7,
        choices=Status.choices,
        default=Status.PENDING,
    )
    type = models.CharField(
        max_length=7,
        choices=Type.choices,
    )
    borrowing = models.ForeignKey(
        Borrowing,
        on_delete=models.CASCADE,
        related_name="payments",
    )
    session_url = models.URLField(
        blank=True,
        null=True,
    )
    session_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )
    money_to_pay = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    def __str__(self):
        return f"{self.type} - {self.money_to_pay}"
