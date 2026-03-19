const API_URL = "http://localhost:8000/api";

// Helper to get the auth header
function getAuthHeader() {
  const token = localStorage.getItem('access_token');
  return {
    "Content-Type": "application/json",
    "Authorization": token ? `Bearer ${token}` : ""
  };
}

// --- Accounting API ---

export async function fetchSpendingEvolution(startDate: string, endDate: string, interval: string) {
  const res = await fetch(`${API_URL}/accounting/spending-evolution?start_date=${startDate}&end_date=${endDate}&interval=${interval}`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) throw new Error("Failed to fetch spending evolution");
  return res.json();
}

export async function fetchSpendingByCategory(startDate: string, endDate: string) {
  const res = await fetch(`${API_URL}/accounting/spending-by-category?start_date=${startDate}&end_date=${endDate}`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) throw new Error("Failed to fetch spending by category");
  return res.json();
}

export async function fetchAnnualStatements(year: number) {
  const res = await fetch(`${API_URL}/accounting/annual-statements?year=${year}`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) throw new Error("Failed to fetch annual statements");
  return res.json();
}

export async function fetchDimensionDetail(slug: string, year: number) {
  const res = await fetch(`${API_URL}/accounting/reports/dimension/${slug}?year=${year}`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) throw new Error("Failed to fetch dimension breakdown");
  return res.json();
}

export async function fetchAccountDetail(id: number, year?: number) {
  const url = `${API_URL}/accounting/accounts/${id}${year ? `?year=${year}` : ''}`;
  const res = await fetch(url, {
    headers: getAuthHeader(),
  });
  if (!res.ok) {
    if (res.status === 401) throw new Error("Unauthorized");
    throw new Error("Failed to fetch account details");
  }
  return res.json();
}

export async function fetchAccountTree() {
  const res = await fetch(`${API_URL}/accounts/tree`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) throw new Error("Failed to fetch account tree");
  return res.json();
}

export async function deleteAccount(id: number) {
  const res = await fetch(`${API_URL}/accounts/${id}`, {
    method: "DELETE",
    headers: getAuthHeader(),
  });
  if (!res.ok) throw new Error("Failed to delete account");
  return res.json();
}

