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

    def __str__(self):
        return self.email
