const API_URL = "http://localhost:8000/api";

// Helper to get the auth header
function getAuthHeader() {
  const token = localStorage.getItem('access_token');
  return {
    "Content-Type": "application/json",
    "Authorization": token ? `Bearer ${token}` : ""
  };
}

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

export async function loginUser(credentials: any) {
  const res = await fetch(`${API_URL}/auth/pair`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ 
      email: credentials.email,
      password: credentials.password 
    }),
  });
  
  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    throw new Error(errorData?.detail || "Invalid email or password");
  }
  
  return res.json();
}

// --- Family Member API ---

export async function fetchFamilyMembers() {
  const res = await fetch(`${API_URL}/users/members`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) {
    if (res.status === 401) throw new Error("Unauthorized");
    throw new Error("Failed to fetch family members");
  }
  return res.json();
}

export async function createFamilyMember(data: any) {
  const res = await fetch(`${API_URL}/users/members`, {
    method: "POST",
    headers: getAuthHeader(),
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    throw new Error(errorData?.detail || "Failed to create family member");
  }
  return res.json();
}

export async function updateFamilyMember(id: number, data: any) {
  const res = await fetch(`${API_URL}/users/members/${id}`, {
    method: "PUT",
    headers: getAuthHeader(),
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    throw new Error(errorData?.detail || "Failed to update family member");
  }
  return res.json();
}

export async function deleteFamilyMember(id: number) {
  const res = await fetch(`${API_URL}/users/members/${id}`, {
    method: "DELETE",
    headers: getAuthHeader(),
  });
  if (!res.ok) throw new Error("Failed to delete family member");
  return res.json();
}
