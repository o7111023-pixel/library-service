from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase
from unittest.mock import patch, Mock

from books.models import Book
from borrowings.models import Borrowing
from payments.models import Payment

User = get_user_model()


class PaymentListDetailTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="paymentuser",
            email="payment@example.com",
            password="TestPassword123!",
        )

        self.book = Book.objects.create(
            title="Payment Book",
            author="Test Author",
            cover="HARD",
            inventory=5,
            daily_fee="2.50",
        )

        self.borrowing = Borrowing.objects.create(
            borrow_date="2026-09-21",
            expected_return_date="2026-09-28",
            book=self.book,
            user=self.user,
        )

        self.payment = Payment.objects.create(
            status=Payment.Status.PENDING,
            type=Payment.Type.PAYMENT,
            borrowing=self.borrowing,
            money_to_pay=Decimal("17.50"),
        )

    def test_payment_list(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/payments/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.payment.id)

    def test_payment_detail(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/payments/{self.payment.id}/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.payment.id)

    @patch("payments.stripe.stripe.checkout.Session.create")
    def test_create_stripe_session(self, mock_create_session):
        mock_session = Mock()
        mock_session.id = "cs_test_123"
        mock_session.url = "https://checkout.stripe.com/test"
        mock_create_session.return_value = mock_session

        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            f"/api/payments/{self.payment.id}/create-session/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            response.data["session_id"],
            "cs_test_123",
        )

        self.assertEqual(
            response.data["session_url"],
            "https://checkout.stripe.com/test",
        )

        self.payment.refresh_from_db()

        self.assertEqual(
            self.payment.session_id,
            "cs_test_123",
        )

        self.assertEqual(
            self.payment.session_url,
            "https://checkout.stripe.com/test",
        )

        mock_create_session.assert_called_once()
