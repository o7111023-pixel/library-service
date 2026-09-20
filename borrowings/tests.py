from datetime import date

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from books.models import Book
from borrowings.models import Borrowing

User = get_user_model()


class BorrowingListDetailTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="TestPassword123!",
        )

        self.book = Book.objects.create(
            title="Test Book",
            author="Test Author",
            cover="HARD",
            inventory=5,
            daily_fee="2.50",
        )

        self.borrowing = Borrowing.objects.create(
            borrow_date=date(2026, 9, 20),
            expected_return_date=date(2026, 9, 27),
            book=self.book,
            user=self.user,
        )

    def test_borrowing_list(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/borrowings/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_borrowing_detail(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/borrowings/{self.borrowing.id}/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.borrowing.id)

    def test_create_borrowing(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/borrowings/",
            {
                "borrow_date": "2026-09-20",
                "expected_return_date": "2026-09-27",
                "book": self.book.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.book.refresh_from_db()
        self.assertEqual(self.book.inventory, 4)

        self.assertEqual(
            Borrowing.objects.filter(user=self.user).count(),
            2,
        )

    def test_create_borrowing_when_inventory_is_zero(self):
        self.client.force_authenticate(user=self.user)

        self.book.inventory = 0
        self.book.save()

        response = self.client.post(
            "/api/borrowings/",
            {
                "borrow_date": "2026-09-20",
                "expected_return_date": "2026-09-27",
                "book": self.book.id,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
