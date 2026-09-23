from django.utils import timezone
from django.conf import settings
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from borrowings.models import Borrowing
from payments.models import Payment
from payments.serializers import PaymentSerializer
from payments.stripe import create_payment_session


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = (IsAuthenticated,)
    queryset = Payment.objects.all()

    @action(detail=True, methods=["post"], url_path="create-session")
    def create_session(self, request, pk=None):
        payment = self.get_object()

        session = create_payment_session(payment)

        return Response(
            {
                "session_id": session.id,
                "session_url": session.url,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["post"], url_path="create-fine")
    def create_fine(self, request):
        borrowing_id = request.data.get("borrowing_id")

        try:
            borrowing = Borrowing.objects.get(
                id=borrowing_id,
                user=request.user,
            )
        except Borrowing.DoesNotExist:
            raise ValidationError(
                {"borrowing_id": "Borrowing not found."}
            )

        if borrowing.actual_return_date is not None:
            raise ValidationError(
                {"borrowing": "This borrowing is already returned."}
            )

        today = timezone.now().date()

        if borrowing.expected_return_date >= today:
            raise ValidationError(
                {"borrowing": "This borrowing is not overdue."}
            )

        overdue_days = (
            today - borrowing.expected_return_date
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

        session = create_payment_session(payment)

        return Response(
            {
                "payment_id": payment.id,
                "session_id": session.id,
                "session_url": session.url,
                "money_to_pay": payment.money_to_pay,
            },
            status=status.HTTP_201_CREATED,
        )


class PaymentSuccessView(APIView):
    def get(self, request):
        return Response(
            {"message": "Payment successful."},
            status=status.HTTP_200_OK,
        )


class PaymentCancelView(APIView):
    def get(self, request):
        return Response(
            {"message": "Payment cancelled."},
            status=status.HTTP_200_OK,
        )
