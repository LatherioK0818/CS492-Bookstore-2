from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from rest_framework.permissions import IsAuthenticated
from .models import Book, Order, CustomUser
from .serializers import BookSerializer, OrderSerializer, RegistrationSerializer,  CustomUserSerializer


# ✅ Custom permission: only staff can write, everyone can read
class IsStaffOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated and request.user.is_staff


# ✅ ViewSet for managing books
class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.all()
    serializer_class = BookSerializer
    permission_classes = [IsStaffOrReadOnly]

    @action(detail=True, methods=['post'], url_path='restock')
    def restock(self, request, pk=None):
        if not request.user.is_staff:
            return Response({'error': 'Only staff can restock books.'}, status=status.HTTP_403_FORBIDDEN)

        book = self.get_object()
        quantity = request.data.get('quantity')

        try:
            quantity = int(quantity)
            if quantity <= 0:
                raise ValueError("Quantity must be positive.")
        except (ValueError, TypeError):
            return Response({'error': 'Invalid quantity'}, status=status.HTTP_400_BAD_REQUEST)

        book.quantity += quantity
        book.save()
        return Response({'message': f"Restocked {quantity} units of '{book.title}'."})


# ✅ ViewSet for managing orders
class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    ordering_fields = ['created_at', 'status']
    search_fields = ['status']

    def get_queryset(self):
        user = self.request.user
        queryset = Order.objects.all() if user.is_staff else Order.objects.filter(customer=user)

        # Add optional status filtering
        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)

        return queryset

    def perform_create(self, serializer):
        serializer.save(customer=self.request.user)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_current_user(request):
    serializer = CustomUserSerializer(request.user)
    return Response(serializer.data)


# ✅ Registration endpoint
@api_view(['POST'])
def register_user(request):
    serializer = RegistrationSerializer(data=request.data)
    if serializer.is_valid():
        try:
            user = CustomUser.objects.create_user(  # Use CustomUser here
                username=serializer.validated_data['username'],
                email=serializer.validated_data['email'],
                password=serializer.validated_data['password']
            )
            return Response({'message': 'User registered successfully'}, status=status.HTTP_201_CREATED)
        except IntegrityError as e:
            if "UNIQUE constraint failed: inventory_customuser.username" in str(e):
                return Response({'error': 'This username is already taken.'}, status=status.HTTP_400_BAD_REQUEST)
            elif "UNIQUE constraint failed: inventory_customuser.email" in str(e):
                return Response({'error': 'This email address is already registered.'}, status=status.HTTP_400_BAD_REQUEST)
            else:
                # Log the full error for debugging
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Unhandled IntegrityError during registration: {e}")
                return Response({'error': 'Registration failed due to a database error.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)