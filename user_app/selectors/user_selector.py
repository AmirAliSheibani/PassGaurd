from django.contrib.auth import get_user_model

User = get_user_model()

class UserSelector:

    @classmethod
    def get_by_id(cls, *, user_id: int) -> User:
        return User.objects.get(pk=user_id)

    @classmethod
    def get_by_username(cls, *, username: str) -> User:
        return User.objects.get(username__iexact=username)

    @classmethod
    def get_by_id_if_active(cls, *, user_id: int) -> User:
        return User.objects.get(pk=user_id, is_active=True)

    @classmethod
    def exist_by_username(cls, *, username: str) -> bool:
        return User.objects.filter(username__iexact=username).exists()