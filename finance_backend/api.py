from ninja import NinjaAPI, Router
from accounting.models import Account
from django.shortcuts import get_object_or_404

api = NinjaAPI()

auth_router = Router()

@auth_router.post("/login")
def login(request):
    return {"message": "login mocked"}

@auth_router.post("/logout")
def logout(request):
    return {"message": "logout mocked"}

@auth_router.get("/me")
def me(request):
    return {"message": "me mocked"}

api.add_router("/auth/", auth_router)

@api.get("/accounts/tree")
def accounts_tree(request):
    def get_children(node):
        return {
            "id": node.id,
            "name": node.name,
            "account_type": node.account_type,
            "children": [get_children(child) for child in node.get_children()]
        }
    
    root_nodes = Account.objects.filter(parent__isnull=True)
    return [get_children(node) for node in root_nodes]
