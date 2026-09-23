from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from books.models import Book
from borrowings.models import Borrowing
from borrowings.tasks import check_overdue_borrowings

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

    @patch("borrowings.views.send_telegram_message")
    def test_create_borrowing_as_staff(self, mock_send_telegram_message):
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

        mock_send_telegram_message.assert_called_once()

    @patch("borrowings.views.create_payment_session")
    @patch("borrowings.views.send_telegram_message")
    def test_create_borrowing(
            self,
            mock_send_telegram_message,
            mock_create_payment_session,
    ):
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

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.book.refresh_from_db()
        self.assertEqual(self.book.inventory, 4)

        self.assertEqual(
            Borrowing.objects.filter(user=self.user).count(),
            2,
        )

        mock_create_payment_session.assert_called_once()
        mock_send_telegram_message.assert_called_once()

    def test_regular_user_sees_only_own_borrowings(self):
        another_user = User.objects.create_user(
            username="anotheruser",
            email="another@example.com",
            password="TestPassword123!",
        )

        Borrowing.objects.create(
            borrow_date=date(2026, 9, 20),
            expected_return_date=date(2026, 9, 27),
            book=self.book,
            user=another_user,
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/borrowings/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["user"], self.user.id)

    def test_filter_active_borrowings(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            "/api/borrowings/?is_active=true"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_filter_inactive_borrowings(self):
        self.borrowing.actual_return_date = date(2026, 9, 25)
        self.borrowing.save()

        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            "/api/borrowings/?is_active=false"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_admin_can_filter_by_user_id(self):
        admin = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="AdminPassword123!",
        )

        another_user = User.objects.create_user(
            username="anotheruser",
            email="another@example.com",
            password="TestPassword123!",
        )

        Borrowing.objects.create(
            borrow_date=date(2026, 9, 20),
            expected_return_date=date(2026, 9, 27),
            book=self.book,
            user=another_user,
        )

        self.client.force_authenticate(user=admin)

        response = self.client.get(
            f"/api/borrowings/?user_id={another_user.id}"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            response.data[0]["user"],
            another_user.id,
        )

    def test_return_borrowing(self):
        self.client.force_authenticate(user=self.user)

        self.book.inventory = 4
        self.book.save()

        response = self.client.post(
            f"/api/borrowings/{self.borrowing.id}/return/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.borrowing.refresh_from_db()
        self.book.refresh_from_db()

        self.assertIsNotNone(self.borrowing.actual_return_date)
        self.assertEqual(self.book.inventory, 5)

    def test_cannot_return_borrowing_twice(self):
        self.client.force_authenticate(user=self.user)

        self.client.post(
            f"/api/borrowings/{self.borrowing.id}/return/",
            {},
            format="json",
        )

        response = self.client.post(
            f"/api/borrowings/{self.borrowing.id}/return/",
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )


class OverdueBorrowingTaskTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="overdueuser",
            email="overdue@example.com",
            password="TestPassword123!",
        )

        self.book = Book.objects.create(
            title="Overdue Book",
            author="Test Author",
            cover="HARD",
            inventory=5,
            daily_fee="2.50",
        )

    @patch("borrowings.tasks.send_telegram_message")
    def test_check_overdue_borrowings(self, mock_send_telegram_message):
        Borrowing.objects.create(
            borrow_date=date(2026, 9, 1),
            expected_return_date=date(2026, 9, 20),
            actual_return_date=None,
            book=self.book,
            user=self.user,
        )

        result = check_overdue_borrowings()

        self.assertEqual(result, 1)
        mock_send_telegram_message.assert_called_once()
