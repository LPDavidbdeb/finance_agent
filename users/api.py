from ninja import Router
from django.db import transaction
from django.shortcuts import get_object_or_404
from ninja_jwt.authentication import JWTAuth
from typing import List
from .schemas import RegisterUserIn, FamilyMemberOut, FamilyMemberIn, FamilyMemberUpdate
from .models import Family, CustomUser, FamilyMember

router = Router()

@router.post("/register", auth=None)
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

@router.get("/members", response=List[FamilyMemberOut], auth=JWTAuth())
def list_family_members(request):
    """List all family members for the authenticated user's family."""
    user = request.auth
    return FamilyMember.objects.filter(family=user.family)

@router.post("/members", response=FamilyMemberOut, auth=JWTAuth())
def create_family_member(request, payload: FamilyMemberIn):
    """Create a new family member linked to the authenticated user's family."""
    user = request.auth
    
    member = FamilyMember.objects.create(
        family=user.family,
        **payload.dict()
    )
    return member

@router.get("/members/{member_id}", response=FamilyMemberOut, auth=JWTAuth())
def get_family_member(request, member_id: int):
    """Get a specific family member."""
    user = request.auth
    member = get_object_or_404(FamilyMember, id=member_id, family=user.family)
    return member

@router.put("/members/{member_id}", response=FamilyMemberOut, auth=JWTAuth())
def update_family_member(request, member_id: int, payload: FamilyMemberUpdate):
    """Update a specific family member."""
    user = request.auth
    member = get_object_or_404(FamilyMember, id=member_id, family=user.family)
    
    for attr, value in payload.dict(exclude_unset=True).items():
        setattr(member, attr, value)
    
    member.save()
    return member

@router.delete("/members/{member_id}", auth=JWTAuth())
def delete_family_member(request, member_id: int):
    """Delete a specific family member."""
    user = request.auth
    member = get_object_or_404(FamilyMember, id=member_id, family=user.family)
    member.delete()
    return {"success": True}
