from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from payments.models import Payment
from payments.serializers import PaymentSerializer
from payments.stripe import create_stripe_session
from rest_framework.views import APIView


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = (IsAuthenticated,)
    queryset = Payment.objects.all()

    @action(detail=True, methods=["post"], url_path="create-session")
    def create_session(self, request, pk=None):
        payment = self.get_object()

        session = create_stripe_session(payment)

        return Response(
            {
                "session_id": session.id,
                "session_url": session.url,
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
