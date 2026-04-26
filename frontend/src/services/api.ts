import type {
  Categoria,
  CategoriaInput,
  Ingrediente,
  IngredienteInput,
  ProductoListItem,
  ProductoDetalle,
  ProductoCreate,
  ProductoUpdate,
} from "../types";

const BASE = "http://localhost:8000";

// ─── helpers ─────────────────────────────────────────────
async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const msg =
      body?.detail ??
      (Array.isArray(body?.detail)
        ? body.detail.map((d: { msg: string }) => d.msg).join(", ")
        : `Error ${res.status}`);
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

function post<T>(url: string, data: unknown): Promise<T> {
  return fetch(`${BASE}${url}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  }).then((r) => handleResponse<T>(r));
}

function put<T>(url: string, data: unknown): Promise<T> {
  return fetch(`${BASE}${url}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  }).then((r) => handleResponse<T>(r));
}

function del(url: string): Promise<void> {
  return fetch(`${BASE}${url}`, { method: "DELETE" }).then((r) =>
    handleResponse<void>(r)
  );
}

function get<T>(url: string): Promise<T> {
  return fetch(`${BASE}${url}`).then((r) => handleResponse<T>(r));
}

// ─── Categorías ──────────────────────────────────────────
export const categoriasApi = {
  getAll: () => get<Categoria[]>("/categorias/"),
  getById: (id: number) => get<Categoria>(`/categorias/${id}`),
  create: (data: CategoriaInput) => post<Categoria>("/categorias/", data),
  update: (id: number, data: CategoriaInput) =>
    put<Categoria>(`/categorias/${id}`, data),
  delete: (id: number) => del(`/categorias/${id}`),
};

// ─── Ingredientes ────────────────────────────────────────
export const ingredientesApi = {
  getAll: () => get<Ingrediente[]>("/ingredientes/"),
  getById: (id: number) => get<Ingrediente>(`/ingredientes/${id}`),
  create: (data: IngredienteInput) =>
    post<Ingrediente>("/ingredientes/", data),
  update: (id: number, data: IngredienteInput) =>
    put<Ingrediente>(`/ingredientes/${id}`, data),
  delete: (id: number) => del(`/ingredientes/${id}`),
};

// ─── Productos ───────────────────────────────────────────
export const productosApi = {
  getAll: () => get<ProductoListItem[]>("/productos/"),
  getById: (id: number) => get<ProductoDetalle>(`/productos/${id}`),
  create: (data: ProductoCreate) =>
    post<ProductoDetalle>("/productos/", data),
  update: (id: number, data: ProductoUpdate) =>
    put<ProductoDetalle>(`/productos/${id}`, data),
  delete: (id: number) => del(`/productos/${id}`),
};