export async function moveAccount(accountId: number, targetParentId: number) {
  const res = await fetch(`${API_URL}/accounts/${accountId}/move`, {
    method: "PATCH",
    headers: getAuthHeader(),
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

export async function fetchFamilyMember(id: number) {
  const res = await fetch(`${API_URL}/users/members/${id}`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) {
    if (res.status === 401) throw new Error("Unauthorized");
    throw new Error("Failed to fetch family member");
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

// --- Banking API ---

export async function fetchInstitutions() {
  const res = await fetch(`${API_URL}/banking/institutions`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) {
    if (res.status === 401) throw new Error("Unauthorized");
    throw new Error("Failed to fetch institutions");
  }
  return res.json();
}

export async function createInstitution(data: any) {
  const res = await fetch(`${API_URL}/banking/institutions`, {
    method: "POST",
    headers: getAuthHeader(),
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    throw new Error(errorData?.detail || "Failed to create institution");
  }
  return res.json();
}

export async function updateInstitution(id: number, data: any) {
  const res = await fetch(`${API_URL}/banking/institutions/${id}`, {
    method: "PUT",
    headers: getAuthHeader(),
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    throw new Error(errorData?.detail || "Failed to update institution");
  }
  return res.json();
}

export async function deleteInstitution(id: number) {
  const res = await fetch(`${API_URL}/banking/institutions/${id}`, {
    method: "DELETE",
    headers: getAuthHeader(),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    // Explicitly catch the 400 protected error from Django
    if (res.status === 400) {
      throw new Error(errorData?.detail || "Cannot delete this institution because it is currently linked to one or more financial products.");
    }
    throw new Error("Failed to delete institution");
  }
  return res.json();
}

export async function fetchMemberProducts(memberId: number) {
  const res = await fetch(`${API_URL}/banking/products?owner_id=${memberId}`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) {
    if (res.status === 401) throw new Error("Unauthorized");
    throw new Error("Failed to fetch member products");
  }
  return res.json();
}

export async function fetchFinancialProduct(id: number) {
  const res = await fetch(`${API_URL}/banking/products/${id}`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) {
    if (res.status === 401) throw new Error("Unauthorized");
    throw new Error("Failed to fetch financial product");
  }
  return res.json();
}

export async function createFinancialProduct(data: any) {
  const res = await fetch(`${API_URL}/banking/products`, {
    method: "POST",
    headers: getAuthHeader(),
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    throw new Error(errorData?.detail || "Failed to create financial product");
  }
  return res.json();
}

export async function uploadStatement(productId: number, file: File, documentDate?: string) {
  const token = localStorage.getItem('access_token');
  const formData = new FormData();
  formData.append('file', file);
  if (documentDate) {
    formData.append('document_date', documentDate);
  }

  const res = await fetch(`${API_URL}/banking/products/${productId}/statements/upload`, {
    method: 'POST',
    headers: {
      Authorization: token ? `Bearer ${token}` : '',
    },
    body: formData,
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    if (res.status === 401) throw new Error('Unauthorized');
    throw new Error(errorData?.detail || 'Failed to upload statement');
  }

  return res.json();
}

export async function fetchProductStatements(productId: number) {
  const res = await fetch(`${API_URL}/banking/products/${productId}/statements`, {
    headers: getAuthHeader(),
  });

  if (!res.ok) {
    if (res.status === 401) throw new Error('Unauthorized');
    throw new Error('Failed to fetch statements');
  }

  return res.json();
}

export async function deleteStatementImport(importId: number) {
  const res = await fetch(`${API_URL}/banking/imports/${importId}`, {
    method: "DELETE",
    headers: getAuthHeader(),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    if (res.status === 401) throw new Error("Unauthorized");
    throw new Error(errorData?.detail || "Failed to delete statement import");
  }

  return res.json();
}

export async function fetchStatementMonths(productId: number) {
  const res = await fetch(`${API_URL}/banking/products/${productId}/statement-months`, {
    headers: getAuthHeader(),
  });

  if (!res.ok) {
    if (res.status === 401) throw new Error('Unauthorized');
    throw new Error('Failed to fetch statement months');
  }

  return res.json();
}

export async function fetchStatementTransactions(productId: number, year: number, month: number) {
  const res = await fetch(`${API_URL}/banking/products/${productId}/statements/${year}/${month}/transactions`, {
    headers: getAuthHeader(),
  });

  if (!res.ok) {
    if (res.status === 401) throw new Error('Unauthorized');
    throw new Error('Failed to fetch statement transactions');
  }

  return res.json();
}

// --- Categorization API ---

export async function fetchMerchants() {
  const res = await fetch(`${API_URL}/categorization/merchants`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) {
    if (res.status === 401) throw new Error("Unauthorized");
    throw new Error("Failed to fetch merchants");
  }
  return res.json();
}

export async function fetchMerchantDetail(id: number) {
  const res = await fetch(`${API_URL}/categorization/merchants/${id}`, {
    headers: getAuthHeader(),
  });
  if (!res.ok) {
    if (res.status === 401) throw new Error("Unauthorized");
    throw new Error("Failed to fetch merchant details");
  }
  return res.json();
}

export async function updateMerchant(id: number, data: { name?: string; default_account_id?: number; is_unique_provider?: boolean; update_history?: boolean }) {
  const res = await fetch(`${API_URL}/categorization/merchants/${id}`, {
    method: "PATCH",
    headers: getAuthHeader(),
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    throw new Error(errorData?.detail || "Failed to update merchant");
  }
  return res.json();
}

export async function mergeMerchants(targetId: number, sourceIds: number[]) {
  const res = await fetch(`${API_URL}/categorization/merchants/merge`, {
    method: "POST",
    headers: getAuthHeader(),
    body: JSON.stringify({ target_id: targetId, source_ids: sourceIds }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    throw new Error(errorData?.detail || "Failed to merge merchants");
  }
  return res.json();
}

export async function updateMerchantAccount(merchantId: number, accountId: number) {
  const res = await fetch(`${API_URL}/categorization/merchants/${merchantId}`, {
    method: "PATCH",
    headers: getAuthHeader(),
    body: JSON.stringify({ default_account_id: accountId }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    throw new Error(errorData?.detail || "Failed to update merchant category");
  }
  return res.json();
}

export async function createAndApplyRule(data: {
  search_text: string;
  merchant_name: string;
  target_account_id?: number;
  is_unique_provider?: boolean;
  institution_id?: number;
}) {
  const res = await fetch(`${API_URL}/categorization/create-and-apply`, {
    method: "POST",
    headers: getAuthHeader(),
    body: JSON.stringify(data),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    if (res.status === 401) throw new Error("Unauthorized");
    throw new Error(errorData?.detail || "Failed to create and apply rule");
  }

  return res.json();
}

export async function fetchStagedTransactions(productId: number) {
  const res = await fetch(`${API_URL}/banking/products/${productId}/staged-transactions`, {
    headers: getAuthHeader(),
  });

  if (!res.ok) {
    if (res.status === 401) throw new Error('Unauthorized');
    throw new Error('Failed to fetch staged transactions');
  }

  return res.json();
}

export async function approveTransaction(productId: number, transactionId: number, targetAccountId: number) {
  const res = await fetch(`${API_URL}/banking/products/${productId}/staged-transactions/${transactionId}/approve`, {
    method: "POST",
    headers: getAuthHeader(),
    body: JSON.stringify({ target_account_id: targetAccountId }),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: "An unknown error occurred." }));
    if (res.status === 401) throw new Error("Unauthorized");
    throw new Error(errorData.detail);
  }

  return res.json();
}
