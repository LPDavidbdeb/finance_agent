from ninja import Router
from django.db import transaction
from .schemas import RegisterUserIn
from .models import Family, CustomUser

router = Router()

@router.post("/register")
def register_user(request, payload: RegisterUserIn):
    with transaction.atomic():
        # Step A: Create the Family
        family = Family.objects.create(name=payload.household_name)
        
        # Step B: Create the CustomUser
        user = CustomUser.objects.create_user(
            email=payload.email,
            password=payload.password,
            first_name=payload.first_name,
            last_name=payload.last_name,
            family=family
        )
        
    return {
        "status": "success",
        "message": "User and Household created successfully",
        "family_id": family.id,
        "user_id": user.id
    }