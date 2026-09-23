from django.conf import settings
from django.db import transaction
from django.utils import timezone

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from books.models import Book
from borrowings.models import Borrowing
from borrowings.serializers import (
    BorrowingSerializer,
    CreateBorrowingSerializer,
)
from notifications.telegram import send_telegram_message
from payments.models import Payment
from payments.stripe import create_payment_session


class BorrowingViewSet(viewsets.ModelViewSet):
    serializer_class = BorrowingSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        queryset = Borrowing.objects.all()

        if not self.request.user.is_staff:
            queryset = queryset.filter(user=self.request.user)
        else:
            user_id = self.request.query_params.get("user_id")

            if user_id:
                queryset = queryset.filter(user_id=user_id)

        is_active = self.request.query_params.get("is_active")

        if is_active is not None:
            if is_active.lower() == "true":
                queryset = queryset.filter(
                    actual_return_date__isnull=True
                )
            elif is_active.lower() == "false":
                queryset = queryset.filter(
                    actual_return_date__isnull=False
                )

        return queryset

    def get_serializer_class(self):
        if self.action == "create":
            return CreateBorrowingSerializer

        return BorrowingSerializer

    @transaction.atomic
    def perform_create(self, serializer):
        book = Book.objects.select_for_update().get(
            pk=serializer.validated_data["book"].pk
        )

        if book.inventory == 0:
            raise ValidationError(
                {"book": "This book is not available."}
            )

        book.inventory -= 1
        book.save(update_fields=["inventory"])

        borrowing = serializer.save(user=self.request.user)

        payment = Payment.objects.create(
            status=Payment.Status.PENDING,
            type=Payment.Type.PAYMENT,
            borrowing=borrowing,
            money_to_pay=(
                borrowing.book.daily_fee
                * (
                    borrowing.expected_return_date
                    - borrowing.borrow_date
                ).days
            ),
        )

        create_payment_session(payment)

        send_telegram_message(
            f"📚 New borrowing created!\n"
            f"User: {self.request.user.email}\n"
            f"Book: {book.title}\n"
            f"Expected return: "
            f"{borrowing.expected_return_date}"
        )

    @action(detail=True, methods=["post"], url_path="return")
    @transaction.atomic
    def return_borrowing(self, request, pk=None):
        borrowing = self.get_object()

        if borrowing.actual_return_date is not None:
            return Response(
                {
                    "detail": (
                        "This borrowing has already been returned."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        actual_return_date = timezone.now().date()
        borrowing.actual_return_date = actual_return_date
        borrowing.save(update_fields=["actual_return_date"])

        borrowing.book.inventory += 1
        borrowing.book.save(update_fields=["inventory"])

        if actual_return_date > borrowing.expected_return_date:
            overdue_days = (
                actual_return_date
                - borrowing.expected_return_date
            ).days

            money_to_pay = (
                borrowing.book.daily_fee
                * overdue_days
                * settings.FINE_MULTIPLIER
            )

            payment = Payment.objects.create(
                status=Payment.Status.PENDING,
                type=Payment.Type.FINE,
                borrowing=borrowing,
                money_to_pay=money_to_pay,
            )

            create_payment_session(payment)

        return Response(
            BorrowingSerializer(borrowing).data,
            status=status.HTTP_200_OK,
        )
