from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class UserTests(APITestCase):
    def test_user_registration(self):
        response = self.client.post(
            "/api/register/",
            {
                "username": "newuser",
                "email": "newuser@example.com",
                "first_name": "New",
                "last_name": "User",
                "password": "TestPassword123!",
            },
            format="json",
        )

        print(response.data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_password_is_hashed(self):
        user = User.objects.create_user(
            username="hasheduser",
            email="hashed@example.com",
            password="TestPassword123!",
        )

        self.assertNotEqual(
            user.password,
            "TestPassword123!",
        )

    def test_user_list(self):
        User.objects.create_user(
            username="listuser",
            email="list@example.com",
            password="TestPassword123!",
        )

        response = self.client.get("/api/users/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
