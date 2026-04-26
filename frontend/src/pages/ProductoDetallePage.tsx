import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { productosApi } from "../services/api";

export default function ProductoDetallePage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const {
    data: producto,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["productos", id],
    queryFn: () => productosApi.getById(Number(id)),
    enabled: !!id,
  });

  if (isLoading) {
    return (
      <div className="text-center py-20">
        <div className="w-10 h-10 border-3 border-brand-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
        <p className="text-surface-400 text-sm">Cargando producto...</p>
      </div>
    );
  }

  if (isError || !producto) {
    return (
      <div className="text-center py-20">
        <p className="text-3xl mb-3">😕</p>
        <p className="text-danger-500 font-medium mb-4">
          No se pudo cargar el producto
        </p>
        <button
          onClick={() => navigate("/productos")}
          className="text-brand-600 hover:text-brand-800 text-sm font-semibold cursor-pointer bg-brand-50 px-4 py-2 rounded-xl hover:bg-brand-100 transition"
        >
          ← Volver a productos
        </button>
      </div>
    );
  }

  return (
    <div>
      {/* Back */}
      <button
        onClick={() => navigate("/productos")}
        className="text-surface-500 hover:text-surface-700 text-sm font-medium mb-6 cursor-pointer inline-flex items-center gap-2 bg-white border border-surface-200 px-4 py-2 rounded-xl hover:bg-surface-50 transition"
      >
        ← Volver a productos
      </button>

      {/* Product header card */}
      <div className="bg-white rounded-xl border border-surface-200 p-6 mb-6 shadow-sm">
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-4">
            <div className="w-14 h-14 rounded-xl bg-brand-500 flex items-center justify-center text-2xl shadow-sm shadow-brand-500/20">
              📦
            </div>
            <div>
              <h1 className="text-2xl font-bold text-surface-800">
                {producto.nombre}
              </h1>
              {producto.descripcion && (
                <p className="text-surface-500 mt-1">{producto.descripcion}</p>
              )}
              <div className="flex items-center gap-3 mt-3">
                <span className="inline-flex items-center bg-surface-100 text-surface-500 px-3 py-1 rounded-lg text-xs font-bold">
                  ID: {producto.id}
                </span>
                <span className="inline-flex items-center bg-success-50 text-success-700 px-3 py-1 rounded-lg text-xs font-bold">
                  Activo
                </span>
              </div>
            </div>
          </div>
          <div className="text-right">
            <p className="text-xs text-surface-400 mb-1 uppercase font-bold tracking-wider">Precio</p>
            <span className="text-3xl font-bold text-success-600">
              ${producto.precio.toLocaleString("es-AR")}
            </span>
          </div>
        </div>
      </div>

      {/* Grid: categorías e ingredientes */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Categorías */}
        <div className="bg-white rounded-xl border border-surface-200 overflow-hidden shadow-sm">
          <div className="px-6 py-4 bg-warning-50 border-b border-warning-100 flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-warning-500 flex items-center justify-center text-sm">
              🏷️
            </div>
            <div>
              <h2 className="font-bold text-surface-800 text-sm">Categorías</h2>
              <p className="text-xs text-surface-400">
                {producto.categorias.length} asignada{producto.categorias.length !== 1 && "s"}
              </p>
            </div>
          </div>
          <div className="p-6">
            {producto.categorias.length === 0 ? (
              <div className="text-center py-6">
                <p className="text-surface-300 text-sm">Sin categorías asignadas</p>
              </div>
            ) : (
              <div className="flex flex-wrap gap-2">
                {producto.categorias.map((cat) => (
                  <div
                    key={cat.id}
                    className="bg-warning-50 border border-warning-100 rounded-xl px-4 py-2.5"
                  >
                    <p className="text-sm font-semibold text-warning-600">
                      {cat.nombre}
                    </p>
                    {cat.descripcion && (
                      <p className="text-xs text-surface-400 mt-0.5">
                        {cat.descripcion}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Ingredientes */}
        <div className="bg-white rounded-xl border border-surface-200 overflow-hidden shadow-sm">
          <div className="px-6 py-4 bg-success-50 border-b border-success-100 flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-success-500 flex items-center justify-center text-sm">
              🧂
            </div>
            <div>
              <h2 className="font-bold text-surface-800 text-sm">Ingredientes</h2>
              <p className="text-xs text-surface-400">
                {producto.ingredientes.length} ingrediente{producto.ingredientes.length !== 1 && "s"}
              </p>
            </div>
          </div>
          <div className="p-0">
            {producto.ingredientes.length === 0 ? (
              <div className="text-center py-10">
                <p className="text-surface-300 text-sm">Sin ingredientes asignados</p>
              </div>
            ) : (
              <div>
                {producto.ingredientes.map((ing, i) => (
                  <div
                    key={ing.id}
                    className={`flex items-center justify-between px-6 py-3.5 border-b border-surface-100 last:border-0 ${
                      i % 2 === 0 ? "bg-white" : "bg-surface-50/50"
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <span className="w-7 h-7 rounded-md bg-success-50 flex items-center justify-center text-xs font-bold text-success-600">
                        {i + 1}
                      </span>
                      <span className="text-sm font-medium text-surface-700">
                        {ing.nombre}
                      </span>
                    </div>
                    <span className="inline-flex items-center gap-1.5 bg-purple-50 text-purple-700 px-3 py-1 rounded-lg text-xs font-bold">
                      {ing.cantidad} {ing.unidad_medida}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
