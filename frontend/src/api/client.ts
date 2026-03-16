const BASE_URL = 'http://localhost:8000/api';

export const fetchTree = async () => {
  const response = await fetch(`${BASE_URL}/accounts/tree`);
  if (!response.ok) {
    throw new Error('Failed to fetch tree data');
  }
  return response.json();
};