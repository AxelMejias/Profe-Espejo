import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ingredientesApi } from "../services/api";
import type { Ingrediente, IngredienteInput } from "../types";
import Modal from "../components/Modal";

export default function IngredientesPage() {
  const queryClient = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Ingrediente | null>(null);

  const [nombre, setNombre] = useState("");
  const [unidadMedida, setUnidadMedida] = useState("");
  const [error, setError] = useState("");

  const {
    data: ingredientes,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["ingredientes"],
    queryFn: ingredientesApi.getAll,
  });

  const createMutation = useMutation({
    mutationFn: (data: IngredienteInput) => ingredientesApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ingredientes"] });
      closeModal();
    },
    onError: (err: Error) => setError(err.message),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: IngredienteInput }) =>
      ingredientesApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ingredientes"] });
      closeModal();
    },
    onError: (err: Error) => setError(err.message),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => ingredientesApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ingredientes"] });
    },
  });

  function openCreate() {
    setEditing(null);
    setNombre("");
    setUnidadMedida("");
    setError("");
    setModalOpen(true);
  }

  function openEdit(ing: Ingrediente) {
    setEditing(ing);
    setNombre(ing.nombre);
    setUnidadMedida(ing.unidad_medida);
    setError("");
    setModalOpen(true);
  }

  function closeModal() {
    setModalOpen(false);
    setEditing(null);
    setError("");
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    const data: IngredienteInput = { nombre, unidad_medida: unidadMedida };
    if (editing) {
      updateMutation.mutate({ id: editing.id, data });
    } else {
      createMutation.mutate(data);
    }
  }

  function handleDelete(id: number) {
    if (window.confirm("¿Estás seguro de eliminar este ingrediente?")) {
      deleteMutation.mutate(id);
    }
  }

  const isSaving = createMutation.isPending || updateMutation.isPending;

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-success-50 flex items-center justify-center text-xl">
            🧂
          </div>
          <div>
            <h1 className="text-2xl font-bold text-surface-800">Ingredientes</h1>
            <p className="text-sm text-surface-400 mt-0.5">
              {ingredientes ? `${ingredientes.length} ingrediente${ingredientes.length !== 1 ? "s" : ""} registrado${ingredientes.length !== 1 ? "s" : ""}` : "Cargando..."}
            </p>
          </div>
        </div>
        <button
          onClick={openCreate}
          className="bg-success-500 hover:bg-success-600 text-white px-5 py-2.5 rounded-xl text-sm font-semibold transition-all shadow-sm shadow-success-500/25 hover:shadow-md hover:shadow-success-500/30 cursor-pointer flex items-center gap-2"
        >
          <span className="text-lg leading-none">+</span>
          Nuevo Ingrediente
        </button>
      </div>

      {/* Loading / Error */}
      {isLoading && (
        <div className="bg-white rounded-xl border border-surface-200 p-16 text-center">
          <div className="w-10 h-10 border-3 border-success-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-surface-400 text-sm">Cargando ingredientes...</p>
        </div>
      )}
      {isError && (
        <div className="bg-danger-50 border border-danger-100 rounded-xl p-6 text-center text-danger-600">
          Error al cargar los ingredientes
        </div>
      )}

      {/* Table */}
      {ingredientes && (
        <div className="bg-white rounded-xl border border-surface-200 overflow-hidden shadow-sm">
          <table className="w-full">
            <thead>
              <tr className="bg-surface-50 border-b border-surface-200">
                <th className="text-left px-6 py-3.5 text-xs font-bold text-surface-500 uppercase tracking-wider">
                  ID
                </th>
                <th className="text-left px-6 py-3.5 text-xs font-bold text-surface-500 uppercase tracking-wider">
                  Nombre
                </th>
                <th className="text-left px-6 py-3.5 text-xs font-bold text-surface-500 uppercase tracking-wider">
                  Unidad de Medida
                </th>
                <th className="text-center px-6 py-3.5 text-xs font-bold text-surface-500 uppercase tracking-wider">
                  Acciones
                </th>
              </tr>
            </thead>
            <tbody>
              {ingredientes.length === 0 && (
                <tr>
                  <td colSpan={4} className="text-center py-16 text-surface-400">
                    <p className="text-3xl mb-2">🧂</p>
                    <p className="font-medium">No hay ingredientes todavía</p>
                    <p className="text-xs mt-1">Creá el primero con el botón de arriba</p>
                  </td>
                </tr>
              )}
              {ingredientes.map((ing, i) => (
                <tr
                  key={ing.id}
                  className={`table-row-hover border-b border-surface-100 last:border-0 ${
                    i % 2 === 0 ? "bg-white" : "bg-surface-50/50"
                  }`}
                >
                  <td className="px-6 py-4">
                    <span className="inline-flex items-center justify-center w-8 h-8 rounded-lg bg-surface-100 text-xs font-bold text-surface-500">
                      {ing.id}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <span className="font-semibold text-sm text-surface-800">
                      {ing.nombre}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <span className="inline-flex items-center gap-1.5 bg-purple-50 text-purple-700 px-3 py-1 rounded-lg text-xs font-bold">
                      📏 {ing.unidad_medida}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center justify-center gap-2">
                      <button
                        onClick={() => openEdit(ing)}
                        className="p-2 rounded-lg bg-brand-50 text-brand-600 hover:bg-brand-100 transition-all text-xs font-semibold cursor-pointer"
                      >
                        ✏️ Editar
                      </button>
                      <button
                        onClick={() => handleDelete(ing.id)}
                        className="p-2 rounded-lg bg-danger-50 text-danger-600 hover:bg-danger-100 transition-all text-xs font-semibold cursor-pointer"
                      >
                        🗑️ Eliminar
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {ingredientes.length > 0 && (
            <div className="px-6 py-3 bg-surface-50 border-t border-surface-200 text-xs text-surface-400">
              Mostrando {ingredientes.length} ingrediente{ingredientes.length !== 1 && "s"}
            </div>
          )}
        </div>
      )}

      {/* Modal */}
      <Modal
        open={modalOpen}
        onClose={closeModal}
        title={editing ? "Editar Ingrediente" : "Nuevo Ingrediente"}
      >
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="bg-danger-50 border border-danger-100 text-danger-600 text-sm px-4 py-3 rounded-xl flex items-center gap-2">
              <span>⚠️</span> {error}
            </div>
          )}

          <div>
            <label className="block text-sm font-semibold text-surface-700 mb-1.5">
              Nombre <span className="text-danger-500">*</span>
            </label>
            <input
              type="text"
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              required
              className="w-full border border-surface-300 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500 transition bg-white"
              placeholder="Ej: Harina"
            />
          </div>

          <div>
            <label className="block text-sm font-semibold text-surface-700 mb-1.5">
              Unidad de Medida <span className="text-danger-500">*</span>
            </label>
            <input
              type="text"
              value={unidadMedida}
              onChange={(e) => setUnidadMedida(e.target.value)}
              required
              className="w-full border border-surface-300 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500 transition bg-white"
              placeholder="Ej: kg, lt, unidad"
            />
          </div>

          <div className="flex justify-end gap-3 pt-3 border-t border-surface-100">
            <button
              type="button"
              onClick={closeModal}
              className="px-5 py-2.5 rounded-xl text-sm font-semibold text-surface-600 hover:bg-surface-100 transition cursor-pointer border border-surface-200"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={isSaving}
              className="bg-success-500 hover:bg-success-600 disabled:opacity-50 text-white px-6 py-2.5 rounded-xl text-sm font-semibold transition-all shadow-sm shadow-success-500/25 cursor-pointer"
            >
              {isSaving ? "Guardando..." : editing ? "Actualizar" : "Crear Ingrediente"}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
