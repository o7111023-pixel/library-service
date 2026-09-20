from django.db import transaction
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
                queryset = queryset.filter(actual_return_date__isnull=True)
            elif is_active.lower() == "false":
                queryset = queryset.filter(actual_return_date__isnull=False)

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

        serializer.save(user=self.request.user)

    @action(
        detail=True,
        methods=["post"],
        url_path="return",
    )
    @transaction.atomic
    def return_borrowing(self, request, pk=None):
        borrowing = self.get_object()

        if borrowing.actual_return_date is not None:
            return Response(
                {"detail": "This borrowing has already been returned."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        borrowing.actual_return_date = request.data.get(
            "actual_return_date"
        )

        if borrowing.actual_return_date is None:
            from django.utils import timezone

            borrowing.actual_return_date = timezone.now().date()

        borrowing.save(update_fields=["actual_return_date"])

        borrowing.book.inventory += 1
        borrowing.book.save(update_fields=["inventory"])

        return Response(
            BorrowingSerializer(borrowing).data,
            status=status.HTTP_200_OK,
        )
