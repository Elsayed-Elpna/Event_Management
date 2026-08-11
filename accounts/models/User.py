from django.db import models
from django.contrib.auth.models import AbstractUser

from common.models import BaseModel
from ..managers import UserManager

# Create your models here.


class User(BaseModel, AbstractUser):
    username = None
    email = models.EmailField(unique=True, db_index=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = UserManager()

    is_event_maker = models.BooleanField(default=False)

    def __str__(self):
        return self.email
