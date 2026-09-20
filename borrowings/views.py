from django.db import transaction
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from books.models import Book
from borrowings.models import Borrowing
from borrowings.serializers import (
    BorrowingSerializer,
    CreateBorrowingSerializer,
)


class BorrowingViewSet(viewsets.ModelViewSet):
    queryset = Borrowing.objects.all()
    permission_classes = (IsAuthenticated,)

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
            from rest_framework.exceptions import ValidationError

            raise ValidationError(
                {"book": "This book is not available."}
            )

        book.inventory -= 1
        book.save(update_fields=["inventory"])

        serializer.save(user=self.request.user)
