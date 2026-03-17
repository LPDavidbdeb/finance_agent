const API_URL = "http://localhost:8000/api";

export async function fetchAccountTree() {
  const res = await fetch(`${API_URL}/accounts/tree`);
  if (!res.ok) throw new Error("Failed to fetch account tree");
  return res.json();
}

export async function deleteAccount(id: number) {
  const res = await fetch(`${API_URL}/accounts/${id}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("Failed to delete account");
  return res.json();
}

export async function moveAccount(accountId: number, targetParentId: number) {
  const res = await fetch(`${API_URL}/accounts/${accountId}/move`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ target_parent_id: targetParentId }),
  });
  if (!res.ok) throw new Error("Failed to move account");
  return res.json();
}

export async function registerHousehold(data: any) {
  const res = await fetch(`${API_URL}/users/register`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    throw new Error(errorData?.message || "Registration failed");
  }
  return res.json();
}
